
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.retriever import retrieve_context


TEST_CASES = [
    {
        "question": "When does Semester II start for second-year students?",
        "expected_source": "Academic-Calendar-2026-27.txt",
        "expected_text": "4",
    },
    {
        "question": "When does Semester I start for third-year students?",
        "expected_source": "Academic-Calendar-2026-27.txt",
        "expected_text": None,
    },
    {
        "question": "What are the rules for revaluation?",
        "expected_source": "Examination",
        "expected_text": None,
    },
    {
        "question": "What are the backlog rules?",
        "expected_source": "Examination",
        "expected_text": None,
    },
]


def main():
    passed = 0

    for index, test in enumerate(TEST_CASES, 1):
        question = test["question"]

        context, sources = retrieve_context(
            question,
            top_k=3
        )

        source_match = any(
            test["expected_source"].lower() in source.lower()
            for source in sources
        )

        text_match = (
            test["expected_text"] is None
            or test["expected_text"] in context
        )

        success = bool(context) and source_match and text_match

        if success:
            passed += 1

        print(f"\nTest {index}: {'PASS' if success else 'FAIL'}")
        print("Question:", question)
        print("Sources:", sources)
        print("Context found:", bool(context))

    print(f"\nIntegration tests: {passed}/{len(TEST_CASES)} passed")


if __name__ == "__main__":
    main()
