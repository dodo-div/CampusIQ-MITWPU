
"""
CampusIQ — Citation Relevance Filter

Retains validated citations for documented facts,
including partially supported answers.

Avoids citing older calendars as evidence for
unavailable future academic years.

This is citation filtering, not full claim verification.
"""

import re


DOCUMENT_PAGE = re.compile(
    r"([A-Za-z0-9_.-]+\.txt)"
    r"\*?\s*,\s*Page\s*:?\s*(\d+)",
    re.IGNORECASE,
)

PAGE_REFERENCE = re.compile(
    r"\bPage\s*:?\s*(\d+)\b",
    re.IGNORECASE,
)

UNAVAILABLE = re.compile(
    r"could not be verified|cannot be verified|"
    r"not available|couldn't find sufficiently relevant|"
    r"no relevant evidence|unable to verify|"
    r"cannot confirm|couldn\x27t verify|does not (?:mention|specify|provide)|"
    r"do not (?:mention|specify|provide)",
    re.IGNORECASE,
)

CALENDAR_YEAR = re.compile(
    r"\b(20\d{2})\s*[-–]\s*(?:20)?(\d{2})\b"
)


def _page_number(citation):
    try:
        page = int(citation.get("page"))
        return page if page > 0 else None
    except (TypeError, ValueError, AttributeError):
        return None


def _unique(citations):
    result = []
    seen = set()

    for item in citations or []:
        if not isinstance(item, dict):
            continue

        document = str(item.get("document", "")).strip()
        page = _page_number(item)

        if not document or page is None:
            continue

        key = (document.lower(), page)

        if key not in seen:
            seen.add(key)
            result.append(dict(item))

    return result


def _unavailable_calendar_request(question, answer):
    """
    An unavailable academic-year question must
    not be supported using a different year's
    calendar citation.
    """

    question = str(question or "")
    answer = str(answer or "")

    if not re.search(r"\bcalendar\b", question, re.I):
        return False

    if not UNAVAILABLE.search(answer):
        return False

    requested_years = CALENDAR_YEAR.findall(question)

    if not requested_years:
        return False

    return True


def select_answer_citations(
    answer,
    citations,
    question="",
):
    """
    Select only from validated retrieved citations.

    Priority:
    1. Suppress citations for an unavailable
       academic calendar year.
    2. Keep explicit document+page references
       supporting factual background.
    3. Use unambiguous page references.
    4. Suppress citations for wholly unsupported
       answers.
    5. Otherwise keep validated citations.
    """

    valid = _unique(citations)

    if not valid:
        return []

    if not isinstance(answer, str):
        return valid

    if _unavailable_calendar_request(question, answer):
        return []

    citation_text = answer
    if UNAVAILABLE.search(answer):
        # A citation attached only to an absence claim does not support the
        # requested fact. Keep explicit citations on separate factual sentences.
        factual_sentences = []
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", answer):
            if UNAVAILABLE.search(sentence) or re.match(r"\s*(?:Important|Note):", sentence, re.I):
                continue
            prose = DOCUMENT_PAGE.sub("", sentence)
            prose = re.sub(r"[\[\]()*#:.,]|\bSource\b", "", prose, flags=re.I).strip()
            if len(prose) >= 25:
                factual_sentences.append(sentence)
        citation_text = " ".join(factual_sentences)

    explicit_pairs = {
        (document.lower(), int(page))
        for document, page in DOCUMENT_PAGE.findall(citation_text)
    }

    if explicit_pairs:
        selected = [
            citation
            for citation in valid
            if (
                str(citation["document"]).lower(),
                citation["page"],
            ) in explicit_pairs
        ]

        return selected

    if UNAVAILABLE.search(answer):
        # No explicitly cited, validated factual
        # evidence: avoid implying the unresolved
        # requested fact is documented.
        return []

    mentioned_pages = {
        int(page)
        for page in PAGE_REFERENCE.findall(answer)
    }

    documents = {
        citation["document"].lower()
        for citation in valid
    }

    if mentioned_pages and len(documents) == 1:
        selected = [
            citation
            for citation in valid
            if citation["page"] in mentioned_pages
        ]

        return selected

    return valid


def remove_duplicate_source_lines(answer):
    """
    Remove text-only citation formatting while
    preserving the answer and its qualifications.
    """

    if not isinstance(answer, str):
        return answer

    cleaned = answer
    cleaned = re.sub(
        r"(?im)^[ \t]*(?:[-*+]\s+)?\*{0,2}Source\*{0,2}:\*{0,2}\s*"
        r"\*{0,2}[A-Za-z0-9_.-]+\.txt\*{0,2}\s*,\s*Page\s*:?\s*\d+\*{0,2}[ \t]*$",
        "", cleaned,
    )
    cleaned = re.sub(r"\s*\[Source:\s*[A-Za-z0-9_.-]+\.txt\s*,\s*Page\s*:?\s*\d+\]", "", cleaned, flags=re.I)

    # Remove standalone lines containing only
    # a source reference, including italic markers.
    cleaned = re.sub(
        r"(?im)^[ \t]*"
        r"\*?\(?\*?Source:\s*"
        r"[A-Za-z0-9_.-]+\.txt"
        r"\*?\s*,\s*Page\s*:?\s*\d+"
        r"\*?\)?\*?[ \t]*$",
        "",
        cleaned,
    )

    # Remove inline parenthesized references:
    # (*Examination-Ordinance-2022.txt, Page 5*)
    cleaned = re.sub(
        r"\s*\(\s*\*?"
        r"[A-Za-z0-9_.-]+\.txt"
        r"\*?\s*,\s*Page\s*:?\s*\d+"
        r"\*?\s*\)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Remove inline (*Source: document.txt, Page 1*)
    cleaned = re.sub(
        r"\s*\(\s*\*?Source:\s*"
        r"[A-Za-z0-9_.-]+\.txt"
        r"\s*,\s*Page\s*:?\s*\d+"
        r"\*?\s*\)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Remove standalone generic page markers.
    cleaned = re.sub(
        r"\s*\(\s*Page\s*:?\s*\d+\s*\)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    # Clean common incorrectly decoded dash.
    cleaned = cleaned.replace("â€“", "–")

    cleaned = re.sub(
        r"\n[ \t]*\n[ \t]*\n+",
        "\n\n",
        cleaned,
    )

    # --------------------------------------------
    # Remove empty Markdown bullet points
    # --------------------------------------------

    # Examples:
    # - 
    # *
    # •
    # 1.
    # These should not appear as empty list items.
    cleaned = re.sub(
        r"(?m)^[ \t]*"
        r"(?:[-*+•]|\d+[.)])"
        r"[ \t]*$",
        "",
        cleaned,
    )

    # --------------------------------------------
    # Remove duplicate source headings
    # --------------------------------------------

    # The frontend already renders a Sources
    # section from structured citations.
    #
    # Only remove a standalone heading, not
    # explanatory text about source documents.
    cleaned = re.sub(
        r"(?im)^[ \t]*"
        r"(?:#{1,6}[ \t]*)?"
        r"\*{0,2}Sources\*{0,2}"
        r"[ \t]*:?[ \t]*$",
        "",
        cleaned,
    )

    # --------------------------------------------
    # Normalize whitespace
    # --------------------------------------------

    # Remove trailing spaces on each line.
    cleaned = re.sub(
        r"(?m)[ \t]+$",
        "",
        cleaned,
    )

    # Reduce three or more consecutive
    # newlines to a single paragraph break.
    cleaned = re.sub(
        r"\n{3,}",
        "\n\n",
        cleaned,
    )

    return cleaned.strip()
