
import re
import os
import time
import logging
from pathlib import Path
from copy import deepcopy

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field

# AI and RAG
from app.ai.gemini import generate_response
from app.rag.retriever import retrieve_context
from app.rag.document_versions import build_version_notice
from app.rag.citation_validator import validate_citations
from app.rag.answer_validator import validate_answer_dates, exact_calendar_answer
from app.rag.retriever import is_calendar_question, detect_semester, detect_student_group, detect_calendar_event
from app.rag.citation_focus import (
    select_answer_citations,
    remove_duplicate_source_lines,
)
from app.rag.claim_verifier import audit_answer_claims

# Conversation memory
from app.memory.conversation import (
    resolve_followup,
    clean_history,
)

# Security
from app.security.guardrails import (
    SecurityError,
    validate_message,
    rate_limiter,
)

# Caching
from app.cache.response_cache import response_cache
from app.cache.cache_version import get_knowledge_version

# Monitoring
from app.monitoring.metrics import metrics

# PDF and citation highlighting
from app.pdf_highlighter import router as pdf_highlighter_router
from app.citation_evidence import attach_evidence_highlights

from app.memory.policy_followup import resolve_policy_followup
# --------------------------------------------------
# Configuration
# --------------------------------------------------

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("CampusIQ")

APP_VERSION = "1.9.0"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCUMENT_DIR = PROJECT_ROOT / "documents"

ALLOWED_DOCUMENTS = {
    "Academic-Calendar-2026-27.pdf",
    "Examination-Ordinance-2022.pdf",
    "Examination_Ordinances_2020.pdf",
}


app = FastAPI(
    title="CampusIQ",
    description="MIT-WPU AI Academic Assistant",
    version=APP_VERSION,
)

app.include_router(pdf_highlighter_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",") if origin.strip()],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# --------------------------------------------------
# Request Model
# --------------------------------------------------

class ChatRequest(BaseModel):
    message: str

    # Optional recent conversation history.
    # Existing requests with only "message" still work.
    history: list[dict[str, str]] = Field(
        default_factory=list,
        max_length=10,
    )


# --------------------------------------------------
# Response Monitoring
# --------------------------------------------------

@app.middleware("http")
async def monitor_requests(
    request: Request,
    call_next,
):
    start = time.perf_counter()

    try:
        response = await call_next(request)

    except Exception:
        duration = time.perf_counter() - start

        if request.url.path == "/api/chat":
            metrics.record_request(duration, 500)

        logger.exception("Unhandled API error")
        raise

    duration = time.perf_counter() - start

    if request.url.path == "/api/chat":
        metrics.record_request(
            duration,
            response.status_code,
        )

    logger.info(
        "HTTP %s %s | status=%s | duration=%.3fs",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )

    return response


# --------------------------------------------------
# Security Error Handler
# --------------------------------------------------

@app.exception_handler(SecurityError)
async def security_error_handler(
    request: Request,
    exc: SecurityError,
):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": str(exc)},
    )


# --------------------------------------------------
# Citation Extraction
# --------------------------------------------------

def extract_citations(context: str):
    """
    Extract unique document/page citations from
    the retrieved RAG context.
    """

    pattern = (
        r"\[Source:\s*([^,\]\r\n]+),"
        r"\s*Page:\s*(\d+)\s*\]"
    )

    citations = []
    seen = set()

    for source, page in re.findall(
        pattern,
        context,
        flags=re.IGNORECASE,
    ):
        source = source.strip()
        page_number = int(page)

        key = (source.lower(), page_number)

        if key in seen:
            continue

        seen.add(key)

        citations.append({
            "document": source,
            "page": page_number,
        })

    return citations


# --------------------------------------------------
# Helper: Standard Response
# --------------------------------------------------

def empty_response(
    message,
    reason="No relevant evidence found.",
):
    return {
        "answer": message,
        "sources": [],
        "citations": [],
        "validation": {
            "status": "not_checked",
            "valid": None,
            "reason": reason,
            "unsupported_dates": [],
        },
        "claim_audit": {
            "status": "not_applicable",
            "claims_checked": 0,
            "candidate_supported": 0,
            "partial_matches": 0,
            "unverified": 0,
            "claims": [],
        },
        "cached": False,
    }


# --------------------------------------------------
# Helper: Ordinance Warning
# --------------------------------------------------

def get_topic_version_notice(question, sources):
    """
    Apply ordinance applicability warnings only
    to relevant examination-policy questions.
    """

    has_ordinance_source = any(
        "ordinance" in str(source).lower()
        for source in sources
    )

    if not has_ordinance_source:
        return ""

    return build_version_notice(
        question=question,
        sources=sources,
    ) or ""


# --------------------------------------------------
# Helper: Evidence Audit
# --------------------------------------------------

def create_claim_audit(answer, context):
    """
    Non-blocking factual claim audit.

    A lexical match is not proof of factual
    entailment. Audit results are diagnostic.
    """

    try:
        audit = audit_answer_claims(
            answer=answer,
            context=context,
        )

        logger.info(
            "Claim audit | status=%s | "
            "checked=%d | partial=%d | unverified=%d",
            audit.get("status"),
            audit.get("claims_checked", 0),
            audit.get("partial_matches", 0),
            audit.get("unverified", 0),
        )

        return audit

    except Exception:
        logger.exception(
            "Claim-level verification failed."
        )

        return {
            "status": "audit_error",
            "claims_checked": 0,
            "candidate_supported": 0,
            "partial_matches": 0,
            "unverified": 0,
            "claims": [],
        }


# --------------------------------------------------
# Home Endpoint
# --------------------------------------------------

@app.get("/")
def home():
    return {
        "message": "Welcome to CampusIQ",
        "university": "MIT-WPU",
        "status": "running",
        "version": APP_VERSION,
        "features": [
            "RAG",
            "Document citations",
            "PDF highlighting",
            "Claim auditing",
            "Conversation memory",
        ],
    }


# --------------------------------------------------
# PDF Document Viewer
# --------------------------------------------------

@app.get("/api/documents/{filename}")
def view_document(filename: str):

    if filename not in ALLOWED_DOCUMENTS:
        raise HTTPException(
            status_code=404,
            detail="Document not found.",
        )

    file_path = DOCUMENT_DIR / filename

    if not file_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="PDF file is unavailable.",
        )

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        content_disposition_type="inline",
    )


# --------------------------------------------------
# Health Endpoint
# --------------------------------------------------

@app.get("/api/health")
def health():
    return {
        "status": "healthy",
        "service": "CampusIQ API",
        "version": APP_VERSION,
    }


# --------------------------------------------------
# Metrics (Local Development Only)
# --------------------------------------------------

@app.get("/api/metrics")
def get_api_metrics(request: Request):

    client_host = (
        request.client.host
        if request.client
        else ""
    )

    if client_host not in (
        "127.0.0.1",
        "::1",
    ):
        raise HTTPException(
            status_code=403,
            detail="Metrics restricted to local development.",
        )

    return {
        "service": "CampusIQ",
        "knowledge_version": get_knowledge_version(),
        "metrics": metrics.get_metrics(),
    }


# --------------------------------------------------
# Main Chat Endpoint
# --------------------------------------------------

@app.post("/api/chat")
def chat(
    request: ChatRequest,
    http_request: Request,
):

    # ----------------------------------------------
    # STEP 1: Validate student message
    # ----------------------------------------------

    original_question = validate_message(
        request.message
    )

    # ----------------------------------------------
    # STEP 2: Rate limiting
    # ----------------------------------------------

    client_id = (
        http_request.client.host
        if http_request.client
        else "unknown"
    )

    allowed, retry_after = rate_limiter.check(
        client_id
    )

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail=(
                "Too many requests. "
                "Please try again later."
            ),
            headers={
                "Retry-After": str(retry_after)
            },
        )

    # ----------------------------------------------
    # STEP 3: Clean conversation history
    # ----------------------------------------------

    history = clean_history(
        request.history
    )

    # ----------------------------------------------
    # STEP 4: Resolve conversational follow-up
    # ----------------------------------------------

    
    # First resolve academic-calendar follow-ups.
    question = resolve_followup(
        question=original_question,
        history=history,
    )

    # If calendar resolution did not change the
    # question, attempt ordinance follow-up
    # resolution instead.
    if question == original_question:
        question = resolve_policy_followup(
            question=original_question,
            history=history,
        )


    # Revalidate the resolved question before it
    # is used by retrieval or Gemini.
    question = validate_message(question)

    if question != original_question:
        logger.info(
            "Resolved follow-up | original=%r | resolved=%r",
            original_question,
            question,
        )

    # ----------------------------------------------
    # STEP 5: Knowledge-base version
    # ----------------------------------------------

    if is_calendar_question(question):
        # Do not substitute the indexed calendar for an unavailable year.
        years = re.findall(r"\b(20\d{2})\s*[-?]\s*(?:20)?(\d{2})\b", question)
        unsupported_year = any(year not in {"2026", "2027"} for year in re.findall(r"\b20\d{2}\b", question))
        if unsupported_year or any(start != "2026" or end != "27" for start, end in years):
            return empty_response("The requested academic calendar is not available in the current knowledge base.")
        if detect_calendar_event(question) in {"commencement of term", "last instructional day"}:
            semesters = set(re.findall(r"\b(?:semester|sem)\s*(ii|i|2|1|second|first)\b", question, re.I))
            if len(semesters) > 1:
                return empty_response("Please ask about one semester at a time.", reason="Multiple calendar qualifiers.")
            missing = []
            if not detect_semester(question):
                missing.append("semester (I or II)")
            if not detect_student_group(question):
                missing.append("student group (first year or all except first year)")
            if missing:
                return empty_response("Please specify the " + " and ".join(missing) + ".", reason="Calendar clarification required.")

    knowledge_version = get_knowledge_version()

    # ----------------------------------------------
    # STEP 6: Cache lookup
    #
    # Use the resolved question, not the short
    # original follow-up, to prevent cache collisions
    # between different student conversations.
    # ----------------------------------------------

    cached_response = None

    if knowledge_version:
        cached_response = response_cache.get(
            question,
            namespace=knowledge_version,
        )

    if cached_response is not None:
        metrics.record_cache_hit()

        result = deepcopy(cached_response)
        result["cached"] = True

        logger.info(
            "CampusIQ cache HIT | question=%r",
            question,
        )

        return result

    metrics.record_cache_miss()

    logger.info(
        "CampusIQ cache MISS | question=%r",
        question,
    )

    try:

        # ------------------------------------------
        # STEP 7: Retrieve RAG evidence
        # ------------------------------------------

        timings = {}
        retrieval_start = time.perf_counter()
        context, sources = retrieve_context(
            question,
            top_k=3,
        )

        timings["retrieval"] = time.perf_counter() - retrieval_start
        if not context:
            return empty_response(
                (
                    "I couldn't find sufficiently relevant "
                    "information in my current MIT-WPU "
                    "knowledge base. Please consult an "
                    "official university source."
                ),
                reason="No relevant evidence found.",
            )

        # ------------------------------------------
        # STEP 8: Extract citations
        # ------------------------------------------

        citations = extract_citations(context)

        # ------------------------------------------
        # STEP 9: Validate citations
        # ------------------------------------------

        citation_start = time.perf_counter()
        citation_results = validate_citations(
            citations
        )

        citations = [
            result["citation"]
            for result in citation_results
            if result.get("valid")
        ]

        timings["citation_validation"] = time.perf_counter() - citation_start
        if not citations:
            return empty_response(
                (
                    "Relevant university information "
                    "was retrieved, but its document "
                    "references could not be verified."
                ),
                reason="No valid citations found.",
            )

        # ------------------------------------------
        # STEP 10: Gemini answer generation
        # ------------------------------------------

        generation_start = time.perf_counter()
        answer = exact_calendar_answer(question, context)
        answer_method = "structured_calendar"
        if answer is None and is_calendar_question(question) and detect_calendar_event(question) in {"commencement of term", "last instructional day"}:
            return empty_response("The indexed calendar records do not establish one unambiguous date for this event.", reason="Missing or conflicting structured dates.")
        if answer is None:
            answer_method = "gemini"
            metrics.record_gemini_call()
            answer = generate_response(question=question, context=context)
        timings["generation"] = time.perf_counter() - generation_start

        # ------------------------------------------
        # STEP 11: Date verification
        # ------------------------------------------

        validation_start = time.perf_counter()
        validation = validate_answer_dates(
            answer=answer,
            context=context,
            question=question,
        )

        timings["date_validation"] = time.perf_counter() - validation_start
        if validation.get("status") == "unsupported":

            logger.warning(
                "Unsupported dates detected: %s",
                validation.get("unsupported_dates"),
            )

            return {
                "answer": (
                    "The generated answer contained "
                    "dates that could not be verified "
                    "against the university documents. "
                    "Please consult an official "
                    "university source."
                ),
                "sources": sources,
                "citations": [],
                "validation": validation,
                "claim_audit": create_claim_audit(
                    answer,
                    context,
                ),
                "cached": False,
            }

        # ------------------------------------------
        # STEP 12: Ordinance applicability notice
        # ------------------------------------------

        version_notice = get_topic_version_notice(
            question,
            sources,
        )

        if version_notice:
            answer += "\n\n" + version_notice

        # ------------------------------------------
        # STEP 13: Focus citations on the answer
        # ------------------------------------------

        focused_citations = select_answer_citations(
            answer=answer,
            citations=citations,
            question=question,
        )

        # ------------------------------------------
        # STEP 14: Attach PDF highlighting evidence
        #
        # Uses the existing citation-evidence module.
        # ------------------------------------------

        if not focused_citations:
            return empty_response("I couldn't verify a supporting document reference for this answer.", reason="No supporting citations survived filtering.")
        sources = list(dict.fromkeys(c["document"] for c in focused_citations))
        highlight_start = time.perf_counter()
        if focused_citations:
            focused_citations = attach_evidence_highlights(
                question=question,
                answer=answer,
                context=context,
                citations=focused_citations,
            )

        # ------------------------------------------
        # STEP 15: Clean duplicate source text
        # ------------------------------------------

        timings["highlighting"] = time.perf_counter() - highlight_start
        answer = remove_duplicate_source_lines(
            answer
        )

        # ------------------------------------------
        # STEP 16: Claim-level evidence audit
        # ------------------------------------------

        audit_start = time.perf_counter()
        claim_audit = create_claim_audit(
            answer=answer,
            context=context,
        )

        # ------------------------------------------
        # STEP 17: Final response
        # ------------------------------------------

        timings["claim_audit"] = time.perf_counter() - audit_start
        response_data = {
            "answer": answer,
            "sources": sources,
            "citations": focused_citations,
            "answer_method": answer_method,
            "timings_seconds": {key: round(value, 6) for key, value in timings.items()},
            "validation": validation,
            "claim_audit": claim_audit,
            "cached": False,
        }

        # ------------------------------------------
        # STEP 18: Version-aware response caching
        # ------------------------------------------

        if knowledge_version:
            response_cache.set(
                question,
                response_data,
                namespace=knowledge_version,
            )

        return response_data

    except HTTPException:
        raise

    except SecurityError:
        raise

    except Exception:
        logger.exception(
            "CampusIQ chat processing failed."
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "CampusIQ could not process the "
                "request. Please try again."
            ),
        )
