
"""
CampusIQ — Policy Conversation Follow-ups

Resolves short follow-up questions referring to
an earlier examination ordinance.

Examples:
Previous: What does the 2022 ordinance say
          about post-examination processing?

Current: Does it mention digital masking?

Resolved:
Under Examination Ordinance 2022, does the
ordinance mention digital masking?

This module does NOT produce factual answers.
It only rewrites sufficiently clear questions.
"""

import re

from app.memory.conversation import clean_history


ORDINANCE_CONTEXT = re.compile(
    r"\b(?:ordinance|examination regulation|"
    r"exam regulation|revaluation|re-evaluation|"
    r"retotaling|re-totaling|post-examination)\b",
    re.IGNORECASE,
)

ORDINANCE_YEAR = re.compile(
    r"\b(?:2017|2020|2022)\b"
)

FOLLOWUP_START = re.compile(
    r"^(?:and\s+|also\s+|what about\s+|"
    r"does it\b|does that\b|"
    r"what does it\b|what does that\b|"
    r"is it\b|can it\b|"
    r"how about\s+)",
    re.IGNORECASE,
)

FOLLOWUP_REFERENCES = re.compile(
    r"\b(?:it|its|that|this|"
    r"the same|the ordinance)\b",
    re.IGNORECASE,
)



def last_policy_question(history):
    """
    Use only the most recent previous user question.

    Prevents an old ordinance conversation from
    leaking into a newer, unrelated topic.

    Returns None when:
    - The latest user question is unrelated.
    - The ordinance year is missing.
    - Multiple ordinance years are mentioned.
    """

    cleaned = clean_history(history)

    latest_user_message = next(
        (
            item["content"]
            for item in reversed(cleaned)
            if item["role"] == "user"
        ),
        None,
    )

    if not latest_user_message:
        return None

    if not ORDINANCE_CONTEXT.search(
        latest_user_message
    ):
        return None

    years = set(
        ORDINANCE_YEAR.findall(
            latest_user_message
        )
    )

    if len(years) != 1:
        return None

    return {
        "question": latest_user_message,
        "year": years.pop(),
    }



def resolve_policy_followup(question, history):
    """
    Resolve short policy follow-ups when there
    is enough context.

    Return the original question if:
    - It is not a follow-up.
    - There is no clear previous ordinance.
    - It explicitly names another ordinance.
    - The intent or reference is ambiguous.
    """

    original = str(question or "").strip()

    if not original:
        return original

    if len(original) > 180:
        return original

    if re.search(r"\b(?:calendar|semester|hostel|fees?|scholarships?)\b", original, re.I):
        return original

    context = last_policy_question(history)

    if context is None:
        return original

    # Do not override an explicitly named
    # ordinance year in the new question.
    current_years = set(
        ORDINANCE_YEAR.findall(original)
    )

    if current_years:
        return original

    starts_as_followup = bool(
        FOLLOWUP_START.search(original)
    )

    references_previous = bool(
        FOLLOWUP_REFERENCES.search(original)
    )

    if not (
        starts_as_followup
        or references_previous
    ):
        return original

    year = context["year"]

    # Replace simple standalone pronouns to
    # make document identity explicit.
    rewritten = re.sub(
        r"\b(?:it|its|that|this)\b",
        "the ordinance",
        original,
        flags=re.IGNORECASE,
    )

    return (
        f"Under Examination Ordinance {year}, "
        f"{rewritten}"
    )
