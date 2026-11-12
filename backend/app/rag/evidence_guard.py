
import re


# --------------------------------------------------
# Topic definitions
# --------------------------------------------------

TOPIC_PATTERNS = {
    "revaluation": [
        r"\bre[\s-]*evaluation\b",
        r"\brevaluation\b",
        r"\breassessment\b",
    ],
    "retotaling": [
        r"\bre[\s-]*total(?:ing|ling)?\b",
        r"\bretotal(?:ing|ling)?\b",
        r"\brechecking\b",
    ],
    "result_declaration": [
        r"\bresult[s]?\s+declaration\b",
        r"\bdeclaration\s+of\s+result[s]?\b",
        r"\bdeclaring\s+(?:the\s+)?result[s]?\b",
        r"\bpreparation\s+and\s+declaration\s+of\s+result",
    ],
    "digital_masking": [
        r"\bdigital(?:ly)?\s+mask(?:ed|ing)\b",
        r"\bmask(?:ed|ing)\s+answer\s+sheets?\b",
    ],
    "post_examination": [
        r"\bpost[\s-]*examinations?\b",
        r"\bpost[\s-]*exam\b",
        r"\bCAP[\s-]*assessment\b",
        r"\bmoderation\b",
    ],
    "backlog": [
        r"\bbacklogs?\b",
        r"\bATKT\b",
        r"\bfailed\s+(?:courses?|subjects?)\b",
    ],
}


# --------------------------------------------------
# Topic detection
# --------------------------------------------------

def detect_topic(question):
    """
    Identify the primary ordinance topic.

    More specific subjects are checked before
    broader examination terminology.
    """

    text = str(question or "").casefold()

    priority = [
        "digital_masking",
        "retotaling",
        "revaluation",
        "result_declaration",
        "backlog",
        "post_examination",
    ]

    for topic in priority:
        patterns = TOPIC_PATTERNS[topic]

        if any(
            re.search(pattern, text, re.IGNORECASE)
            for pattern in patterns
        ):
            return topic

    return None


# --------------------------------------------------
# Evidence filtering
# --------------------------------------------------

def evidence_matches_topic(question, text):
    """
    Check whether a passage discusses the topic.

    This is a lexical relevance check only;
    it does NOT prove that the passage supports
    every claim in a generated answer.
    """

    passage = re.sub(
        r"\s+",
        " ",
        str(text or ""),
    ).strip()

    if not passage:
        return False

    # Reject ordinance cover/title-only chunks.
    title_only = re.fullmatch(
        r"(?:\[Page\s+\d+\]\s*)?"
        r"(?:Page\s+\d+\s+of\s+\d+\s*)?"
        r"Examination\s+Ordinances?"
        r"(?:\s+\d{4})?",
        passage,
        flags=re.IGNORECASE,
    )

    if title_only:
        return False

    topic = detect_topic(question)

    # For questions without a recognized topic,
    # leave semantic relevance decisions to the
    # retriever instead of falsely rejecting them.
    if topic is None:
        return True

    return any(
        re.search(
            pattern,
            passage,
            flags=re.IGNORECASE,
        )
        for pattern in TOPIC_PATTERNS[topic]
    )
