import pytest
import numpy as np
from openjarvis.core.memory_store import MemoryStore, MemoryObject
from unittest.mock import MagicMock

def test_memory_store_basic():
    store = MemoryStore(":memory:")
    obj = MemoryObject(id="1", content="test content", metadata={"source": "test"})
    store.store(obj)

    retrieved = store.get_by_id("1")
    assert retrieved.content == "test content"
    assert retrieved.metadata["source"] == "test"

def test_memory_store_search():
    store = MemoryStore(":memory:")
    engine = MagicMock()

    # Mock embeddings
    def mock_embed(text, model=""):
        if "apple" in text: return [1.0, 0.0]
        if "banana" in text: return [0.0, 1.0]
        return [0.5, 0.5]

    engine.embed.side_effect = mock_embed

    store.store(MemoryObject(id="a", content="apple", embedding=[1.0, 0.0]))
    store.store(MemoryObject(id="b", content="banana", embedding=[0.0, 1.0]))

    results = store.search("Tell me about apples", engine, "model")
    assert len(results) > 0
    assert results[0].content == "apple"

def test_knowledge_graph():
    store = MemoryStore(":memory:")
    store.add_entity("e1", "Alice", "person")
    store.add_entity("e2", "Project X", "project")
    store.add_relation("e1", "e2", "works_on")

    results = store.query_graph("e1")
    assert len(results) == 1
    assert results[0]["name"] == "Project X"
    assert results[0]["rel_type"] == "works_on"
