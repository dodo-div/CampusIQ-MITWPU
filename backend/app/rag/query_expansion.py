
import re


def expand_query(question):
    """
    Generate targeted alternative search queries
    for MIT-WPU examination terminology.

    Returns [] when no expansion is appropriate.
    """

    question_lower = question.casefold()

    expansions = []

    # Backlog / ATKT-related questions
    if re.search(
        r"\b(backlogs?|atkt|failed subjects?|"
        r"reappear|reappearance)\b",
        question_lower
    ):
        expansions.extend([
            "ATKT examination rules for failed courses",
            "Backlog examination and reappearance regulations",
            "Promotion criteria for students with backlogs"
        ])

    # Revaluation-related questions
    if re.search(
        r"\b(revaluation|rechecking|reassessment)\b",
        question_lower
    ):
        expansions.extend([
            "Examination answer sheet revaluation rules",
            "Reassessment and verification of examination marks"
        ])

    # Attendance-related questions
    if re.search(
        r"\b(attendance|detained|detention)\b",
        question_lower
    ):
        expansions.extend([
            "Minimum attendance requirements examination eligibility",
            "Attendance shortage and detention examination rules"
        ])

    return list(dict.fromkeys(expansions))
