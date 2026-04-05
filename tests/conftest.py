import os
import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "sk-test-fake-key")
os.environ.setdefault("SERPAPI_KEY", "test-serpapi-key")
os.environ.setdefault("MENUCHAT_BACKEND_URL", "http://localhost:3000")
os.environ.setdefault("CRM_API_KEY", "test-crm-key")
os.environ.setdefault("SMARTLEAD_API_KEY", "test-smartlead-key")
os.environ.setdefault("POSTGRES_URL", "postgresql://agent:agent@localhost:5432/agent_test")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")


@pytest.fixture
def sample_agent_request():
    from app.api.models import AgentRequest, ContactData, Classification, AgentIdentity

    return AgentRequest(
        contact=ContactData(
            name="Trattoria da Mario",
            email="mario@trattoria.it",
            phone="+393331234567",
            city="Roma",
            rating=4.1,
            reviews=62,
            source="smartlead_outbound",
            category="ristorante",
        ),
        conversation_id="conv_test_001",
        messages=[],
        stage="initial_reply",
        lead_source="smartlead_outbound",
        lead_message="Sono curioso di sapere come funziona e a che costi",
        classification=Classification(category="INTERESTED", confidence=0.85, extracted={}),
        existing_objections=[],
        existing_pain_points=[],
        is_first_contact=False,
        agent_identity=AgentIdentity(name="Marco", surname="Benvenuti", role="co-founder"),
    )


@pytest.fixture
def sample_proactive_request():
    from app.api.models import ProactiveRequest, ContactData, AgentIdentity

    return ProactiveRequest(
        task_type="rank_checker_outreach",
        contact=ContactData(
            name="Pizzeria Bella Napoli",
            email="info@bellanapoli.it",
            phone="+393209876543",
            city="Napoli",
            rating=3.8,
            reviews=45,
            source="inbound_rank_checker",
        ),
        lead_source="inbound_rank_checker",
        rank_checker_data={
            "keyword": "pizzeria napoli centro",
            "ranking": {"mainRank": 8, "competitorsAhead": 7, "estimatedLostCustomers": 35},
            "dailyCovers": 80,
            "hasDigitalMenu": False,
        },
        agent_identity=AgentIdentity(name="Marco", surname="Benvenuti", role="co-founder"),
        task_context={"source": "rank_checker"},
    )


@pytest.fixture
def sample_research_data():
    return {
        "contact": {
            "name": "Trattoria da Mario",
            "email": "mario@trattoria.it",
            "phone": "+393331234567",
            "city": "Roma",
            "rating": 4.1,
            "reviews": 62,
        },
        "ranking": None,
        "competitors": [],
        "google_data": {"name": "Trattoria da Mario", "rating": 4.1, "reviews": 62, "place_id": "ChIJ_test123"},
        "recent_reviews": [
            {"rating": 2, "text": "Servizio lentissimo, abbiamo aspettato 45 minuti", "date": "2026-03-28", "author": "Laura R."},
            {"rating": 5, "text": "Ottima carbonara", "date": "2026-03-25", "author": "Giovanni M."},
        ],
        "negative_reviews_summary": "1 recensione negativa recente:\n★2: Servizio lentissimo, abbiamo aspettato 45 minuti",
        "similar_clients": [
            {
                "name": "Osteria del Sole",
                "city": "Roma",
                "current_reviews": 340,
                "initial_reviews": 120,
                "reviews_gained": 220,
                "months_active": 8,
                "menu_url": "https://menuchat.it/menu/test456",
            }
        ],
        "fallback_case_studies": [],
        "email_thread": [],
        "projected_reviews_2_weeks": None,
        "projected_reviews_12_months": None,
        "has_digital_menu": None,
        "available_data_summary": "Nome: Trattoria da Mario\nRating: 4.1\nRecensioni: 62\nCliente MenuChat: Osteria del Sole (Roma) — 220 rec in 8 mesi",
    }
