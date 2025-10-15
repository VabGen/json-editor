# utils.py
from pypdf import PdfReader
from tempfile import NamedTemporaryFile
import os


def pdf_to_text(pdf_file) -> str:
    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_file.file.read())
        tmp_path = tmp.name

    try:
        reader = PdfReader(tmp_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        return text.strip()
    finally:
        os.unlink(tmp_path)
