import pytest
from unittest.mock import patch, Mock
import src.files as files

def test_extract_text_pdf():
    # Mock fitz
    with patch('src.files.fitz') as mock_fitz:
        mock_doc = Mock()
        mock_page = Mock()
        mock_page.get_text.return_value = "PDF text"
        mock_doc.__iter__.return_value = [mock_page]
        mock_fitz.open.return_value = mock_doc
        
        result = files.extract_text("test.pdf", "pdf")
        assert result == "PDF text"

def test_extract_text_docx():
    with patch('src.files.Document') as mock_doc:
        mock_para = Mock()
        mock_para.text = "DOCX text"
        mock_doc.return_value.paragraphs = [mock_para]
        
        result = files.extract_text("test.docx", "docx")
        assert result == "DOCX text"

def test_extract_text_txt():
    with patch('builtins.open', create=True) as mock_open:
        mock_file = Mock()
        mock_file.read.return_value = "TXT content"
        mock_open.return_value.__enter__.return_value = mock_file
        
        result = files.extract_text("test.txt", "txt")
        assert result == "TXT content"