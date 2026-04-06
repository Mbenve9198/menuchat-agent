"""
Test: come l'agente gestisce la riattivazione di lead dormienti.

Verifica:
1. Che il researcher riceva e usi correttamente i dati di riattivazione
2. Che il contesto passato all'agente sia sufficiente per scrivere un messaggio sensato
3. GAP: evidenzia i dati che MANCANO nel payload (chiamate, note, activity)
"""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.api.models import (
    ProactiveRequest,
    ContactData,
    AgentIdentity,
    SmartleadData,
    Message,
    CrmEnrichment,
    CallRecord,
)
from app.graph.nodes.researcher import _build_user_context, _extract_contact


# ── Fixture: lead vecchio con storico ricco ──────────────────────

@pytest.fixture
def old_lead_reactivation_request():
    """Simula un lead dormiente da 30+ giorni con dati ricchi."""
    return ProactiveRequest(
        task_type="reactivation",
        contact=ContactData(
            name="Ristorante Il Vecchio Mulino",
            email="info@vecchiomulino.it",
            phone="+393481234567",
            city="Firenze",
            address="Via dei Neri 35, Firenze, FI",
            rating=4.3,
            reviews=127,
            source="smartlead_outbound",
            category="Ristorante",
            website="https://vecchiomulino.it",
            google_maps_link="https://maps.google.com/?cid=456",
            contact_person="Giovanni Rossi",
        ),
        conversation_id="conv_reactivation_001",
        messages=[
            Message(
                role="agent",
                content="Buongiorno Giovanni, ho visto i risultati del Rank Checker...",
                channel="email",
                created_at="2025-10-16T09:00:00Z",
            ),
            Message(
                role="lead",
                content="Grazie Marco, interessante ma al momento siamo nel pieno della stagione. Ricontattami dopo Natale.",
                channel="email",
                created_at="2025-10-17T14:00:00Z",
            ),
            Message(
                role="agent",
                content="Capisco perfettamente Giovanni! Ti ricontatto dopo le feste...",
                channel="email",
                created_at="2025-10-17T15:00:00Z",
            ),
            Message(
                role="lead",
                content="Perfetto, a dopo le feste.",
                channel="email",
                created_at="2025-10-18T10:00:00Z",
            ),
        ],
        lead_source="smartlead_outbound",
        rank_checker_data={
            "keyword": "ristorante firenze centro",
            "ranking": {
                "mainRank": 12,
                "competitorsAhead": 11,
                "estimatedLostCustomers": 28,
                "fullResults": {
                    "mainResult": {"rank": 12, "coordinates": {"lat": 43.7696, "lng": 11.2558}},
                    "competitors": [
                        {"name": "Trattoria Mario", "rank": 1, "rating": 4.5, "reviews": 3200, "place_id": "comp1"},
                        {"name": "Osteria dell'Enoteca", "rank": 2, "rating": 4.4, "reviews": 1800, "place_id": "comp2"},
                    ],
                },
            },
            "placeId": "ChIJ_vecchiomulino_123",
            "dailyCovers": 120,
            "hasDigitalMenu": False,
            "estimatedMonthlyReviews": 22,
            "restaurantData": {
                "rating": 4.3,
                "reviewCount": 127,
                "address": "Via dei Neri 35, Firenze, FI",
                "coordinates": {"lat": 43.7696, "lng": 11.2558},
            },
        },
        smartlead_data=SmartleadData(campaign_id="campaign_202", lead_id="sl_lead_789"),
        agent_identity=AgentIdentity(name="Marco", surname="Benvenuti", role="co-founder"),
        task_context={"reason": "Dormant 30+ days"},
        previous_insights={
            "objections": ["bad_timing"],
            "pain_points": ["poche_recensioni", "competitor_visibili"],
        },
        days_since_last_contact=135,
        last_outcome=None,
        crm_enrichment=CrmEnrichment(
            call_history=[
                CallRecord(
                    date="2025-10-20T10:55:00Z",
                    duration_seconds=185,
                    outcome="callback",
                    notes="Giovanni conferma interesse, ha 2 locali. Vuole partire col locale di Firenze centro. Budget ok (~100€/mese dice che è niente), il problema è che in stagione non ha tempo. Richiamare dopo Natale.",
                    initiated_by="Marco Benvenuti",
                ),
                CallRecord(
                    date="2026-01-10T10:00:00Z",
                    duration_seconds=0,
                    outcome="no-answer",
                    initiated_by="Marco Benvenuti",
                ),
                CallRecord(
                    date="2026-01-12T11:00:00Z",
                    duration_seconds=45,
                    outcome="callback",
                    notes="Risponde veloce, dice che è ancora interessato ma deve parlarne col socio. Mi farà sapere entro fine mese.",
                    initiated_by="Marco Benvenuti",
                ),
            ],
            human_notes=[
                {"note": "Chiamato Giovanni il 20/10. Molto cordiale, conferma interesse. Ha 2 locali, quello di Firenze centro e uno a Fiesole. Vuole iniziare col primo. Budget non è un problema, è il tempo. Richiamare dopo Natale.", "date": "2025-10-20T11:00:00Z"},
                {"note": "Giovanni ha risposto a una mail di Natale generica. Ha scritto 'buone feste anche a voi'. Buon segno.", "date": "2025-12-23T09:00:00Z"},
            ],
            conversation_summary="Giovanni del Vecchio Mulino a Firenze è interessato ma ha chiesto di risentirci dopo le feste. Ha 2 locali, è consapevole del problema recensioni (127 vs 3200 del competitor principale). Obiezione: bad timing per la stagione.",
            contact_notes="Proprietario molto gentile, ha 2 locali. Interessato ma voleva aspettare dopo la stagione estiva.",
            activity_summary={
                "total_activities": 6,
                "calls_made": 3,
                "calls_answered": 2,
                "last_call_date": "2026-01-12T11:00:00Z",
                "last_call_outcome": "callback",
                "notes_count": 1,
                "emails_count": 1,
                "status_changes": ["da contattare → contattato", "contattato → ghosted/bad timing"],
            },
        ),
    )


@pytest.fixture
def old_lead_minimal_request():
    """Lead dormiente SENZA rank checker data e senza storico messaggi."""
    return ProactiveRequest(
        task_type="reactivation",
        contact=ContactData(
            name="Trattoria Nonna Maria",
            email="nonna@trattorianonna.it",
            phone="+393339876543",
            city="Bologna",
            source="smartlead_outbound",
        ),
        lead_source="smartlead_outbound",
        agent_identity=AgentIdentity(name="Marco", surname="Benvenuti", role="co-founder"),
        task_context={"reason": "Dormant 30+ days"},
        days_since_last_contact=45,
        last_outcome=None,
    )


# ── Test: contesto costruito per il researcher ───────────────────

class TestReactivationContext:
    """Verifica cosa il researcher "vede" quando processa una riattivazione."""

    def test_context_contains_proactive_action_type(self, old_lead_reactivation_request):
        contact = _extract_contact(old_lead_reactivation_request)
        rc_data = old_lead_reactivation_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_reactivation_request, contact, rc_data)

        assert "AZIONE PROATTIVA: reactivation" in ctx
        assert "Dormant 30+ days" in ctx

    def test_context_contains_contact_info(self, old_lead_reactivation_request):
        contact = _extract_contact(old_lead_reactivation_request)
        rc_data = old_lead_reactivation_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_reactivation_request, contact, rc_data)

        assert "Ristorante Il Vecchio Mulino" in ctx
        assert "info@vecchiomulino.it" in ctx
        assert "Firenze" in ctx
        assert "4.3" in ctx
        assert "Giovanni Rossi" in ctx

    def test_context_contains_conversation_history(self, old_lead_reactivation_request):
        contact = _extract_contact(old_lead_reactivation_request)
        rc_data = old_lead_reactivation_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_reactivation_request, contact, rc_data)

        assert "STORICO CONVERSAZIONE (4 messaggi)" in ctx
        assert "pieno della stagione" in ctx
        assert "dopo le feste" in ctx

    def test_context_contains_rank_checker_data(self, old_lead_reactivation_request):
        contact = _extract_contact(old_lead_reactivation_request)
        rc_data = old_lead_reactivation_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_reactivation_request, contact, rc_data)

        assert "DATI RANK CHECKER" in ctx
        assert "ristorante firenze centro" in ctx
        assert "12°" in ctx  # mainRank

    def test_context_contains_smartlead_ids(self, old_lead_reactivation_request):
        contact = _extract_contact(old_lead_reactivation_request)
        rc_data = old_lead_reactivation_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_reactivation_request, contact, rc_data)

        assert "campaign_202" in ctx
        assert "sl_lead_789" in ctx


class TestEnrichmentNowPresent:
    """Verifica che i dati precedentemente mancanti ORA arrivano al researcher."""

    def test_call_history_in_context(self, old_lead_reactivation_request):
        contact = _extract_contact(old_lead_reactivation_request)
        rc_data = old_lead_reactivation_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_reactivation_request, contact, rc_data)

        assert "STORICO CHIAMATE (3 chiamate)" in ctx
        assert "callback" in ctx
        assert "Giovanni conferma interesse" in ctx
        assert "parlarne col socio" in ctx

    def test_human_notes_in_context(self, old_lead_reactivation_request):
        contact = _extract_contact(old_lead_reactivation_request)
        rc_data = old_lead_reactivation_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_reactivation_request, contact, rc_data)

        assert "NOTE DEL TEAM VENDITE" in ctx
        assert "2 locali" in ctx
        assert "buone feste" in ctx

    def test_conversation_summary_in_context(self, old_lead_reactivation_request):
        contact = _extract_contact(old_lead_reactivation_request)
        rc_data = old_lead_reactivation_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_reactivation_request, contact, rc_data)

        assert "RIASSUNTO CONVERSAZIONE PRECEDENTE" in ctx
        assert "risentirci dopo le feste" in ctx

    def test_contact_notes_in_context(self, old_lead_reactivation_request):
        contact = _extract_contact(old_lead_reactivation_request)
        rc_data = old_lead_reactivation_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_reactivation_request, contact, rc_data)

        assert "NOTE SUL CONTATTO" in ctx
        assert "Proprietario molto gentile" in ctx

    def test_activity_summary_in_context(self, old_lead_reactivation_request):
        contact = _extract_contact(old_lead_reactivation_request)
        rc_data = old_lead_reactivation_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_reactivation_request, contact, rc_data)

        assert "ATTIVITÀ CRM: 6 totali" in ctx
        assert "Chiamate: 3" in ctx

    def test_contact_status_in_context(self, old_lead_reactivation_request):
        old_lead_reactivation_request.contact.status = "ghosted/bad timing"
        contact = _extract_contact(old_lead_reactivation_request)
        rc_data = old_lead_reactivation_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_reactivation_request, contact, rc_data)

        assert "Stato CRM: ghosted/bad timing" in ctx

    def test_callback_info_in_context(self, old_lead_reactivation_request):
        old_lead_reactivation_request.contact.callback_at = "2026-03-15T10:00:00Z"
        old_lead_reactivation_request.contact.callback_note = "Richiamare dopo Pasqua"
        contact = _extract_contact(old_lead_reactivation_request)
        rc_data = old_lead_reactivation_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_reactivation_request, contact, rc_data)

        assert "Callback programmato" in ctx
        assert "Richiamare dopo Pasqua" in ctx

    def test_days_since_last_contact_in_context(self, old_lead_reactivation_request):
        contact = _extract_contact(old_lead_reactivation_request)
        rc_data = old_lead_reactivation_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_reactivation_request, contact, rc_data)

        assert "GIORNI DALL'ULTIMO CONTATTO: 135" in ctx

    def test_call_requested_in_context(self, old_lead_reactivation_request):
        old_lead_reactivation_request.contact.call_requested = True
        old_lead_reactivation_request.contact.call_preference = "Mattina presto"
        contact = _extract_contact(old_lead_reactivation_request)
        rc_data = old_lead_reactivation_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_reactivation_request, contact, rc_data)

        assert "IL LEAD HA GIA RICHIESTO UNA CHIAMATA" in ctx
        assert "Mattina presto" in ctx

    def test_crm_enrichment_model_fields(self):
        """CrmEnrichment ha tutti i campi necessari."""
        fields = CrmEnrichment.model_fields.keys()
        assert "call_history" in fields
        assert "human_notes" in fields
        assert "conversation_summary" in fields
        assert "contact_notes" in fields
        assert "activity_summary" in fields

    def test_contact_data_has_new_fields(self):
        """ContactData ha i nuovi campi."""
        fields = ContactData.model_fields.keys()
        assert "status" in fields
        assert "notes" in fields
        assert "callback_at" in fields
        assert "callback_note" in fields
        assert "call_requested" in fields
        assert "place_id" in fields


class TestMinimalReactivation:
    """Lead con dati minimi — caso peggiore per l'agente."""

    def test_minimal_context_is_very_poor(self, old_lead_minimal_request):
        contact = _extract_contact(old_lead_minimal_request)
        rc_data = old_lead_minimal_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_minimal_request, contact, rc_data)

        assert "AZIONE PROATTIVA: reactivation" in ctx
        assert "Trattoria Nonna Maria" in ctx
        assert "Bologna" in ctx

        # Non c'è praticamente nulla su cui basare il messaggio
        assert "STORICO CONVERSAZIONE" not in ctx
        assert "DATI RANK CHECKER" not in ctx
        assert "SMARTLEAD" not in ctx
        assert "OBIEZIONI" not in ctx

    def test_minimal_request_has_no_messages(self, old_lead_minimal_request):
        assert len(old_lead_minimal_request.messages) == 0

    def test_minimal_request_has_no_rank_checker(self, old_lead_minimal_request):
        assert old_lead_minimal_request.rank_checker_data is None


class TestContextCompleteness:
    """Verifica che i dati presenti vengano formattati correttamente."""

    def test_full_context_output(self, old_lead_reactivation_request):
        """Stampa il contesto completo per ispezione manuale."""
        contact = _extract_contact(old_lead_reactivation_request)
        rc_data = old_lead_reactivation_request.rank_checker_data or {}
        ctx = _build_user_context(old_lead_reactivation_request, contact, rc_data)

        print("\n" + "=" * 60)
        print("  CONTESTO RICEVUTO DAL RESEARCHER (riattivazione)")
        print("=" * 60)
        print(ctx)
        print("=" * 60)

        # Verifica struttura
        assert "CONTATTO:" in ctx
        assert "AZIONE PROATTIVA:" in ctx

    def test_extract_contact_preserves_all_fields(self, old_lead_reactivation_request):
        contact = _extract_contact(old_lead_reactivation_request)

        assert contact["name"] == "Ristorante Il Vecchio Mulino"
        assert contact["email"] == "info@vecchiomulino.it"
        assert contact["phone"] == "+393481234567"
        assert contact["city"] == "Firenze"
        assert contact["rating"] == 4.3
        assert contact["reviews"] == 127
        assert contact["contact_person"] == "Giovanni Rossi"
        assert contact["website"] == "https://vecchiomulino.it"

    def test_extract_contact_includes_call_requested(self, old_lead_reactivation_request):
        """_extract_contact ora include call_requested."""
        contact = _extract_contact(old_lead_reactivation_request)
        assert "call_requested" in contact

    def test_extract_contact_includes_new_fields(self, old_lead_reactivation_request):
        contact = _extract_contact(old_lead_reactivation_request)
        assert "status" in contact
        assert "notes" in contact
        assert "callback_at" in contact
        assert "place_id" in contact
