import base64
from pathlib import Path

from cognitive_os.brain.toolkit import BrainToolkit
from cognitive_os.core.cognition_loop import CognitiveLoop
from cognitive_os.memory.repository import MemoryPlane
from cognitive_os.skills.registry import SkillManager
from cognitive_os.vector.vector_store import LocalVectorDB


def _toolkit(tmp_path: Path) -> BrainToolkit:
    memory = MemoryPlane(tmp_path / "m.db")
    loop = CognitiveLoop(memory, SkillManager())
    vec = LocalVectorDB(tmp_path / "v.db")
    return BrainToolkit(memory, loop, vec)


def test_validate_upload_accepts_octet_stream_for_docx(tmp_path: Path):
    toolkit = _toolkit(tmp_path)
    raw = b"dummy-docx-content"
    b64 = base64.b64encode(raw).decode("ascii")
    ret = toolkit.validate_upload("demo.docx", "application/octet-stream", b64)
    assert ret["ok"] is True
    assert ret["size"] == len(raw)


def test_validate_upload_rejects_bad_base64(tmp_path: Path):
    toolkit = _toolkit(tmp_path)
    ret = toolkit.validate_upload("demo.pdf", "application/pdf", "bad###")
    assert ret["ok"] is False
    assert ret["code"] == "INVALID_BASE64"


def test_validate_upload_accepts_data_url_and_whitespace(tmp_path: Path):
    toolkit = _toolkit(tmp_path)
    raw = b"hello-pdf"
    b64 = base64.b64encode(raw).decode("ascii")
    data_url = f"data:application/pdf;base64,{b64}\n"
    ret = toolkit.validate_upload("demo.pdf", "application/pdf", data_url)
    assert ret["ok"] is True
    assert ret["size"] == len(raw)
    assert ret["normalized_base64"] == b64
