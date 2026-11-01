import os
import pdfplumber

try:
    import pytesseract
    if os.name == 'nt' and os.path.exists(r'C:\Program Files\Tesseract-OCR\tesseract.exe'):
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    HAS_PYTESSERACT = True
except Exception:
    HAS_PYTESSERACT = False


def extract_text_hybrid(pdf_path):
    """
    Fast two-tier PDF text extraction:
    1. Digital text extraction via pdfplumber across all pages (instant for born-digital PDFs).
    2. Fallback to Tesseract OCR only if the document contains virtually no digital text (scanned PDF).
    """
    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t and t.strip():
                pages_text.append(t.strip())

        full_digital_text = "\n\n".join(pages_text)

        # If digital text exists, return immediately (skips OCR entirely)
        if len(full_digital_text.strip()) > 50:
            return full_digital_text

        # If no digital text found (e.g. scanned marksheet, certificate), run OCR on pages
        if HAS_PYTESSERACT:
            ocr_pages = []
            for page in pdf.pages:
                try:
                    pil_image = page.to_image(resolution=150).original
                    ocr_text = pytesseract.image_to_string(pil_image)
                    if ocr_text and ocr_text.strip():
                        ocr_pages.append(ocr_text.strip())
                except Exception:
                    pass
            return "\n\n".join(ocr_pages)

    return ""
