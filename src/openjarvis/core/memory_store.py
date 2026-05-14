"""Ultimate Memory Subsystem — FAISS + SQLite + Knowledge Graph."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class MemoryObject:
    """A single piece of information stored in memory."""
    id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    embedding: Optional[List[float]] = None

class MemoryStore:
    """Hybrid memory store combining vector search and relational data.

    Provides a unified interface for session memory (short-term) and
    persistent facts (long-term).
    """

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()
        self._index: Any = None # FAISS index
        self._id_map: List[str] = [] # Maps index position to SQL ID
        self._last_index_sync: float = 0

    def _init_db(self):
        with self._conn:
            # Main content table
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_chunks (
                    id TEXT PRIMARY KEY,
                    content TEXT,
                    metadata TEXT,
                    timestamp REAL,
                    source TEXT,
                    doc_type TEXT,
                    is_fact INTEGER DEFAULT 0,
                    embedding BLOB
                )
            """)
            # Knowledge Graph entities
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_entities (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    properties TEXT
                )
            """)
            # Knowledge Graph relations
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS kg_relations (
                    source_id TEXT,
                    target_id TEXT,
                    type TEXT,
                    weight REAL,
                    properties TEXT,
                    PRIMARY KEY (source_id, target_id, type)
                )
            """)

    def store(self, obj: MemoryObject, engine: Optional[Any] = None, model: str = ""):
        """Store a memory object, optionally computing embeddings."""
        embedding_blob = None
        if engine and not obj.embedding:
            obj.embedding = engine.embed(obj.content, model=model)

        if obj.embedding:
            embedding_blob = np.array(obj.embedding).astype("float32").tobytes()

        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO memory_chunks (id, content, metadata, timestamp, source, doc_type, embedding) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    obj.id,
                    obj.content,
                    json.dumps(obj.metadata),
                    obj.timestamp,
                    obj.metadata.get("source", ""),
                    obj.metadata.get("doc_type", ""),
                    embedding_blob
                )
            )
        # Mark index as stale
        self._index = None

    def search(self, query: str, engine: Any, model: str, top_k: int = 5) -> List[MemoryObject]:
        """Perform semantic search using FAISS."""
        embedding = engine.embed(query, model=model)
        if not embedding:
            return []

        if self._index is None:
            self._refresh_index()

        if self._index is None or self._index.ntotal == 0:
            return []

        xq = np.array([embedding]).astype("float32")
        D, I = self._index.search(xq, top_k)

        results = []
        for idx in I[0]:
            if idx == -1: continue
            mem_id = self._id_map[idx]
            obj = self.get_by_id(mem_id)
            if obj:
                results.append(obj)
        return results

    def get_by_id(self, mem_id: str) -> Optional[MemoryObject]:
        cursor = self._conn.execute("SELECT * FROM memory_chunks WHERE id = ?", (mem_id,))
        row = cursor.fetchone()
        if row:
            return MemoryObject(
                id=row["id"],
                content=row["content"],
                metadata=json.loads(row["metadata"]),
                timestamp=row["timestamp"]
            )
        return None

    def _refresh_index(self):
        """Rebuild the FAISS index from stored chunks."""
        import faiss

        cursor = self._conn.execute("SELECT id, embedding FROM memory_chunks WHERE embedding IS NOT NULL")
        rows = cursor.fetchall()

        if not rows:
            return

        embeddings = []
        self._id_map = []
        for row in rows:
            emb = np.frombuffer(row["embedding"], dtype="float32")
            embeddings.append(emb)
            self._id_map.append(row["id"])

        if embeddings:
            xb = np.array(embeddings).astype("float32")
            self._index = faiss.IndexFlatL2(xb.shape[1])
            self._index.add(xb)
            self._last_index_sync = time.time()

    # -- Knowledge Graph Implementation ---------------------------------------

    def add_entity(self, entity_id: str, name: str, etype: str, properties: Dict[str, Any] = None):
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO kg_entities (id, name, type, properties) VALUES (?, ?, ?, ?)",
                (entity_id, name, etype, json.dumps(properties or {}))
            )

    def add_relation(self, source_id: str, target_id: str, rtype: str, weight: float = 1.0):
        with self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO kg_relations (source_id, target_id, type, weight, properties) VALUES (?, ?, ?, ?, ?)",
                (source_id, target_id, rtype, weight, "{}")
            )

    def query_graph(self, entity_id: str) -> List[Dict[str, Any]]:
        """Retrieve neighboring entities and their relations."""
        cursor = self._conn.execute("""
            SELECT e.*, r.type as rel_type, r.weight
            FROM kg_entities e
            JOIN kg_relations r ON e.id = r.target_id
            WHERE r.source_id = ?
        """, (entity_id,))
        return [dict(row) for row in cursor.fetchall()]

    def close(self):
        self._conn.close()

__all__ = ["MemoryObject", "MemoryStore"]
