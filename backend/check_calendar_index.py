
from pathlib import Path
import chromadb

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

# Change this only if retriever.py uses another location.
CHROMA_PATH = PROJECT_ROOT / "vector_db"

COLLECTION_NAME = "campusiq_documents"

print("ChromaDB path:", CHROMA_PATH)

if not CHROMA_PATH.exists():
    print("Database directory not found.")
    print("Check the path in app/rag/retriever.py")
    raise SystemExit(1)

client = chromadb.PersistentClient(
    path=str(CHROMA_PATH)
)

print("Collections:", client.list_collections())

try:
    collection = client.get_collection(
        COLLECTION_NAME
    )
except Exception as error:
    print("Collection not found:", error)
    raise SystemExit(1)

data = collection.get(
    include=["documents", "metadatas"]
)

found = 0
page2_found = False

for doc_id, document, metadata in zip(
    data["ids"],
    data["documents"],
    data["metadatas"],
):
    metadata = metadata or {}
    document = document or ""

    combined = (
        str(document) + " " + str(metadata)
    ).lower()

    if "academic-calendar-2026-27" not in combined:
        continue

    found += 1

    print("\n" + "=" * 60)
    print("CHUNK ID:", doc_id)
    print("METADATA:", metadata)
    print("TEXT:", document[:1200])

    if (
        "all except first year" in combined
        and "semester ii" in combined
        and (
            "4th jan 2027" in combined
            or "4 january 2027" in combined
        )
    ):
        page2_found = True

print("\n" + "=" * 60)
print("TOTAL CALENDAR CHUNKS:", found)
print("PAGE 2 RELEVANT CONTENT FOUND:", page2_found)

