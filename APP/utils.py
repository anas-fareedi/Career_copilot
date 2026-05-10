from io import BytesIO

import PyPDF2


def extract_text_from_pdf(pdf_content: bytes) -> str:
    """
    Extracts text from a PDF file's content.
    """
    try:
        pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        # Handle potential PyPDF2 errors, e.g., for encrypted or corrupted PDFs
        print(f"Error extracting PDF text: {e}")
        return ""
