
import os
from pathlib import Path
from datetime import datetime, timezone
import json
import time
import urllib.request
import urllib.error

API = os.getenv("CAMPUSIQ_API_URL", "http://127.0.0.1:8000").rstrip("/") + "/api/chat"

QUESTIONS = [
    "When does Semester II begin for second-year students?",
    "When does Semester II end for second-year students?",
    "What are post-examination activities under the 2022 ordinance?",
    "Does the 2022 ordinance mention digital masking?",
    "What does the 2022 ordinance say about result declaration?",
]


def ask(question):
    payload = json.dumps({
        "message": question,
        "history": [],
    }).encode("utf-8")

    request = urllib.request.Request(
        API,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    start = time.perf_counter()

    try:
        with urllib.request.urlopen(
            request, timeout=120
        ) as response:
            result = json.loads(response.read())

        elapsed = time.perf_counter() - start

        return {
            "time": round(elapsed, 3),
            "cached": result.get("cached", False),
            "answer": result.get("answer", ""),
            "status": "OK",
            "validation": result.get("validation", {}),
            "citations": result.get("citations", []),
            "answer_method": result.get("answer_method"),
            "timings_seconds": result.get("timings_seconds", {}),
        }

    except Exception as error:
        return {
            "time": round(
                time.perf_counter() - start, 3
            ),
            "cached": False,
            "answer": "",
            "status": str(error),
        }


def main():
    first_times = []
    repeat_times = []
    cache_hits = 0
    results = []

    for index, question in enumerate(QUESTIONS, 1):
        print(f"\nTEST {index}: {question}")

        first = ask(question)
        second = ask(question)

        results.append({"question": question, "first": first, "repeat": second})
        print("First:", first["time"], "seconds",
              "| Cached:", first["cached"])
        print("Repeat:", second["time"], "seconds",
              "| Cached:", second["cached"])
        print("Status:", first["status"], second["status"])
        print(
            "Same answer:",
            first["answer"] == second["answer"]
        )

        if first["status"] == "OK" and second["status"] == "OK":
            first_times.append(first["time"])
            repeat_times.append(second["time"])

            if second["cached"]:
                cache_hits += 1

    print("\n===== PERFORMANCE SUMMARY =====")

    if first_times:
        print(
            "Average first request:",
            round(sum(first_times) / len(first_times), 3),
            "seconds",
        )
        print(
            "Average repeated request:",
            round(sum(repeat_times) / len(repeat_times), 3),
            "seconds",
        )
        print(
            "Repeated cache hits:",
            cache_hits, "/", len(first_times),
        )
    else:
        print("No successful request pairs.")

    output = Path(__file__).resolve().parents[1] / "reports" / "performance_latest.json"
    output.write_text(json.dumps({"recorded_at": datetime.now(timezone.utc).isoformat(),
                                  "api": API, "results": results}, indent=2), encoding="utf-8")
    print("Report:", output)


if __name__ == "__main__":
    main()
