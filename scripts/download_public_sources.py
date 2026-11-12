"""Download explicitly approved public PDFs from metadata/approved_downloads.txt.
Review each source's terms and obtain permission before adding it to the list.
Run: pip install requests; python scripts/download_public_sources.py
"""
from pathlib import Path
from urllib.parse import urlparse
import requests
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'documents'
DEST.mkdir(exist_ok=True)
approved = ROOT / 'metadata' / 'approved_downloads.txt'
for line in approved.read_text(encoding='utf-8').splitlines():
    url = line.strip()
    if not url or url.startswith('#'):
        continue
    if urlparse(url).scheme != 'https':
        print('Skipped non-HTTPS URL:', url)
        continue
    try:
        r = requests.get(url, timeout=30, headers={'User-Agent':'CampusIQ-Research/0.1'})
        r.raise_for_status()
        if not r.content.startswith(b'%PDF-'):
            print('Skipped non-PDF:', url)
            continue
        name = Path(urlparse(url).path).name or 'document.pdf'
        target = DEST / name
        target.write_bytes(r.content)
        print('Saved:', target)
    except requests.RequestException as e:
        print('Failed:', url, e)
