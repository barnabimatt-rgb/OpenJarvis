import pytest
from pathlib import Path
from openjarvis.connectors.obsidian import ObsidianConnector, ObsidianNoteManager
from openjarvis.connectors.obsidian_adapter import ObsidianIndexAdapter
from openjarvis.core.memory_store import MemoryStore
from unittest.mock import MagicMock

def test_obsidian_index_adapter(tmp_path):
    # Setup vault
    vault_path = tmp_path / "vault"
    vault_path.mkdir()
    (vault_path / "Note1.md").write_text("# Heading 1\nContent 1\n# Heading 2\nContent 2")

    connector = ObsidianConnector(str(vault_path))
    store = MemoryStore(str(tmp_path / "memory.db"))
    adapter = ObsidianIndexAdapter(connector, store)

    engine = MagicMock()
    engine.embed.return_value = [0.1] * 128

    adapter.index_vault(engine, "test-model")

    # Verify chunks in store
    chunk1 = store.get_by_id("obsidian:Note1.md:chunk_0")
    assert chunk1 is not None
    assert "Heading 1" in chunk1.content or "Content 1" in chunk1.content

def test_obsidian_note_manager(tmp_path):
    manager = ObsidianNoteManager(tmp_path)
    fpath = manager.create_note("Test Note", "Hello world", folder="Inbox", frontmatter={"tags": ["test"]})

    assert fpath.exists()
    content = fpath.read_text()
    assert "---" in content
    assert "tags: ['test']" in content
    assert "Hello world" in content

    manager.append_to_note("Test Note", "More content")
    content = fpath.read_text()
    assert "More content" in content

def test_obsidian_connector_sync(tmp_path):
    (tmp_path / "Note1.md").write_text("---\ntitle: Note 1\n---\nBody 1")
    connector = ObsidianConnector(str(tmp_path))

    docs = list(connector.sync())
    assert len(docs) == 1
    assert docs[0].title == "Note 1"
    assert "Body 1" in docs[0].content
