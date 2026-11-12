
import json
import os
import re
import hashlib

from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer


# --------------------------------------------------
# Configuration
# --------------------------------------------------

ROOT = Path(__file__).resolve().parents[1]
TEXT_DIR = ROOT / "metadata" / "extracted_text"
DB_PATH = ROOT / "vector_db"

COLLECTION_NAME = "campusiq_documents"
MODEL_NAME = "all-MiniLM-L6-v2"

CALENDAR_FILE = "Academic-Calendar-2026-27.txt"

all_documents = []
all_metadata = []
all_ids = []


# --------------------------------------------------
# Document Storage
# --------------------------------------------------

def add_document(text, metadata):
    text = text.strip()

    if not text:
        return

    document_id = hashlib.sha256(
        (
            metadata["source"] + ":" +
            str(metadata["page"]) + ":" +
            str(len(all_documents)) + ":" +
            text
        ).encode("utf-8")
    ).hexdigest()

    all_documents.append(text)
    all_metadata.append(metadata)
    all_ids.append(document_id)


# --------------------------------------------------
# Page Splitting
# --------------------------------------------------

def split_pages(text):
    """Preserve extracted page markers."""

    parts = re.split(
        r"(?=\[Page\s+\d+\])",
        text
    )

    for part in parts:
        part = part.strip()

        if not part:
            continue

        match = re.match(
            r"\[Page\s+(\d+)\]",
            part
        )

        page = int(match.group(1)) if match else 0

        yield page, part


# --------------------------------------------------
# Text Chunking
# --------------------------------------------------

def chunk_text(text, max_chars=1200):
    """Split text while preserving lines."""

    chunks = []
    current = ""

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        if (
            current
            and len(current) + len(line) + 1 > max_chars
        ):
            chunks.append(current)
            current = ""

        if len(line) > max_chars:
            if current:
                chunks.append(current)
                current = ""

            for start in range(0, len(line), max_chars):
                chunks.append(
                    line[start:start + max_chars]
                )

            continue

        current = (
            current + "\n" + line
            if current
            else line
        )

    if current:
        chunks.append(current)

    return chunks


# --------------------------------------------------
# Academic Calendar Processing
# --------------------------------------------------

def process_calendar(file):

    text = file.read_text(encoding="utf-8-sig")

    count_before = len(all_documents)

    for page, content in split_pages(text):

        student_group = (
            "first_year"
            if page == 1
            else "other_years"
            if page == 2
            else "unknown"
        )

        semester = "unknown"
        context = []

        for raw_line in content.splitlines():

            line = raw_line.strip()

            if not line:
                continue

            semester_match = re.match(
                r"Semester\s+(I|II)\s*\(",
                line,
                flags=re.IGNORECASE
            )

            if semester_match:
                semester = semester_match.group(1).upper()
                context.append(line)
                continue

            columns = [
                part.strip()
                for part in line.split("|")
            ]

            if (
                len(columns) >= 4
                and columns[3].isdigit()
                and page == int(columns[3])
                and semester != "unknown"
            ):

                date_text = columns[0]
                event = columns[1]
                applicable = columns[2]

                remarks = (
                    columns[4]
                    if len(columns) > 4
                    else ""
                )

                erp = (
                    columns[5]
                    if len(columns) > 5
                    else ""
                )

                entry = (
                    "MIT-WPU Academic Calendar 2026-27\n"
                    f"Semester: {semester}\n"
                    f"Student category: {applicable}\n"
                    f"Date: {date_text}\n"
                    f"Event: {event}\n"
                    f"Remarks: {remarks}\n"
                    f"ERP locking: {erp}\n"
                    f"Source page: {page}"
                )

                add_document(
                    entry,
                    {
                        "source": file.name,
                        "page": page,
                        "type": "calendar_event",
                        "semester": semester,
                        "student_group": student_group,
                        "event": event,
                        "date": date_text,
                        "academic_year": "2026-27"
                    }
                )

            else:
                context.append(line)

        # Preserve non-event calendar information.
        if context:

            context_text = "\n".join(context)

            for index, chunk in enumerate(
                chunk_text(
                    context_text,
                    max_chars=1000
                )
            ):

                add_document(
                    chunk,
                    {
                        "source": file.name,
                        "page": page,
                        "type": "calendar_context",
                        "semester": "mixed",
                        "student_group": student_group,
                        "chunk_index": index
                    }
                )

    count = len(all_documents) - count_before

    print(f"Calendar processed: {count} chunks")


# --------------------------------------------------
# Examination Ordinance Processing
# --------------------------------------------------

def process_ordinance(file):

    text = file.read_text(encoding="utf-8-sig")

    count_before = len(all_documents)

    for page, content in split_pages(text):

        for index, chunk in enumerate(
            chunk_text(content)
        ):

            add_document(
                chunk,
                {
                    "source": file.name,
                    "page": page,
                    "type": "ordinance",
                    "chunk_index": index
                }
            )

    count = len(all_documents) - count_before

    print(
        f"Ordinance processed: {file.name} "
        f"| {count} chunks"
    )


# --------------------------------------------------
# Knowledge Base Versioning
# --------------------------------------------------

def generate_knowledge_version(files):

    hasher = hashlib.sha256()

    hasher.update(
        MODEL_NAME.encode("utf-8")
    )

    # Include the index schema version so changes
    # to the ingestion logic can invalidate the cache.
    hasher.update(b"campusiq-index-schema-v2")

    for file in files:

        hasher.update(
            file.name.encode("utf-8")
        )

        hasher.update(
            file.read_bytes()
        )

    return hasher.hexdigest()[:16]


def save_manifest(version, indexed_count, files):

    DB_PATH.mkdir(
        parents=True,
        exist_ok=True
    )

    manifest_path = (
        DB_PATH / "index_manifest.json"
    )

    temporary_path = (
        DB_PATH / "index_manifest.tmp"
    )

    manifest = {
        "version": version,
        "collection": COLLECTION_NAME,
        "embedding_model": MODEL_NAME,
        "total_chunks": indexed_count,
        "documents": [
            file.name for file in files
        ]
    }

    temporary_path.write_text(
        json.dumps(
            manifest,
            indent=2
        ),
        encoding="utf-8"
    )

    # Replace the manifest only after indexing
    # completes and the chunk count is verified.
    os.replace(
        temporary_path,
        manifest_path
    )

    print(
        "Knowledge base version:",
        version
    )

    print(
        "Cache manifest updated successfully."
    )


# --------------------------------------------------
# Main Ingestion Pipeline
# --------------------------------------------------

def main():

    # Clear in-memory document buffers.
    all_documents.clear()
    all_metadata.clear()
    all_ids.clear()

    files = sorted(
        TEXT_DIR.glob("*.txt")
    )

    if not files:
        raise RuntimeError(
            "No extracted text files found."
        )

    # STEP 1: Process extracted documents.
    usable_files = []

    for file in files:

        if not file.read_text(
            encoding="utf-8-sig"
        ).strip():

            print(
                "Skipping empty file:",
                file.name
            )

            continue

        usable_files.append(file)

        if file.name == CALENDAR_FILE:
            process_calendar(file)
        else:
            process_ordinance(file)

    if not all_documents:
        raise RuntimeError(
            "No usable document chunks found."
        )

    print(
        f"\nTotal chunks prepared: "
        f"{len(all_documents)}"
    )

    # STEP 2: Load embedding model.
    print("\nLoading embedding model...")

    model = SentenceTransformer(
        MODEL_NAME
    )

    # STEP 3: Generate embeddings.
    print(
        f"Generating embeddings for "
        f"{len(all_documents)} chunks..."
    )

    embeddings = []
    batch_size = 64

    for start in range(
        0,
        len(all_documents),
        batch_size
    ):

        batch = all_documents[
            start:start + batch_size
        ]

        vectors = model.encode(
            batch,
            normalize_embeddings=True
        ).tolist()

        embeddings.extend(vectors)

        print(
            f"Embedded {len(embeddings)}"
            f"/{len(all_documents)}"
        )

    # STEP 4: Connect to existing ChromaDB.
    client = chromadb.PersistentClient(
        path=str(DB_PATH)
    )

    # Replace only the CampusIQ collection.
    try:
        client.get_collection(
            COLLECTION_NAME
        )

        client.delete_collection(
            COLLECTION_NAME
        )

        print(
            "Previous CampusIQ collection removed."
        )

    except chromadb.errors.NotFoundError:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={
            "hnsw:space": "cosine"
        }
    )

    # STEP 5: Store embeddings.
    for start in range(
        0,
        len(all_documents),
        batch_size
    ):

        end = start + batch_size

        collection.upsert(
            ids=all_ids[start:end],
            documents=all_documents[start:end],
            embeddings=embeddings[start:end],
            metadatas=all_metadata[start:end]
        )

    # STEP 6: Verify indexing.
    indexed_count = collection.count()

    if indexed_count != len(all_documents):
        raise RuntimeError(
            "Vector database build incomplete. "
            f"Expected {len(all_documents)} chunks, "
            f"found {indexed_count}."
        )

    print(
        "\nCampusIQ database rebuilt successfully!"
    )

    print(
        "Total chunks:",
        indexed_count
    )

    print(
        "Database location:",
        DB_PATH
    )

    # STEP 7: Generate knowledge-base version.
    version = generate_knowledge_version(
        usable_files
    )

    # STEP 8: Save manifest after successful build.
    save_manifest(
        version=version,
        indexed_count=indexed_count,
        files=usable_files
    )


# --------------------------------------------------
# Entry Point
# --------------------------------------------------

if __name__ == "__main__":
    main()
