"""Bounded, versioned text extraction. Offsets refer to extracted page text, not PDF bytes."""
import hashlib
import io
import json
import subprocess
import sys

MAX_BYTES = 10 * 1024 * 1024
MAX_CHARS = 1_000_000
PARSER_VERSION = "pypdf-6.18.1+utf8-v1"
CHUNK_VERSION = "page-window-1200-150-v1"


def parse(data: bytes, media_type: str):
    if not 0 < len(data) <= MAX_BYTES:
        raise ValueError("SOURCE_SIZE_LIMIT")
    if media_type == "text/plain":
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise ValueError("INVALID_UTF8") from None
        if any(ord(c) < 32 and c not in "\n\r\t\f" for c in text):
            raise ValueError("BINARY_TEXT_UNSUPPORTED")
        pages = text.split("\f")
    elif media_type == "application/pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("MALFORMED_PDF")
        from pypdf import PdfReader
        try:
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted:
                raise ValueError("ENCRYPTED_PDF_UNSUPPORTED")
            if len(reader.pages) > 50:
                raise ValueError("SOURCE_PAGE_LIMIT")
            pages = []
            length = 0
            for page in reader.pages:
                content = page.get_contents()
                if content is not None and len(content.get_data()) > 8 * 1024 * 1024:
                    raise ValueError("PDF_STREAM_LIMIT")
                text = page.extract_text() or ""
                length += len(text)
                if length > MAX_CHARS:
                    raise ValueError("SOURCE_TEXT_LIMIT")
                pages.append(text)
        except ValueError:
            raise
        except Exception:
            raise ValueError("MALFORMED_PDF") from None
    else:
        raise ValueError("UNSUPPORTED_SOURCE_TYPE")
    if len(pages) > 50:
        raise ValueError("SOURCE_PAGE_LIMIT")
    if sum(map(len, pages)) > MAX_CHARS:
        raise ValueError("SOURCE_TEXT_LIMIT")
    if not any(p.strip() for p in pages):
        raise ValueError("NO_EXTRACTABLE_TEXT")
    chunks = []
    for number, page in enumerate(pages, 1):
        for start in range(0, len(page), 1050):
            text = page[start:start + 1200]
            if text.strip():
                chunks.append(dict(ordinal=len(chunks), page=number, section=f"Page {number}",
                                   start=start, end=start+len(text), text=text,
                                   sha256=hashlib.sha256(text.encode()).hexdigest()))
            if start + 1200 >= len(page):
                break
    return dict(parserVersion=PARSER_VERSION, chunkVersion=CHUNK_VERSION,
                sourceSha256=hashlib.sha256(data).hexdigest(), pageCount=len(pages),
                pages=pages, chunks=chunks, warnings=["EMPTY_PAGES"] if any(not p.strip() for p in pages) else [])


def isolated_parse(data: bytes, media_type: str):
    if not 0 < len(data) <= MAX_BYTES:
        raise ValueError("SOURCE_SIZE_LIMIT")
    try:
        process = subprocess.run([sys.executable, "-m", "caseflow_worker.parser_process", media_type],
                                 input=data, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                 timeout=20, check=False)
    except subprocess.TimeoutExpired:
        raise ValueError("PARSER_TIME_LIMIT") from None
    if process.returncode != 0:
        raise ValueError("PARSER_RESOURCE_LIMIT")
    result = json.loads(process.stdout)
    if "error" in result:
        raise ValueError(result["error"])
    return result
