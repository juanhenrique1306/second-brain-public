from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

COLLECTION_NAME = "second_brain"

client = QdrantClient(url="http://127.0.0.1:6333")

model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")

test_text = """
O meu servidor doméstico utiliza Proxmox para virtualização.
Também utilizo Docker, Portainer, Traefik, Nextcloud e Jellyfin.
"""

vector = model.encode(test_text).tolist()

existing = [c.name for c in client.get_collections().collections]

if COLLECTION_NAME not in existing:
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=len(vector),
            distance=Distance.COSINE,
        ),
    )

client.upsert(
    collection_name=COLLECTION_NAME,
    points=[
        PointStruct(
            id=1,
            vector=vector,
            payload={
                "text": test_text,
                "source": "teste",
            },
        )
    ],
)

print("Coleção:", COLLECTION_NAME)
print("Dimensão do vetor:", len(vector))
print("Documento de teste indexado com sucesso.")
