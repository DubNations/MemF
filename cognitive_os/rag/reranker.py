from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


@dataclass
class RerankResult:
    text: str
    score: float
    original_score: float
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "score": self.score,
            "original_score": self.original_score,
            "metadata": self.metadata,
        }


class Reranker(ABC):
    @abstractmethod
    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_n: int = 5) -> List[RerankResult]:
        pass


class CohereReranker(Reranker):
    def __init__(self, api_key: Optional[str] = None, model: str = "rerank-multilingual-v3.0"):
        self._api_key = api_key
        self._model = model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import cohere
                self._client = cohere.Client(self._api_key)
            except ImportError:
                raise ImportError("cohere package not installed. Run: pip install cohere")
        return self._client

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_n: int = 5) -> List[RerankResult]:
        if not candidates:
            return []

        try:
            client = self._get_client()
            documents = [c.get("text", c.get("content", "")) for c in candidates]

            response = client.rerank(
                model=self._model,
                query=query,
                documents=documents,
                top_n=min(top_n, len(documents)),
            )

            results = []
            for item in response.results:
                idx = item.index
                results.append(RerankResult(
                    text=documents[idx],
                    score=item.relevance_score,
                    original_score=candidates[idx].get("score", 0.0),
                    metadata=candidates[idx].get("metadata", {}),
                ))
            return results
        except Exception:
            return self._fallback_rerank(query, candidates, top_n)

    def _fallback_rerank(self, query: str, candidates: List[Dict[str, Any]], top_n: int) -> List[RerankResult]:
        query_words = set(query.lower().split())
        scored = []
        for c in candidates:
            text = c.get("text", c.get("content", ""))
            text_words = set(text.lower().split())
            overlap = len(query_words & text_words) / max(1, len(query_words))
            score = c.get("score", 0.5) * 0.7 + overlap * 0.3
            scored.append(RerankResult(
                text=text,
                score=score,
                original_score=c.get("score", 0.5),
                metadata=c.get("metadata", {}),
            ))
        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_n]


class CrossEncoderReranker(Reranker):
    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self._model_name = model_name
        self._model = None

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self._model_name)
            except ImportError:
                raise ImportError("sentence-transformers not installed. Run: pip install sentence-transformers")
        return self._model

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_n: int = 5) -> List[RerankResult]:
        if not candidates:
            return []

        try:
            model = self._get_model()
            documents = [c.get("text", c.get("content", "")) for c in candidates]
            pairs = [(query, doc) for doc in documents]

            scores = model.predict(pairs)

            results = []
            for i, score in enumerate(scores):
                results.append(RerankResult(
                    text=documents[i],
                    score=float(score),
                    original_score=candidates[i].get("score", 0.0),
                    metadata=candidates[i].get("metadata", {}),
                ))

            results.sort(key=lambda x: x.score, reverse=True)
            return results[:top_n]
        except Exception:
            return self._simple_rerank(query, candidates, top_n)

    def _simple_rerank(self, query: str, candidates: List[Dict[str, Any]], top_n: int) -> List[RerankResult]:
        results = []
        for c in candidates:
            text = c.get("text", c.get("content", ""))
            results.append(RerankResult(
                text=text,
                score=c.get("score", 0.5),
                original_score=c.get("score", 0.5),
                metadata=c.get("metadata", {}),
            ))
        return results[:top_n]


class LocalReranker(Reranker):
    def __init__(self):
        pass

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_n: int = 5) -> List[RerankResult]:
        if not candidates:
            return []

        query_lower = query.lower()
        query_words = set(query_lower.split())

        results = []
        for c in candidates:
            text = c.get("text", c.get("content", ""))
            text_lower = text.lower()
            text_words = set(text_lower.split())

            word_overlap = len(query_words & text_words) / max(1, len(query_words))

            phrase_bonus = 0.0
            for phrase in query_lower.split():
                if phrase in text_lower:
                    phrase_bonus += 0.1

            length_penalty = min(1.0, len(text) / 500)

            original_score = c.get("score", 0.5)
            final_score = (
                original_score * 0.5 +
                word_overlap * 0.3 +
                phrase_bonus * 0.1 +
                length_penalty * 0.1
            )

            results.append(RerankResult(
                text=text,
                score=final_score,
                original_score=original_score,
                metadata=c.get("metadata", {}),
            ))

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:top_n]


class RerankerFactory:
    _registry: Dict[str, type] = {
        "cohere": CohereReranker,
        "cross-encoder": CrossEncoderReranker,
        "local": LocalReranker,
    }

    @classmethod
    def create(
        cls,
        supplier: str = "local",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs: Any,
    ) -> Reranker:
        supplier_lower = supplier.lower()

        if supplier_lower == "cohere":
            return CohereReranker(
                api_key=api_key,
                model=model or "rerank-multilingual-v3.0",
            )
        elif supplier_lower == "cross-encoder":
            return CrossEncoderReranker(
                model_name=model or "cross-encoder/ms-marco-MiniLM-L-6-v2",
            )
        else:
            return LocalReranker()

    @classmethod
    def register(cls, name: str, reranker_class: type) -> None:
        cls._registry[name.lower()] = reranker_class

    @classmethod
    def available_rerankers(cls) -> List[str]:
        return list(cls._registry.keys())
