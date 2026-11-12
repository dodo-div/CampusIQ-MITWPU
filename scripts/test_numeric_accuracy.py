
"""
CampusIQ numerical claim verification tests.

Run from backend:
python ../scripts/test_numeric_accuracy.py
"""

from pathlib import Path
import sys

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.rag.claim_verifier import (
    audit_answer_claims,
    normalize,
)


def check(name, claim, evidence, expected):
    context = (
        "[Source: Test-Policy.txt, Page: 1]\n"
        + evidence
    )

    report = audit_answer_claims(claim, context)

    if not report["claims"]:
        raise AssertionError(
            f"{name}: no claim was extracted"
        )

    actual = report["claims"][0]["status"]

    passed = actual == expected

    print(
        f"{'PASS' if passed else 'FAIL'} "
        f"| {name}"
        f" | expected={expected}"
        f" | actual={actual}"
    )

    if not passed:
        raise AssertionError(name)


def main():

    assert normalize("five days") == "5 days"
    assert normalize("twenty-five days") == "25 days"

    tests = [
        (
            "Matching numerical deadline",
            "Applications close within 5 days.",
            "Applications close within 5 days.",
            "candidate_supported",
        ),
        (
            "Different numerical deadline",
            "Applications close within 7 days.",
            "Applications close within 5 days.",
            "unverified",
        ),
        (
            "Matching number words",
            "Applications close within five days.",
            "Applications close within 5 days.",
            "candidate_supported",
        ),
        (
            "Conflicting number words",
            "Applications close within seven days.",
            "Applications close within five days.",
            "unverified",
        ),
        (
            "Conflicting calendar date",
            "Semester II begins on 5 January 2027.",
            "Semester II begins on 4 January 2027.",
            "unverified",
        ),
        (
            "Matching calendar date",
            "Semester II begins on 4 January 2027.",
            "Semester II begins on 4 January 2027.",
            "candidate_supported",
        ),
        (
            "Conflicting percentage",
            "The minimum attendance is 80 percent.",
            "The minimum attendance is 75 percent.",
            "unverified",
        ),
        (
            "Matching percentage",
            "The minimum attendance is 75 percent.",
            "The minimum attendance is 75 percent.",
            "candidate_supported",
        ),
    ]

    for test in tests:
        check(*test)

    print("\nALL 8 NUMERICAL TESTS PASSED")


if __name__ == "__main__":
    main()
