import fitz  # PyMuPDF
from docx import Document
import os

def extract_text(file_path, file_type):
    try:
        if file_type == "pdf":
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            return text
        elif file_type == "docx":
            doc = Document(file_path)
            text = ""
            for para in doc.paragraphs:
                text += para.text + "\n"
            return text
        elif file_type == "xlsx" or file_type == "xls":
            try:
                import openpyxl
                wb = openpyxl.load_workbook(file_path, data_only=True)
                text = ""
                for sheet in wb.sheetnames:
                    ws = wb[sheet]
                    text += f"Sheet: {sheet}\n"
                    for row in ws.iter_rows(values_only=True):
                        text += " | ".join(str(cell) if cell is not None else "" for cell in row) + "\n"
                    text += "\n"
                return text
            except ImportError:
                return ""
        elif file_type == "image":
            return ""  # Images don't have extractable text
        elif file_type == "txt":
            with open(file_path, 'r', encoding='utf-8') as f:
                return f.read()
        else:
            return ""
    except:
        return ""