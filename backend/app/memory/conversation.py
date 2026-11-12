
"""
CampusIQ — Short-term Conversation Context

Resolves common academic-calendar follow-up questions
using recent user messages.

No persistent student data is stored.
No Gemini API call is required.

Returns the original question when the context
cannot be resolved safely.
"""

import re


MAX_HISTORY_MESSAGES = 10
MAX_MESSAGE_LENGTH = 2000


def clean_history(history):
    """
    Accept a list of dictionaries:
      {"role": "user", "content": "..."}
      {"role": "assistant", "content": "..."}

    Ignore malformed or unexpected entries.
    """

    if not isinstance(history, list):
        return []

    cleaned = []

    for item in history[-MAX_HISTORY_MESSAGES:]:
        if not isinstance(item, dict):
            continue

        role = item.get("role")
        content = item.get("content")

        if role not in ("user", "assistant"):
            continue

        if not isinstance(content, str):
            continue

        content = content.strip()

        if not content:
            continue

        cleaned.append({
            "role": role,
            "content": content[:MAX_MESSAGE_LENGTH],
        })

    return cleaned


def get_last_user_question(history):
    """
    Find the most recent previous user message.
    """

    for item in reversed(clean_history(history)):
        if item["role"] == "user":
            return item["content"]

    return None


def detect_group(question):
    """
    Explicit exclusion has priority over
    the phrase 'first year'.
    """

    text = str(question or "").lower()

    if re.search(
        r"\b(?:except|excluding|other than)\s+"
        r"(?:the\s+)?first[\s-]*year\b"
        r"|\bnon[\s-]*first[\s-]*year\b",
        text,
    ):
        return "all except first year"

    if re.search(
        r"\b(?:second|third|fourth|fifth|final)"
        r"[\s-]*year\b"
        r"|\b(?:2nd|3rd|4th|5th)[\s-]*year\b",
        text,
    ):
        return "all except first year"

    if re.search(
        r"\bfirst[\s-]*year\b"
        r"|\b1st[\s-]*year\b"
        r"|\bfreshers?\b",
        text,
    ):
        return "first year"

    return None


def detect_semester(question):
    text = str(question or "").lower()

    if re.search(
        r"\b(?:semester|sem)\s*(?:ii|2|second)\b",
        text,
    ):
        return "Semester II"

    if re.search(
        r"\b(?:semester|sem)\s*(?:i|1|first)\b",
        text,
    ):
        return "Semester I"

    return None


def is_followup(question):
    """
    Conservative detection for short calendar
    follow-up questions.
    """

    text = str(question or "").strip().lower()

    if len(text) > 150:
        return False

    patterns = (
        r"\b(?:when|what date|which date)\s+"
        r"(?:does|did|will|is)\s+(?:it|that)\b",
        r"\bwhen\s+does\s+(?:the\s+)?"
        r"(?:semester|term)\s+end\b",
        r"\b(?:and|what about)\s+when\b",
        r"\b(?:when|what date)\s+(?:does\s+)?it\s+end\b",
        r"\b(?:and|what about)\s+"
        r"(?:the\s+)?(?:first|second|third|fourth)"
        r"[\s-]*year\b",
    )

    return any(
        re.search(pattern, text)
        for pattern in patterns
    )


def detect_requested_event(question):
    text = str(question or "").lower()

    if re.search(
        r"\b(?:end|ends|ending|finish|finishes|"
        r"last day|conclude|concludes)\b",
        text,
    ):
        return "end"

    if re.search(
        r"\b(?:begin|begins|start|starts|"
        r"commence|commencement)\b",
        text,
    ):
        return "start"

    return None


def resolve_followup(question, history):
    """
    Resolve calendar follow-up references.

    Example:
    Previous: When does Semester II begin for
              second-year students?
    Current:  And when does it end?

    Result:
    When does Semester II end for all except
    first year students?

    Does not resolve unrelated questions.
    """

    original = str(question or "").strip()

    if not original:
        return original

    if not is_followup(original):
        return original

    previous = get_last_user_question(history)

    if not previous:
        return original

    previous_semester = detect_semester(previous)
    previous_group = detect_group(previous)

    if not previous_semester:
        return original

    # Do not override explicitly stated details.
    current_semester = (
        detect_semester(original)
        or previous_semester
    )

    current_group = (
        detect_group(original)
        or previous_group
    )

    event = detect_requested_event(original)

    if not event:
        return original

    if not current_group:
        return original

    year_match = re.search(r"\b20\d{2}\s*[-?]\s*(?:20)?\d{2}\b", original + " " + previous)
    academic_year = year_match.group(0) if year_match else "2026-27"

    
    if event == "end":
        return (
            f"What is the date of the Last Instructional Day "
            f"for {current_semester}, for {current_group} "
            f"students, according to the MIT-WPU "
            f"academic calendar {academic_year}? "
            f"Use the Last Instructional Day event, "
            f"not the Attendance Locking date."
        )

    return (
        f"When does {current_semester} begin "
        f"for {current_group} students "
        f"in the MIT-WPU academic calendar {academic_year}?"
    )


