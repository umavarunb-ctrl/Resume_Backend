import re
from typing import Tuple
from fastapi import HTTPException, status
import pymupdf


class PDFService:
    """Service handling PDF document text extraction and structural validation."""

    MIN_SELECTABLE_CHARACTERS = 30

    @staticmethod
    def normalize_text(text: str) -> str:
        """Clean and normalize extracted text: replace multiple spaces and consecutive blank lines."""
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def extract_text_from_bytes(self, file_bytes: bytes) -> Tuple[str, int]:
        """
        Extract clean, selectable text and page count from raw PDF bytes.
        Raises HTTPException if file is encrypted, corrupt, or contains no selectable text.
        """
        try:
            doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        except Exception:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unable to open or parse the uploaded file. Please ensure it is a valid PDF.",
            )

        try:
            if doc.is_encrypted:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password-protected or encrypted PDF resumes are not supported.",
                )

            page_count = len(doc)
            if page_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The uploaded PDF contains no pages.",
                )

            extracted_pages = []
            for page_index in range(page_count):
                page = doc[page_index]
                page_text = page.get_text("text")
                if page_text and page_text.strip():
                    extracted_pages.append(page_text.strip())

            raw_combined_text = "\n\n".join(extracted_pages)
            cleaned_text = self.normalize_text(raw_combined_text)

            if len(cleaned_text) < self.MIN_SELECTABLE_CHARACTERS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No selectable text detected in PDF. Scanned image-only PDFs are not supported in V1 (digitally generated/selectable text PDFs only).",
                )

            return cleaned_text, page_count
        finally:
            doc.close()
