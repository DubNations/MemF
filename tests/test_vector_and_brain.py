from pathlib import Path

from cognitive_os.brain.assistant import PersonalKnowledgeAssistant
from cognitive_os.brain.toolkit import BrainToolkit
from cognitive_os.core.cognition_loop import CognitiveLoop
from cognitive_os.memory.repository import MemoryPlane
from cognitive_os.skills.registry import SkillManager
from cognitive_os.vector.vector_store import LocalVectorDB


def test_vector_retrieval_and_brain_fallback(tmp_path: Path):
    memory = MemoryPlane(tmp_path / "m.db")
    loop = CognitiveLoop(memory, SkillManager())
    vec = LocalVectorDB(tmp_path / "v.db")
    toolkit = BrainToolkit(memory, loop, vec)
    assistant = PersonalKnowledgeAssistant(toolkit)

    vec.upsert("k1", "营销客服必须遵循国家广告法，不得夸大收益", {"confidence": 0.8, "source": "human_verified", "conflict_count": 0, "topic": "policy"})
    vec.upsert("k2", "客服可以随意承诺高收益", {"confidence": 0.4, "source": "public", "conflict_count": 2, "topic": "policy"})

    result = assistant.handle_query("请给营销客服回复建议", scenario="marketing_customer_service_assistant")
    assert len(result.retrieved) >= 1
    assert result.model in {"local-fallback", "Pro/deepseek-ai/DeepSeek-V3.2"}
    assert any(t["tool"] == "vector_retrieve" for t in result.tool_trace)
