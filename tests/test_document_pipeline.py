import base64
import io
import zipfile

from cognitive_os.ingestion.document_pipeline import DocumentPipeline


def _mk_docx_base64(text: str) -> str:
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, "w") as zf:
        xml = (
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            f'<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>'
        )
        zf.writestr("word/document.xml", xml)
    return base64.b64encode(bio.getvalue()).decode("ascii")


def test_docx_parse_and_mapping():
    b64 = _mk_docx_base64("政策条款A：不得夸大收益")
    result, text = DocumentPipeline.parse_base64_document("policy.docx", b64)
    assert result.status == "OK"
    assert "夸大收益" in text
    units = DocumentPipeline.to_knowledge_units("policy.docx", text, scenario="marketing_customer_service")
    assert len(units) >= 1


def test_pdf_reject_invalid_base64():
    result, text = DocumentPipeline.parse_base64_document("policy.pdf", "bad")
    assert result.status == "FAILED"
    assert result.message == "invalid_base64"
    assert text == ""
