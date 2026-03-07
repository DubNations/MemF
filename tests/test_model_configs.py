from pathlib import Path

from cognitive_os.memory.repository import MemoryPlane


def test_get_model_config_by_id_and_default_independent(tmp_path: Path):
    memory = MemoryPlane(tmp_path / "m.db")
    a = memory.save_model_config(
        {
            "name": "a",
            "provider": "siliconflow",
            "model": "m1",
            "api_key_masked": "sk****",
            "api_key_secret": "sk-a",
            "timeout_sec": 30,
            "context_window": 4096,
            "temperature": 0.2,
            "is_default": True,
            "status": "unknown",
        }
    )
    b = memory.save_model_config(
        {
            "name": "b",
            "provider": "siliconflow",
            "model": "m2",
            "api_key_masked": "sk****",
            "api_key_secret": "sk-b",
            "timeout_sec": 45,
            "context_window": 8192,
            "temperature": 0.3,
            "is_default": False,
            "status": "unknown",
        }
    )

    active = memory.get_active_model_config()
    assert active is not None
    assert active["id"] == a["id"]

    cfg_b = memory.get_model_config_by_id(b["id"])
    assert cfg_b is not None
    assert cfg_b["id"] == b["id"]
    assert cfg_b["api_key"] == "sk-b"

    active_after = memory.get_active_model_config()
    assert active_after is not None
    assert active_after["id"] == a["id"]
