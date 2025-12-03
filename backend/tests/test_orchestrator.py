from npc.llm import DialogueResult, TemplateDialogueModel
from npc.memory import MemoryStore
from npc.orchestrator import Orchestrator


class DummyModel(TemplateDialogueModel):
    def generate(self, **kwargs):  # type: ignore[override]
        speaker = kwargs["speaker"]
        listener = kwargs["listener"]
        return DialogueResult(
            utterance=f"{speaker.name} quietly updates {listener.name}",
            rumor_delta=0.15,
            sentiment="worried",
            new_memory="Rumor noted",
        )


def test_orchestrator_step_updates_world_state(tmp_path) -> None:
    store = MemoryStore(tmp_path / "memory")
    orchestrator = Orchestrator(
        memory_store=store,
        model=DummyModel(seed=42),
        personalities=["shopkeeper", "guard"],
    )

    turn = orchestrator.step()
    snapshot = orchestrator.snapshot()

    assert turn.speaker in {"Mara, the Grumpy Shopkeeper", "Rylan, the Anxious Guard"}
    assert turn.speaker_profession
    assert turn.speaker_mood
    assert snapshot["world_state"]["rumor_heat"] > 0
    assert snapshot["history"], "History should contain the last turn"
