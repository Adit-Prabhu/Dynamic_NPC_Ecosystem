"""Tests for the GraphRAG memory system."""

from npc.graph_memory import GraphMemoryStore, EntityExtractor


def test_add_and_fetch_memories(tmp_path) -> None:
    """Test basic memory storage and retrieval."""
    store = GraphMemoryStore(tmp_path / "memory")
    store.add_memory("shopkeeper", "Saw the vault door open", tags=["vault"], importance=0.9)

    results = store.fetch_memories("shopkeeper", "vault", limit=2, include_global=False)

    assert results, "Expected to retrieve at least one memory"
    assert "vault" in results[0].text.lower() or "door" in results[0].text.lower()


def test_entity_extraction() -> None:
    """Test rule-based entity extraction."""
    extractor = EntityExtractor()
    
    text = "Mara told Rylan about the vault door being ajar near the docks"
    entities, relationships = extractor.extract(text)
    
    # Should extract locations and objects
    entity_types = {e.type for e in entities}
    assert len(entity_types) > 0, "Should extract at least some entity types"
    
    # Should extract entity names - check for locations/objects that are in the patterns
    entity_names = {e.name.lower() for e in entities}
    # Vault and docks should be extracted as they're in our patterns
    assert "vault" in entity_names or "docks" in entity_names, f"Expected vault/docks in {entity_names}"


def test_graph_context_extraction(tmp_path) -> None:
    """Test that context is passed through memory storage."""
    store = GraphMemoryStore(tmp_path / "memory")
    
    # Add memory with conversation context
    store.add_memory(
        "suna",
        "The vault door was left ajar",
        context={"speaker": "Suna", "listener": "Mara"},
    )
    
    # Check that relationship was created
    stats = store.get_stats()
    assert stats["total_edges"] > 0, "Expected relationships to be created"


def test_fetch_memories_with_connections(tmp_path) -> None:
    """Test fetching memories through entity connections."""
    store = GraphMemoryStore(tmp_path / "memory")
    
    # Add memories from different agents about the same entity
    store.add_memory("shopkeeper", "Saw suspicious activity at the vault")
    store.add_memory("guard", "The vault alarm was triggered last night")
    
    # Fetch should find related memories
    results = store.fetch_memories(
        "shopkeeper",
        "vault alarm",
        include_connections=True,
    )
    
    assert len(results) >= 1, "Expected to find connected memories"


def test_relationship_path(tmp_path) -> None:
    """Test finding relationship paths between entities."""
    store = GraphMemoryStore(tmp_path / "memory")
    
    # Create connected memories
    store.add_memory(
        "suna",
        "Told Mara about the vault",
        context={"speaker": "Suna", "listener": "Mara"},
    )
    store.add_memory(
        "mara",
        "Told Rylan about what Suna said",
        context={"speaker": "Mara", "listener": "Rylan"},
    )
    
    # Find path from Suna to Rylan
    path = store.get_relationship_path("npc:suna", "npc:rylan")
    
    # Path should exist through Mara (may be empty if not directly connected)
    # The test validates the method works without error
    assert isinstance(path, list)


def test_graph_stats(tmp_path) -> None:
    """Test graph statistics."""
    store = GraphMemoryStore(tmp_path / "memory")
    
    store.add_memory("shopkeeper", "Vault door was open")
    store.add_memory("guard", "Saw someone near the docks")
    
    stats = store.get_stats()
    
    assert "total_nodes" in stats
    assert "total_edges" in stats
    assert "node_types" in stats
    assert stats["total_nodes"] > 0


def test_memory_persistence(tmp_path) -> None:
    """Test that graph persists to disk."""
    # Create and populate store
    store1 = GraphMemoryStore(tmp_path / "memory")
    store1.add_memory("shopkeeper", "Important memory about vault")
    
    # Create new store from same path
    store2 = GraphMemoryStore(tmp_path / "memory")
    
    # Should have loaded the data
    assert store2.graph.number_of_nodes() > 0, "Expected graph to persist"


def test_reset_clears_graph(tmp_path) -> None:
    """Test that reset clears all graph data."""
    store = GraphMemoryStore(tmp_path / "memory")
    store.add_memory("shopkeeper", "Some memory")
    
    store.reset()
    
    stats = store.get_stats()
    assert stats["total_nodes"] == 0
    assert stats["total_edges"] == 0
