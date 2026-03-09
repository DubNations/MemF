from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

    class BaseModel:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
        
        def dict(self):
            return self.__dict__
        
        def json(self):
            return json.dumps(self.__dict__, ensure_ascii=False)
    
    def Field(*args, **kwargs):
        return None


@dataclass
class AtomicKnowledge:
    subject: str
    predicate: str
    object: str
    condition: str = "无"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "condition": self.condition,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AtomicKnowledge":
        return cls(
            subject=data.get("subject", ""),
            predicate=data.get("predicate", ""),
            object=data.get("object", ""),
            condition=data.get("condition", "无"),
        )


@dataclass
class DocumentExtraction:
    knowledge_units: List[AtomicKnowledge] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "knowledge_units": [ku.to_dict() for ku in self.knowledge_units],
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentExtraction":
        return cls(
            knowledge_units=[AtomicKnowledge.from_dict(ku) for ku in data.get("knowledge_units", [])],
        )


class AtomicKnowledgeExtractor:
    def __init__(self, llm_client: Any = None) -> None:
        self.llm_client = llm_client
    
    def get_extraction_prompt(self, text: str) -> List[Dict[str, str]]:
        return [
            {
                "role": "system",
                "content": """你是一个严谨的本体论知识提取引擎。请将以下文本拆解为绝对原子的逻辑三元组和约束条件。

每个知识单元应该是：
- subject: 知识的主体（名词）
- predicate: 动作或关系（动词，如'导致', '依赖于', '等于', '说明', '表明'）
- object: 知识的客体或结果（名词）
- condition: 这个逻辑成立的前置条件，如果没有则填'无'

例如：
- subject="利率下降", predicate="导致", object="资产价格上涨", condition="流动性未陷阱时"
- subject="公司营收增长", predicate="表明", object="经营状况改善", condition="无"

请确保每个逻辑单元都是原子的，不要包含多个逻辑关系。输出JSON格式。""",
            },
            {
                "role": "user",
                "content": f"请从以下文本中提取原子知识单元：\n\n{text}",
            },
        ]
    
    def extract(self, text: str, max_units: int = 20) -> DocumentExtraction:
        if self.llm_client is None:
            return self._fallback_extract(text, max_units)
        
        try:
            messages = self.get_extraction_prompt(text)
            response = self.llm_client.chat(messages)
            
            content = response.content if hasattr(response, 'content') else str(response)
            
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            
            if json_start >= 0 and json_end > json_start:
                json_str = content[json_start:json_end]
                data = json.loads(json_str)
                return DocumentExtraction.from_dict(data)
        except Exception:
            pass
        
        return self._fallback_extract(text, max_units)
    
    def _fallback_extract(self, text: str, max_units: int = 20) -> DocumentExtraction:
        import re
        
        sentences = re.split(r'[。！？.!?]', text)
        units: List[AtomicKnowledge] = []
        
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue
            
            words = sentence.split()
            if len(words) >= 3:
                subject = words[0] if len(words) > 0 else ""
                predicate = words[1] if len(words) > 1 else "相关"
                obj = " ".join(words[2:6]) if len(words) > 2 else ""
                
                if subject and obj:
                    units.append(AtomicKnowledge(
                        subject=subject,
                        predicate=predicate,
                        object=obj,
                        condition="无",
                    ))
            
            if len(units) >= max_units:
                break
        
        return DocumentExtraction(knowledge_units=units)
