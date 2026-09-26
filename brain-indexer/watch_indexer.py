import hashlib
import os
import re
import time
import threading
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL

import frontmatter

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    FilterSelector,
)

from sentence_transformers import SentenceTransformer


# ============================================================
# CONFIGURAÇÕES
# ============================================================

VAULT_PATH = Path(
    os.getenv(
        "VAULT_PATH",
        "/vault")
)

QDRANT_URL = os.getenv(
    "QDRANT_URL",
    "http://qdrant:6333",
)

COLLECTION_NAME = os.getenv(
    "QDRANT_COLLECTION",
    "second_brain",
)

MODEL_NAME = os.getenv(
    "MODEL_NAME",
    "intfloat/multilingual-e5-base",
)

CHUNK_SIZE = int(
    os.getenv(
        "CHUNK_SIZE",
        "1200",
    )
)

CHUNK_OVERLAP = int(
    os.getenv(
        "CHUNK_OVERLAP",
        "200",
    )
)

# Tempo que o indexador espera após o ÚLTIMO evento do arquivo.
# Eventos consecutivos reiniciam este contador.
DEBOUNCE_SECONDS = float(
    os.getenv(
        "DEBOUNCE_SECONDS",
        "3.0",
    )
)

if CHUNK_SIZE <= 0:
    raise ValueError("CHUNK_SIZE deve ser maior que zero.")

if CHUNK_OVERLAP < 0:
    raise ValueError("CHUNK_OVERLAP não pode ser negativo.")

if CHUNK_OVERLAP >= CHUNK_SIZE:
    raise ValueError(
        "CHUNK_OVERLAP deve ser menor que CHUNK_SIZE."
    )

if DEBOUNCE_SECONDS < 0:
    raise ValueError(
        "DEBOUNCE_SECONDS não pode ser negativo."
    )


IGNORE_DIRS = {
    ".obsidian",
    ".git",
    ".trash",
    "tmp",
    "node_modules",
    "__pycache__",
}


IGNORE_FILES = {
    "00 Caixa de Entrada.md",
}


LOW_VALUE_FILES = {
    "Áreas.md",
    "Conhecimento.md",
    "Memória.md",
    "Projetos.md",
}


# ============================================================
# ESTADO DO WATCHER
# ============================================================

# path -> {"timer": Timer, "token": object()}
pending_timers = {}
pending_lock = threading.Lock()

# Fingerprint SHA-256 da última versão indexada.
# Evita reindexar conteúdo idêntico mesmo quando o filesystem
# gera novos eventos depois do debounce.
indexed_fingerprints = {}
fingerprint_lock = threading.Lock()


# ============================================================
# INICIALIZAÇÃO DO MODELO
# ============================================================

print("=" * 70, flush=True)
print("SECOND BRAIN INDEXER", flush=True)
print("=" * 70, flush=True)

print(
    f"Vault: {VAULT_PATH}",
    flush=True,
)

print(
    f"Qdrant: {QDRANT_URL}",
    flush=True,
)

print(
    f"Coleção: {COLLECTION_NAME}",
    flush=True,
)

print(
    f"Modelo: {MODEL_NAME}",
    flush=True,
)

print(
    f"Debounce: {DEBOUNCE_SECONDS:.1f}s",
    flush=True,
)

print(flush=True)

print(
    "Carregando modelo de embeddings...",
    flush=True,
)

model = SentenceTransformer(
    MODEL_NAME
)

VECTOR_SIZE = model.get_embedding_dimension()

print(
    f"Dimensão dos vetores: {VECTOR_SIZE}",
    flush=True,
)


# ============================================================
# CLIENTE QDRANT
# ============================================================

client = QdrantClient(
    url=QDRANT_URL
)


# ============================================================
# QDRANT - ESPERAR DISPONIBILIDADE
# ============================================================

def wait_for_qdrant():
    """
    Aguarda o Qdrant ficar disponível.

    O Docker depends_on garante que o container seja iniciado,
    mas não necessariamente que a aplicação já esteja pronta.
    """

    print(
        "Aguardando Qdrant...",
        flush=True,
    )

    while True:
        try:
            client.get_collections()

            print(
                "Qdrant disponível.",
                flush=True,
            )

            return

        except Exception as error:
            print(
                f"Qdrant ainda indisponível: {error}",
                flush=True,
            )

            time.sleep(3)


# ============================================================
# GARANTIR COLEÇÃO
# ============================================================

def ensure_collection():
    if client.collection_exists(
        COLLECTION_NAME
    ):
        print(
            f"Coleção '{COLLECTION_NAME}' encontrada.",
            flush=True,
        )

        return

    print(
        f"Criando coleção '{COLLECTION_NAME}'...",
        flush=True,
    )

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE,
        ),
    )

    print(
        "Coleção criada.",
        flush=True,
    )


# ============================================================
# FILTROS
# ============================================================

def should_ignore(path: Path):
    """
    Retorna True quando o caminho não deve participar do índice.

    Não exige que o arquivo exista, pois também é usada em
    eventos de exclusão e movimentação.
    """

    path = Path(path)

    try:
        relative_path = path.relative_to(
            VAULT_PATH
        )
    except ValueError:
        return True

    # Apenas Markdown
    if path.suffix.lower() != ".md":
        return True

    # Diretórios ignorados
    for part in relative_path.parts[:-1]:
        if part.startswith("."):
            return True

        if part in IGNORE_DIRS:
            return True

    # Arquivos ocultos
    if path.name.startswith("."):
        return True

    # Arquivos explicitamente ignorados
    if path.name in IGNORE_FILES:
        return True

    return False


# ============================================================
# FINGERPRINT
# ============================================================

def get_file_fingerprint(path: Path):
    """
    Calcula SHA-256 do conteúdo do arquivo.

    Isso permite ignorar uma reindexação quando Syncthing,
    Obsidian ou o sistema de arquivos geram eventos novos para
    um conteúdo que já foi indexado.
    """

    hasher = hashlib.sha256()

    with path.open("rb") as file_handle:
        while True:
            block = file_handle.read(1024 * 1024)

            if not block:
                break

            hasher.update(block)

    return hasher.hexdigest()


def get_stored_fingerprint(relative_path: Path):
    key = str(relative_path)

    with fingerprint_lock:
        return indexed_fingerprints.get(key)


def set_stored_fingerprint(
    relative_path: Path,
    fingerprint: str,
):
    key = str(relative_path)

    with fingerprint_lock:
        indexed_fingerprints[key] = fingerprint


def clear_stored_fingerprint(
    relative_path: Path,
):
    key = str(relative_path)

    with fingerprint_lock:
        indexed_fingerprints.pop(
            key,
            None,
        )


# ============================================================
# LEITURA DE MARKDOWN
# ============================================================

def read_markdown(path: Path):
    """
    Lê frontmatter e conteúdo Markdown.
    """

    try:
        post = frontmatter.load(
            path
        )

        metadata = dict(
            post.metadata
        )

        content = post.content

        return metadata, content

    except Exception as error:
        print(
            f"Erro ao ler {path}: {error}",
            flush=True,
        )

        return {}, ""


# ============================================================
# METADADOS
# ============================================================

def metadata_to_text(metadata: dict):
    if not metadata:
        return ""

    result = []

    for key, value in metadata.items():
        if isinstance(
            value,
            list,
        ):
            value = ", ".join(
                str(item)
                for item in value
            )

        result.append(
            f"{key}: {value}"
        )

    return "\n".join(
        result
    )


# ============================================================
# MARKDOWN - DIVISÃO POR SEÇÕES
# ============================================================

def split_markdown_sections(text: str):
    """
    Divide Markdown pelos cabeçalhos:

    #
    ##
    ###
    etc.
    """

    lines = text.splitlines()

    sections = []

    current_heading = ""
    current_content = []

    heading_pattern = re.compile(
        r"^(#{1,6})\s+(.*)$"
    )

    for line in lines:
        match = heading_pattern.match(
            line
        )

        if match:
            if (
                current_heading
                or current_content
            ):
                sections.append(
                    {
                        "heading":
                            current_heading.strip(),

                        "content":
                            "\n".join(
                                current_content
                            ).strip(),
                    }
                )

            current_heading = (
                line.strip()
            )

            current_content = []

        else:
            current_content.append(
                line
            )

    # Última seção
    if (
        current_heading
        or current_content
    ):
        sections.append(
            {
                "heading":
                    current_heading.strip(),

                "content":
                    "\n".join(
                        current_content
                    ).strip(),
            }
        )

    return sections


# ============================================================
# DIVISÃO DE TEXTOS GRANDES
# ============================================================

def split_large_text(
    text: str,
    chunk_size: int,
    overlap: int,
):
    text = text.strip()

    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks = []

    start = 0

    while start < len(text):
        end = start + chunk_size

        chunk = text[
            start:end
        ].strip()

        if chunk:
            chunks.append(
                chunk
            )

        start += (
            chunk_size
            - overlap
        )

    return chunks


# ============================================================
# CHUNKING MARKDOWN
# ============================================================

def chunk_markdown(text: str):
    """
    Primeiro divide pelas seções Markdown.

    Apenas se uma seção for grande demais ela será
    subdividida por tamanho.
    """

    sections = (
        split_markdown_sections(
            text
        )
    )

    chunks = []

    for section in sections:
        heading = section[
            "heading"
        ]

        content = section[
            "content"
        ]

        section_text = ""

        if heading:
            section_text += heading

        if content:
            if section_text:
                section_text += "\n\n"

            section_text += content

        section_text = (
            section_text.strip()
        )

        if not section_text:
            continue

        # Seção pequena
        if (
            len(section_text)
            <= CHUNK_SIZE
        ):
            chunks.append(
                {
                    "heading":
                        heading,

                    "text":
                        section_text,
                }
            )

            continue

        # Seção grande
        smaller_chunks = (
            split_large_text(
                section_text,
                CHUNK_SIZE,
                CHUNK_OVERLAP,
            )
        )

        for chunk in smaller_chunks:
            chunks.append(
                {
                    "heading":
                        heading,

                    "text":
                        chunk,
                }
            )

    return chunks


# ============================================================
# EMBEDDING TEXT
# ============================================================

def build_embedding_text(
    title: str,
    relative_path: Path,
    metadata: dict,
    heading: str,
    chunk: str,
    document_type: str,
):
    """
    Cria o texto usado pelo modelo E5.

    Documentos usam prefixo:
    passage:
    """

    parts = [
        "passage:",
        f"Título: {title}",
        f"Caminho: {relative_path}",
        f"Tipo de documento: {document_type}",
    ]

    if heading:
        parts.append(
            f"Seção: {heading}"
        )

    metadata_text = (
        metadata_to_text(
            metadata
        )
    )

    if metadata_text:
        parts.append(
            "Metadados:"
        )

        parts.append(
            metadata_text
        )

    parts.append("")

    parts.append(
        chunk
    )

    return "\n".join(
        parts
    ).strip()


# ============================================================
# REMOVER NOTA DO QDRANT
# ============================================================

def delete_note_from_qdrant(
    relative_path,
):
    client.delete(
        collection_name=COLLECTION_NAME,

        points_selector=FilterSelector(
            filter=Filter(
                must=[
                    FieldCondition(
                        key="source",
                        match=MatchValue(
                            value=str(
                                relative_path
                            )
                        ),
                    )
                ]
            )
        ),
    )


# ============================================================
# INDEXAR UMA NOTA
# ============================================================

def index_note(
    path: Path,
    force: bool = False,
):
    path = Path(path)

    if should_ignore(path):
        return False

    if not path.exists():
        return False

    try:
        relative_path = (
            path.relative_to(
                VAULT_PATH
            )
        )
    except ValueError:
        return False

    try:
        fingerprint = (
            get_file_fingerprint(
                path
            )
        )
    except Exception as error:
        print(
            f"Erro calculando fingerprint "
            f"{relative_path}: {error}",
            flush=True,
        )
        return False

    if not force:
        previous_fingerprint = (
            get_stored_fingerprint(
                relative_path
            )
        )

        if (
            previous_fingerprint
            == fingerprint
        ):
            print(
                f"Sem alteração: {relative_path}",
                flush=True,
            )
            return False

    print(
        f"Indexando: {relative_path}",
        flush=True,
    )

    metadata, content = (
        read_markdown(
            path
        )
    )

    # Remove versão anterior da nota
    delete_note_from_qdrant(
        relative_path
    )

    if not content.strip():
        clear_stored_fingerprint(
            relative_path
        )

        print(
            f"Nota vazia: {relative_path}",
            flush=True,
        )

        return True

    chunks = chunk_markdown(
        content
    )

    if not chunks:
        clear_stored_fingerprint(
            relative_path
        )

        print(
            f"Nenhum chunk: {relative_path}",
            flush=True,
        )

        return True

    document_type = (
        "índice"
        if path.name in LOW_VALUE_FILES
        else "conteúdo"
    )

    points = []

    for (
        chunk_index,
        chunk_data,
    ) in enumerate(chunks):
        chunk = chunk_data[
            "text"
        ]

        heading = chunk_data[
            "heading"
        ]

        embedding_text = (
            build_embedding_text(
                title=path.stem,
                relative_path=relative_path,
                metadata=metadata,
                heading=heading,
                chunk=chunk,
                document_type=document_type,
            )
        )

        vector = model.encode(
            embedding_text,
            normalize_embeddings=True,
        ).tolist()

        unique_string = (
            f"{relative_path}:"
            f"{heading}:"
            f"{chunk_index}:"
            f"{chunk}"
        )

        point_id = str(
            uuid5(
                NAMESPACE_URL,
                unique_string,
            )
        )

        payload = {
            "source":
                str(relative_path),

            "title":
                path.stem,

            "folder":
                str(
                    relative_path.parent
                ),

            "heading":
                heading,

            "chunk_index":
                chunk_index,

            "total_chunks":
                len(chunks),

            "text":
                chunk,

            "metadata":
                metadata,

            "document_type":
                document_type,
        }

        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload=payload,
            )
        )

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points,
    )

    set_stored_fingerprint(
        relative_path,
        fingerprint,
    )

    print(
        f"OK: {relative_path} "
        f"({len(points)} chunks)",
        flush=True,
    )

    return True


# ============================================================
# REMOVER NOTA
# ============================================================

def remove_note(
    path: Path,
    quiet_if_unknown: bool = False,
):
    path = Path(path)

    try:
        relative_path = (
            path.relative_to(
                VAULT_PATH
            )
        )
    except ValueError:
        return False

    if should_ignore(path):
        return False

    known_before = (
        get_stored_fingerprint(
            relative_path
        )
        is not None
    )

    if (
        quiet_if_unknown
        and not known_before
    ):
        return False

    print(
        f"Removendo do índice: "
        f"{relative_path}",
        flush=True,
    )

    delete_note_from_qdrant(
        relative_path
    )

    clear_stored_fingerprint(
        relative_path
    )

    return True


# ============================================================
# INDEXAÇÃO INICIAL
# ============================================================

def initial_index():
    print()
    print(
        "Verificando Vault...",
        flush=True,
    )

    files = list(
        VAULT_PATH.rglob(
            "*.md"
        )
    )

    valid_files = [
        path
        for path in files
        if not should_ignore(
            path
        )
    ]

    valid_files.sort()

    print(
        f"Notas encontradas: "
        f"{len(valid_files)}",
        flush=True,
    )

    print()

    for number, path in enumerate(
        valid_files,
        start=1,
    ):
        print(
            f"[{number}/"
            f"{len(valid_files)}]",
            flush=True,
        )

        try:
            # Na inicialização força sincronização com o Qdrant.
            index_note(
                path,
                force=True,
            )

        except Exception as error:
            print(
                f"ERRO: {path}: {error}",
                flush=True,
            )

    print()
    print(
        "Indexação inicial concluída.",
        flush=True,
    )


# ============================================================
# RECONCILIAÇÃO
# ============================================================

def reconcile_path(
    path: Path,
):
    """
    Aplica o estado FINAL do filesystem ao Qdrant.

    Depois do debounce:
      - se o arquivo existe -> indexa;
      - se não existe -> remove.

    Isso evita reagir individualmente a sequências como:
      DELETE -> CREATE -> MODIFY -> MODIFY
    geradas por Obsidian/Syncthing.
    """

    path = Path(path)

    if should_ignore(path):
        return

    try:
        if (
            path.exists()
            and path.is_file()
        ):
            index_note(
                path
            )
        else:
            remove_note(
                path,
                quiet_if_unknown=True,
            )

    except Exception as error:
        print(
            f"Erro reconciliando "
            f"{path}: {error}",
            flush=True,
        )


# ============================================================
# DEBOUNCE TRAILING-EDGE
# ============================================================

def process_scheduled_reconcile(
    path: Path,
    key: str,
    token,
):
    """
    Executa somente se este timer ainda for o timer atual
    associado ao caminho.

    O token evita que um timer cancelado, mas que já tenha
    começado a executar, remova ou substitua o estado de um
    timer mais recente.
    """

    with pending_lock:
        current = pending_timers.get(
            key
        )

        if (
            current is None
            or current["token"] is not token
        ):
            return

    try:
        reconcile_path(
            path
        )

    finally:
        with pending_lock:
            current = pending_timers.get(
                key
            )

            if (
                current is not None
                and current["token"] is token
            ):
                pending_timers.pop(
                    key,
                    None,
                )


def schedule_reconcile(
    path: Path,
):
    """
    Agenda a reconciliação do caminho.

    Se houver novo evento antes do prazo, o timer anterior
    é cancelado e um novo timer começa do zero.
    """

    path = Path(path)

    if should_ignore(path):
        return

    key = str(path)
    token = object()

    with pending_lock:
        previous = pending_timers.get(
            key
        )

        if previous is not None:
            previous[
                "timer"
            ].cancel()

        timer = threading.Timer(
            DEBOUNCE_SECONDS,
            process_scheduled_reconcile,
            args=(
                path,
                key,
                token,
            ),
        )

        timer.daemon = True

        pending_timers[key] = {
            "timer": timer,
            "token": token,
        }

        timer.start()


def cancel_all_pending():
    """
    Cancela todos os timers pendentes durante o encerramento.
    """

    with pending_lock:
        items = list(
            pending_timers.values()
        )

        pending_timers.clear()

    for item in items:
        item["timer"].cancel()


# ============================================================
# WATCHDOG
# ============================================================

class VaultEventHandler(
    FileSystemEventHandler
):

    def process_path(
        self,
        path,
    ):
        path = Path(
            path
        )

        if should_ignore(
            path
        ):
            return

        schedule_reconcile(
            path
        )


    def on_created(
        self,
        event,
    ):
        if event.is_directory:
            return

        self.process_path(
            event.src_path
        )


    def on_modified(
        self,
        event,
    ):
        if event.is_directory:
            return

        self.process_path(
            event.src_path
        )


    def on_deleted(
        self,
        event,
    ):
        if event.is_directory:
            return

        self.process_path(
            event.src_path
        )


    def on_moved(
        self,
        event,
    ):
        if event.is_directory:
            return

        old_path = Path(
            event.src_path
        )

        new_path = Path(
            event.dest_path
        )

        # O caminho antigo será removido se não existir mais.
        if not should_ignore(
            old_path
        ):
            schedule_reconcile(
                old_path
            )

        # O caminho novo será indexado se existir.
        if not should_ignore(
            new_path
        ):
            schedule_reconcile(
                new_path
            )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    if not VAULT_PATH.exists():
        raise RuntimeError(
            f"Vault não encontrado: "
            f"{VAULT_PATH}"
        )

    wait_for_qdrant()

    ensure_collection()

    initial_index()

    event_handler = (
        VaultEventHandler()
    )

    observer = Observer()

    observer.schedule(
        event_handler,
        str(VAULT_PATH),
        recursive=True,
    )

    observer.start()

    print()
    print("=" * 70)
    print(
        "SECOND BRAIN INDEXER ATIVO",
        flush=True,
    )
    print("=" * 70)

    print(
        f"Monitorando: {VAULT_PATH}",
        flush=True,
    )

    print(
        f"Debounce: {DEBOUNCE_SECONDS:.1f}s",
        flush=True,
    )

    print(
        "Aguardando alterações...",
        flush=True,
    )

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print(
            "Encerrando...",
            flush=True,
        )

        cancel_all_pending()

        observer.stop()

    observer.join()
