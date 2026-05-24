"""Local embedding index for policy document retrieval."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import hashlib
import json
import math
import re
from typing import Any

from app.services.document_loader import DocumentChunk, chunk_documents, load_documents


EMBEDDING_MODEL_NAME = "local-hashed-char-word-embedding-v1"


class LocalEmbeddingStore:
    """Small deterministic embedding store with cosine search.

    The vectorizer intentionally uses no network calls. It hashes Chinese
    character n-grams and latin/number tokens into a fixed-dimensional vector,
    which is sufficient for policy-document retrieval and easy to replace later.
    """

    def __init__(
        self,
        source_dir: Path,
        index_path: Path,
        dimensions: int = 1024,
    ) -> None:
        self.source_dir = source_dir
        self.index_path = index_path
        self.dimensions = dimensions
        self.chunks: list[DocumentChunk] = []
        self.embeddings: list[dict[int, float]] = []
        self.document_count = 0

    def build(self) -> None:
        documents = load_documents(self.source_dir)
        chunks = chunk_documents(documents)
        self.document_count = len(documents)
        self.chunks = chunks
        self.embeddings = [self.embed(chunk.text) for chunk in chunks]
        self.save()

    def load_or_build(self) -> None:
        if self.index_path.exists():
            self.load()
            return
        self.build()

    def load(self) -> None:
        payload = json.loads(self.index_path.read_text(encoding="utf-8"))
        self.document_count = int(payload.get("document_count", 0))
        self.dimensions = int(payload.get("dimensions", self.dimensions))
        self.chunks = [DocumentChunk(**item) for item in payload.get("chunks", [])]
        self.embeddings = [
            {int(key): float(value) for key, value in item.items()}
            for item in payload.get("embeddings", [])
        ]

    def save(self) -> None:
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        payload: dict[str, Any] = {
            "embedding_model": EMBEDDING_MODEL_NAME,
            "dimensions": self.dimensions,
            "source_dir": str(self.source_dir),
            "document_count": self.document_count,
            "chunks": [asdict(chunk) for chunk in self.chunks],
            "embeddings": [
                {str(key): value for key, value in embedding.items()}
                for embedding in self.embeddings
            ],
        }
        self.index_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def search(self, query: str, top_k: int = 5) -> list[tuple[DocumentChunk, float]]:
        self.load_or_build()
        if not self.chunks:
            return []

        query_embedding = self.embed(query)
        query_terms = _query_terms(query)
        scored = [
            (chunk, _hybrid_score(query_embedding, embedding, query_terms, chunk.text))
            for chunk, embedding in zip(self.chunks, self.embeddings)
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[:top_k]

    def status(self) -> dict[str, Any]:
        if self.index_path.exists() and not self.chunks:
            self.load()
        return {
            "index_path": str(self.index_path),
            "source_dir": str(self.source_dir),
            "document_count": self.document_count,
            "chunk_count": len(self.chunks),
            "embedding_model": EMBEDDING_MODEL_NAME,
            "ready": self.index_path.exists() and bool(self.chunks),
        }

    def embed(self, text: str) -> dict[int, float]:
        features = _features(text)
        counts: dict[int, float] = {}
        for feature in features:
            index = _hash_feature(feature, self.dimensions)
            counts[index] = counts.get(index, 0.0) + 1.0

        norm = math.sqrt(sum(value * value for value in counts.values()))
        if norm == 0:
            return {}
        return {key: value / norm for key, value in counts.items()}


def _features(text: str) -> list[str]:
    normalized = re.sub(r"\s+", "", text.lower())
    features: list[str] = []

    for size in (2, 3, 4):
        features.extend(normalized[index : index + size] for index in range(max(0, len(normalized) - size + 1)))

    words = re.findall(r"[a-z0-9_]+|[\u4e00-\u9fff]{2,}", text.lower())
    features.extend(words)
    return [feature for feature in features if feature.strip()]


def _hash_feature(feature: str, dimensions: int) -> int:
    digest = hashlib.blake2b(feature.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") % dimensions


def _cosine_similarity(left: dict[int, float], right: dict[int, float]) -> float:
    if not left or not right:
        return 0.0
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(index, 0.0) for index, value in left.items())


def _hybrid_score(
    query_embedding: dict[int, float],
    chunk_embedding: dict[int, float],
    query_terms: list[str],
    text: str,
) -> float:
    embedding_score = _cosine_similarity(query_embedding, chunk_embedding)
    if not query_terms:
        return embedding_score

    compact_text = re.sub(r"\s+", "", text)
    hits = sum(1 for term in query_terms if term in compact_text)
    keyword_score = hits / len(query_terms)
    return (embedding_score * 0.7) + (keyword_score * 0.3)


def _query_terms(query: str) -> list[str]:
    compact_query = re.sub(r"\s+", "", query)
    terms = set(re.findall(r"[a-zA-Z0-9_]+", compact_query))
    for keyword in (
        "广东",
        "售电公司",
        "批发用户",
        "日前",
        "实时",
        "现货",
        "中长期",
        "申报",
        "报量",
        "报价",
        "曲线",
        "结算",
        "偏差",
        "考核",
        "限价",
        "出清",
        "信息披露",
        "96点",
        "24点",
        "15分钟",
    ):
        if keyword in compact_query:
            terms.add(keyword)

    for size in (2, 3, 4):
        for index in range(max(0, len(compact_query) - size + 1)):
            token = compact_query[index : index + size]
            if re.fullmatch(r"[\u4e00-\u9fff]+", token):
                terms.add(token)
    return sorted(terms, key=len, reverse=True)
