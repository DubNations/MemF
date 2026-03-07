import sqlite3
from pathlib import Path

from cognitive_os.memory.repository import MemoryPlane


def test_migrate_legacy_schema_for_documents_and_model_configs(tmp_path: Path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            format TEXT NOT NULL,
            status TEXT NOT NULL,
            sections INTEGER NOT NULL,
            text_length INTEGER NOT NULL,
            scenario TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE model_configs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            api_key_masked TEXT NOT NULL,
            api_key_secret TEXT NOT NULL,
            timeout_sec INTEGER NOT NULL,
            context_window INTEGER NOT NULL,
            temperature REAL NOT NULL,
            is_default INTEGER NOT NULL DEFAULT 0,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.close()

    memory = MemoryPlane(db)

    # migration should make read paths compatible with latest code
    docs = memory.load_documents(limit=5)
    assert docs == []

    saved = memory.save_model_config(
        {
            "name": "legacy-ok",
            "provider": "siliconflow",
            "model": "m",
            "api_key_masked": "****",
            "api_key_secret": "sk-test",
            "timeout_sec": 30,
            "context_window": 2048,
            "temperature": 0.2,
            "is_default": True,
            "status": "unknown",
        }
    )
    assert saved["id"] > 0
    items = memory.list_model_configs()
    assert len(items) == 1
    assert "status" in items[0]
