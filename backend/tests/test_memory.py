from npc.memory import MemoryStore


def test_add_and_fetch_memories(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    store.add_memory("shopkeeper", "Saw the vault door open", tags=["vault"], importance=0.9)

    results = store.fetch_memories("shopkeeper", "vault", limit=2, include_global=False)

    assert results, "Expected to retrieve at least one memory"
    assert "vault door open" in results[0].text.lower()
