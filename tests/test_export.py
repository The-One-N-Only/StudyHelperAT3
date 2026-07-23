import pytest
from unittest.mock import Mock, patch, MagicMock
import io

import src.export as export


SAMPLE_ITEM = {
    "title": "Test Article",
    "summary": "A summary of the article.",
    "bullets": ["Point one", "Point two"],
    "citation_apa": "Author, A. (2023). Test Article. Journal of Tests.",
    "citation_harvard": "Author (2023) 'Test Article', Journal of Tests.",
}

ATN = "Research Essay"


def _mock_reportlab(monkeypatch):
    """Replace reportlab classes so Paragraph never tries to parse a mocked style."""
    monkeypatch.setattr(export, "Paragraph", MagicMock())
    monkeypatch.setattr(export, "Spacer", MagicMock())
    monkeypatch.setattr(export, "ListFlowable", MagicMock())
    monkeypatch.setattr(export, "ListItem", MagicMock())
    monkeypatch.setattr(export, "getSampleStyleSheet", lambda: MagicMock())
    monkeypatch.setattr(export, "ParagraphStyle", lambda name, parent: MagicMock())


class TestExportPdf:
    def test_exports_pdf_with_atn(self, monkeypatch):
        fake_doc = MagicMock()
        monkeypatch.setattr(export, "SimpleDocTemplate", lambda buffer, pagesize: fake_doc)
        _mock_reportlab(monkeypatch)
        result = export.export_pdf([SAMPLE_ITEM], atn=ATN, citation_format="apa")
        assert isinstance(result, bytes)
        fake_doc.build.assert_called_once()

    def test_exports_pdf_harvard_format(self, monkeypatch):
        fake_doc = MagicMock()
        monkeypatch.setattr(export, "SimpleDocTemplate", lambda buffer, pagesize: fake_doc)
        _mock_reportlab(monkeypatch)
        result = export.export_pdf([SAMPLE_ITEM], citation_format="harvard")
        assert isinstance(result, bytes)

    def test_exports_pdf_empty_items(self, monkeypatch):
        fake_doc = MagicMock()
        monkeypatch.setattr(export, "SimpleDocTemplate", lambda buffer, pagesize: fake_doc)
        _mock_reportlab(monkeypatch)
        result = export.export_pdf([])
        assert isinstance(result, bytes)


class TestExportDocx:
    def test_exports_docx_with_atn(self, monkeypatch):
        fake_doc = MagicMock()
        monkeypatch.setattr(export, "Document", lambda: fake_doc)
        result = export.export_docx([SAMPLE_ITEM], atn=ATN, citation_format="apa")
        assert isinstance(result, bytes)
        fake_doc.save.assert_called_once()

    def test_exports_docx_harvard_format(self, monkeypatch):
        fake_doc = MagicMock()
        monkeypatch.setattr(export, "Document", lambda: fake_doc)
        result = export.export_docx([SAMPLE_ITEM], citation_format="harvard")
        assert isinstance(result, bytes)

    def test_exports_docx_empty_items(self, monkeypatch):
        fake_doc = MagicMock()
        monkeypatch.setattr(export, "Document", lambda: fake_doc)
        result = export.export_docx([])
        assert isinstance(result, bytes)
