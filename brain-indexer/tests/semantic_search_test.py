from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer


COLLECTION_NAME = "second_brain"
MODEL_NAME = "intfloat/multilingual-e5-base"

SEARCH_LIMIT = 15
MAX_RESULTS = 3


client = QdrantClient(
    url="http://127.0.0.1:6333"
)

print("Carregando modelo...")

model = SentenceTransformer(MODEL_NAME)

print()
print("Second Brain - Busca Semântica")
print("Digite 'sair' para encerrar.")
print()


while True:

    query = input("Pergunta: ").strip()

    if query.lower() in {"sair", "exit", "quit"}:
        print("Encerrando.")
        break

    if not query:
        continue

    # O E5 espera prefixo "query:" nas consultas
    query_text = f"query: {query}"

    query_vector = model.encode(
        query_text,
        normalize_embeddings=True
    ).tolist()

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=SEARCH_LIMIT
    )

    if not results.points:

        print()
        print("Nenhum resultado encontrado.")
        print()
        continue

    # ========================================================
    # AGRUPAR POR ARQUIVO
    # ========================================================

    best_by_file = {}

    for point in results.points:

        payload = point.payload or {}

        source = payload.get("source")

        if not source:
            continue

        current = best_by_file.get(source)

        # Mantém apenas o melhor chunk de cada arquivo
        if current is None or point.score > current.score:
            best_by_file[source] = point

    # ========================================================
    # ORDENAR POR SCORE
    # ========================================================

    grouped_results = sorted(
        best_by_file.values(),
        key=lambda point: point.score,
        reverse=True
    )

    # ========================================================
    # PEQUENO RERANKING
    # ========================================================

    reranked = []

    query_lower = query.lower()

    for point in grouped_results:

        payload = point.payload or {}

        title = str(
            payload.get("title", "")
        ).lower()

        heading = str(
            payload.get("heading", "")
        ).lower()

        source = str(
            payload.get("source", "")
        ).lower()

        document_type = payload.get(
            "document_type",
            "conteúdo"
        )

        adjusted_score = point.score

        # Pequeno bônus se a pergunta aparecer no título
        for term in query_lower.split():

            if len(term) <= 3:
                continue

            if term in title:
                adjusted_score += 0.015

            if term in heading:
                adjusted_score += 0.010

            if term in source:
                adjusted_score += 0.005

        # Pequena penalização para páginas de índice
        if document_type == "índice":
            adjusted_score -= 0.025

        reranked.append(
            {
                "point": point,
                "adjusted_score": adjusted_score
            }
        )

    reranked.sort(
        key=lambda item: item["adjusted_score"],
        reverse=True
    )

    final_results = reranked[:MAX_RESULTS]

    # ========================================================
    # MOSTRAR RESULTADOS
    # ========================================================

    print()
    print("Resultados:")
    print()

    for index, item in enumerate(
        final_results,
        start=1
    ):

        point = item["point"]
        adjusted_score = item["adjusted_score"]

        payload = point.payload or {}

        source = payload.get("source")
        title = payload.get("title")
        heading = payload.get("heading")
        text = payload.get("text")
        document_type = payload.get(
            "document_type",
            "conteúdo"
        )

        print(f"Resultado {index}")
        print(f"Score vetorial: {point.score:.4f}")
        print(
            f"Score ajustado: "
            f"{adjusted_score:.4f}"
        )
        print(f"Arquivo: {source}")
        print(f"Título: {title}")
        print(f"Tipo: {document_type}")

        if heading:
            print(f"Seção: {heading}")

        print()
        print(text)
        print()
        print("-" * 70)
        print()
