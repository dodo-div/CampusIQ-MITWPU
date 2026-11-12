
from io import BytesIO
from pathlib import Path
import os
import re

import pymupdf
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

router = APIRouter()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCUMENT_DIR = PROJECT_ROOT / "documents"

ALLOWED_DOCUMENTS = {
    "Academic-Calendar-2026-27.pdf",
    "Examination-Ordinance-2022.pdf",
    "Examination_Ordinances_2020.pdf",
}

TESSDATA = Path(
    os.getenv("TESSDATA_PREFIX", r"C:\Program Files\Tesseract-OCR\tessdata")
)

# Coordinates visually verified for this specific
# Academic Calendar 2026-27 PDF, physical page 2.
SEMESTER_II_START_RECT = pymupdf.Rect(
    250, 333, 290, 346
)


def is_semester_ii_start(filename, page, text):
    if filename != "Academic-Calendar-2026-27.pdf":
        return False

    if page != 2:
        return False

    normalized = re.sub(
        r"\s+",
        " ",
        text.lower().strip()
    )

    return normalized in {
        "4th jan 2027",
        "4 jan 2027",
        "4 january 2027",
        "4th january 2027",
        "04/01/2027",
        "04-01-2027",
    }


def search_pdf_text(pdf_page, text):
    if pdf_page.get_text("text").strip():
        return (
            pdf_page.search_for(text, quads=True),
            "native"
        )

    options = {
        "language": "eng",
        "dpi": 250,
        "full": True,
    }

    if TESSDATA.is_dir():
        options["tessdata"] = str(TESSDATA)

    textpage = pdf_page.get_textpage_ocr(**options)

    matches = pdf_page.search_for(
        text,
        textpage=textpage,
        quads=True,
    )

    return matches, "ocr"


@router.get("/api/documents/{filename}/highlight")
def highlight_pdf(
    filename: str,
    page: int = Query(ge=1),
    text: str = Query(min_length=3, max_length=500),
):
    if filename not in ALLOWED_DOCUMENTS:
        raise HTTPException(
            status_code=404,
            detail="Document not allowed."
        )

    pdf_path = DOCUMENT_DIR / filename

    if not pdf_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="PDF not found."
        )

    matches = []
    method = "unavailable"

    try:
        with pymupdf.open(str(pdf_path)) as pdf:
            if page > len(pdf):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid page number."
                )

            pdf_page = pdf[page - 1]

            # Special handling for the visually
            # verified Semester II start-date cell.
            if is_semester_ii_start(
                filename, page, text
            ):
                rect = SEMESTER_II_START_RECT

                if pdf_page.rect.contains(rect):
                    matches = [rect]
                    method = "verified_region"

            else:
                try:
                    matches, method = search_pdf_text(
                        pdf_page,
                        text
                    )
                except Exception:
                    matches = []
                    method = "unavailable"

            if matches:
                annotation = pdf_page.add_highlight_annot(
                    matches
                )

                if annotation:
                    annotation.update()

            pdf_bytes = pdf.tobytes(
                garbage=3,
                deflate=True,
            )

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to process PDF."
        )

    output = BytesIO(pdf_bytes)

    return StreamingResponse(
        output,
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                'inline; filename="highlighted.pdf"',
            "Cache-Control": "no-store",
            "X-Highlight-Matches": str(len(matches)),
            "X-Highlight-Method": method,
        },
    )
