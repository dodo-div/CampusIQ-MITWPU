
"""
CampusIQ — Conversation Isolation Tests

Tests:
1. Calendar follow-up
2. Ordinance follow-up
3. Topic switching
4. Explicit ordinance version switching
5. Ambiguous ordinance versions
6. Empty history
7. Previous unrelated question
8. Multiple independent conversations

No Gemini API requests.
"""

import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

from app.memory.conversation import resolve_followup
from app.memory.policy_followup import resolve_policy_followup


def resolve(question, history):
    calendar_result = resolve_followup(
        question=question,
        history=history,
    )

    if calendar_result != question:
        return calendar_result

    return resolve_policy_followup(
        question=question,
        history=history,
    )


def user(content):
    return {
        "role": "user",
        "content": content,
    }


def assistant(content):
    return {
        "role": "assistant",
        "content": content,
    }


def run(name, question, history, expected, unchanged=False):
    result = resolve(question, history)

    if unchanged:
        passed = result == question
    else:
        passed = expected.lower() in result.lower()

    print(
        f"{'PASS' if passed else 'FAIL'} | {name}"
    )

    print("  Input:", question)
    print("  Resolved:", result)

    if not passed:
        raise AssertionError(
            f"{name}: unexpected resolution"
        )


def main():

    # TEST 1 — Calendar follow-up
    run(
        "Calendar memory",
        "And when does it end?",
        [
            user(
                "When does Semester II begin "
                "for second-year students?"
            ),
            assistant("4 January 2027."),
        ],
        "Last Instructional Day",
    )

    # TEST 2 — Ordinance follow-up
    run(
        "Ordinance memory",
        "Does it mention digital masking?",
        [
            user(
                "What does the 2022 ordinance say "
                "about post-examination processing?"
            ),
            assistant("Post-examination activities."),
        ],
        "Examination Ordinance 2022",
    )

    # TEST 3 — Topic switch
    # Old ordinance context must NOT be reused.
    run(
        "Ordinance to calendar topic switch",
        "Does it mention digital masking?",
        [
            user(
                "What does the 2022 ordinance say "
                "about post-examination processing?"
            ),
            assistant("Post-examination activities."),
            user(
                "When does Semester II begin "
                "for second-year students?"
            ),
            assistant("4 January 2027."),
        ],
        "",
        unchanged=True,
    )

    # TEST 4 — Explicitly switch versions
    run(
        "Explicit ordinance switch",
        "What does the 2020 ordinance say?",
        [
            user(
                "Explain the 2022 examination ordinance."
            ),
            assistant("2022 ordinance summary."),
        ],
        "",
        unchanged=True,
    )

    # TEST 5 — Multiple possible versions
    run(
        "Ambiguous ordinance context",
        "Does it mention digital masking?",
        [
            user(
                "Compare the 2020 and 2022 ordinances."
            ),
            assistant("Comparison."),
        ],
        "",
        unchanged=True,
    )

    # TEST 6 — Empty conversation
    run(
        "No previous history",
        "And when does it end?",
        [],
        "",
        unchanged=True,
    )

    # TEST 7 — Unrelated latest question
    run(
        "Old ordinance must not leak",
        "Does it mention digital masking?",
        [
            user(
                "Explain the 2022 ordinance."
            ),
            assistant("Ordinance summary."),
            user(
                "What is the academic calendar?"
            ),
            assistant("Academic calendar overview."),
        ],
        "",
        unchanged=True,
    )

    # TEST 8 — Independent conversations
    history_a = [
        user(
            "When does Semester II begin "
            "for first-year students?"
        )
    ]

    history_b = [
        user(
            "When does Semester II begin "
            "for third-year students?"
        )
    ]

    result_a = resolve(
        "And when does it end?",
        history_a,
    )

    result_b = resolve(
        "And when does it end?",
        history_b,
    )

    passed = (
        "for first year students" in result_a.lower()
        and "for all except first year students"
        in result_b.lower()
        and result_a != result_b
    )

    print(
        f"{'PASS' if passed else 'FAIL'}"
        " | Independent conversation isolation"
    )

    if not passed:
        print("Conversation A:", result_a)
        print("Conversation B:", result_b)
        raise AssertionError(
            "Independent conversation isolation failed"
        )

    print("\nALL 8 CONVERSATION ISOLATION TESTS PASSED")


if __name__ == "__main__":
    main()
