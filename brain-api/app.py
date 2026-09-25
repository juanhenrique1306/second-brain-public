import os
import re
import json
from enum import Enum
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel

from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer
from google import genai


# ============================================================
# CONFIGURAÇÕES
# ============================================================

COLLECTION_NAME = os.getenv(
    "QDRANT_COLLECTION",
    "second_brain"
)

EMBEDDING_MODEL = os.getenv(
    "EMBEDDING_MODEL",
    "intfloat/multilingual-e5-base"
)

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.5-flash-lite"
)

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)

QDRANT_URL = os.getenv(
    "QDRANT_URL",
    "http://qdrant:6333"
)

VAULT_PATH = Path(
    os.getenv(
        "VAULT_PATH",
        "/vault"
    )
)

SEARCH_LIMIT = int(
    os.getenv(
        "SEARCH_LIMIT",
        "20"
    )
)

MAX_RESULTS = int(
    os.getenv(
        "MAX_RESULTS",
        "5"
    )
)

MIN_ADJUSTED_SCORE = float(
    os.getenv(
        "MIN_ADJUSTED_SCORE",
        "0.82"
    )
)

DUPLICATE_SCORE_THRESHOLD = float(
    os.getenv(
        "DUPLICATE_SCORE_THRESHOLD",
        "0.87"
    )
)

MEMORY_CANDIDATE_THRESHOLD = float(
    os.getenv(
        "MEMORY_CANDIDATE_THRESHOLD",
        "0.80"
    )
)

MEMORY_NOTE_MAX_CHARS = int(
    os.getenv(
        "MEMORY_NOTE_MAX_CHARS",
        "30000"
    )
)

if MEMORY_NOTE_MAX_CHARS < 4000:
    raise ValueError(
        "MEMORY_NOTE_MAX_CHARS deve ser >= 4000."
    )

EXCLUDED_SEARCH_FILES = {
    "Home.md",
}

BRAIN_API_KEY = os.getenv(
    "BRAIN_API_KEY"
)


# ============================================================
# PROTEGE AS ROTAS COM API KEY
# ============================================================
def verify_api_key(
    x_api_key: str | None = Header(
        default=None,
        alias="X-API-Key",
    )
):
    if not BRAIN_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="BRAIN_API_KEY não configurada.",
        )

    if x_api_key != BRAIN_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="API key inválida.",
        )

# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title="Second Brain API",
    version="0.7.0",
)


# ============================================================
# INICIALIZAÇÃO
# ============================================================

print("=" * 70, flush=True)
print("SECOND BRAIN API", flush=True)
print("=" * 70, flush=True)

print(
    f"Qdrant: {QDRANT_URL}",
    flush=True
)

print(
    f"Coleção: {COLLECTION_NAME}",
    flush=True
)

print(
    f"Vault: {VAULT_PATH}",
    flush=True
)

print(
    f"Embedding: {EMBEDDING_MODEL}",
    flush=True
)

print(
    f"Gemini: {GEMINI_MODEL}",
    flush=True
)

print(
    f"Score mínimo: {MIN_ADJUSTED_SCORE}",
    flush=True
)


# ============================================================
# EMBEDDINGS
# ============================================================

print(
    "Carregando modelo de embeddings...",
    flush=True
)

embedding_model = SentenceTransformer(
    EMBEDDING_MODEL
)

print(
    "Modelo de embeddings carregado.",
    flush=True
)


# ============================================================
# QDRANT
# ============================================================

qdrant = QdrantClient(
    url=QDRANT_URL
)


# ============================================================
# GEMINI
# ============================================================

gemini_client = None

if GEMINI_API_KEY:

    gemini_client = genai.Client(
        api_key=GEMINI_API_KEY
    )

    print(
        "Gemini configurado.",
        flush=True
    )

else:

    print(
        "AVISO: GEMINI_API_KEY não configurada.",
        flush=True
    )


# ============================================================
# INTENTS
# ============================================================

class Intent(str, Enum):
    MEMORY = "MEMORY"
    GENERAL = "GENERAL"
    HYBRID = "HYBRID"

class MemoryOperation(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    IGNORE = "IGNORE"


# ============================================================
# REQUEST MODELS
# ============================================================

class SearchRequest(BaseModel):
    query: str


class AskRequest(BaseModel):
    query: str


class MemoryAnalyzeRequest(BaseModel):
    text: str


class MemoryWriteRequest(BaseModel):
    text: str
    confirm: bool = False
    allow_duplicate: bool = False

# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():

    return {
        "status": "ok",
        "service": "Second Brain API",
        "version": "0.7.0",
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok",
        "collection": COLLECTION_NAME,
        "embedding_model": EMBEDDING_MODEL,
        "duplicate_score_threshold": DUPLICATE_SCORE_THRESHOLD,
        "memory_candidate_threshold": MEMORY_CANDIDATE_THRESHOLD,
        "memory_note_max_chars": MEMORY_NOTE_MAX_CHARS,
        "api_auth_enabled": bool(BRAIN_API_KEY),
        "gemini_model": GEMINI_MODEL,
        "gemini_configured": bool(
            GEMINI_API_KEY
        ),
        "vault_path": str(
            VAULT_PATH
        ),
        "vault_available": (
            VAULT_PATH.exists()
        ),
        "min_adjusted_score": (
            MIN_ADJUSTED_SCORE
        ),
    }


# ============================================================
# INTENT ROUTER
# ============================================================

def heuristic_intent(query: str):

    text = query.lower().strip()

    hybrid_patterns = [
        r"\bcom base nas minhas notas\b",
        r"\bcompare .* minhas notas\b",
        r"\bcompare .* meu projeto\b",
        r"\brelacione .* minhas notas\b",
        r"\buse minhas notas\b",
        r"\bconsiderando o que anotei\b",
        r"\bconsiderando meu projeto\b",
        r"\bde acordo com minhas notas\b",
        r"\bmelhore .* meu projeto\b",
        r"\bavalie .* meu projeto\b",
    ]

    memory_patterns = [
        r"\bminhas? notas?\b",
        r"\bmeu obsidian\b",
        r"\bsecond brain\b",
        r"\beu tenho anotado\b",
        r"\btenho anotado\b",
        r"\bo que anotei\b",
        r"\bminha documentação\b",
        r"\bmeu projeto\b",
        r"\bmeu homelab\b",
        r"\bminha configuração\b",
        r"\bcomo configurei\b",
        r"\bqual .* eu uso\b",
        r"\bonde eu hospedo\b",
        r"\bminhas decisões\b",
        r"\bdecidi\b",
    ]

    general_patterns = [
        r"^o que é\b",
        r"^o que são\b",
        r"^explique\b",
        r"^como funciona\b",
        r"^qual a diferença\b",
        r"^defina\b",
        r"^me explique\b",
    ]

    for pattern in hybrid_patterns:

        if re.search(
            pattern,
            text
        ):
            return Intent.HYBRID

    for pattern in memory_patterns:

        if re.search(
            pattern,
            text
        ):
            return Intent.MEMORY

    for pattern in general_patterns:

        if re.search(
            pattern,
            text
        ):
            return Intent.GENERAL

    return None


def classify_intent(query: str):

    heuristic = heuristic_intent(
        query
    )

    if heuristic:
        return heuristic

    if not gemini_client:
        return Intent.MEMORY

    prompt = f"""
Classifique a pergunta abaixo em apenas uma categoria:

MEMORY
A pergunta depende de informações pessoais, projetos,
configurações, decisões ou notas armazenadas no Second Brain.

GENERAL
A pergunta é de conhecimento geral.

HYBRID
A pergunta precisa combinar conhecimento geral com informações
do Second Brain.

Pergunta:

{query}

Responda somente com:

MEMORY
GENERAL
ou
HYBRID
""".strip()

    try:

        response = (
            gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
        )

        result = (
            response.text
            .strip()
            .upper()
        )

        if result == "HYBRID":
            return Intent.HYBRID

        if result == "GENERAL":
            return Intent.GENERAL

        return Intent.MEMORY

    except Exception as error:

        print(
            f"Erro classificando intent: {error}",
            flush=True
        )

        return Intent.MEMORY


# ============================================================
# BUSCA SEMÂNTICA
# ============================================================

def search_second_brain(
    query: str,
    max_results: int = MAX_RESULTS
):

    query = query.strip()

    if not query:
        return []

    query_vector = embedding_model.encode(
        f"query: {query}",
        normalize_embeddings=True,
    ).tolist()

    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=SEARCH_LIMIT,
    )

    # --------------------------------------------------------
    # MELHOR CHUNK POR ARQUIVO
    # --------------------------------------------------------

    best_by_file = {}

    for point in results.points:

        payload = point.payload or {}

        source = payload.get(
            "source"
        )

        if not source:
            continue

        if source in EXCLUDED_SEARCH_FILES:
            continue

        current = best_by_file.get(
            source
        )

        if (
            current is None
            or point.score > current.score
        ):
            best_by_file[source] = point

    # --------------------------------------------------------
    # RERANKING
    # --------------------------------------------------------

    query_lower = query.lower()

    reranked = []

    for point in best_by_file.values():

        payload = point.payload or {}

        title = str(
            payload.get(
                "title",
                ""
            )
        ).lower()

        heading = str(
            payload.get(
                "heading",
                ""
            )
        ).lower()

        source = str(
            payload.get(
                "source",
                ""
            )
        ).lower()

        document_type = payload.get(
            "document_type",
            "conteúdo"
        )

        adjusted_score = point.score

        for term in query_lower.split():

            clean_term = re.sub(
                r"[^\wÀ-ÿ-]",
                "",
                term
            )

            if len(clean_term) <= 3:
                continue

            if clean_term in title:
                adjusted_score += 0.015

            if clean_term in heading:
                adjusted_score += 0.010

            if clean_term in source:
                adjusted_score += 0.005

        if document_type == "índice":
            adjusted_score -= 0.040

        reranked.append(
            {
                "point": point,
                "adjusted_score": adjusted_score,
            }
        )

    reranked.sort(
        key=lambda item:
            item["adjusted_score"],
        reverse=True,
    )

    # --------------------------------------------------------
    # FILTRO FINAL POR SCORE
    # --------------------------------------------------------

    final_results = []

    for item in reranked:

        if (
            item["adjusted_score"]
            < MIN_ADJUSTED_SCORE
        ):
            continue

        point = item[
            "point"
        ]

        payload = (
            point.payload
            or {}
        )

        final_results.append(
            {
                "score": round(
                    point.score,
                    4
                ),
                "adjusted_score": round(
                    item[
                        "adjusted_score"
                    ],
                    4
                ),
                "source": payload.get(
                    "source"
                ),
                "title": payload.get(
                    "title"
                ),
                "heading": payload.get(
                    "heading"
                ),
                "document_type": payload.get(
                    "document_type"
                ),
                "text": payload.get(
                    "text"
                ),
            }
        )

        if (
            len(final_results)
            >= max_results
        ):
            break

    return final_results


# ============================================================
# CONTEXTO DO OBSIDIAN
# ============================================================

def build_context(results):

    context_parts = []

    for index, result in enumerate(
        results,
        start=1
    ):

        context_parts.append(
            f"""
FONTE {index}

Arquivo:
{result.get("source")}

Título:
{result.get("title")}

Seção:
{result.get("heading")}

Conteúdo:
{result.get("text")}
""".strip()
        )

    return "\n\n---\n\n".join(
        context_parts
    )


def build_obsidian_sources(results):

    sources = []

    seen = set()

    for result in results:

        source = result.get(
            "source"
        )

        title = result.get(
            "title"
        )

        if not source or not title:
            continue

        if source in seen:
            continue

        seen.add(
            source
        )

        sources.append(
            {
                "file": source,
                "wikilink": f"[[{title}]]",
            }
        )

    return sources


# ============================================================
# SEARCH
# ============================================================

@app.post("/search")
def search(
    request: SearchRequest,
    _: None = Depends(verify_api_key),
):

    return {
        "query": request.query,
        "results": search_second_brain(
            request.query
        ),
    }


# ============================================================
# ROUTE
# ============================================================

@app.post("/route")
def route(
    request: AskRequest,
    _: None = Depends(verify_api_key),

):

    intent = classify_intent(
        request.query
    )

    return {
        "query": request.query,
        "intent": intent.value,
    }


# ============================================================
# MEMORY ANALYZER
# ============================================================

MEMORY_CATEGORIES = {
    "IGNORE",
    "TEMPORARY",
    "MEMORY",
    "KNOWLEDGE",
    "PROJECT",
    "TASK",
    "DECISION",
    "JOURNAL",
}


MEMORY_FOLDER_MAP = {
    "MEMORY": "10 Memória",
    "KNOWLEDGE": "30 Conhecimento",
    "PROJECT": "20 Projetos",
    "TASK": "00 Caixa de Entrada",
    "DECISION": "10 Memória",
    "JOURNAL": "60 Diário",
}


def clean_json_response(
    text: str
):

    cleaned = (
        text.strip()
    )

    if cleaned.startswith(
        "```"
    ):

        cleaned = re.sub(
            r"^```(?:json)?\s*",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )

        cleaned = re.sub(
            r"\s*```$",
            "",
            cleaned,
        )

    return json.loads(
        cleaned
    )


def normalize_memory_analysis(
    data: dict
):

    action = str(
        data.get(
            "action",
            "IGNORE"
        )
    ).upper()

    if (
        action
        not in MEMORY_CATEGORIES
    ):
        action = "IGNORE"

    should_store = bool(
        data.get(
            "should_store",
            False
        )
    )

    if action in {
        "IGNORE",
        "TEMPORARY",
    }:
        should_store = False

    confidence = data.get(
        "confidence",
        0
    )

    try:

        confidence = float(
            confidence
        )

    except (
        TypeError,
        ValueError,
    ):

        confidence = 0.0

    confidence = max(
        0.0,
        min(
            confidence,
            1.0
        )
    )

    return {
        "action": action,
        "should_store": should_store,
        "suggested_folder": data.get(
            "suggested_folder"
        ),
        "suggested_title": data.get(
            "suggested_title"
        ),
        "summary": data.get(
            "summary"
        ),
        "reason": data.get(
            "reason"
        ),
        "confidence": confidence,
    }


def analyze_memory_text(
    text: str
):

    if not gemini_client:

        raise HTTPException(
            status_code=503,
            detail="Gemini não configurado.",
        )

    text = text.strip()

    if not text:

        raise HTTPException(
            status_code=400,
            detail="Texto vazio.",
        )

    prompt = f"""
Você é o classificador de memória de um Second Brain pessoal
baseado em Obsidian.

Analise a informação e determine se ela merece ser armazenada.

CLASSIFICAÇÕES:

IGNORE
Conversa trivial ou informação sem valor futuro.

TEMPORARY
Informação útil apenas temporariamente.

MEMORY
Fato persistente sobre o usuário, ambiente, configuração,
preferência ou contexto pessoal.

KNOWLEDGE
Conhecimento técnico, procedimento, troubleshooting,
aprendizado ou referência reutilizável.

PROJECT
Informação relacionada diretamente a um projeto.

TASK
Ação objetiva ainda pendente.

DECISION
Escolha já tomada e relevante para o futuro.

JOURNAL
Registro cronológico de atividade ou acontecimento.

ESTRUTURA DO VAULT:

00 Caixa de Entrada
10 Memória
20 Projetos
30 Conhecimento
40 Áreas
50 Referências
60 Diário
90 Legado
99 Arquivo

REGRAS:

1. Não invente informações.
2. Prefira IGNORE quando não houver valor futuro claro.
3. TASK representa algo pendente.
4. DECISION representa uma escolha tomada.
5. PROJECT representa algo relacionado a um projeto.
6. KNOWLEDGE representa conhecimento reutilizável.
7. MEMORY representa contexto persistente.
8. Não use emojis.
9. Gere um título curto e objetivo.
10. confidence deve ficar entre 0 e 1.

Responda somente com JSON válido:

{{
  "action": "DECISION",
  "should_store": true,
  "suggested_folder": "10 Memória",
  "suggested_title": "Uso do Gemini no Second Brain",
  "summary": "Foi decidido utilizar Gemini como modelo de linguagem do Second Brain.",
  "reason": "Decisão arquitetural relevante.",
  "confidence": 0.95
}}

TEXTO:

{text}
""".strip()

    raw_response = ""

    try:

        response = (
            gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
        )

        raw_response = (
            response.text
        )

        parsed = clean_json_response(
            raw_response
        )

        return normalize_memory_analysis(
            parsed
        )

    except json.JSONDecodeError:

        print(
            "JSON inválido:",
            raw_response,
            flush=True,
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Gemini retornou JSON inválido."
            ),
        )

    except HTTPException:
        raise

    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Erro ao analisar memória: {error}"
            ),
        )


# ============================================================
# MEMORY ANALYZE
# ============================================================

@app.post("/memory/analyze")
def memory_analyze(
    request: MemoryAnalyzeRequest,
    _: None = Depends(verify_api_key),

):

    analysis = analyze_memory_text(
        request.text
    )

    return {
        "text": request.text,
        **analysis,
    }


# ============================================================
# MEMORY WRITER
# ============================================================

def sanitize_filename(
    title: str
):

    if not title:
        title = "Nota sem título"

    title = title.strip()

    title = re.sub(
        r'[<>:"/\\|?*]',
        "",
        title
    )

    title = re.sub(
        r"[\x00-\x1f]",
        "",
        title
    )

    title = re.sub(
        r"\s+",
        " ",
        title
    )

    title = title.strip(
        ". "
    )

    if not title:
        title = "Nota sem título"

    return title[:120]


def resolve_memory_folder(
    action: str
):

    folder_name = MEMORY_FOLDER_MAP.get(
        action
    )

    if not folder_name:
        return None

    folder_path = (
        VAULT_PATH
        / folder_name
    )

    vault_resolved = (
        VAULT_PATH.resolve()
    )

    folder_resolved = (
        folder_path.resolve()
    )

    if not folder_resolved.is_relative_to(
        vault_resolved
    ):

        raise HTTPException(
            status_code=400,
            detail="Destino inválido.",
        )

    return folder_path


def build_memory_markdown(
    text: str,
    analysis: dict,
    title: str
):

    now = datetime.now()

    created_iso = (
        now.isoformat(
            timespec="seconds"
        )
    )

    created_date = (
        now.strftime(
            "%Y-%m-%d"
        )
    )

    action = (
        analysis[
            "action"
        ]
    )

    summary = (
        analysis.get(
            "summary"
        )
        or text
    )

    reason = (
        analysis.get(
            "reason"
        )
        or ""
    )

    markdown = f"""---
type: {action.lower()}
created: {created_iso}
source: second-brain
---

# {title}

## Resumo

{summary}

## Registro original

{text}
"""

    if reason:

        markdown += f"""
## Contexto da classificação

{reason}
"""

    markdown += f"""
## Metadados

- Categoria: {action}
- Registrado em: {created_date}
"""

    if action == "TASK":

        markdown += """
- Status: Pendente
"""

    return (
        markdown.strip()
        + "\n"
    )

# ============================================================
# PREPARAÇÃO DE NOVA MEMÓRIA
# ============================================================

def prepare_memory_write(
    text: str
):

    analysis = analyze_memory_text(
        text
    )

    if not analysis[
        "should_store"
    ]:

        return {
            "analysis": analysis,
            "can_write": False,
            "reason": (
                "O Memory Analyzer decidiu "
                "que este conteúdo não deve "
                "ser armazenado."
            ),
        }

    action = (
        analysis[
            "action"
        ]
    )

    folder = resolve_memory_folder(
        action
    )

    if folder is None:

        return {
            "analysis": analysis,
            "can_write": False,
            "reason": (
                "A categoria não possui "
                "destino de escrita."
            ),
        }

    title = sanitize_filename(
        analysis.get(
            "suggested_title"
        )
        or "Nota sem título"
    )

    filename = (
        f"{title}.md"
    )

    target = (
        folder
        / filename
    )

    vault_resolved = (
        VAULT_PATH.resolve()
    )

    target_resolved = (
        target.resolve()
    )

    if not target_resolved.is_relative_to(
        vault_resolved
    ):

        raise HTTPException(
            status_code=400,
            detail=(
                "Caminho de destino inválido."
            ),
        )

    markdown = build_memory_markdown(
        text=text,
        analysis=analysis,
        title=title,
    )

    relative_target = (
        target.relative_to(
            VAULT_PATH
        )
    )

    return {
        "analysis": analysis,
        "can_write": True,
        "title": title,
        "folder": str(
            folder.relative_to(
                VAULT_PATH
            )
        ),
        "file": str(
            relative_target
        ),
        "target": target,
        "content": markdown,
    }

# ============================================================
# LEITURA SEGURA DE NOTA COMPLETA
# ============================================================

def resolve_vault_source(
    source: str
):
    """
    Resolve um caminho vindo do Qdrant sem permitir acesso
    fora do Vault.
    """

    if not source:
        return None

    source_path = Path(
        source
    )

    if source_path.is_absolute():
        return None

    target = (
        VAULT_PATH
        / source_path
    )

    vault_resolved = (
        VAULT_PATH.resolve()
    )

    target_resolved = (
        target.resolve()
    )

    if not target_resolved.is_relative_to(
        vault_resolved
    ):
        return None

    if target_resolved.suffix.lower() != ".md":
        return None

    return target_resolved


def read_full_memory_note(
    source: str
):
    """
    Lê a nota Markdown completa usada como candidata pelo Qdrant.

    Se a nota for muito grande, preserva o início e o fim.
    Isso mantém frontmatter/contexto inicial e também as
    atualizações mais recentes, que normalmente são anexadas
    no final da nota.

    Retorna None quando o arquivo não puder ser lido. Nesse caso,
    o classificador pode usar como fallback o chunk do Qdrant.
    """

    target = resolve_vault_source(
        source
    )

    if target is None:
        return None

    if not target.exists():
        return None

    if not target.is_file():
        return None

    try:
        content = target.read_text(
            encoding="utf-8"
        )
    except Exception as error:
        print(
            f"Erro lendo nota completa "
            f"{source}: {error}",
            flush=True
        )
        return None

    content = content.strip()

    if not content:
        return None

    if (
        len(content)
        <= MEMORY_NOTE_MAX_CHARS
    ):
        return content

    marker = (
        "\n\n"
        "[... conteúdo intermediário omitido "
        "por limite de contexto ...]"
        "\n\n"
    )

    available = (
        MEMORY_NOTE_MAX_CHARS
        - len(marker)
    )

    head_size = (
        available // 2
    )

    tail_size = (
        available
        - head_size
    )

    return (
        content[:head_size]
        + marker
        + content[-tail_size:]
    )


# ============================================================
# ATUALIZAÇÃO DE MEMÓRIA EXISTENTE
# ============================================================

def classify_memory_operation(
    new_text: str,
    duplicate: dict | None
):

    if duplicate is None:

        return {
            "operation": "CREATE",
            "reason": (
                "Nenhuma memória semanticamente semelhante "
                "foi encontrada."
            ),
            "update_summary": None,
            "confidence": 1.0,
            "comparison_scope": None,
        }

    existing_title = (
        duplicate.get("title")
        or ""
    )

    existing_source = (
        duplicate.get("source")
        or ""
    )

    # O Qdrant continua sendo usado para localizar a nota candidata.
    # A comparação CREATE / UPDATE / IGNORE passa a usar o Markdown
    # completo do Vault quando ele estiver disponível.
    full_note_text = read_full_memory_note(
        existing_source
    )

    if full_note_text:
        existing_text = full_note_text
        comparison_scope = "NOTA COMPLETA DO VAULT"
    else:
        existing_text = (
            duplicate.get("text")
            or ""
        )
        comparison_scope = (
            "CHUNK DO QDRANT (FALLBACK)"
        )

    prompt = f"""
Você é responsável por manter um Second Brain em Obsidian
sem duplicações desnecessárias.

Compare a NOVA INFORMAÇÃO com a MEMÓRIA EXISTENTE.

Escolha exatamente uma operação:

IGNORE
Use quando a nova informação disser essencialmente a mesma
coisa que já está registrada, sem acrescentar nada relevante.

UPDATE
Use quando a nova informação tratar do mesmo assunto ou decisão
da memória existente, mas acrescentar, corrigir, substituir ou
evoluir alguma informação importante.

CREATE
Use quando a nova informação representar um assunto,
decisão ou contexto suficientemente diferente para merecer
uma nova nota.

REGRAS:

1. Não invente informações.
2. Não escolha UPDATE apenas porque os textos falam do mesmo tema.
3. Se o significado for praticamente o mesmo, escolha IGNORE.
4. Se houver informação nova sobre o mesmo registro, escolha UPDATE.
5. Se forem fatos distintos, escolha CREATE.
6. update_summary deve conter somente a informação nova relevante.
7. confidence deve ser um número entre 0 e 1.
8. Responda somente com JSON válido.

MEMÓRIA EXISTENTE

Título:
{existing_title}

Arquivo:
{existing_source}

Escopo usado na comparação:
{comparison_scope}

Conteúdo:
{existing_text}

NOVA INFORMAÇÃO

{new_text}

Responda:

{{
  "operation": "UPDATE",
  "reason": "A informação acrescenta um novo detalhe à memória existente.",
  "update_summary": "Resumo apenas da nova informação relevante.",
  "confidence": 0.95
}}
""".strip()

    raw_response = ""

    try:

        response = (
            gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
        )

        raw_response = response.text

        data = clean_json_response(
            raw_response
        )

    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail=(
                "Erro ao comparar memória existente: "
                f"{error}"
            ),
        )

    operation = str(
        data.get(
            "operation",
            "IGNORE"
        )
    ).upper()

    if operation not in {
        "CREATE",
        "UPDATE",
        "IGNORE",
    }:

        operation = "IGNORE"

    confidence = data.get(
        "confidence",
        0
    )

    try:

        confidence = float(
            confidence
        )

    except (
        TypeError,
        ValueError,
    ):

        confidence = 0.0

    confidence = max(
        0.0,
        min(
            confidence,
            1.0
        )
    )

    return {
        "operation": operation,
        "reason": data.get(
            "reason"
        ),
        "update_summary": data.get(
            "update_summary"
        ),
        "confidence": confidence,
        "comparison_scope": comparison_scope,
    }


# ========================================================
# ATUALIZA NOTA EXISTENTE
# ========================================================

def append_memory_update(
    duplicate: dict,
    new_text: str,
    decision: dict
):

    source = duplicate.get(
        "source"
    )

    if not source:

        raise HTTPException(
            status_code=400,
            detail=(
                "A memória existente não possui "
                "caminho válido."
            ),
        )

    target = (
        VAULT_PATH
        / source
    )

    vault_resolved = (
        VAULT_PATH.resolve()
    )

    target_resolved = (
        target.resolve()
    )

    if not target_resolved.is_relative_to(
        vault_resolved
    ):

        raise HTTPException(
            status_code=400,
            detail="Caminho de atualização inválido.",
        )

    if not target.exists():

        raise HTTPException(
            status_code=404,
            detail=(
                "A nota encontrada no Qdrant "
                "não existe mais no Vault."
            ),
        )

    now = datetime.now()

    timestamp = now.strftime(
        "%Y-%m-%d %H:%M"
    )

    summary = (
        decision.get(
            "update_summary"
        )
        or new_text
    )

    addition = f"""

## Atualização — {timestamp}

{summary}

### Registro original da atualização

{new_text}
"""

    try:

        with target.open(
            "a",
            encoding="utf-8"
        ) as file:

            file.write(
                addition
            )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Erro ao atualizar nota: {error}"
            ),
        )

    return {
        "file": source,
        "title": duplicate.get(
            "title"
        ),
        "wikilink": duplicate.get(
            "wikilink"
        ),
    }

# ============================================================
# BUSCA DE MEMÓRIA SEMELHANTE
# ============================================================

def find_duplicate_memory(
    text: str
):

    text = text.strip()

    if not text:
        return None

    query_vector = embedding_model.encode(
        f"query: {text}",
        normalize_embeddings=True,
    ).tolist()

    results = qdrant.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=10,
    )

    best_match = None

    for point in results.points:

        payload = point.payload or {}

        source = payload.get(
            "source"
        )

        if not source:
            continue

        if source in EXCLUDED_SEARCH_FILES:
            continue

        if (
            payload.get(
                "document_type"
            )
            == "índice"
        ):
            continue

        if (
            best_match is None
            or point.score > best_match.score
        ):
            best_match = point

    if best_match is None:
        return None

    # Aqui usamos 0.80 para considerar uma nota
    # como candidata a CREATE / UPDATE / IGNORE.
    if (
        best_match.score
        < MEMORY_CANDIDATE_THRESHOLD
    ):
        return None

    payload = (
        best_match.payload
        or {}
    )

    title = payload.get(
        "title"
    )

    return {
        "score": round(
            best_match.score,
            4
        ),
        "source": payload.get(
            "source"
        ),
        "title": title,
        "heading": payload.get(
            "heading"
        ),
        "text": payload.get(
            "text"
        ),
        "wikilink": (
            f"[[{title}]]"
            if title
            else None
        ),
    }

# ============================================================
# MEMORY WRITE
# ============================================================
@app.post("/memory/write")
def memory_write(
    request: MemoryWriteRequest,
    _: None = Depends(verify_api_key),

):

    text = request.text.strip()

    if not text:

        raise HTTPException(
            status_code=400,
            detail="Texto vazio.",
        )

    # ========================================================
    # PROCURA MEMÓRIA SEMELHANTE
    # ========================================================

    duplicate = find_duplicate_memory(
        text
    )

    # ========================================================
    # SE ENCONTROU, GEMINI DECIDE:
    # CREATE / UPDATE / IGNORE
    # ========================================================

    decision = classify_memory_operation(
        text,
        duplicate
    )

    operation = decision[
        "operation"
    ]

    # ========================================================
    # IGNORE
    # ========================================================

    if operation == "IGNORE":

        return {
            "written": False,
            "updated": False,
            "operation": "IGNORE",
            "message": (
                "A informação já está suficientemente "
                "registrada no Second Brain."
            ),
            "existing_memory": duplicate,
            "decision": decision,
        }

    # ========================================================
    # UPDATE
    # ========================================================

    if (
        operation == "UPDATE"
        and duplicate
    ):

        preview = {
            "operation": "UPDATE",
            "existing_file": duplicate.get(
                "source"
            ),
            "existing_title": duplicate.get(
                "title"
            ),
            "wikilink": duplicate.get(
                "wikilink"
            ),
            "update_summary": decision.get(
                "update_summary"
            ),
            "reason": decision.get(
                "reason"
            ),
            "confidence": decision.get(
                "confidence"
            ),
            "comparison_scope": decision.get(
                "comparison_scope"
            ),
        }

        if not request.confirm:

            return {
                "written": False,
                "updated": False,
                "confirmed": False,
                "operation": "UPDATE",
                "message": (
                    "Preview de atualização gerado. "
                    "Envie confirm=true para atualizar."
                ),
                "preview": preview,
            }

        result = append_memory_update(
            duplicate=duplicate,
            new_text=text,
            decision=decision,
        )

        print(
            f"Memória atualizada: {result['file']}",
            flush=True
        )

        return {
            "written": False,
            "updated": True,
            "confirmed": True,
            "operation": "UPDATE",
            "file": result[
                "file"
            ],
            "title": result[
                "title"
            ],
            "wikilink": result[
                "wikilink"
            ],
            "summary": decision.get(
                "update_summary"
            ),
        }

    # ========================================================
    # CREATE
    # ========================================================

    prepared = prepare_memory_write(
        text
    )

    analysis = prepared[
        "analysis"
    ]

    if not prepared[
        "can_write"
    ]:

        return {
            "written": False,
            "updated": False,
            "operation": "IGNORE",
            "analysis": analysis,
            "reason": prepared[
                "reason"
            ],
        }

    preview = {
        "operation": "CREATE",
        "action": analysis[
            "action"
        ],
        "title": prepared[
            "title"
        ],
        "folder": prepared[
            "folder"
        ],
        "file": prepared[
            "file"
        ],
        "summary": analysis.get(
            "summary"
        ),
        "confidence": analysis.get(
            "confidence"
        ),
    }

    if not request.confirm:

        return {
            "written": False,
            "updated": False,
            "confirmed": False,
            "operation": "CREATE",
            "message": (
                "Preview de criação gerado. "
                "Envie confirm=true para gravar."
            ),
            "preview": preview,
        }

    target = prepared[
        "target"
    ]

    if target.exists():

        raise HTTPException(
            status_code=409,
            detail=(
                "O arquivo já existe. "
                "Nenhum arquivo foi sobrescrito."
            ),
        )

    try:

        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        target.write_text(
            prepared[
                "content"
            ],
            encoding="utf-8",
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=(
                f"Erro ao gravar nota: {error}"
            ),
        )

    print(
        f"Memória criada: {prepared['file']}",
        flush=True
    )

    return {
        "written": True,
        "updated": False,
        "confirmed": True,
        "operation": "CREATE",
        "file": prepared[
            "file"
        ],
        "action": analysis[
            "action"
        ],
        "title": prepared[
            "title"
        ],
        "summary": analysis.get(
            "summary"
        ),
    }

# ============================================================
# ASK
# ============================================================

@app.post("/ask")
def ask(
    request: AskRequest,
    _: None = Depends(verify_api_key),

):

    if not gemini_client:

        raise HTTPException(
            status_code=503,
            detail="Gemini não configurado.",
        )

    query = request.query.strip()

    if not query:

        raise HTTPException(
            status_code=400,
            detail="Pergunta vazia.",
        )

    intent = classify_intent(
        query
    )

    # --------------------------------------------------------
    # GENERAL
    # --------------------------------------------------------

    if intent == Intent.GENERAL:

        prompt = f"""
Você é um assistente de conhecimento geral.

Responda em português do Brasil.

Pergunta:

{query}
""".strip()

        try:

            response = (
                gemini_client.models.generate_content(
                    model=GEMINI_MODEL,
                    contents=prompt,
                )
            )

        except Exception as error:

            raise HTTPException(
                status_code=502,
                detail=(
                    f"Erro ao consultar Gemini: {error}"
                ),
            )

        return {
            "query": query,
            "intent": intent.value,
            "answer": response.text,
            "sources": [],
        }

    # --------------------------------------------------------
    # MEMORY / HYBRID
    # --------------------------------------------------------

    results = search_second_brain(
        query
    )

    if not results:

        return {
            "query": query,
            "intent": intent.value,
            "answer": (
                "Não encontrei notas com relevância suficiente "
                "no Second Brain para responder com segurança."
            ),
            "sources": [],
            "context_results": [],
        }

    context = build_context(
        results
    )

    sources = build_obsidian_sources(
        results
    )

    if intent == Intent.MEMORY:

        instruction = """
Responda principalmente com base nas notas recuperadas do
Obsidian.

Não invente fatos ausentes das notas.

Se a informação não estiver registrada, diga isso claramente.
""".strip()

    else:

        instruction = """
Combine as informações do Obsidian com conhecimento geral.

Diferencie claramente o que vem das notas e o que vem de
conhecimento geral.
""".strip()

    prompt = f"""
Você é o assistente do meu Second Brain.

INTENÇÃO:
{intent.value}

INSTRUÇÕES:

{instruction}

REGRAS:

1. Responda em português do Brasil.
2. Não invente informações.
3. Ao usar uma nota, mencione seu título.
4. Não trate similaridade semântica como prova factual.
5. Use apenas o contexto recuperado para fatos pessoais.
6. Ignore fontes que não contribuam para responder à pergunta.

PERGUNTA:

{query}

CONTEXTO DO OBSIDIAN:

{context}
""".strip()

    try:

        response = (
            gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
        )

    except Exception as error:

        raise HTTPException(
            status_code=502,
            detail=(
                f"Erro ao consultar Gemini: {error}"
            ),
        )

    return {
        "query": query,
        "intent": intent.value,
        "answer": response.text,
        "sources": sources,
        "context_results": results,
    }