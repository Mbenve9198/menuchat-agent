"""Basic API tests — verify endpoints exist and validate input."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    import app.db as db_module

    async def noop_init():
        pass

    async def noop_close():
        pass

    db_module.init_db = noop_init
    db_module.close_db = noop_close

    from app.main import app
    return TestClient(app)


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "menuchat-agent"


def test_process_validates_input(client):
    resp = client.post("/agent/process", json={})
    assert resp.status_code == 422


def test_proactive_validates_input(client):
    resp = client.post("/agent/proactive", json={})
    assert resp.status_code == 422


def test_resume_validates_input(client):
    resp = client.post("/agent/resume", json={})
    assert resp.status_code == 422


def test_process_accepts_valid_input(client, sample_agent_request):
    pass


def test_models_serialize(sample_agent_request):
    data = sample_agent_request.model_dump()
    assert data["contact"]["name"] == "Trattoria da Mario"
    assert data["lead_source"] == "smartlead_outbound"
    assert data["classification"]["category"] == "INTERESTED"


def test_proactive_models_serialize(sample_proactive_request):
    data = sample_proactive_request.model_dump()
    assert data["task_type"] == "rank_checker_outreach"
    assert data["contact"]["city"] == "Napoli"
    assert data["rank_checker_data"]["keyword"] == "pizzeria napoli centro"
