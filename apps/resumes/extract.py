"""Safe text extraction from PDF and DOCX. Uploaded files are only ever *parsed*, never executed or rendered.
The file's real format is decided by its content signature, not by its extension."""
from __future__ import annotations

import io
import logging
import re
import unicodedata
import zipfile
from dataclasses import dataclass, field

from django.conf import settings

log = logging.getLogger("skillvar.resumes")

MAX_ZIP_UNCOMPRESSED = 50 * 1024 * 1024
MIN_USEFUL_CHARS = 100


class ResumeError(Exception):
    """Raised with a message that is safe to show to the user."""


@dataclass
class Extracted:
    text: str
    fmt: str
    page_count: int | None
    warnings: list[str] = field(default_factory=list)


def detect_format(data: bytes) -> str:
    if b"%PDF-" in data[:1024]:
        return "pdf"
    if data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = set(z.namelist())
        except zipfile.BadZipFile:
            raise ResumeError("This file is corrupted or is not a valid PDF or DOCX document.")
        if "[Content_Types].xml" in names and "word/document.xml" in names:
            return "docx"
    raise ResumeError("Unsupported file. Please upload a PDF or a DOCX (Word) document.")


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace("\x00", "")
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def _pdf(data: bytes) -> tuple[str, int]:
    from pypdf import PdfReader
    try:
        reader = PdfReader(io.BytesIO(data), strict=False)
        if reader.is_encrypted and not reader.decrypt(""):
            raise ResumeError("This PDF is password-protected. Please remove the password and upload it again.")
        pages = len(reader.pages)
        if pages > settings.RESUME_MAX_PAGES:
            raise ResumeError(f"This PDF has {pages} pages; the limit is {settings.RESUME_MAX_PAGES}.")
        return "\n".join((p.extract_text() or "") for p in reader.pages), pages
    except ResumeError:
        raise
    except Exception as exc:  # parsing libraries raise many unrelated types on malformed input
        log.warning("pdf extraction failed: %s", type(exc).__name__)
        raise ResumeError("We could not read this PDF. It may be damaged. Try exporting it again.")


def _docx(data: bytes) -> tuple[str, None]:
    import docx
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if sum(i.file_size for i in z.infolist()) > MAX_ZIP_UNCOMPRESSED:
                raise ResumeError("This document expands to an unreasonable size and was rejected.")
        document = docx.Document(io.BytesIO(data))
        parts = [p.text for p in document.paragraphs]
        for table in document.tables:
            for row in table.rows:
                parts.append(" | ".join(c.text for c in row.cells))
        return "\n".join(parts), None
    except ResumeError:
        raise
    except Exception as exc:
        log.warning("docx extraction failed: %s", type(exc).__name__)
        raise ResumeError("We could not read this Word document. It may be damaged.")


def extract(data: bytes) -> Extracted:
    if not data:
        raise ResumeError("The file is empty.")
    fmt = detect_format(data)
    raw, pages = _pdf(data) if fmt == "pdf" else _docx(data)
    text, warnings = normalize_text(raw), []
    if len(text) > settings.RESUME_MAX_TEXT_CHARS:
        text = text[:settings.RESUME_MAX_TEXT_CHARS]
        warnings.append("The document was very long, so only the first part was analyzed.")
    if len(text) < MIN_USEFUL_CHARS:
        warnings.append("Very little text could be extracted. If this is a scanned or image-based PDF, it needs OCR, "
                        "which SkillVar does not support yet. Try a text-based PDF or a DOCX.")
    return Extracted(text, fmt, pages, warnings)
