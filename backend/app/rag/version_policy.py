
import re

LATEST_ORDINANCE = "Examination-Ordinance-2022.txt"
LEGACY_ORDINANCE = "Examination_Ordinances_2020.txt"


def detect_admission_year(question):
    """
    Detect an explicitly stated admission batch.

    Does not interpret calendar years or academic
    event dates as admission years.
    """
    text = question.lower()

    patterns = [
        r"\b(?:admitted|joined|enrolled)\s+in\s+(20\d{2})\b",
        r"\badmission\s+(?:year|batch)\s*(?:is|:)?\s*(20\d{2})\b",
        r"\bbatch\s+(?:of\s+)?(20\d{2})\b",
        r"\b(20\d{2})\s*[-/]\s*\d{2}\s+batch\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)

        if match:
            return int(match.group(1))

    return None


def get_ordinance_policy(question):
    """
    Choose which indexed ordinance may be searched.

    This is a conservative retrieval policy, not
    a legal determination of applicability.
    """
    explicit = set(re.findall(
        r"\b(20\d{2})\s+(?:examination\s+)?ordinances?\b"
        r"|\bordinances?\s+(?:of\s+|from\s+)?(20\d{2})\b",
        question, re.I))
    years = {year for pair in explicit for year in pair if year}
    if years:
        source = {"2020": LEGACY_ORDINANCE, "2022": LATEST_ORDINANCE}.get(next(iter(years))) if len(years) == 1 else None
        return {"admission_year": detect_admission_year(question),
                "preferred_source": source, "requires_confirmation": True,
                "notice": "Explicit ordinance version requested; applicability remains unverified."}
    admission_year = detect_admission_year(question)

    if admission_year is None:
        return {
            "admission_year": None,
            "preferred_source": LATEST_ORDINANCE,
            "requires_confirmation": True,
            "notice": (
                "This information comes from the 2022 "
                "examination ordinance. Its applicability "
                "to your admission batch has not been confirmed."
            )
        }

    if admission_year >= 2022:
        return {
            "admission_year": admission_year,
            "preferred_source": LATEST_ORDINANCE,
            "requires_confirmation": True,
            "notice": (
                "The 2022 examination ordinance was prioritized "
                "for this admission batch. Check any subsequent "
                "amendments and program-specific exceptions."
            )
        }

    return {
        "admission_year": admission_year,
        "preferred_source": LEGACY_ORDINANCE,
        "requires_confirmation": True,
        "notice": (
            "An older examination ordinance was selected "
            "for review. The exact ordinance applicable to "
            "this admission batch has not been confirmed, "
            "and additional historical regulations may apply."
        )
    }
