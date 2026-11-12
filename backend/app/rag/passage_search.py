
import re

from app.rag.evidence_guard import (
    detect_topic,
    evidence_matches_topic
)


def search_topic_passages(
    collection,
    question,
    source,
    top_k=3
):
    """
    Search indexed ordinance chunks for exact
    topic terminology when semantic search fails.

    Only searches the selected document version.
    """

    topic = detect_topic(question)

    if topic is None:
        return []

    results = collection.get(
        where={
            "$and": [
                {"type": "ordinance"},
                {"source": source}
            ]
        },
        include=["documents", "metadatas"]
    )

    matches = []

    for document_id, text, metadata in zip(
        results["ids"],
        results["documents"],
        results["metadatas"]
    ):

        if not evidence_matches_topic(question, text):
            continue

        # Prefer substantive content over contents pages.
        normalized = re.sub(r"\s+", " ", text).strip()

        if len(normalized) < 100:
            continue

        matches.append({
            "id": document_id,
            "text": text,
            "metadata": metadata,
            "distance": 1.0,
           "retrieval_method": "keyword_fallback"
        })

    # Prefer substantial passages containing
    # topic-specific explanations.
    matches.sort(
    key=lambda item: (
        -len(item["text"]),
        item["metadata"].get("page", 0)
    )
)

    return matches[:top_k]
