
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.retriever import (
    is_calendar_question,
    detect_semester,
    detect_student_group,
    detect_calendar_event
)

TESTS = [
    ("When does Semester II start for second-year students?",
     True, "II", "other_years", "commencement of term"),

    ("When are Semester I exams for first-year students?",
     True, "I", "first_year", "exam"),

    ("When does Semester I start for third-year students?",
     True, "I", "other_years", "commencement of term"),

    ("What are the rules for revaluation?",
     False, None, None, None),

    ("What is the MIT-WPU hostel fee?",
     False, None, None, None),

    ("What are the backlog rules?",
     False, None, None, None),

    ("When does Semester II start?",
     True, "II", None, "commencement of term"),

    ("When are my exams?",
     True, None, None, "exam")
]

passed = 0

for index, test in enumerate(TESTS, 1):
    question, calendar, semester, group, event = test

    actual = (
        is_calendar_question(question),
        detect_semester(question),
        detect_student_group(question),
        detect_calendar_event(question)
    )

    expected = (calendar, semester, group, event)

    success = actual == expected
    passed += int(success)

    print(
        f"Test {index}: "
        f"{'PASS' if success else 'FAIL'}"
    )

    if not success:
        print("Question:", question)
        print("Expected:", expected)
        print("Actual:", actual)

print(f"\nQuery routing tests: {passed}/{len(TESTS)} passed")


assert passed == len(TESTS), "Query routing regression"
