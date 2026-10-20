import io
import logging
import zipfile
from dataclasses import dataclass

from docx import Document as WordDocument
from pypdf import PdfReader

from app.config import get_settings

# Parser diagnostics may contain source fragments. Only safe job errors are exposed.
logging.getLogger("pypdf").disabled = True

MIMES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "txt": "text/plain",
    "md": "text/markdown",
}


class InvalidSource(Exception):
    pass


@dataclass
class ParsedSpan:
    locator: str
    text: str


def validate_original(filename: str, mime: str, content: bytes) -> str:
    extension = filename.rsplit(".", 1)[-1].lower()
    if extension not in MIMES:
        raise InvalidSource("Use PDF, DOCX, UTF-8 TXT or Markdown.")
    accepted = {MIMES[extension], "application/octet-stream"}
    if extension == "md":
        accepted.add("text/plain")
    if mime.split(";", 1)[0].strip().lower() not in accepted:
        raise InvalidSource("File extension and content type do not match.")
    if not content:
        raise InvalidSource("The file is empty.")
    if extension == "pdf" and not content.startswith(b"%PDF-"):
        raise InvalidSource("The file is not a PDF.")
    if extension == "docx":
        if not content.startswith(b"PK"):
            raise InvalidSource("The file is not a DOCX document.")
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                files = archive.infolist()
                if len(files) > 2000 or sum(f.file_size for f in files) > 40 * 1024 * 1024:
                    raise InvalidSource("DOCX decompressed size or entry limit exceeded.")
                if any(f.flag_bits & 1 for f in files):
                    raise InvalidSource("Encrypted DOCX files are not supported.")
                if "word/document.xml" not in archive.namelist():
                    raise InvalidSource("The file is not a DOCX document.")
        except zipfile.BadZipFile as exc:
            raise InvalidSource("The DOCX archive is invalid.") from exc
    if extension in {"txt", "md"}:
        try:
            value = content.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidSource("Save text documents as UTF-8.") from exc
        if any(ord(c) < 32 and c not in "\r\n\t" for c in value):
            raise InvalidSource("Text documents cannot contain binary control characters.")
    return MIMES[extension]


def parse_original(filename: str, content: bytes) -> tuple[list[ParsedSpan], str | None]:
    settings = get_settings()
    extension = filename.rsplit(".", 1)[-1].lower()
    validate_original(filename, MIMES.get(extension, ""), content)
    spans: list[ParsedSpan] = []
    total = 0

    def append(locator: str, value: str) -> None:
        nonlocal total
        # XML/JSON/database cannot represent NUL. Reject rather than alter evidence.
        if "\x00" in value:
            raise InvalidSource("The extracted source contains unsupported characters.")
        total += len(value)
        if total > settings.max_source_chars or len(spans) >= settings.max_source_spans:
            raise InvalidSource("Extracted text exceeds the configured source limits.")
        spans.append(ParsedSpan(locator, value))

    try:
        if extension == "pdf":
            reader = PdfReader(io.BytesIO(content))
            if reader.is_encrypted:
                raise InvalidSource("Encrypted PDFs are not supported.")
            if len(reader.pages) > settings.max_pdf_pages:
                raise InvalidSource("PDF page limit exceeded.")
            for number, page in enumerate(reader.pages, 1):
                stream = page.get_contents()
                if stream is not None and len(stream.get_data()) > 10 * 1024 * 1024:
                    raise InvalidSource("PDF page content limit exceeded.")
                append(f"Page {number}", page.extract_text() or "")
        elif extension == "docx":
            document = WordDocument(io.BytesIO(content))
            # XML order preserves paragraphs in table cells as well as body paragraphs.
            for number, paragraph in enumerate(
                document.element.body.iter(
                    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}p"
                ),
                1,
            ):
                from docx.text.paragraph import Paragraph

                append(f"Paragraph {number}", Paragraph(paragraph, document).text)
        else:
            for number, line in enumerate(content.decode("utf-8-sig").splitlines(keepends=True), 1):
                append(f"Line {number}", line)
    except InvalidSource:
        raise
    except Exception as exc:
        raise InvalidSource(
            "This document could not be parsed. Supply a valid file or manual text."
        ) from exc
    if not any(span.text.strip() for span in spans):
        return (
            [],
            "No selectable text found. Add a manually authored text version; OCR is not available.",
        )
    warning = (
        "PDF layout may be imperfect; verify extracted text against the original."
        if extension == "pdf"
        else None
    )
    return spans, warning
