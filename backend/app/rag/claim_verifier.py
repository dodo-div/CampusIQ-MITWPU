
"""
CampusIQ — Claim-Level Evidence Auditor v2

Improvements:
- Recognizes re-evaluation across broken lines
- Ignores source references and introductory headings
- Matches claims against local evidence passages
- Requires numeric facts to match
- Reports lexical support, not factual entailment

Non-blocking: does not modify the Gemini answer.
"""

import re


SOURCE_HEADER = re.compile(
    r"(?im)^\s*\[Source:\s*([^,\]\r\n]+),"
    r"\s*Page:\s*(\d+)\s*\]\s*$"
)

UNCERTAIN = re.compile(
    r"could not be verified|cannot be verified|"
    r"couldn't find|not available|"
    r"no relevant evidence|insufficient information|"
    r"unable to confirm|does not specify|"
    r"does not establish|has not been verified",
    re.IGNORECASE,
)

SOURCE_LINE = re.compile(
    r"(?i)^\s*[\s*()]*"
    r"Source:\s*[A-Za-z0-9_.-]+\.txt"
    r"\s*,\s*Page\s*:?\s*\d+"
    r"[\s*()]*$"
)

RISK_TERMS = re.compile(
    r"\bdeadline\b|\bwithin\b|\bfees?\b|"
    r"\bpercent(?:age)?\b|\bguarantee[ds]?\b|"
    r"\bmandatory\b|\bminimum\b|\bmaximum\b|"
    r"\b(?:days?|weeks?|months?)\b",
    re.IGNORECASE,
)

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were",
    "be", "been", "being", "of", "in", "on", "at",
    "to", "for", "from", "by", "with", "and",
    "or", "as", "it", "its", "this", "that",
    "these", "those", "which", "what", "when",
    "where", "who", "how", "under", "according",
    "based", "students", "student", "university",
    "document", "documents", "page", "source",
    "information", "provided", "available","additionally",
    "also",
    "furthermore",
    "moreover",
    "ordinance",
    "notes",
    "states",
    "mentions",
    "specifies",
    "indicates",
    "during",
    "activities",
}

MONTHS = {
    "january": "jan",
    "february": "feb",
    "march": "mar",
    "april": "apr",
    "june": "jun",
    "july": "jul",
    "august": "aug",
    "september": "sep",
    "october": "oct",
    "november": "nov",
    "december": "dec",
}


NUMBER_WORDS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
    "eleven": "11",
    "twelve": "12",
    "thirteen": "13",
    "fourteen": "14",
    "fifteen": "15",
    "sixteen": "16",
    "seventeen": "17",
    "eighteen": "18",
    "nineteen": "19",
    "twenty": "20",
    "thirty": "30",
}

NUMBER_PATTERN = re.compile(
    r"\b(" +
    "|".join(
        sorted(NUMBER_WORDS, key=len, reverse=True)
    ) +
    r")\b",
    re.IGNORECASE,
)


def normalize_number_words(text):
    """
    Normalize simple English number words.

    Examples:
      five days -> 5 days
      seven days -> 7 days
      twenty five days -> 25 days
    """

    text = NUMBER_PATTERN.sub(
        lambda match: NUMBER_WORDS[
            match.group(1).lower()
        ],
        text,
    )

    # Combine simple compound numbers:
    # twenty-five -> 25
    # twenty five -> 25
    # thirty two -> 32
    def combine(match):
        tens = int(match.group(1))
        units = int(match.group(2))
        return str(tens + units)

    text = re.sub(
        r"\b(20|30)[ -]([1-9])\b",
        combine,
        text,
    )

    return text



def normalize(value):
    text = str(value or "").lower()
    text = normalize_number_words(text)

    # Handle different document extraction formats:
    # re-evaluation
    # re- evaluation
    # re-\nevaluation
    # revaluation
    text = re.sub(
        r"\bre\s*[-–]\s*evaluation\b",
        "reevaluation",
        text,
    )

    text = re.sub(
        r"\brevaluation\b",
        "reevaluation",
        text,
    )

    text = re.sub(
        r"\bre\s*[-–]\s*totaling\b",
        "retotaling",
        text,
    )

    text = re.sub(
        r"(\d+)(?:st|nd|rd|th)\b",
        r"\1",
        text,
    )

    text = re.sub(
        r"(\d{1,2})(jan|feb|mar|apr|may|jun|jul|"
        r"aug|sep|oct|nov|dec)",
        r"\1 \2",
        text,
    )

    for full, short in MONTHS.items():
        text = re.sub(
            rf"\b{full}\b",
            short,
            text,
        )

    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokens(value):
    words = re.findall(
        r"[a-z0-9]+",
        normalize(value),
    )

    return {
        word
        for word in words
        if len(word) >= 2
        and word not in STOPWORDS
    }


def numeric_facts(value):
    return set(
        re.findall(
            r"\b\d+(?:\.\d+)?\b",
            normalize(value),
        )
    )


def get_evidence_blocks(context):
    if not isinstance(context, str):
        return []

    markers = list(SOURCE_HEADER.finditer(context))
    blocks = []

    for index, marker in enumerate(markers):
        end = (
            markers[index + 1].start()
            if index + 1 < len(markers)
            else len(context)
        )

        passage = context[
            marker.end():end
        ].strip()

        if passage:
            blocks.append({
                "document": marker.group(1).strip(),
                "page": int(marker.group(2)),
                "text": passage,
            })

    return blocks



def extract_claims(answer):
    """
    Extract factual statements while removing
    Markdown formatting and source citations.
    """

    if not isinstance(answer, str):
        return []

    claims = []

    # Remove inline RAG source markers before
    # extracting facts or numerical values.
    #
    # Example:
    # [Source: Examination-Ordinance-2022.txt, Page: 12]

    answer = re.sub(
        r"\[\s*Source:\s*"
        r"[A-Za-z0-9_.-]+\.txt"
        r"\s*,\s*Page\s*:?\s*\d+\s*\]",
        "",
        answer,
        flags=re.IGNORECASE,
    )

    # Remove parenthesized textual citations.
    answer = re.sub(
        r"\(\s*\*?(?:Source:\s*)?"
        r"[A-Za-z0-9_.-]+\.txt"
        r"\*?\s*,\s*Page\s*:?\s*\d+"
        r"\*?\s*\)",
        "",
        answer,
        flags=re.IGNORECASE,
    )

    for raw_line in answer.splitlines():

        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        line = re.sub(
            r"^[*\-•]\s+",
            "",
            line,
        )

        line = line.replace("**", "").strip()

        if SOURCE_LINE.fullmatch(line):
            continue

        if line.lower().startswith(
            ("important:", "note:", "source:")
        ):
            continue

        if line.endswith(":"):
            continue

        for part in re.split(
            r"(?<=[.!?])\s+",
            line,
        ):
            part = part.strip()

            if not part:
                continue

            if UNCERTAIN.search(part):
                continue

            if len(part) < 5:
                continue

            if not tokens(part):
                continue

            claims.append(part)

    return claims[:30]



def evidence_windows(text, window=45, stride=15):
    words = str(text or "").split()

    if not words:
        return []

    if len(words) <= window:
        return [" ".join(words)]

    results = []

    for start in range(0, len(words), stride):
        chunk = words[start:start + window]

        if not chunk:
            break

        results.append(" ".join(chunk))

        if start + window >= len(words):
            break

    return results

NEGATION_PATTERN = re.compile(
    r"\b(?:not|never|no|without|cannot|"
    r"can't|won't|isn't|doesn't|don't|"
    r"didn't|wasn't|weren't|mustn't)\b",
    re.IGNORECASE,
)


def has_negation(text):
    return bool(
        NEGATION_PATTERN.search(
            normalize(text)
        )
    )


def closest_evidence_sentence(claim, excerpt):
    """
    Find the most lexically relevant local
    sentence for a basic polarity comparison.
    """

    sentences = re.split(
        r"(?<=[.!?;])\s+",
        str(excerpt or ""),
    )

    claim_words = tokens(claim) - {
        "not", "never", "no", "without",
        "cannot",
    }

    if not sentences:
        return excerpt

    return max(
        sentences,
        key=lambda sentence: len(
            claim_words & tokens(sentence)
        ),
    )



def check_claim(claim, evidence_blocks):
    claim_tokens = tokens(claim)
    claim_numbers = numeric_facts(claim)

    best_score = 0.0
    best_source = None
    best_excerpt = None

    for block in evidence_blocks:
        for excerpt in evidence_windows(block["text"]):
            excerpt_tokens = tokens(excerpt)
            excerpt_numbers = numeric_facts(excerpt)

            if not claim_numbers.issubset(
                excerpt_numbers
            ):
                continue

            overlap = len(
                claim_tokens & excerpt_tokens
            )

            score = (
                overlap / len(claim_tokens)
                if claim_tokens
                else 0.0
            )

            if score > best_score:
                best_score = score
                best_excerpt = excerpt

                best_source = {
                    "document": block["document"],
                    "page": block["page"],
                    "excerpt": excerpt[:350],
                }

    reason = None

    if best_excerpt and best_score >= 0.40:
        matching_sentence = closest_evidence_sentence(
            claim,
            best_excerpt,
        )

        if has_negation(claim) != has_negation(
            matching_sentence
        ):
            status = "unverified"
            reason = "possible_negation_conflict"

        elif best_score >= 0.75:
            status = "candidate_supported"

        else:
            status = "partial_match"

    else:
        status = "unverified"
        reason = "insufficient_evidence_match"

    return {
        "claim": claim,
        "status": status,
        "match_score": round(best_score, 3),
        "high_risk": bool(
            RISK_TERMS.search(claim)
        ),
        "reason": reason,
        "evidence": best_source,
    }



def audit_answer_claims(answer, context):
    claims = extract_claims(answer)
    blocks = get_evidence_blocks(context)

    if not claims:
        return {
            "status": "not_applicable",
            "claims_checked": 0,
            "candidate_supported": 0,
            "partial_matches": 0,
            "unverified": 0,
            "claims": [],
        }

    results = [
        check_claim(claim, blocks)
        for claim in claims
    ]

    supported = sum(
        item["status"] == "candidate_supported"
        for item in results
    )

    partial = sum(
        item["status"] == "partial_match"
        for item in results
    )

    unverified = sum(
        item["status"] == "unverified"
        for item in results
    )

    if unverified:
        status = "review_required"
    elif partial:
        status = "partial_evidence"
    else:
        status = "candidate_supported"

    return {
        "status": status,
        "claims_checked": len(results),
        "candidate_supported": supported,
        "partial_matches": partial,
        "unverified": unverified,
        "claims": results,
    }
