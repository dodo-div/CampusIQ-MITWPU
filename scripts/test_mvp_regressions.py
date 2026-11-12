"""Focused regressions: existing index, no Gemini and no DB rebuild."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from fastapi.testclient import TestClient
from app.main import app
from app.cache.response_cache import response_cache, ResponseCache
from app.rag.retriever import retrieve_context
from app.rag.answer_validator import exact_calendar_answer, validate_answer_dates
from app.rag.citation_focus import select_answer_citations
from app.memory.conversation import resolve_followup
from app.memory.policy_followup import resolve_policy_followup
from app.security.guardrails import rate_limiter

QUESTION = "When does Semester II end for second-year students?"

class MVPRegressions(unittest.TestCase):
    def setUp(self):
        response_cache.clear()
        self.client = TestClient(app)

    def ask(self, question, history=None):
        # Each request has its own IP to avoid exercising the limiter here.
        with patch.object(rate_limiter, "check", return_value=(True, 0)):
            result = self.client.post("/api/chat", json={"message": question, "history": history or []})
        self.assertEqual(result.status_code, 200, result.text)
        return result.json()

    def test_exact_end_is_validated_cached_and_highlighted_without_model(self):
        with patch("app.main.generate_response", side_effect=AssertionError("Gemini called")), patch("app.rag.retriever.embed_query", side_effect=AssertionError("embedding called")):
            first = self.ask(QUESTION)
            second = self.ask(QUESTION)
        self.assertIn("8 May 2027", first["answer"])
        self.assertNotIn("9 May", first["answer"])
        self.assertEqual(first["validation"]["status"], "verified")
        self.assertEqual(first["answer_method"], "structured_calendar")
        self.assertFalse(first["cached"])
        self.assertTrue(second["cached"])
        self.assertEqual(first["citations"][0]["page"], 2)
        self.assertTrue(first["citations"][0].get("highlight_text"))

    def test_wrong_attendance_date_rejected(self):
        context, _ = retrieve_context(QUESTION)
        self.assertFalse(validate_answer_dates("9 May 2027", context, QUESTION)["valid"])
        self.assertTrue(validate_answer_dates("8 May 2027", context, QUESTION)["valid"])

    def test_missing_evidence_never_becomes_exact_answer(self):
        self.assertIsNone(exact_calendar_answer(QUESTION, ""))

    def test_missing_group_requires_clarification(self):
        with patch("app.main.generate_response", side_effect=AssertionError("Gemini called")):
            result = self.ask("When does Semester II end?")
        self.assertIn("student group", result["answer"])
        self.assertEqual(result["citations"], [])

    def test_unavailable_academic_year(self):
        result = self.ask(QUESTION + " in academic year 2027-28")
        self.assertEqual(result["citations"], [])
        self.assertIn("not available", result["answer"])

    def test_calendar_followup_and_isolation(self):
        history = [{"role": "user", "content": "When does Semester II begin for second-year students?"}]
        answer = self.ask("And when does it end?", history)
        self.assertIn("8 May 2027", answer["answer"])
        self.assertEqual(resolve_followup("And when does it end?", [{"role": "user", "content": "What is the hostel fee?"}]), "And when does it end?")

    def test_policy_context_does_not_rewrite_new_calendar(self):
        q = "And when does Semester II begin for first-year students?"
        history = [{"role": "user", "content": "What does the 2022 ordinance say?"}]
        self.assertEqual(resolve_policy_followup(q, history), q)

    def test_fabricated_citation_not_replaced_by_irrelevant_sources(self):
        self.assertEqual(select_answer_citations("See Unknown.txt, Page 999", [{"document": "Examination-Ordinance-2022.txt", "page": 12}]), [])

    def test_unavailable_answer_does_not_cite_absent_deadline(self):
        citation = {"document": "Examination-Ordinance-2022.txt", "page": 12}
        answer = "The evidence does not mention the deadline (Examination-Ordinance-2022.txt, Page 12). Therefore this information could not be verified."
        self.assertEqual(select_answer_citations(answer, [citation]), [])
        partial = "The ordinance includes result processing [Source: Examination-Ordinance-2022.txt, Page: 12]. The deadline could not be verified."
        self.assertEqual(select_answer_citations(partial, [citation]), [citation])

    def test_bold_source_heading_cleanup(self):
        from app.rag.citation_focus import remove_duplicate_source_lines
        self.assertEqual(remove_duplicate_source_lines("Supported answer.\n\n**Source:** Examination-Ordinance-2022.txt, Page: 12\n-"), "Supported answer.")

    def test_conflicting_exact_records_abstain(self):
        context, _ = retrieve_context(QUESTION)
        self.assertIsNone(exact_calendar_answer(QUESTION, context + "\n\n" + context.replace("08th May 2027", "09th May 2027")))

    def test_document_endpoints(self):
        response = self.client.get("/api/documents/Academic-Calendar-2026-27.pdf")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertEqual(self.client.get("/api/documents/unknown.pdf").status_code, 404)
        self.assertEqual(self.client.get("/api/documents/Academic-Calendar-2026-27.pdf/highlight?page=0&text=example").status_code, 422)

    def test_explicit_ordinance_versions(self):
        from app.rag.version_policy import get_ordinance_policy
        self.assertEqual(get_ordinance_policy("What does the 2020 ordinance say?")["preferred_source"], "Examination_Ordinances_2020.txt")
        self.assertEqual(get_ordinance_policy("What does ordinance 2022 say?")["preferred_source"], "Examination-Ordinance-2022.txt")
        self.assertIsNone(get_ordinance_policy("Compare ordinance 2020 and ordinance 2022")["preferred_source"])
        self.assertIsNone(get_ordinance_policy("What does the 2017 ordinance say?")["preferred_source"])

    def test_cache_namespace_and_copy_isolation(self):
        cache = ResponseCache()
        cache.set(" question ", {"answer": ["a"]}, "one")
        self.assertIsNone(cache.get("question", "two"))
        value = cache.get("QUESTION", "one")
        value["answer"].append("b")
        self.assertEqual(cache.get("question", "one")["answer"], ["a"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
