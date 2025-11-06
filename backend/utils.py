"""import pdfplumber
import io

def extract_text_from_pdf(file_bytes: bytes) -> str:
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                pdf_text = page.extract_text() or ""
                text += pdf_text + "\n\n"
    except Exception as e:
        print(f"Error extracting text from PDF: {e}")
        return ""
    
    return text.strip()"""
import fitz 
import re

def extract_text_from_pdf(file_bytes: bytes) -> str:
    text = ""
    try:
        with fitz.open(stream=file_bytes, filetype="pdf") as doc:
            for page in doc:
                text += page.get_text("text") + "\n\n"
    except Exception as e:
        print(f"Error extracting text with PyMuPDF: {e}")
    return text.strip()

def extract_email(text:str) -> str | None:
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    match = re.search(email_pattern, text)
    return match.group(0) if match else None

def extract_name(text: str) -> str | None:
    lines = text.strip().split('\n')[:5]
    for line in lines:
        name_match = re.search(r'\b[A-Z][a-z]+ [A-Z][a-z]+\b', line)
        if name_match:
            return name_match.group(0)
        
        if not re.search(r'\d|@', line):
            words = line.split()
            if 1 < len(words) <= 4:
                return line.strip()
    return None