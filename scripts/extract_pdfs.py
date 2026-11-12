
from pathlib import Path
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = ROOT / "documents"
OUTPUT = ROOT / "metadata" / "extracted_text"

OUTPUT.mkdir(parents=True, exist_ok=True)

pdf_files = list(DOCUMENTS.glob("*.pdf"))

if not pdf_files:
    print("No PDF files found in documents/")
else:
    for pdf_path in pdf_files:
        print(f"Processing: {pdf_path.name}")

        with pymupdf.open(pdf_path) as pdf:
            pages = []

            for page_number, page in enumerate(pdf, start=1):
                text = page.get_text("text").strip()

                if text:
                    pages.append(
                        f"[Page {page_number}]\n{text}"
                    )

        output_path = OUTPUT / f"{pdf_path.stem}.txt"
        output_path.write_text(
            "\n\n".join(pages),
            encoding="utf-8"
        )

        print(f"Saved: {output_path.name}")
