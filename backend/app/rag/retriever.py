
import re
import logging
from pathlib import Path
from functools import lru_cache

import chromadb
from sentence_transformers import SentenceTransformer

from app.monitoring.metrics import metrics
from app.rag.query_expansion import expand_query
from app.rag.version_policy import get_ordinance_policy
from app.rag.evidence_guard import evidence_matches_topic
from app.rag.passage_search import search_topic_passages

# --------------------------------------------------
# Configuration
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "vector_db"

COLLECTION_NAME = "campusiq_documents"
MODEL_NAME = "all-MiniLM-L6-v2"

CALENDAR_FILE = "Academic-Calendar-2026-27.txt"

MAX_DISTANCE = 0.55

logger = logging.getLogger("CampusIQ.Retriever")


# --------------------------------------------------
# Load ChromaDB and Embedding Model
# --------------------------------------------------

@lru_cache(maxsize=1)
def get_embedding_model():
    return SentenceTransformer(MODEL_NAME)


@lru_cache(maxsize=1)
def get_collection():

    client = chromadb.PersistentClient(
        path=str(DB_PATH)
    )

    return client.get_collection(
        COLLECTION_NAME
    )


# --------------------------------------------------
# Query Classification
# --------------------------------------------------

def detect_semester(question):

    text = question.lower()

    # Check Semester II before Semester I.
    if re.search(
        r"\b(?:semester|sem)\s*(?:ii|2|second)\b",
        text
    ):
        return "II"

    if re.search(
        r"\b(?:semester|sem)\s*(?:i|1|first)\b",
        text
    ):
        return "I"

    return None



def detect_student_group(question):
    """
    Identify the academic calendar student category.

    first_year  -> All First Year (page 1)
    other_years -> All except first year (page 2)

    Explicit exclusions take priority.
    """

    text = question.lower().strip()

    # STEP 1: Detect phrases excluding first year.
    # These MUST be checked before "first year".
    excluding_first_year = (
        r"\b(?:all\s+)?except\s+(?:the\s+)?first[\s-]*year\b"
        r"|\b(?:all\s+)?(?:students?\s+)?other\s+than\s+"
        r"(?:the\s+)?first[\s-]*year\b"
        r"|\bnon[\s-]*first[\s-]*year\b"
        r"|\bexcluding\s+(?:the\s+)?first[\s-]*year\b"
        r"|\bnot\s+(?:in\s+)?(?:the\s+)?first[\s-]*year\b"
    )

    if re.search(excluding_first_year, text):
        return "other_years"

    # STEP 2: Detect second year and above.
    other_years_pattern = (
        r"\b(?:second[\s-]*year|2nd[\s-]*year|"
        r"third[\s-]*year|3rd[\s-]*year|"
        r"fourth[\s-]*year|4th[\s-]*year|"
        r"fifth[\s-]*year|5th[\s-]*year|"
        r"sy|ty|final[\s-]*year|"
        r"higher[\s-]*year)\b"
    )

    if re.search(other_years_pattern, text):
        return "other_years"

    # STEP 3: Detect first-year students.
    first_year_pattern = (
        r"\b(?:first[\s-]*year|1st[\s-]*year|"
        r"fy|freshers?)\b"
    )

    if re.search(first_year_pattern, text):
        return "first_year"

    return None




def detect_calendar_event(question):

    text = question.lower()
        # Explicit last instructional day questions
    # must take priority over semantic ranking.
    if re.search(
        r"\b(?:last|final)\s+instructional\s+day\b",
        text,
    ):
        return "last instructional day"

    # Handle semester-end questions before other events.
    # "End" refers to the academic term here, not
    # automatically to term-end examinations.
    if (
        detect_semester(question)
        and re.search(
            r"\b(?:end|ends|ending|finish|finishes)\b",
            text,
        )
        and not re.search(
            r"\b(?:exams?|examinations?|midterm|mid-term)\b",
            text,
        )
    ):
        return "last instructional day"

    # Midterm must be checked before general exams.
    if re.search(
        r"\b(?:mid[\s-]*term|mid[\s-]*sem(?:ester)?|mte)\b",
        text
    ):
        return "midterm"

    if re.search(
        r"\b(?:term[\s-]*end|end[\s-]*semester|"
        r"final exams?|final examinations?)\b",
        text
    ):
        return "term end exam"

    if re.search(
        r"\b(?:exam|exams|examination|examinations)\b",
        text
    ):
        return "exam"

    if re.search(
        r"\b(?:start|starts|starting|begin|begins|"
        r"commence|commences|commencement|"
        r"reopen|reopening)\b",
        text
    ):
        return "commencement of term"

    if re.search(
        r"\b(?:holiday|holidays|vacation|break)\b",
        text
    ):
        return "holiday"

    if re.search(
        r"\b(?:result|results|declaration)\b",
        text
    ):
        return "result"

    return None



def is_calendar_question(question):

    text = question.lower()

    # Examination regulations are not calendar questions.
    regulatory_terms = (
        r"\b(?:revaluation|rechecking|reassessment|"
        r"backlogs?|atkt|promotion criteria|"
        r"eligibility|ordinance|regulation|"
        r"passing criteria|grade improvement|"
        r"failed subjects?)\b"
    )

    if re.search(regulatory_terms, text):
        return False

    if detect_semester(question):
        return True

    if re.search(
        r"\b(?:academic calendar|academic schedule|"
        r"semester dates|exam dates|examination dates|"
        r"when are my exams|when do exams|"
        r"when is the exam|holidays|vacation)\b",
        text
    ):
        return True

    return False


# --------------------------------------------------
# Embedding Generation
# --------------------------------------------------

def embed_query(question):

    with metrics.stage("embedding"):
        model = get_embedding_model()
        return model.encode([question], normalize_embeddings=True).tolist()


# --------------------------------------------------
# Search ChromaDB
# --------------------------------------------------

def search_collection(
    question,
    top_k=3,
    where=None,
    max_distance=MAX_DISTANCE,
    candidate_count=None
):

    collection = get_collection()

    total_count = collection.count()

    if total_count == 0:
        return []

    if candidate_count is None:
        candidate_count = max(top_k * 5, 15)

    candidate_count = min(
        candidate_count,
        total_count
    )

    query_embedding = embed_query(question)

    arguments = {
        "query_embeddings": query_embedding,
        "n_results": candidate_count,
        "include": [
            "documents",
            "metadatas",
            "distances"
        ]
    }

    if where is not None:
        arguments["where"] = where

    results = collection.query(**arguments)

    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]
    ids = results["ids"][0]

    matches = []

    for document, metadata, distance, doc_id in zip(
        documents,
        metadatas,
        distances,
        ids
    ):

        if distance > max_distance:
            continue

        matches.append({
            "id": doc_id,
            "text": document,
            "metadata": metadata,
            "distance": float(distance)
        })

    return matches[:top_k]


# --------------------------------------------------
# Calendar Event Filtering
# --------------------------------------------------


def calendar_event_matches(event_text, event_type):

    if not event_type:
        return True

    text = event_text.lower()

    if event_type == "last instructional day":
        return "last instructional day" in text
    
    midterm_pattern = (
        r"\b(?:mid[\s-]*term|mid[\s-]*sem(?:ester)?|mte)\b"
    )

    if event_type == "midterm":
        return bool(re.search(midterm_pattern, text))

    if event_type == "term end exam":
        return (
            bool(re.search(
                r"\b(?:term[\s-]*end|end[\s-]*semester|"
                r"summative|final)\b",
                text
            ))
            and not re.search(midterm_pattern, text)
        )

    if event_type == "exam":
        return bool(re.search(
            r"\b(?:exam|examination|assessment)\b",
            text
        ))

    if event_type == "commencement of term":
        return bool(
            re.search(
                r"\b(?:commencement\s+of\s+term|"
                r"commencement\s+of\s+semester|"
                r"term\s+begins?|semester\s+begins?)\b",
                text,
            )
        ) and not bool(
            re.search(
                r"\bnext\s+academic\s+year\b",
                text,
            )
        )

    if event_type == "holiday":
        return bool(re.search(
            r"\b(?:holiday|vacation|break)\b",
            text
        ))

    if event_type == "result":
        return bool(re.search(
            r"\b(?:result|declaration)\b",
            text
        ))

    return True



def search_calendar(question, top_k=3):

    semester = detect_semester(question)
    student_group = detect_student_group(question)
    event_type = detect_calendar_event(question)

    collection = get_collection()

    filters = [
        {
            "type": "calendar_event"
        }
    ]

    if semester:
        filters.append({
            "semester": semester
        })

    if student_group:
        filters.append({
            "student_group": student_group
        })

    where_filter = (
        filters[0]
        if len(filters) == 1
        else {"$and": filters}
    )

    # Calendar events are structured records.
    # Read matching metadata directly rather than
    # rejecting correct dates because of semantic distance.

    results = collection.get(
        where=where_filter,
        include=[
            "documents",
            "metadatas"
        ]
    )

    candidates = []

    for doc_id, document, metadata in zip(
        results["ids"],
        results["documents"],
        results["metadatas"]
    ):

       
        event_text = str(
            metadata.get("event", "")
        ).strip()

        normalized_event = re.sub(
            r"\s+",
            " ",
            event_text.casefold(),
        )

        # Exact matching for critical calendar events.
        # These events must not be selected using
        # broad semantic similarity.

        if event_type == "commencement of term":
            if normalized_event != "commencement of term":
                continue

        elif event_type == "last instructional day":
            if normalized_event != "last instructional day":
                continue

        else:
            if not calendar_event_matches(
                event_text,
                event_type,
            ):
                continue


        candidates.append({
            "id": doc_id,
            "text": document,
            "metadata": metadata,
            "distance": 0.0
        })

    if not candidates:
        logger.info(
            "No exact calendar event matched."
        )
        return []

    # If the question lacks essential qualifiers,
    # return a mixture of applicable records rather
    # than silently assuming first/other-year dates.
    if not semester or not student_group:

        candidates.sort(
            key=lambda item: (
                item["metadata"].get(
                    "student_group", ""
                ),
                item["metadata"].get(
                    "semester", ""
                ),
                item["metadata"].get(
                    "event", ""
                )
            )
        )

        return candidates[:top_k]

    # Metadata already selected the event, semester and student category.
    # Keep all equally applicable records available to detect conflicts.
    return sorted(candidates, key=lambda item: item["id"])[:top_k]


def is_substantive_ordinance_passage(text):
    """
    Reject title-only or nearly empty ordinance
    chunks before treating them as evidence.

    Does not reject a valid passage merely because
    it comes from page 1.
    """
    normalized = re.sub(
        r"\s+",
        " ",
        str(text or ""),
    ).strip()

    if not normalized:
        return False

    title_only = re.fullmatch(
        r"(?:\[Page\s+\d+\]\s*)?"
        r"(?:Page\s+\d+\s+of\s+\d+\s*)?"
        r"Examination\s+Ordinances?"
        r"(?:\s+\d{4})?\s*",
        normalized,
        flags=re.IGNORECASE,
    )

    if title_only:
        return False

    if len(normalized) < 100:
        return False

    return True

# --------------------------------------------------
# Ordinance Semantic Search
# --------------------------------------------------


def search_ordinances(question, top_k=3):
    """
    Retrieve ordinance passages using:

    1. Version-aware document filtering
    2. Targeted masking evidence
    3. Broad semantic candidate search
    4. Topic relevance filtering
    5. Query-expansion retrieval
    6. Targeted passage fallback
    7. Deduplication and ranking

    All evidence remains restricted to the
    ordinance selected by version_policy.py.
    """

    policy = get_ordinance_policy(question)
    selected_source = policy["preferred_source"]

    logger.info(
        "Ordinance search | source=%s | admission_year=%s",
        selected_source,
        policy.get("admission_year"),
    )

    if not selected_source:
        logger.warning(
            "No ordinance source could be selected."
        )
        return []

    where_filter = {
        "$and": [
            {"type": "ordinance"},
            {"source": selected_source},
        ]
    }

    collection = get_collection()

    # --------------------------------------------------
    # 1. Preserve targeted digital-masking retrieval
    # --------------------------------------------------

    normalized_question = question.lower()

    is_masking_question = (
        bool(
            re.search(
                r"\b(?:digital|digitally)\b",
                normalized_question,
            )
        )
        and bool(
            re.search(
                r"\bmask(?:ing|ed)?\b",
                normalized_question,
            )
        )
    )

    if is_masking_question:
        records = collection.get(
            where=where_filter,
            include=[
                "documents",
                "metadatas",
            ],
        )

        targeted_matches = []

        for doc_id, document, metadata in zip(
            records["ids"],
            records["documents"],
            records["metadatas"],
        ):
            document = str(document or "")
            metadata = metadata or {}

            normalized_text = re.sub(
                r"\s+",
                " ",
                document.lower(),
            )

            has_evidence = bool(
                re.search(
                    r"\bdigital(?:ly)?\s+mask(?:ed|ing)\b",
                    normalized_text,
                )
            )

            if not has_evidence:
                continue

            priority = (
                0.0
                if "answer sheet" in normalized_text
                else 1.0
            )

            targeted_matches.append({
                "id": doc_id,
                "text": document,
                "metadata": metadata,
                "distance": priority,
            })

        if targeted_matches:
            targeted_matches.sort(
                key=lambda item: item["distance"]
            )

            logger.info(
                "Digital masking: %d evidence matches",
                len(targeted_matches),
            )

            return targeted_matches[:top_k]

    # --------------------------------------------------
    # 2. Collect a wider set of semantic candidates
    # --------------------------------------------------

    # --------------------------------------------------
    # Targeted retrieval: Result Declaration
    # --------------------------------------------------

    is_result_declaration = bool(
        re.search(
            r"\bresult[s]?\s+declaration\b"
            r"|\bdeclaration\s+of\s+result[s]?\b"
            r"|\bdeclaring\s+(?:the\s+)?result[s]?\b",
            question.lower(),
        )
    )

    if is_result_declaration:
        records = collection.get(
            where=where_filter,
            include=["documents", "metadatas"],
        )

        result_matches = []

        for doc_id, document, metadata in zip(
            records["ids"],
            records["documents"],
            records["metadatas"],
        ):
            document = str(document or "")
            metadata = metadata or {}

            normalized = re.sub(
                r"\s+",
                " ",
                document.lower(),
            )

            # Don't use document title pages.
            if not is_substantive_ordinance_passage(
                document
            ):
                continue

            # Require the relevant subject in
            # the actual indexed passage.
            if not re.search(
                r"\bresult[s]?\s+declaration\b"
                r"|\bdeclaration\s+of\s+result[s]?\b"
                r"|\bdeclaring\s+(?:the\s+)?result[s]?\b",
                normalized,
            ):
                continue

            
            # Require actual result-processing details.
            # A table of contents can contain the
            # section heading but not the provisions.
            substantive_patterns = [
                r"verification\s+and\s+confirmation",
                r"pre[\s-]*requisites\s+required\s+"
                r"for\s+declaring",
                r"preparation\s+and\s+declaration",
                r"gracing,\s*grading,\s*cgpa",
                r"displaying\s+result\s+at\s+"
                r"student",
            ]

            is_substantive = any(
                re.search(pattern, normalized)
                for pattern in substantive_patterns
            )

            if not is_substantive:
                continue

            # Prioritize the actual section 8.1.
            has_section_heading = bool(
                re.search(
                    r"\b8\.1\s+result\s+declaration\b",
                    normalized,
                )
            )

            priority = (
                0.0 if has_section_heading else 1.0
            )


            result_matches.append({
                "id": doc_id,
                "text": document,
                "metadata": metadata,
                "distance": float(priority),
                "retrieval_method": "targeted_result",
            })

        if result_matches:
            result_matches.sort(
                key=lambda item: (
                    item["distance"],
                    -len(item["text"]),
                )
            )

            logger.info(
                "Targeted result declaration "
                "retrieval found %d passages.",
                len(result_matches),
            )

            return result_matches[:top_k]

    candidate_limit = max(12, top_k * 4)

    combined_matches = {}

    
    def add_matches(matches):
        """
        Add relevant, substantive ordinance
        passages to the candidate collection.
        """

        for match in matches:

            # Skip empty passages and title pages.
            if not is_substantive_ordinance_passage(
                match["text"]
            ):
                continue

            # Keep only topic-relevant passages.
            if not evidence_matches_topic(
                question,
                match["text"]
            ):
                continue

            document_id = match["id"]

            previous = combined_matches.get(
                document_id
            )

            if (
                previous is None
                or match["distance"] < previous["distance"]
            ):
                combined_matches[document_id] = match


    original_matches = search_collection(
        question=question,
        top_k=candidate_limit,
        where=where_filter,
        max_distance=MAX_DISTANCE,
        candidate_count=max(
            20,
            candidate_limit,
        ),
    )

    add_matches(original_matches)

    logger.info(
        "Original semantic retrieval: %d "
        "relevant candidates",
        len(combined_matches),
    )

    # --------------------------------------------------
    # 3. Expand when original evidence is insufficient
    # --------------------------------------------------

    add_matches(search_topic_passages(collection, question, selected_source, top_k=candidate_limit))
    if not combined_matches:
        expanded_questions = expand_query(
            question
        ) or []

        for expanded_question in expanded_questions:
            if len(combined_matches) >= top_k:
                break

            expanded_matches = search_collection(
                question=expanded_question,
                top_k=candidate_limit,
                where=where_filter,
                max_distance=MAX_DISTANCE,
                candidate_count=max(
                    20,
                    candidate_limit,
                ),
            )

            add_matches(expanded_matches)

    # --------------------------------------------------
    # 4. Keyword fallback, even without expansions
    # --------------------------------------------------

    if not combined_matches:
        logger.info(
            "Semantic retrieval insufficient. "
            "Trying targeted passage search."
        )

        keyword_matches = search_topic_passages(
            collection=collection,
            question=question,
            source=selected_source,
            top_k=top_k,
        )

        add_matches(keyword_matches)

    # --------------------------------------------------
    # 5. Rank, deduplicate and return
    # --------------------------------------------------

    ranked = sorted(
        combined_matches.values(),
        key=lambda item: item["distance"],
    )

    if not ranked:
        logger.warning(
            "No relevant evidence found in %s",
            selected_source,
        )
        return []

    logger.info(
        "Ordinance retrieval returned %d "
        "ranked records",
        min(len(ranked), top_k),
    )

    return ranked[:top_k]





def select_best_evidence(matches, question, top_k=3):
    """
    Select a compact, relevant set of ordinance
    passages before passing them to Gemini.

    - Reject title-only / contents-only passages.
    - Prioritize passages mentioning the topic.
    - Prefer passages with substantive explanations.
    - Avoid repeated evidence from the same page.

    Does not change ChromaDB or embedding scores.
    """

    if not matches:
        return []

    question_words = set(
        re.findall(r"[a-z]{3,}", question.lower())
    )

    stopwords = {
        "what", "when", "where", "does", "about",
        "under", "which", "with", "from", "that",
        "this", "have", "been", "were", "there",
        "ordinance", "examination", "examinations",
        "2022", "2020", "the", "and", "for",
        "say", "are",
    }

    question_words -= stopwords

    ranked = []
    seen_ids = set()

    for match in matches:
        doc_id = match.get("id")
        text = str(match.get("text") or "")

        if doc_id in seen_ids:
            continue

        seen_ids.add(doc_id)

        if not is_substantive_ordinance_passage(text):
            continue

        normalized = re.sub(
            r"\s+",
            " ",
            text.lower(),
        )

        # Remove extracted PDF page labels from
        # relevance scoring.
        normalized = re.sub(
            r"\[page\s+\d+\]",
            " ",
            normalized,
        )

        normalized = re.sub(
            r"\bpage\s+\d+\s+of\s+\d+\b",
            " ",
            normalized,
        )

        passage_words = set(
            re.findall(r"[a-z]{3,}", normalized)
        )

        overlap = (
            len(question_words & passage_words)
            / max(len(question_words), 1)
        )

        # Prefer evidence with explanatory content.
        substantive_signals = (
            "shall",
            "required",
            "includes",
            "including",
            "verification",
            "preparation",
            "processing",
            "assessment",
            "declaration",
            "digitally masked",
        )

        explanation_bonus = min(
            sum(
                signal in normalized
                for signal in substantive_signals
            ),
            3,
        ) * 0.15

        # Penalize pages that contain numerous
        # section headings but little actual prose.
        section_headings = len(
            re.findall(
                r"(?m)^\s*\d+(?:\.\d+){0,3}\s+"
                r"[A-Z][^\n]{3,80}$",
                text,
            )
        )

        contents_penalty = (
            3.0 if section_headings >= 6 else 0.0
        )

        # Existing retrieval order remains useful.
        # But keyword / targeted scores are not
        # actual semantic distances.
        distance = float(
            match.get("distance", 1.0)
        )

        method = match.get(
            "retrieval_method", "semantic"
        )

        semantic_bonus = (
            max(0.0, 0.55 - distance)
            if method == "semantic"
            else 0.0
        )

        score = (
            overlap * 3.0
            + explanation_bonus
            + semantic_bonus
            - contents_penalty
        )

        ranked.append({
            "match": match,
            "score": score,
        })

    ranked.sort(
        key=lambda item: item["score"],
        reverse=True,
    )

    selected = []
    seen_pages = set()

    for item in ranked:
        match = item["match"]
        metadata = match.get("metadata") or {}

        page_key = (
            metadata.get("source"),
            metadata.get("page"),
        )

        # One representative chunk per page for
        # compact responses. Other pages may still
        # contribute additional evidence.
        passage_key = (page_key, re.sub(r"\s+", " ", match["text"]).strip())
        if passage_key in seen_pages:
            continue
        seen_pages.add(passage_key)
        selected.append(match)

        if len(selected) >= top_k:
            break

    return selected

# --------------------------------------------------
# Format Retrieved Evidence
# --------------------------------------------------

def format_matches(matches):

    if not matches:
        return "", []

    context_parts = []
    sources = []
    seen_sources = set()

    for match in matches:

        metadata = match["metadata"]

        source = metadata.get(
            "source",
            "Unknown document"
        )

        page = metadata.get(
            "page",
            0
        )

        text = match["text"]

        context_parts.append(
            f"[Source: {source}, Page: {page}]\n"
            f"{text}"
        )

        if source not in seen_sources:
            sources.append(source)
            seen_sources.add(source)

    context = "\n\n".join(
        context_parts
    )

    return context, sources


# --------------------------------------------------
# Main Retrieval Function
# --------------------------------------------------

def retrieve_context(question, top_k=3):

    question = question.strip()

    if not question:
        return "", []

    try:

        # Route academic calendar questions.
        if is_calendar_question(question):

            logger.info(
                "Query routed to calendar retrieval."
            )

            matches = search_calendar(
                question,
                top_k=top_k
            )

        else:

            # Route examination regulations.
            logger.info(
                "Query routed to ordinance retrieval."
            )

                        # Retrieve extra candidate passages.
            candidates = search_ordinances(
                question,
                top_k=max(top_k * 3, 8),
            )

            # Select a compact, relevant set.
            matches = select_best_evidence(
                candidates,
                question,
                top_k=top_k,
            )

        if not matches:

            logger.info(
                "No sufficiently relevant evidence found."
            )

            return "", []

        context, sources = format_matches(
            matches
        )

        logger.info(
            "Retrieved %d chunks from %d sources.",
            len(matches),
            len(sources)
        )

        return context, sources

    except Exception:

        logger.exception(
            "CampusIQ retrieval failed."
        )

        raise
