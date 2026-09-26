import os
from pathlib import Path
from uuid import uuid5, NAMESPACE_URL
import re

import frontmatter
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer


# ============================================================
# CONFIGURAÇÕES
# ============================================================

VAULT_PATH = Path(
    os.getenv(
        "VAULT_PATH",
        "/vault",
    )
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
    "EMBEDDING_MODEL",
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

RECREATE_COLLECTION = (
    os.getenv(
        "RECREATE_COLLECTION",
        "false",
    ).lower()
    == "true"
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
# INICIALIZAÇÃO
# ============================================================

print("Carregando modelo de embeddings...")

model = SentenceTransformer(MODEL_NAME)

client = QdrantClient(
    url=QDRANT_URL
)

VECTOR_SIZE = model.get_sentence_embedding_dimension()

print(f"Modelo: {MODEL_NAME}")
print(f"Dimensão dos vetores: {VECTOR_SIZE}")


# ============================================================
# FUNÇÕES DE LEITURA
# ============================================================

def should_ignore(path: Path):
    """
    Ignora arquivos e diretórios que não devem entrar no índice.
    """

    try:
        relative_path = path.relative_to(VAULT_PATH)
    except ValueError:
        return True

    for part in relative_path.parts[:-1]:
        if part.startswith(".") or part in IGNORE_DIRS:
            return True

    if path.name.startswith("."):
        return True

    if path.name in IGNORE_FILES:
        return True

    return False


def read_markdown(path: Path):
    """
    Lê uma nota Markdown e separa frontmatter e conteúdo.
    """

    try:
        post = frontmatter.load(path)

        metadata = dict(post.metadata)
        content = post.content

        return metadata, content

    except Exception as error:
        print(f"ERRO ao ler {path}: {error}")
        return {}, ""


def metadata_to_text(metadata: dict):
    """
    Converte metadados em texto para enriquecer o embedding.
    """

    if not metadata:
        return ""

    parts = []

    for key, value in metadata.items():

        if isinstance(value, list):
            value = ", ".join(str(item) for item in value)

        parts.append(f"{key}: {value}")

    return "\n".join(parts)


# ============================================================
# CHUNKING MARKDOWN
# ============================================================

def split_markdown_sections(text: str):
    """
    Divide Markdown por cabeçalhos.

    Retorna:
    [
        {
            "heading": "...",
            "content": "..."
        }
    ]
    """

    lines = text.splitlines()

    sections = []

    current_heading = ""
    current_content = []

    heading_pattern = re.compile(r"^(#{1,6})\s+(.*)$")

    for line in lines:

        match = heading_pattern.match(line)

        if match:

            if current_heading or current_content:

                sections.append(
                    {
                        "heading": current_heading.strip(),
                        "content": "\n".join(
                            current_content
                        ).strip()
                    }
                )

            current_heading = line.strip()
            current_content = []

        else:
            current_content.append(line)

    if current_heading or current_content:

        sections.append(
            {
                "heading": current_heading.strip(),
                "content": "\n".join(
                    current_content
                ).strip()
            }
        )

    return sections


def split_large_text(
    text: str,
    chunk_size: int,
    overlap: int
):
    """
    Divide seções grandes em blocos menores.
    """

    text = text.strip()

    if not text:
        return []

    if len(text) <= chunk_size:
        return [text]

    chunks = []

    start = 0

    while start < len(text):

        end = start + chunk_size

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        start += chunk_size - overlap

    return chunks


def chunk_markdown(text: str):
    """
    Divide a nota preservando a estrutura Markdown.
    """

    sections = split_markdown_sections(text)

    chunks = []

    for section in sections:

        heading = section["heading"]
        content = section["content"]

        section_text = ""

        if heading:
            section_text += heading

        if content:

            if section_text:
                section_text += "\n\n"

            section_text += content

        section_text = section_text.strip()

        if not section_text:
            continue

        if len(section_text) <= CHUNK_SIZE:

            chunks.append(
                {
                    "heading": heading,
                    "text": section_text,
                }
            )

            continue

        smaller_chunks = split_large_text(
            section_text,
            CHUNK_SIZE,
            CHUNK_OVERLAP
        )

        for chunk in smaller_chunks:

            chunks.append(
                {
                    "heading": heading,
                    "text": chunk,
                }
            )

    return chunks


# ============================================================
# TEXTO PARA EMBEDDING
# ============================================================

def build_embedding_text(
    title: str,
    relative_path: Path,
    metadata: dict,
    heading: str,
    chunk: str,
    document_type: str
):
    """
    Monta o texto usado pelo E5.
    """

    metadata_text = metadata_to_text(metadata)

    parts = [
        "passage:",
        f"Título: {title}",
        f"Caminho: {relative_path}",
        f"Tipo de documento: {document_type}",
    ]

    if heading:
        parts.append(f"Seção: {heading}")

    if metadata_text:
        parts.append("Metadados:")
        parts.append(metadata_text)

    parts.append("")
    parts.append(chunk)

    return "\n".join(parts).strip()


# ============================================================
# VALIDAR VAULT
# ============================================================

if not VAULT_PATH.exists():
    raise RuntimeError(
        f"Vault não encontrado em: {VAULT_PATH}"
    )


# ============================================================
# PREPARAR QDRANT
# ============================================================

if RECREATE_COLLECTION:

    if client.collection_exists(COLLECTION_NAME):

        print(
            f"Removendo coleção antiga: "
            f"{COLLECTION_NAME}"
        )

        client.delete_collection(
            collection_name=COLLECTION_NAME
        )


if not client.collection_exists(COLLECTION_NAME):

    print(
        f"Criando coleção: "
        f"{COLLECTION_NAME}"
    )

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE
        )
    )


# ============================================================
# LOCALIZAR NOTAS
# ============================================================

markdown_files = []

for path in VAULT_PATH.rglob("*.md"):

    if should_ignore(path):
        continue

    markdown_files.append(path)


markdown_files.sort()


print()
print(f"Notas encontradas: {len(markdown_files)}")
print()


# ============================================================
# INDEXAÇÃO
# ============================================================

total_chunks = 0
total_notes = 0
ignored_notes = 0
errors = 0


for number, path in enumerate(markdown_files, start=1):

    relative_path = path.relative_to(VAULT_PATH)

    print(
        f"[{number}/{len(markdown_files)}] "
        f"Indexando: {relative_path}"
    )

    metadata, content = read_markdown(path)

    if not content.strip():

        print("    Ignorada: nota vazia")
        ignored_notes += 1
        continue

    chunks = chunk_markdown(content)

    if not chunks:

        print("    Ignorada: nenhum chunk gerado")
        ignored_notes += 1
        continue

    document_type = (
        "índice"
        if path.name in LOW_VALUE_FILES
        else "conteúdo"
    )

    points = []

    try:

        for chunk_index, chunk_data in enumerate(chunks):

            chunk = chunk_data["text"]
            heading = chunk_data["heading"]

            embedding_text = build_embedding_text(
                title=path.stem,
                relative_path=relative_path,
                metadata=metadata,
                heading=heading,
                chunk=chunk,
                document_type=document_type
            )

            vector = model.encode(
                embedding_text,
                normalize_embeddings=True
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
                    unique_string
                )
            )

            payload = {
                "source": str(relative_path),
                "title": path.stem,
                "folder": str(relative_path.parent),
                "heading": heading,
                "chunk_index": chunk_index,
                "total_chunks": len(chunks),
                "text": chunk,
                "metadata": metadata,
                "document_type": document_type,
            }

            points.append(
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload
                )
            )

        if points:

            client.upsert(
                collection_name=COLLECTION_NAME,
                points=points
            )

            total_chunks += len(points)
            total_notes += 1

    except Exception as error:

        errors += 1

        print(
            f"    ERRO ao indexar {relative_path}: "
            f"{error}"
        )


# ============================================================
# RESULTADO
# ============================================================

print()
print("=" * 70)
print("INDEXAÇÃO CONCLUÍDA")
print("=" * 70)

print(f"Vault: {VAULT_PATH}")
print(f"Coleção: {COLLECTION_NAME}")
print(f"Modelo: {MODEL_NAME}")
print(f"Dimensão dos vetores: {VECTOR_SIZE}")

print()
print(f"Notas encontradas: {len(markdown_files)}")
print(f"Notas indexadas: {total_notes}")
print(f"Notas ignoradas: {ignored_notes}")
print(f"Chunks criados: {total_chunks}")
print(f"Erros: {errors}")
