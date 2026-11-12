
"""
CampusIQ — Real Document Evidence Regression Tests

Uses previously verified excerpts from:
- Academic Calendar 2026-27, page 2
- Examination Ordinance 2022, page 12

Tests claim auditing without Gemini calls.

Run from backend:
.\.venv\Scripts\python.exe ..\scripts\test_real_evidence.py
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.rag.claim_verifier import audit_answer_claims


# Source excerpts verified during CampusIQ development.
# These are fixtures, not a new live document extraction.

CALENDAR_EVIDENCE = """
[Source: Academic-Calendar-2026-27.txt, Page: 2]
Semester II commencement: 4th Jan 2027
"""

ORDINANCE_EVIDENCE = """
[Source: Examination-Ordinance-2022.txt, Page: 12]
7.6.3 Post-examinations
It includes CAP-assessment and moderation,
result processing and declaration, re- evaluation,
issuing documents, Convocation, etc.
The answer sheets will be digitally masked.
"""


TESTS = [
    {
        "name": "Correct academic date",
        "claim": "Semester II commencement: 4 January 2027.",
        "context": CALENDAR_EVIDENCE,
        "expected": "candidate_supported",
    },
    {
        "name": "Incorrect academic date",
        "claim": "Semester II commencement: 5 January 2027.",
        "context": CALENDAR_EVIDENCE,
        "expected": "unverified",
    },
    {
        "name": "Correct post-examination activity",
        "claim": "CAP-assessment and moderation",
        "context": ORDINANCE_EVIDENCE,
        "expected": "candidate_supported",
    },
    {
        "name": "Correct re-evaluation reference",
        "claim": "Re-evaluation",
        "context": ORDINANCE_EVIDENCE,
        "expected": "candidate_supported",
    },
    {
        "name": "Invented five-day deadline",
        "claim": "Revaluation applications close within 5 days.",
        "context": ORDINANCE_EVIDENCE,
        "expected": "unverified",
    },
    {
        "name": "Correct digital masking",
        "claim": "The answer sheets will be digitally masked.",
        "context": ORDINANCE_EVIDENCE,
        "expected": "candidate_supported",
    },
    {
        "name": "Contradictory digital masking",
        "claim": "The answer sheets will not be digitally masked.",
        "context": ORDINANCE_EVIDENCE,
        "expected": "unverified",
    },
]


def run_test(test):
    result = audit_answer_claims(
        test["claim"],
        test["context"],
    )

    claims = result.get("claims", [])

    if len(claims) != 1:
        print("FAIL:", test["name"])
        print("Unexpected extracted claims:", claims)
        return False

    actual = claims[0]["status"]
    expected = test["expected"]

    passed = actual == expected

    print(
        f"{'PASS' if passed else 'FAIL'} "
        f"| {test['name']}"
    )

    print(
        f"  Expected: {expected}"
        f" | Actual: {actual}"
        f" | Score: {claims[0]['match_score']}"
    )

    if claims[0].get("reason"):
        print("  Reason:", claims[0]["reason"])

    return passed


def main():
    passed = 0

    for test in TESTS:
        if run_test(test):
            passed += 1

    total = len(TESTS)

    print("\n==========================")
    print(f"RESULT: {passed}/{total} PASSED")
    print("==========================")

    if passed != total:
        sys.exit(1)

    print("ALL REAL-EVIDENCE TESTS PASSED")


if __name__ == "__main__":
    main()
