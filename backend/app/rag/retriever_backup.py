
from pathlib import Path
import re

import chromadb
from sentence_transformers import SentenceTransformer

from app.rag.query_expansion import expand_query

# --------------------------------------------------
# Configuration
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "vector_db"

COLLECTION_NAME = "campusiq_documents"
MODEL_NAME = "all-MiniLM-L6-v2"


# --------------------------------------------------
# Load Embedding Model and ChromaDB
# --------------------------------------------------

print("Loading CampusIQ retrieval engine...")

model = SentenceTransformer(MODEL_NAME)

client = chromadb.PersistentClient(
    path=str(DB_PATH)
)

collection = client.get_collection(
    name=COLLECTION_NAME
)

print("CampusIQ retrieval engine ready!")


# --------------------------------------------------
# Normalize Questions
# --------------------------------------------------

def normalize_question(question):
    """
    Normalize student questions for reliable
    semester and academic-year detection.
    """

    q = question.lower()

    q = q.replace("-", " ")
    q = q.replace("_", " ")

    q = " ".join(q.split())

    return q


# --------------------------------------------------
# Detect Semester
# --------------------------------------------------

def detect_semester(question):
    q = normalize_question(question)

    if re.search(
        r"\b(semester|sem|term)\s*(ii|2|second)\b",
        q
    ):
        return "II"

    if re.search(
        r"\b(semester|sem|term)\s*(i|1|first)\b",
        q
    ):
        return "I"

    return None


# --------------------------------------------------
# Detect Student Year
# --------------------------------------------------

def detect_student_group(question):
    """
    Determine which academic calendar applies.

    Page 1: First-year students
    Page 2: All students except first year
    """

    q = normalize_question(question)

    other_year_patterns = [
        "except first year",
        "other than first year",
        "not first year",
        "second year",
        "third year",
        "fourth year",
        "final year",
        "2nd year",
        "3rd year",
        "4th year"
    ]

    first_year_patterns = [
        "first year",
        "1st year"
    ]

    if any(pattern in q for pattern in other_year_patterns):
        return "other_years"

    if any(pattern in q for pattern in first_year_patterns):
        return "first_year"

    return None


# --------------------------------------------------
# Detect Calendar Event
# --------------------------------------------------

def detect_calendar_event(question):
    q = normalize_question(question)

    if any(term in q for term in [
        "mid term",
        "midterm",
        "mid semester"
    ]):
        return "formative assessment 2"

    if any(term in q for term in [
        "vacation",
        "holiday",
        "diwali break",
        "winter break"
    ]):
        return "vacation"

    if (
        any(term in q for term in [
            "exam", "examination", "tee"
        ])
        and any(term in q for term in [
            "when", "date", "schedule",
            "start", "end", "term end",
            "termend"
        ])
    ):
        return "term end exam"

    if any(term in q for term in [
        "commence",
        "begin",
        "start",
        "starting",
        "first day",
        "commencement"
    ]):
        return "commencement of term"

    return None


# --------------------------------------------------
# Question Classification
# --------------------------------------------------

def is_calendar_question(question):
    q = normalize_question(question)

    ordinance_terms = [
        "revaluation",
        "re evaluation",
        "retotal",
        "re total",
        "grace marks",
        "promotion rules",
        "passing criteria",
        "backlog rules",
        "ordinance"
    ]

    if any(term in q for term in ordinance_terms):
        return False

    if detect_calendar_event(question):
        return True

    calendar_terms = [
        "academic calendar",
        "semester date",
        "semester start",
        "semester begin",
        "2026 27 calendar"
    ]

    return any(term in q for term in calendar_terms)


# --------------------------------------------------
# Search Academic Calendar
# --------------------------------------------------

def search_calendar(question, top_k=3):
    semester = detect_semester(question)
    student_group = detect_student_group(question)
    event_type = detect_calendar_event(question)

    if not event_type:
        return []

    results = collection.get(
        where={"type": "calendar_event"},
        include=["documents", "metadatas"]
    )

    candidates = []

    for document, metadata in zip(
        results["documents"],
        results["metadatas"]
    ):
        if (
            semester
            and metadata.get("semester") != semester
        ):
            continue

        if (
            student_group
            and metadata.get("student_group") != student_group
        ):
            continue

        event = metadata.get("event", "").lower()

        if event_type == "vacation":
            if "vacation" not in event:
                continue

        elif event_type not in event:
            continue

        score = 0

        if event_type:
            score += 10

        if semester:
            score += 5

        if student_group:
            score += 5

        candidates.append({
            "text": document,
            "source": metadata.get("source", "Unknown"),
            "page": metadata.get("page", 0),
            "score": score
        })

    candidates.sort(
        key=lambda item: (
            -item["score"],
            item["page"]
        )
    )

    return candidates[:top_k]


# --------------------------------------------------
# Search Examination Ordinances
# --------------------------------------------------

def search_ordinances(
    question,
    top_k=3,
    max_distance=0.55
):
    q = normalize_question(question)

    ordinance_terms = [
        "revaluation",
        "re evaluation",
        "retotal",
        "re total",
        "backlog",
        "grace",
        "passing",
        "promotion",
        "sgpa",
        "cgpa",
        "grading",
        "grade",
        "examination rule",
        "ordinance",
        "assessment",
        "attendance"
    ]

    if not any(term in q for term in ordinance_terms):
        return []

    embedding = model.encode(
        [question],
        normalize_embeddings=True
    ).tolist()

    results = collection.query(
        query_embeddings=embedding,
        n_results=min(
            max(top_k * 3, 5),
            collection.count()
        ),
        where={"type": "ordinance"},
        include=[
            "documents",
            "metadatas",
            "distances"
        ]
    )

    threshold = min(max_distance, 0.55)

    matches = []

    for document, metadata, distance in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0]
    ):
        if distance > threshold:
            continue

        matches.append({
            "text": document,
            "source": metadata.get("source", "Unknown"),
            "page": metadata.get("page", 0),
            "distance": round(float(distance), 4)
        })

    return matches[:top_k]


# --------------------------------------------------
# Main Retrieval Function
# --------------------------------------------------

def retrieve_context(
    question: str,
    top_k: int = 3,
    max_distance: float = 0.55
):
    """
    Retrieve relevant MIT-WPU knowledge.

    Returns:
        context: str
        sources: list[str]

    Compatible with existing FastAPI main.py.
    """

    if not question.strip() or top_k < 1:
        return "", []

    if is_calendar_question(question):
        matches = search_calendar(
            question,
            top_k=top_k
        )
    else:
        matches = search_ordinances(
            question,
            top_k=top_k,
            max_distance=max_distance
        )

    if not matches:
        return "", []

    context_parts = []

    for match in matches:
        page = match.get("page", 0)

        page_label = (
            page if page else "unverified"
        )

        context_parts.append(
            f"[Source: {match['source']}, "
            f"Page: {page_label}]\n"
            f"{match['text']}"
        )

    context = "\n\n---\n\n".join(
        context_parts
    )

    sources = list(
        dict.fromkeys(
            match["source"]
            for match in matches
        )
    )

    return context, sources
