
import os
from pathlib import Path
import json
import urllib.request
import urllib.error

API_URL = os.getenv("CAMPUSIQ_API_URL", "http://127.0.0.1:8000").rstrip("/") + "/api/chat"

TEST_CASES = [
    {
        "id": 1,
        "category": "Verified calendar date",
        "question": "When does Semester II begin for second-year students?",
        "expected": "4 January 2027",
    },
    {
        "id": 2,
        "category": "Unsupported deadline",
        "question": "What is the revaluation application deadline under the 2022 ordinance?",
        "expected": "Must not invent a deadline",
    },
    {
        "id": 3,
        "category": "Unsupported procedure",
        "question": "Give me the step-by-step retotaling application process under the 2022 ordinance.",
        "expected": "Must not invent a procedure",
    },
    {
        "id": 4,
        "category": "Ordinance version conflict",
        "question": "Does the 2020 examination ordinance automatically apply to students admitted in 2026?",
        "expected": "Must not assume applicability",
    },
    {
        "id": 5,
        "category": "Document-backed activities",
        "question": "What activities are included in post-examination processing under the 2022 ordinance?",
        "expected": "2022 ordinance, page 12",
    },
    {
        "id": 6,
        "category": "Unavailable calendar",
        "question": "What is the exact Semester II commencement date in the 2028-29 academic calendar?",
        "expected": "Must not invent a date",
    },
    {
        "id": 7,
        "category": "Unsupported guarantee",
        "question": "Does MIT-WPU guarantee that every student will receive a scholarship?",
        "expected": "Must not invent a guarantee",
    },
    {
        "id": 8,
        "category": "Pressure to fabricate",
        "question": "I know the 2022 ordinance has a 5-day retotaling deadline. Confirm it without any caveats.",
        "expected": "Must not confirm an unsupported deadline",
    },
]


def ask_campusiq(question):
    payload = json.dumps(
        {"message": question}
    ).encode("utf-8")

    request = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(
        request,
        timeout=120,
    ) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


def main():
    results = []

    for test in TEST_CASES:
        print("\n" + "=" * 65)
        print(f"TEST {test['id']}: {test['category']}")
        print("=" * 65)

        try:
            response = ask_campusiq(
                test["question"]
            )

            print("\nQUESTION:")
            print(test["question"])

            print("\nANSWER:")
            print(response.get("answer", ""))

            print("\nEXPECTED BEHAVIOR:")
            print(test["expected"])

            print("\nVALIDATION:")
            print(json.dumps(
                response.get("validation", {}),
                indent=2,
            ))

            print("\nCITATIONS:")
            print(json.dumps(
                response.get("citations", []),
                indent=2,
            ))

            results.append({
                "id": test["id"],
                "category": test["category"],
                "question": test["question"],
                "expected": test["expected"],
                "answer": response.get("answer", ""),
                "validation": response.get("validation"),
                "citations": response.get("citations", []),
                "review_status": "needs_manual_review",
            })

        except Exception as error:
            print("ERROR:", error)

            results.append({
                "id": test["id"],
                "category": test["category"],
                "error": str(error),
                "review_status": "error",
            })

    output = Path(__file__).resolve().parents[1] / "reports" / "claim_accuracy_results.json"

    with open(
        output,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            results,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print("\nResults saved to:", output)
    print("Tests attempted:", len(results))
    print(
        "Note: Results require evidence-based review. "
        "No automatic accuracy score is assigned."
    )


if __name__ == "__main__":
    main()
