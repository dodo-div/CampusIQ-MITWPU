
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.citation_focus import (
    select_answer_citations,
)
from app.rag.claim_verifier import (
    audit_answer_claims,
)

DOC = "Examination-Ordinance-2022.txt"

citations = [
    {"document": DOC, "page": 3},
    {"document": DOC, "page": 12},
    {"document": DOC, "page": 12},
]

evidence = (
    f"[Source: {DOC}, Page: 12]\n"
    "8.1 Result Declaration\n"
    "Verification and confirmation of all the "
    "pre-requisites required for declaring the result.\n"
    "Preparation and declaration of result "
    "including Gracing, Grading, CGPA and "
    "displaying result at student's login.\n"
)

tests = [
    {
        "name": "Explicit page selection",
        "answer": (
            "Results are declared after verification "
            f"[Source: {DOC}, Page: 12]."
        ),
        "expected_pages": [12],
    },
    {
        "name": "Duplicate citation removal",
        "answer": "The ordinance discusses result declaration.",
        "expected_pages": [3, 12],
    },
    {
        "name": "Unsupported answer",
        "answer": (
            "I cannot confirm the requested "
            "information from the available evidence."
        ),
        "expected_pages": [],
    },
]

print("\n=== CITATION FILTER TESTS ===")

for test in tests:
    selected = select_answer_citations(
        answer=test["answer"],
        citations=citations,
        question=(
            "What does the 2022 ordinance say "
            "about result declaration?"
        ),
    )

    pages = [c["page"] for c in selected]
    passed = pages == test["expected_pages"]

    print(
        f"{'PASS' if passed else 'FAIL'} "
        f"| {test['name']} | pages={pages}"
    )

    assert passed, test["name"]


print("\n=== CLAIM AUDITOR TEST ===")

answer = (
    "The ordinance includes verification "
    "and confirmation of prerequisites "
    "before declaring results."
)

audit = audit_answer_claims(
    answer=answer,
    context=evidence,
)

print("Status:", audit["status"])
print("Claims checked:", audit["claims_checked"])
print("Unverified:", audit["unverified"])

assert audit["claims_checked"] >= 1

print("\nALL BASELINE TESTS PASSED")

