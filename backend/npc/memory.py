from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils import embedding_functions


@dataclass(slots=True)
class MemoryRecord:
    text: str
    metadata: Dict[str, str]
    score: float


class MemoryStore:
    """Wrapper around Chroma collections per agent plus a shared ledger."""

    def __init__(self, persist_path: str | Path = "../.chroma") -> None:
        path = Path(persist_path)
        path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(path))
        self._embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        self._collections: Dict[str, Collection] = {}

    def _collection(self, key: str) -> Collection:
        if key not in self._collections:
            self._collections[key] = self._client.get_or_create_collection(
                name=key,
                embedding_function=self._embedding_fn,
            )
        return self._collections[key]

    def add_memory(
        self,
        agent_id: str,
        text: str,
        tags: Sequence[str] | None = None,
        importance: float = 0.5,
    ) -> str:
        collection = self._collection(agent_id)
        memory_id = f"{agent_id}-{collection.count()}"
        metadata: Dict[str, str | float] = {"importance": float(importance)}
        if tags:
            metadata["tags"] = ",".join(tags)
        collection.add(
            ids=[memory_id],
            documents=[text],
            metadatas=[metadata],
        )
        return memory_id

    def fetch_memories(
        self,
        agent_id: str,
        topic: str,
        limit: int = 4,
        include_global: bool = True,
    ) -> List[MemoryRecord]:
        memories: List[MemoryRecord] = []
        ids = [agent_id]
        if include_global:
            ids.append("global")
        for cid in ids:
            collection = self._collection(cid)
            if collection.count() == 0:
                continue
            result = collection.query(query_texts=[topic], n_results=limit)
            docs = result.get("documents", [[]])[0]
            metadatas = result.get("metadatas", [[]])[0]
            distances = result.get("distances", [[]])[0]
            for doc, meta, dist in zip(docs, metadatas, distances):
                memories.append(
                    MemoryRecord(
                        text=doc,
                        metadata=meta or {},
                        score=float(1 - dist),
                    )
                )
        memories.sort(key=lambda rec: rec.score, reverse=True)
        return memories[:limit]

    def seed(self, agent_id: str, entries: Iterable[str]) -> None:
        for text in entries:
            self.add_memory(agent_id, text)

    def reset(self) -> None:
        for name in list(self._collections):
            collection = self._collections.pop(name)
            self._client.delete_collection(collection.name)
