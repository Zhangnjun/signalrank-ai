from __future__ import annotations

from pathlib import Path

from docx import Document
from pypdf import PdfReader


def load_resume_text(path: str | Path) -> str:
    resume_path = Path(path).expanduser().resolve()
    if not resume_path.exists():
        raise FileNotFoundError(f"Resume file not found: {resume_path}")

    suffix = resume_path.suffix.lower()
    if suffix in {".txt", ".md"}:
        return resume_path.read_text(encoding="utf-8").strip()
    if suffix == ".pdf":
        return _load_pdf(resume_path)
    if suffix == ".docx":
        return _load_docx(resume_path)

    raise ValueError(
        f"Unsupported resume format: {resume_path.suffix}. Use .txt, .md, .pdf, or .docx."
    )


def _load_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    text = "\n".join(page.extract_text() or "" for page in reader.pages).strip()
    if not text:
        raise ValueError(f"Could not extract text from PDF: {path}")
    return text


def _load_docx(path: Path) -> str:
    document = Document(str(path))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
    if not text:
        raise ValueError(f"Could not extract text from DOCX: {path}")
    return text
