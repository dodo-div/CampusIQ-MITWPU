
import sys
import csv
import json
import re

from pathlib import Path
from datetime import datetime


# --------------------------------------------------
# Project Configuration
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "backend")
)

from app.rag.retriever import retrieve_context
from app.rag.answer_validator import validate_answer_dates


REPORT_DIR = ROOT / "reports"
REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True
)

CALENDAR = "Academic-Calendar-2026-27.txt"

ORDINANCE_2022 = "Examination-Ordinance-2022.txt"


# --------------------------------------------------
# Test Cases
# --------------------------------------------------

TESTS = [

    # Calendar retrieval

    {
        "question": "When does Semester I start for first-year students?",
        "date": "03-Aug-26",
        "page": 1,
        "event": "Commencement of Term",
    },
    {
        "question": "When does Semester I start for second-year students?",
        "date": "6th Jul 2026",
        "page": 2,
        "event": "Commencement of Term",
    },
    {
        "question": "When does Semester II start for first-year students?",
        "date": "4th Jan 2027",
        "page": 1,
        "event": "Commencement of Term",
    },
    {
        "question": "When does Semester II start for second-year students?",
        "date": "4th Jan 2027",
        "page": 2,
        "event": "Commencement of Term",
    },
    {
        "question": "When are Semester I term end exams for first-year students?",
        "date": "7thDec 2026",
        "page": 1,
        "event": "Term End Exam",
    },
    {
        "question": "When are Semester I term end exams for second-year students?",
        "date": "19th Nov 2026",
        "page": 2,
        "event": "Term End Exam",
    },
    {
        "question": "When are Semester II term end exams for first-year students?",
        "date": "12th May 2027",
        "page": 1,
        "event": "Term End Exam",
    },
    {
        "question": "When are Semester II term end exams for second-year students?",
        "date": "12th May 2027",
        "page": 2,
        "event": "Term End Exam",
    },
    {
        "question": "When is the Semester I midterm for first-year students?",
        "date": "12th Oct 2026",
        "page": 1,
        "event": "Formative Assessment 2",
    },
    {
        "question": "When is the Semester I midterm for second-year students?",
        "date": "7th Sep 2026",
        "page": 2,
        "event": "Formative Assessment 2",
    },
    {
        "question": "When is Semester I vacation for first-year students?",
        "date": "7th Nov 2026",
        "page": 1,
        "event": "Diwali Vacation",
    },
    {
        "question": "When is Semester I vacation for second-year students?",
        "date": "7th Nov 2026",
        "page": 2,
        "event": "Diwali Vacation",
    },
    {
        "question": "When is the Semester II midterm for second-year students?",
        "date": "8th Mar 2027",
        "page": 2,
        "event": "Formative Assessment 2",
    },

    # Partial ordinance evidence

    {
        "question": "What are the rules for revaluation?",
        "type": "partial_evidence",
        "source": ORDINANCE_2022,
        "page": 12,
        "topic_pattern": r"\bre[\s-]*evaluation\b|\brevaluation\b",
    },

    # Insufficient ordinance evidence

    {
        "question": "How can students apply for retotaling?",
        "type": "insufficient_evidence",
    },

    # Unsupported queries

    {
        "question": "What is the MIT-WPU hostel fee?",
        "type": "unsupported",
    },
    {
        "question": "What is the campus WiFi password?",
        "type": "unsupported",
    },

    # Date validation

    {
        "question": "When does Semester II start for second-year students?",
        "type": "validation",
        "answer": "Semester II begins on 4 January 2027.",
        "expected_status": "verified",
    },
    {
        "question": "When does Semester II start for second-year students?",
        "type": "validation",
        "answer": "Semester II begins on 12 May 2027.",
        "expected_status": "unsupported",
    },
    {
        "question": "When does Semester II start for second-year students?",
        "type": "validation",
        "answer": "Semester II begins in January 2027.",
        "expected_status": "not_checked",
    }
]


# --------------------------------------------------
# Citation Extraction
# --------------------------------------------------

def citations_from_context(context):

    pattern = (
        r"\[Source:\s*(.+?),\s*Page:\s*([^\]]+)\]"
    )

    citations = []
    seen = set()

    for name, page in re.findall(pattern, context):

        name = name.strip()
        page = page.strip()

        page_number = (
            int(page)
            if page.isdigit()
            else None
        )

        key = (name, page_number)

        if key in seen:
            continue

        seen.add(key)

        citations.append({
            "document": name,
            "page": page_number
        })

    return citations


# --------------------------------------------------
# Evaluate Individual Test
# --------------------------------------------------

def evaluate_one(test):

    question = test["question"]

    test_type = test.get(
        "type",
        "calendar"
    )

    context, sources = retrieve_context(
        question,
        top_k=3
    )

    citations = citations_from_context(
        context
    )

    # ----------------------------------------------
    # Unsupported Queries
    # ----------------------------------------------

    if test_type == "unsupported":

        passed = (
            not context
            and not sources
        )

        actual = (
            "No context"
            if passed
            else "Unexpected evidence returned"
        )

    # ----------------------------------------------
    # Partial Evidence
    # ----------------------------------------------

    elif test_type == "partial_evidence":

        expected_source = test["source"]
        expected_page = test["page"]

        source_ok = (
            expected_source in sources
        )

        page_ok = any(
            citation["document"] == expected_source
            and citation["page"] == expected_page
            for citation in citations
        )

        topic_ok = bool(
            re.search(
                test["topic_pattern"],
                context,
                flags=re.IGNORECASE
            )
        )

        passed = (
            bool(context)
            and source_ok
            and page_ok
            and topic_ok
        )

        actual = (
            f"Source correct: {source_ok}"
            f" | Page correct: {page_ok}"
            f" | Topic mentioned: {topic_ok}"
        )

    # ----------------------------------------------
    # Insufficient Evidence
    # ----------------------------------------------

    elif test_type == "insufficient_evidence":

        passed = (
            not context
            and not sources
        )

        actual = (
            "No supporting evidence returned"
            if passed
            else (
                "Unexpected evidence: "
                + ", ".join(sources)
            )
        )

    # ----------------------------------------------
    # Ordinance Keyword Tests
    # ----------------------------------------------

    elif test_type == "ordinance":

        source_ok = any(
            "ordinance" in source.lower()
            for source in sources
        )

        keyword_ok = (
            test["keyword"].lower()
            in context.lower()
        )

        passed = (
            source_ok
            and keyword_ok
        )

        actual = (
            ", ".join(sources)
            if sources
            else "No evidence"
        )

    # ----------------------------------------------
    # Answer Date Validation
    # ----------------------------------------------

    elif test_type == "validation":

        result = validate_answer_dates(
            answer=test["answer"],
            context=context,
            question=question
        )

        actual = result["status"]

        passed = (
            actual == test["expected_status"]
            and (
                actual == "not_checked"
                or result.get("check_type")
                == "calendar_event"
            )
        )

    # ----------------------------------------------
    # Academic Calendar Retrieval
    # ----------------------------------------------

    elif test_type == "calendar":

        correct_citation = any(
            citation["document"] == CALENDAR
            and citation["page"] == test["page"]
            for citation in citations
        )

        records = re.split(
            r"(?=\[Source:\s*[^\]]+\])",
            context
        )

        correct_record = False

        for record in records:

            if not record.strip():
                continue

            date_found = (
                test["date"].lower()
                in record.lower()
            )

            event_found = (
                test["event"].lower()
                in record.lower()
            )

            page_found = (
                f"Page: {test['page']}]"
                in record
            )

            if (
                date_found
                and event_found
                and page_found
            ):
                correct_record = True
                break

        wrong_page = (
            2 if test["page"] == 1 else 1
        )

        wrong_citation = any(
            citation["document"] == CALENDAR
            and citation["page"] == wrong_page
            for citation in citations
        )

        passed = (
            correct_citation
            and correct_record
            and not wrong_citation
        )

        actual = (
            f"Pages: "
            f"{[c['page'] for c in citations]}"
            f" | Expected date found: {correct_record}"
        )

    else:
        raise ValueError(
            f"Unknown test type: {test_type}"
        )

    return {
        "question": question,
        "type": test_type,
        "status": (
            "PASS" if passed else "FAIL"
        ),
        "actual": actual,
        "sources": sources,
        "citations": citations,
        "context_preview": context[:500]
    }


# --------------------------------------------------
# Main Evaluation
# --------------------------------------------------

def main():

    results = []

    print("\nCampusIQ RAG Evaluation")
    print("=" * 65)

    for index, test in enumerate(
        TESTS,
        start=1
    ):

        try:
            result = evaluate_one(test)

        except Exception as exc:

            result = {
                "question": test["question"],
                "type": test.get(
                    "type",
                    "calendar"
                ),
                "status": "ERROR",
                "actual": str(exc),
                "sources": [],
                "citations": [],
                "context_preview": ""
            }

        results.append(result)

        print(
            f"{index:02d}. "
            f"[{result['status']}] "
            f"{result['question']}"
        )

        if result["status"] != "PASS":
            print(
                "    Actual:",
                result["actual"]
            )

    passed = sum(
        result["status"] == "PASS"
        for result in results
    )

    total = len(results)

    accuracy = (
        100 * passed / total
        if total
        else 0
    )

    print("\n" + "=" * 65)

    print(
        f"Passed: {passed}/{total}"
    )

    print(
        f"Pass rate: {accuracy:.1f}%"
    )

    print(
        f"Failed or errored: {total - passed}"
    )

    # ----------------------------------------------
    # Save Reports
    # ----------------------------------------------

    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    csv_path = (
        REPORT_DIR
        / f"rag_eval_{timestamp}.csv"
    )

    json_path = (
        REPORT_DIR
        / f"rag_eval_{timestamp}.json"
    )

    fieldnames = [
        "question",
        "type",
        "status",
        "actual",
        "sources",
        "citations",
        "context_preview"
    ]

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8-sig"
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames
        )

        writer.writeheader()

        for row in results:

            writer.writerow({
                **row,
                "sources": json.dumps(
                    row["sources"],
                    ensure_ascii=False
                ),
                "citations": json.dumps(
                    row["citations"],
                    ensure_ascii=False
                )
            })

    report = {
        "total": total,
        "passed": passed,
        "pass_rate": round(
            accuracy,
            2
        ),
        "results": results
    }

    json_path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print("\nReports saved:")
    print(csv_path)
    print(json_path)


# --------------------------------------------------
# Entry Point
# --------------------------------------------------

if __name__ == "__main__":
    main()
