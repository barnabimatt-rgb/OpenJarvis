"""Obsidian Index Adapter — bridges the vault and the MemoryStore."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List, Optional

from openjarvis.connectors.obsidian import ObsidianConnector
from openjarvis.core.memory_store import MemoryObject, MemoryStore

class ObsidianIndexAdapter:
    """Adapts Obsidian Documents for ingestion into MemoryStore."""

    def __init__(self, connector: ObsidianConnector, store: MemoryStore):
        self._connector = connector
        self._store = store

    def index_vault(self, engine: Any, model: str):
        """Sync the vault and index all documents into the memory store."""
        for doc in self._connector.sync():
            # Basic semantic chunking by heading
            chunks = self._chunk_by_headings(doc.content)
            for i, chunk in enumerate(chunks):
                obj = MemoryObject(
                    id=f"{doc.doc_id}:chunk_{i}",
                    content=chunk,
                    metadata={
                        **doc.metadata,
                        "source": "obsidian",
                        "title": doc.title,
                        "path": doc.doc_id,
                        "chunk_index": i
                    }
                )
                self._store.store(obj, engine=engine, model=model)

    def _chunk_by_headings(self, text: str) -> List[str]:
        """Split markdown text by # headings."""
        # Split by lines starting with #
        parts = re.split(r'(?m)^#+\s', text)
        return [p.strip() for p in parts if p.strip()]

__all__ = ["ObsidianIndexAdapter"]
