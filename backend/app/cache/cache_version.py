
import json
import hashlib
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DB_PATH = ROOT / "vector_db"
MANIFEST_PATH = DB_PATH / "index_manifest.json"


def get_knowledge_version():
    """
    Return the version of the successfully
    built CampusIQ vector database.

    Returns None if no build manifest exists.
    """
    if not MANIFEST_PATH.exists():
        return None

    try:
        manifest = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8")
        )

        version = manifest.get("version")
        if not version:
            return None
        digest = hashlib.sha256(str(version).encode())
        digest.update(os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite").encode())
        for path in sorted((ROOT / "backend" / "app").rglob("*.py")):
            digest.update(path.relative_to(ROOT).as_posix().encode())
            digest.update(path.read_bytes())
        return digest.hexdigest()[:24]

    except (OSError, ValueError):
        return None
