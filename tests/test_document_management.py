from pathlib import Path

from cognitive_os.brain.toolkit import BrainToolkit
from cognitive_os.core.cognition_loop import CognitiveLoop
from cognitive_os.memory.repository import MemoryPlane
from cognitive_os.skills.registry import SkillManager
from cognitive_os.vector.vector_store import LocalVectorDB


def _setup(tmp_path: Path):
    memory = MemoryPlane(tmp_path / "m.db")
    loop = CognitiveLoop(memory, SkillManager())
    vec = LocalVectorDB(tmp_path / "v.db")
    toolkit = BrainToolkit(memory, loop, vec)
    return memory, vec, toolkit


def test_update_and_delete_document_record_and_vectors(tmp_path: Path):
    memory, vec, toolkit = _setup(tmp_path)
    doc_id = memory.save_document_record(
        {
            "filename": "a.pdf",
            "format": "pdf",
            "status": "OK",
            "sections": 1,
            "text_length": 10,
            "scenario": "general",
            "message": "init",
            "knowledge_base_id": None,
            "mime_type": "application/pdf",
            "file_size_bytes": 10,
        }
    )
    vec.upsert("k1", "text", {"document_id": doc_id})

    ok = toolkit.update_document(doc_id, scenario="finance", message="updated")
    assert ok is True
    docs = memory.load_documents(limit=5)
    assert docs[0]["scenario"] == "finance"
    assert docs[0]["message"] == "updated"

    ret = toolkit.delete_document(doc_id)
    assert ret["deleted"] is True
    assert ret["removed_vectors"] == 1
    assert memory.load_documents(limit=5) == []
