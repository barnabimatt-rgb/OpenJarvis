"""Obsidian-backed memory backend.

Stores new memories as Markdown notes inside an Obsidian vault AND indexes
them into SQLite/FTS5 for fast full-text retrieval.  This gives the user a
human-readable, editable knowledge base in Obsidian while keeping sub-second
search via the existing SQLite backend.

Usage (config.toml):
    [tools.storage]
    default_backend = "obsidian"
    vault_path      = "~/second-brain"
    db_path         = "~/.openjarvis/memory.db"
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.core.registry import ConnectorRegistry, MemoryRegistry
from openjarvis.tools.storage._stubs import MemoryBackend, RetrievalResult
from openjarvis.tools.storage.sqlite import SQLiteMemory


@MemoryRegistry.register("obsidian")
class ObsidianMemoryBackend(MemoryBackend):
    """Write memories to an Obsidian vault and index them in SQLite for retrieval.

    Every call to :meth:`store` does two things:
    1. Creates (or appends to) a Markdown note in ``<vault_path>/<folder>/``.
    2. Persists the content in SQLite/FTS5 so :meth:`retrieve` is instant.

    The vault is the source of truth for human editing; SQLite is the search
    index.  Run :meth:`sync_vault` at startup to rebuild the index from the
    current vault contents.
    """

    backend_id = "obsidian"

    def __init__(
        self,
        vault_path: str = "",
        db_path: str = "",
    ) -> None:
        resolved_vault = str(Path(vault_path).expanduser()) if vault_path else ""
        self._connector = ConnectorRegistry.get("obsidian")(vault_path=resolved_vault)
        self._sqlite = SQLiteMemory(db_path=db_path)

    # ------------------------------------------------------------------
    # MemoryBackend interface
    # ------------------------------------------------------------------

    def store(
        self,
        content: str,
        *,
        source: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Persist *content* to the vault and the SQLite index.

        Metadata keys used:
        - ``title``  — note filename (derived from content[:60] if absent)
        - ``folder`` — vault subfolder (default ``Jarvis/Memories``)
        """
        meta = metadata or {}
        title: str = meta.get("title") or source or content[:60].replace("\n", " ").strip()
        folder: str = meta.get("folder", "Jarvis/Memories")

        if self._connector.is_connected():
            note_path = self._connector.create_note(title, content, folder=folder)
            source = source or str(note_path)

        return self._sqlite.store(content, source=source, metadata=metadata)

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        **kwargs: Any,
    ) -> List[RetrievalResult]:
        """Full-text search over the SQLite index."""
        return self._sqlite.retrieve(query, top_k=top_k, **kwargs)

    def delete(self, doc_id: str) -> bool:
        """Remove a document from the SQLite index (vault note is kept)."""
        return self._sqlite.delete(doc_id)

    def clear(self) -> None:
        """Clear the SQLite index (vault notes are NOT deleted)."""
        self._sqlite.clear()

    # ------------------------------------------------------------------
    # Vault sync
    # ------------------------------------------------------------------

    def sync_vault(self) -> int:
        """Index all existing vault notes into SQLite.

        Call this once at startup (or after manually editing the vault) to
        ensure the search index reflects the current vault contents.  Already-
        indexed chunks are deduplicated by SQLite's ``INSERT OR IGNORE``.

        Returns the number of chunks indexed.
        """
        from openjarvis.tools.storage.chunking import ChunkConfig, chunk_text

        cfg = ChunkConfig()
        count = 0
        for doc in self._connector.sync():
            for chunk in chunk_text(doc.content, cfg):
                self._sqlite.store(
                    chunk.text,
                    source=doc.doc_id,
                    metadata={"title": doc.title, "url": doc.url},
                )
                count += 1
        return count
