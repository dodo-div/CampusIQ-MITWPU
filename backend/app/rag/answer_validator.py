
import re
from datetime import date

from app.rag.retriever import (
    detect_semester,
    detect_student_group,
    detect_calendar_event,
    is_calendar_question
)

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3,
    "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9,
    "oct": 10, "nov": 11, "dec": 12
}

MONTH_PATTERN = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|"
    r"Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t(?:ember)?)?|"
    r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)

DAY_FIRST = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?"
    rf"[\s\-/]+({MONTH_PATTERN})"
    rf"[\s,\-/]+(\d{{2}}|\d{{4}})\b",
    re.IGNORECASE
)

MONTH_FIRST = re.compile(
    rf"\b({MONTH_PATTERN})\s+"
    rf"(\d{{1,2}})(?:st|nd|rd|th)?"
    rf",?\s+(\d{{4}})\b",
    re.IGNORECASE
)

ISO_DATE = re.compile(
    r"\b(20\d{2})-(\d{2})-(\d{2})\b"
)


def make_date(day, month, year):
    try:
        year = int(year)

        if year < 100:
            year += 2000

        return date(
            year,
            MONTHS[month[:3].lower()],
            int(day)
        )
    except (ValueError, KeyError):
        return None


def extract_dates(text):
    """Extract complete dates in supported formats."""
    dates = set()

    for match in DAY_FIRST.finditer(text):
        parsed = make_date(*match.groups())

        if parsed:
            dates.add(parsed)

    for match in MONTH_FIRST.finditer(text):
        month, day, year = match.groups()
        parsed = make_date(day, month, year)

        if parsed:
            dates.add(parsed)

    for match in ISO_DATE.finditer(text):
        year, month, day = map(int, match.groups())

        try:
            dates.add(date(year, month, day))
        except ValueError:
            pass

    return dates


def get_field(text, field):
    """Read one structured calendar field."""
    match = re.search(
        rf"^{re.escape(field)}:\s*(.*)$",
        text,
        re.MULTILINE | re.IGNORECASE
    )

    return match.group(1).strip() if match else ""


def parse_calendar_records(context):
    """
    Extract indexed calendar event records
    from the retrieved RAG context.
    """
    records = []

    parts = re.split(
        r"(?=\[Source:\s*[^]]+\])",
        context
    )

    for part in parts:
        event = get_field(part, "Event")
        semester = get_field(part, "Semester")
        group = get_field(part, "Student category")
        date_text = get_field(part, "Date")

        if not all([event, semester, group, date_text]):
            continue

        if "except first year" in group.lower():
            student_group = "other_years"
        elif "first year" in group.lower():
            student_group = "first_year"
        else:
            student_group = "unknown"

        records.append({
            "event": event.lower(),
            "semester": semester.upper(),
            "student_group": student_group,
            "dates": extract_dates(date_text),
            "date_text": date_text,
            "source": get_field(part, "Source")
        })

    return records


def matching_calendar_dates(question, context):
    """
    Collect dates only from records matching
    the requested semester, student group,
    and academic event.
    """
    semester = detect_semester(question)
    student_group = detect_student_group(question)
    event_type = detect_calendar_event(question)

    if not event_type:
        return None

    records = parse_calendar_records(context)
    matched_dates = set()

    for record in records:
        if semester and record["semester"] != semester:
            continue

        if (
            student_group
            and record["student_group"] != student_group
        ):
            continue

        if event_type == "vacation":
            event_matches = "vacation" in record["event"]
        else:
            event_matches = event_type in record["event"]

        if not event_matches:
            continue

        matched_dates.update(record["dates"])

    return matched_dates


def validate_answer_dates(
    answer: str,
    context: str,
    question: str = ""
):
    """
    Validate complete dates against evidence.

    For recognized calendar questions:
      Check dates against matching event records.

    For other questions:
      Check whether dates appear in the
      retrieved evidence.

    Does not verify non-date claims.
    """
    answer_dates = extract_dates(answer)

    if not answer_dates:
        return {
            "status": "not_checked",
            "valid": None,
            "reason": "No complete dates found in answer.",
            "unsupported_dates": []
        }

    event_dates = None

    if question and is_calendar_question(question):
        event_dates = matching_calendar_dates(
            question,
            context
        )

    if event_dates is not None:
        evidence_dates = event_dates
        check_type = "calendar_event"
    else:
        evidence_dates = extract_dates(context)
        check_type = "date_presence"

    unsupported = answer_dates - evidence_dates

    if unsupported:
        return {
            "status": "unsupported",
            "valid": False,
            "reason": (
                "One or more answer dates are not "
                "supported by the matching evidence."
            ),
            "unsupported_dates": sorted(
                item.isoformat()
                for item in unsupported
            ),
            "check_type": check_type
        }

    return {
        "status": "verified",
        "valid": True,
        "reason": (
            "All complete answer dates match "
            "the selected evidence."
        ),
        "unsupported_dates": [],
        "check_type": check_type
    }


def exact_calendar_answer(question, context):
    """Answer a single structured event only when all qualifiers are explicit."""
    if not is_calendar_question(question):
        return None
    semester = detect_semester(question)
    group = detect_student_group(question)
    event = detect_calendar_event(question)
    if event not in {"commencement of term", "last instructional day"}:
        return None
    if not semester or not group:
        return None
    records = [r for r in parse_calendar_records(context)
               if r["semester"] == semester and r["student_group"] == group
               and r["event"] == event]
    dates = {d for r in records for d in r["dates"]}
    if not records or any(len(r["dates"]) != 1 for r in records) or len(dates) != 1:
        return None
    day = next(iter(dates))
    category = "first-year students" if group == "first_year" else "all students except first-year students"
    label = "commencement of term" if event == "commencement of term" else "last instructional day"
    return (f"The {label} for Semester {semester}, for {category}, "
            f"is {day.day} {day.strftime('%B %Y')}.")
