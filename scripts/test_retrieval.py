
from pathlib import Path
import chromadb
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "vector_db"

model = SentenceTransformer("all-MiniLM-L6-v2")

client = chromadb.PersistentClient(path=str(DB_PATH))
collection = client.get_collection("campusiq_documents")

questions = [
    "When are Semester I term end examinations for students except first year?",
    "When does Semester II commence in the academic year 2026-27?"
]

for question in questions:
    print("\n" + "=" * 70)
    print("QUESTION:", question)

    embedding = model.encode(
        [question],
        normalize_embeddings=True
    ).tolist()

    results = collection.query(
        query_embeddings=embedding,
        n_results=5,
        where={
            "source": "Academic-Calendar-2026-27.txt"
        },
        include=["documents", "metadatas", "distances"]
    )

    for i, (doc, meta, distance) in enumerate(
        zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0]
        ),
        start=1
    ):
        print(f"\nRESULT {i}")
        print("Page:", meta["page"])
        print("Distance:", round(distance, 4))
        print(doc[:1200])
