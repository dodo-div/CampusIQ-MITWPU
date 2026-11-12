
"""
CampusIQ — Calendar category reranking

Prioritizes the relevant student category when
retrieved calendar passages contain both first-year
and non-first-year information.

Does not change ChromaDB or embeddings.
"""

import re


CALENDAR_NAME = "academic-calendar-2026-27"


def requested_category(question):
    q = str(question or "").lower()

    non_first_patterns = (
        r"\bexcept\s+(?:the\s+)?first[\s-]*year\b",
        r"\b(?:second|third|fourth|final)[\s-]*year\b",
        r"\b(?:2nd|3rd|4th)[\s-]*year\b",
        r"\bhigher[\s-]*year\b",
        r"\bnon[\s-]*first[\s-]*year\b",
    )

    if any(re.search(p, q) for p in non_first_patterns):
        return "non_first_year"

    if re.search(r"\bfirst[\s-]*year\b|\b1st[\s-]*year\b", q):
        return "first_year"

    return None


def calendar_category(text):
    content = str(text or "").lower()

    if re.search(
        r"\ball\s+except\s+(?:the\s+)?first[\s-]*year\b",
        content,
    ):
        return "non_first_year"

    if re.search(r"\ball\s+first[\s-]*year\b", content):
        return "first_year"

    return None


def rerank_calendar_results(question, results):
    """
    Results must be a list of dictionaries:
    {
      "document": filename,
      "page": integer,
      "text": passage
    }

    Returns a new ordered list.
    """

    category = requested_category(question)

    if not category:
        return list(results)

    def rank(item):
        document = str(item.get("document", "")).lower()
        text = str(item.get("text", ""))
        page = item.get("page")

        if CALENDAR_NAME not in document:
            return 1

        match = calendar_category(text)

        # The verified PDF separates the categories:
        # page 1 = first year
        # page 2 = all except first year.
        expected_page = (
            2 if category == "non_first_year" else 1
        )

        if match == category or (
            match is None and str(page) == str(expected_page)
        ):
            return 0

        if match is not None and match != category:
            return 3

        return 2

    return sorted(results, key=rank)
