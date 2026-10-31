import pdfplumber
import os

try:
    import pytesseract
    if os.name == 'nt' and os.path.exists(r'C:\Program Files\Tesseract-OCR\tesseract.exe'):
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    HAS_PYTESSERACT = True
except Exception:
    HAS_PYTESSERACT = False

def extract_text_hybrid(pdf_path):
    extracted_text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text and text.strip():
                extracted_text += f"\n{text}"
            elif HAS_PYTESSERACT:
                try:
                    pil_image = page.to_image(resolution=300).original
                    ocr_text = pytesseract.image_to_string(pil_image)
                    extracted_text += f"\n{ocr_text}"
                except Exception:
                    pass
    return extracted_text
