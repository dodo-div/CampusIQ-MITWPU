
import re

DOCUMENT_VERSIONS = {
    "Examination_Ordinances_2020.txt": {
        "year": 2020,
        "document_type": "examination_ordinance",
    },
    "Examination-Ordinance-2022.txt": {
        "year": 2022,
        "document_type": "examination_ordinance",
    },
    "Academic-Calendar-2026-27.txt": {
        "year": 2026,
        "document_type": "academic_calendar",
    },
}


def get_document_info(filename: str):
    return DOCUMENT_VERSIONS.get(
        filename,
        {
            "year": None,
            "document_type": "unknown"
        }
    )


def detect_admission_year(question: str):
    """
    Identify an explicitly mentioned admission batch.

    Example:
    'Rules for students admitted in 2021-22'
    """

    patterns = [
        r"(?:admitted|admission|batch)\s*(?:in|of|year)?"
        r"\s*(20\d{2})\s*[-/]\s*(\d{2,4})",
        r"(?:admitted|admission|batch)\s*(?:in|of|year)?"
        r"\s*(20\d{2})\b",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            question,
            flags=re.IGNORECASE
        )

        if match:
            return int(match.group(1))

    return None


def requires_batch_clarification(question: str):
    """
    Detect questions where applicability of an
    examination rule may depend on admission batch.
    """

    terms = [
        "promotion",
        "backlog",
        "passing criteria",
        "grace marks",
        "ordinance",
        "revaluation",
        "retotaling"
    ]

    q = question.lower()

    return (
        any(term in q for term in terms)
        and detect_admission_year(question) is None
    )


def build_version_notice(question: str, sources: list):
    """
    Provide an applicability warning without
    inventing which ordinance governs a student.
    """

    ordinance_sources = [
        source for source in sources
        if get_document_info(source)["document_type"]
        == "examination_ordinance"
    ]

    if not ordinance_sources:
        return ""

    if requires_batch_clarification(question):
        return (
            "Important: The available examination "
            "ordinances are from different years. "
            "The applicable provisions may depend "
            "on the student's admission batch and "
            "any subsequent university amendments. "
            "Applicability has not been verified."
        )

    return (
        "Note: Verify that the cited ordinance "
        "applies to the relevant admission batch "
        "and has not been amended."
    )

