
import re
from pathlib import Path

import chromadb

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "vector_db"


def validate_citations(citations):
    """
    Confirm that cited document/page pairs exist
    in CampusIQ's indexed knowledge base.

    This checks citation existence, not whether
    an answer's claims are factually supported.
    """
    client = chromadb.PersistentClient(path=str(DB_PATH))
    collection = client.get_collection("campusiq_documents")

    results = []

    for citation in citations:
        document = citation.get("document")
        page = citation.get("page")

        if not document:
            results.append({
                "citation": citation,
                "valid": False,
                "reason": "Missing document name"
            })
            continue

        filters = [{"source": document}]

        if page is not None:
            filters.append({"page": int(page)})

        where = (
            filters[0] if len(filters) == 1
            else {"$and": filters}
        )

        matches = collection.get(
            where=where,
            limit=1,
            include=["metadatas"]
        )

        exists = len(matches["ids"]) > 0

        results.append({
            "citation": citation,
            "valid": exists,
            "reason": (
                "Document/page exists in database"
                if exists
                else "Document/page not found"
            )
        })

    return results

