"""
Integration test for the agent memory system.
Uses Qdrant in-memory mode (no Docker/server needed).

Richiede HF_TOKEN (Inference Providers) per gli embedding reali.

Run with: HF_TOKEN=hf_... python -m pytest tests/test_memory_system.py -v -s
"""

import asyncio
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

if not os.environ.get("HF_TOKEN"):
    pytest.skip(
        "Imposta HF_TOKEN (token HF con permesso Inference Providers) per i test memoria",
        allow_module_level=True,
    )


@pytest.fixture(scope="session", autouse=True)
def setup_in_memory_qdrant():
    """Patch qdrant_store to use in-memory client for all tests."""
    import app.memory.qdrant_store as qs
    from qdrant_client import QdrantClient
    qs._client = QdrantClient(location=":memory:")
    yield
    qs._client.close()
    qs._client = None


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class TestEmbeddings:
    def test_embed_single(self):
        from app.memory.embeddings import embed_single
        vec = embed_single("Ristorante a Roma con 200 recensioni")
        assert isinstance(vec, list)
        assert len(vec) > 0
        assert all(isinstance(x, float) for x in vec)

    def test_embed_multilingual(self):
        from app.memory.embeddings import embed_single
        vec_it = embed_single("Il ristorante ha un menu digitale")
        vec_en = embed_single("The restaurant has a digital menu")
        assert len(vec_it) == len(vec_en)
        assert len(vec_it) > 50

    def test_dimension(self):
        from app.memory.embeddings import get_embedding_dimension
        dim = get_embedding_dimension()
        assert dim > 50
        assert dim < 2048


class TestQdrantStore:

    @pytest.mark.asyncio
    async def test_init_collections(self):
        from app.memory.qdrant_store import init_collections, get_qdrant_client, _collection_name, EPISODES, CONTACT_MEMORIES
        await init_collections()
        client = get_qdrant_client()
        names = [c.name for c in client.get_collections().collections]
        assert _collection_name(EPISODES) in names
        assert _collection_name(CONTACT_MEMORIES) in names


class TestEpisodicMemory:

    @pytest.mark.asyncio
    async def test_store_and_recall_episode(self):
        from app.memory.qdrant_store import init_collections
        await init_collections()

        from app.memory.episodic import store_episode, recall_similar_episodes

        episode = {
            "lead_profile": {"category": "pizzeria", "city": "Roma", "source": "inbound_rank_checker"},
            "situation": "Il ristoratore dice che il costo e troppo alto",
            "objections": ["costo", "non vedo il valore"],
            "task_type": "follow_up_no_reply",
            "stage": "objection_handling",
            "strategy": "Confronto con competitor che hanno 3x recensioni",
            "draft": "Ciao Marco, capisco la preoccupazione sul costo...",
            "outcome": "approved",
            "conversation_id": "test_conv_001",
            "contact_email": "test@pizzeria-roma.it",
        }

        point_id = await store_episode(episode)
        assert point_id

        results = await recall_similar_episodes(
            {"lead_profile": {"category": "pizzeria", "city": "Roma"}, "objections": ["costo"]},
            top_k=3,
            score_threshold=0.2,
        )
        assert len(results) >= 1
        found = any(r.get("outcome") == "approved" for r in results)
        assert found, f"Expected to find the stored episode, got: {results}"

    @pytest.mark.asyncio
    async def test_recall_empty_with_high_threshold(self):
        from app.memory.qdrant_store import init_collections
        await init_collections()
        from app.memory.episodic import recall_similar_episodes

        results = await recall_similar_episodes(
            {"lead_profile": {"category": "gelateria", "city": "Bari"}, "situation": "xyz unique query 12345"},
            top_k=1,
            score_threshold=0.99,
        )
        assert len(results) == 0


class TestContactMemory:

    @pytest.mark.asyncio
    async def test_store_and_recall_contact(self):
        from app.memory.qdrant_store import init_collections
        await init_collections()

        from app.memory.contact_memory import store_observation, recall_contact_history

        email = "memory-test@example.com"
        await store_observation(
            contact_email=email,
            observation="Il lead e preoccupato dal costo ma interessato alla prova gratuita. Preferisce WhatsApp.",
            strategy_used="Confronto competitor + prova gratuita",
            outcome="draft_ready",
            conversation_id="test_conv_002",
            task_type="reactivation",
        )

        results = await recall_contact_history(email)
        assert len(results) >= 1
        found = any("costo" in r.get("observation", "") for r in results)
        assert found, f"Expected to find the observation, got: {results}"

    @pytest.mark.asyncio
    async def test_recall_nonexistent_contact(self):
        from app.memory.qdrant_store import init_collections
        await init_collections()
        from app.memory.contact_memory import recall_contact_history

        results = await recall_contact_history("nonexistent-7382@example.com")
        assert len(results) == 0


class TestMemoryManager:

    @pytest.mark.asyncio
    async def test_recall_all(self):
        from app.memory.qdrant_store import init_collections
        await init_collections()
        from app.memory.manager import recall_all

        result = await recall_all(
            contact_email="memory-test@example.com",
            context={"lead_profile": {"category": "pizzeria"}, "situation": "costo alto"},
        )
        assert "episodic_examples" in result
        assert "contact_memories" in result
        assert isinstance(result["episodic_examples"], list)
        assert isinstance(result["contact_memories"], list)

    @pytest.mark.asyncio
    async def test_store_feedback(self):
        from app.memory.qdrant_store import init_collections
        await init_collections()
        from app.memory.manager import store_feedback

        pid = await store_feedback({
            "lead_profile": {"category": "trattoria", "city": "Firenze"},
            "situation": "Non hanno tempo per gestire recensioni",
            "objections": ["tempo"],
            "strategy": "Sistema automatico che non richiede tempo",
            "draft": "Buongiorno, capisco perfettamente...",
            "outcome": "modified",
            "human_edits": {"modifications": {"toneChange": "Piu informale"}},
            "conversation_id": "test_003",
            "contact_email": "trattoria@firenze.it",
        })
        assert pid is not None

    @pytest.mark.asyncio
    async def test_store_run_memory(self):
        from app.memory.qdrant_store import init_collections
        await init_collections()
        from app.memory.manager import store_run_memory

        pid = await store_run_memory(
            contact_email="test-run@example.com",
            observation="Il lead ha espresso interesse per la prova gratuita ma vuole parlarne con il socio.",
            strategy_used="Prova gratuita + social proof locale",
            outcome="draft_ready",
            conversation_id="test_conv_004",
            task_type="reactivation",
        )
        assert pid is not None


class TestEndToEndFlow:
    """Simulates a complete memory lifecycle."""

    @pytest.mark.asyncio
    async def test_full_memory_lifecycle(self):
        from app.memory.qdrant_store import init_collections
        await init_collections()

        from app.memory.manager import store_feedback, store_run_memory, recall_all

        await store_feedback({
            "lead_profile": {"category": "ristorante", "city": "Milano", "source": "smartlead_outbound"},
            "situation": "Lead non risponde da 5 giorni, ha 120 recensioni",
            "objections": [],
            "task_type": "follow_up_no_reply",
            "stage": "initial_reply",
            "strategy": "Cita competitor locale con 400 recensioni per creare urgenza",
            "draft": "Ciao, ho notato che il tuo competitor...",
            "outcome": "approved",
            "conversation_id": "e2e_conv_001",
            "contact_email": "e2e@ristorante-milano.it",
        })

        await store_feedback({
            "lead_profile": {"category": "ristorante", "city": "Torino"},
            "situation": "Lead dice che costa troppo",
            "objections": ["costo"],
            "task_type": "follow_up_no_reply",
            "strategy": "ROI: 1 cliente in piu al giorno paga MenuChat",
            "draft": "Capisco, ma facciamo due conti...",
            "outcome": "modified",
            "human_edits": {"modifications": {"toneChange": "Meno aggressivo, piu empatico"}},
            "conversation_id": "e2e_conv_002",
            "contact_email": "e2e@ristorante-torino.it",
        })

        await store_feedback({
            "lead_profile": {"category": "pizzeria", "city": "Napoli"},
            "situation": "Lead ha gia un'agenzia che gestisce le recensioni",
            "objections": ["ha gia soluzione"],
            "strategy": "Confronto diretto: quante recensioni al mese con l'agenzia?",
            "draft": "Come va con l'agenzia attuale?",
            "outcome": "discarded",
            "human_edits": {"discard_reason": "wrong_strategy", "discard_notes": "Non attaccare l'agenzia, proponi di integrare"},
            "conversation_id": "e2e_conv_003",
            "contact_email": "e2e@pizzeria-napoli.it",
        })

        await store_run_memory(
            contact_email="e2e-new@ristorante-roma.it",
            observation="Lead molto interessato, ha chiesto dettagli sui costi. Ha 80 recensioni e il competitor ne ha 350.",
            strategy_used="Competitor gap + prova gratuita",
            outcome="draft_ready",
            conversation_id="e2e_conv_004",
            task_type="reactivation",
        )

        result = await recall_all(
            contact_email="e2e-new@ristorante-roma.it",
            context={
                "lead_profile": {"category": "ristorante", "city": "Roma"},
                "situation": "Lead non risponde, ha poche recensioni rispetto ai competitor",
                "objections": [],
                "task_type": "follow_up_no_reply",
            },
        )

        print(f"\n--- E2E Recall Results ---")
        print(f"Episodic examples found: {len(result['episodic_examples'])}")
        for ep in result["episodic_examples"]:
            print(f"  [{ep.get('outcome', '?').upper()}] score={ep.get('score', 0):.3f} | {ep.get('strategy', '?')[:60]}")
        print(f"Contact memories found: {len(result['contact_memories'])}")
        for cm in result["contact_memories"]:
            print(f"  {cm.get('observation', '')[:80]}")

        assert len(result["episodic_examples"]) > 0, "Should recall at least 1 similar episode"
        assert len(result["contact_memories"]) > 0, "Should recall contact observation"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
