from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Message:
    id: str
    sender: str
    content: Any
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "sender": self.sender,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


@dataclass
class MessageQueue:
    messages: List[Message] = field(default_factory=list)
    
    def __init__(self, max_size: int = 100):
        self._messages: List[Message] = []
        self._max_size = max_size
    
    def push(self, message: Message) -> None:
        self._messages.append(message)
        if len(self._messages) > self._max_size:
            self._messages = self._messages[-self._max_size:]
    
    def pop(self) -> Optional[Message]:
        if not self._messages:
            return None
        return self._messages.pop(0)
    
    def peek(self, n: int = 1) -> Optional[Message]:
        return self._messages[-n:] if n > 0 else None
    
    def clear(self) -> None:
        self._messages = []
    
    def get_all(self) -> List[Message]:
        return self._messages.copy()
    
    def size(self) -> int:
        return len(self._messages)


    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "messages": [m.to_dict() for m in self._messages],
            "max_size": self._max_size,
        }


