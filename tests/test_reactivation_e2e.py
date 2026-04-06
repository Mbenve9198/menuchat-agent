"""
Test End-to-End: chiama il servizio agente con un payload di riattivazione realistico.

USO:
  # Dry-run (mostra solo il payload, non chiama l'agente):
  python -m pytest tests/test_reactivation_e2e.py -v -s -k dry_run

  # Chiamata reale all'agente (richiede servizio attivo):
  AGENT_URL=http://localhost:8100 python -m pytest tests/test_reactivation_e2e.py -v -s -k live
"""

import json
import os
import pytest
import httpx

AGENT_URL = os.environ.get("AGENT_URL", "http://localhost:8100")


def build_reactivation_payload_rich():
    """Lead dormiente con storico ricco — scenario reale."""
    return {
        "task_type": "reactivation",
        "contact": {
            "name": "Ristorante Il Vecchio Mulino",
            "email": "info@vecchiomulino.it",
            "phone": "+393481234567",
            "city": "Firenze",
            "address": "Via dei Neri 35, Firenze, FI",
            "rating": 4.3,
            "reviews": 127,
            "source": "smartlead_outbound",
            "category": "Ristorante",
            "website": "https://vecchiomulino.it",
            "google_maps_link": "https://maps.google.com/?cid=456",
            "contact_person": "Giovanni Rossi",
        },
        "conversation_id": "conv_e2e_reactivation_001",
        "messages": [
            {
                "role": "agent",
                "content": "Buongiorno Giovanni, sono Marco Benvenuti, co-founder di MenuChat. Ho visto i risultati del Rank Checker che hai usato sul nostro sito — il Vecchio Mulino è al 12° posto per 'ristorante firenze centro'. Ho dei dati interessanti che vorrei condividere con te. Hai 5 minuti per una chiamata veloce?",
                "channel": "email",
                "created_at": "2025-10-16T09:00:00Z",
            },
            {
                "role": "lead",
                "content": "Grazie Marco, interessante ma al momento siamo nel pieno della stagione e non ho tempo di guardare queste cose. Ricontattami dopo Natale se possibile.",
                "channel": "email",
                "created_at": "2025-10-17T14:00:00Z",
            },
            {
                "role": "agent",
                "content": "Capisco perfettamente Giovanni! La stagione viene prima di tutto. Ti ricontatto dopo le feste, così ne parliamo con calma. In ogni caso il Rank Checker resta disponibile gratuitamente se vuoi monitorare la tua posizione. Buon lavoro!",
                "channel": "email",
                "created_at": "2025-10-17T15:00:00Z",
            },
            {
                "role": "lead",
                "content": "Perfetto, a dopo le feste. Grazie.",
                "channel": "email",
                "created_at": "2025-10-18T10:00:00Z",
            },
        ],
        "lead_source": "smartlead_outbound",
        "rank_checker_data": {
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
                        {"name": "Il Latini", "rank": 3, "rating": 4.2, "reviews": 5600, "place_id": "comp3"},
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
        "smartlead_data": {
            "campaign_id": "campaign_202",
            "lead_id": "sl_lead_789",
        },
        "agent_identity": {"name": "Marco", "surname": "Benvenuti", "role": "co-founder"},
        "task_context": {"reason": "Dormant 30+ days"},
        "previous_insights": {
            "objections": ["bad_timing"],
            "pain_points": ["poche_recensioni", "competitor_visibili"],
        },
        "days_since_last_contact": 135,
        "last_outcome": None,
    }


def build_reactivation_payload_minimal():
    """Lead dormiente con dati minimi — scenario peggiore."""
    return {
        "task_type": "reactivation",
        "contact": {
            "name": "Trattoria Nonna Maria",
            "email": "nonna@trattorianonna.it",
            "phone": "+393339876543",
            "city": "Bologna",
            "source": "smartlead_outbound",
        },
        "lead_source": "smartlead_outbound",
        "agent_identity": {"name": "Marco", "surname": "Benvenuti", "role": "co-founder"},
        "task_context": {"reason": "Dormant 30+ days"},
        "days_since_last_contact": 45,
        "last_outcome": None,
    }


def build_reactivation_payload_with_missing_data():
    """
    Payload ARRICCHITO con i dati che DOVREBBERO essere passati ma che oggi non lo sono.
    Questo mostra come sarebbe un payload "completo" se si risolvessero i gap.
    """
    base = build_reactivation_payload_rich()

    # ── Dati che il CRM ha ma oggi non passa ──
    base["crm_enrichment"] = {
        "contact_status": "ghosted/bad timing",

        "call_history": [
            {
                "date": "2025-10-20T10:55:00Z",
                "duration_seconds": 185,
                "outcome": "callback",
                "notes": "Giovanni conferma interesse, ha 2 locali. Vuole partire col locale di Firenze centro. Budget ok (~100€/mese dice che è niente), il problema è che in stagione non ha tempo. Richiamare dopo Natale. Persona molto gentile e razionale.",
                "initiated_by": "Marco Benvenuti",
            },
            {
                "date": "2026-01-10T10:00:00Z",
                "duration_seconds": 0,
                "outcome": "no-answer",
                "notes": None,
                "initiated_by": "Marco Benvenuti",
            },
            {
                "date": "2026-01-12T11:00:00Z",
                "duration_seconds": 45,
                "outcome": "callback",
                "notes": "Risponde veloce, dice che è ancora interessato ma deve parlarne col socio. Mi farà sapere entro fine mese.",
                "initiated_by": "Marco Benvenuti",
            },
        ],

        "human_notes": [
            {
                "note": "Chiamato Giovanni il 20/10. Molto cordiale, conferma interesse. Ha 2 locali, quello di Firenze centro e uno a Fiesole. Vuole iniziare col primo. Budget non è un problema, è il tempo. Richiamare dopo Natale.",
                "date": "2025-10-20T11:00:00Z",
            },
            {
                "note": "Giovanni ha risposto a una mail di Natale generica. Ha scritto 'buone feste anche a voi'. Buon segno.",
                "date": "2025-12-23T09:00:00Z",
            },
        ],

        "conversation_summary": "Giovanni del Vecchio Mulino a Firenze è interessato ma ha chiesto di risentirci dopo le feste. Ha 2 locali, è consapevole del problema recensioni (127 vs 3200 del competitor principale). Obiezione: bad timing per la stagione. Nella chiamata del 20/10 ha confermato che il budget non è un problema. A gennaio è stato richiamato, dice che deve parlarne col socio.",

        "contact_notes": "Proprietario molto gentile, ha 2 locali. Interessato ma voleva aspettare dopo la stagione estiva.",

        "callback_info": {
            "callback_at": "2026-03-15T10:00:00.000Z",
            "callback_note": "Richiamare dopo Pasqua, dice che è troppo impegnato adesso",
        },

        "activity_summary": {
            "total_activities": 6,
            "calls_made": 3,
            "calls_answered": 2,
            "last_call_date": "2026-01-12T11:00:00Z",
            "last_call_outcome": "callback",
            "notes_count": 1,
            "emails_count": 1,
            "status_changes": ["da contattare → contattato", "contattato → ghosted/bad timing"],
        },
    }

    return base


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DRY RUN TESTS (nessuna chiamata HTTP)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestDryRun:

    def test_dry_run_rich_payload(self):
        """Stampa il payload che verrebbe inviato per un lead ricco."""
        payload = build_reactivation_payload_rich()

        print("\n" + "=" * 70)
        print("  PAYLOAD INVIATO ALL'AGENTE (riattivazione lead ricco)")
        print("=" * 70)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"\nDimensione payload: {len(json.dumps(payload))} bytes")
        print(f"Messaggi in storico: {len(payload.get('messages', []))}")
        print(f"Ha rank checker: {'sì' if payload.get('rank_checker_data') else 'no'}")
        print(f"Ha smartlead: {'sì' if payload.get('smartlead_data') else 'no'}")
        print(f"Ha previous insights: {'sì' if payload.get('previous_insights') else 'no'}")
        print(f"Giorni dall'ultimo contatto: {payload.get('days_since_last_contact')}")

    def test_dry_run_minimal_payload(self):
        """Stampa il payload per un lead con dati minimi."""
        payload = build_reactivation_payload_minimal()

        print("\n" + "=" * 70)
        print("  PAYLOAD INVIATO ALL'AGENTE (riattivazione lead minimale)")
        print("=" * 70)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"\nDimensione payload: {len(json.dumps(payload))} bytes")
        print(f"Messaggi in storico: {len(payload.get('messages', []))}")

    def test_dry_run_show_missing_data(self):
        """Confronta il payload attuale con quello arricchito per evidenziare i gap."""
        current = build_reactivation_payload_rich()
        enriched = build_reactivation_payload_with_missing_data()

        print("\n" + "=" * 70)
        print("  DATI MANCANTI — confronto payload attuale vs arricchito")
        print("=" * 70)

        crm_data = enriched["crm_enrichment"]

        print("\n📞 STORICO CHIAMATE (NON incluso nel payload attuale):")
        for call in crm_data["call_history"]:
            print(f"   {call['date'][:10]} | {call['duration_seconds']}s | {call['outcome']}")
            if call["notes"]:
                print(f"   📝 {call['notes'][:100]}...")

        print("\n📝 NOTE UMANE (NON incluse nel payload attuale):")
        for note in crm_data["human_notes"]:
            print(f"   {note['date'][:10]} | {note['note'][:100]}...")

        print(f"\n📋 CONVERSATION SUMMARY (NON incluso nel payload attuale):")
        print(f"   {crm_data['conversation_summary'][:200]}...")

        print(f"\n🏷️  STATO CONTATTO CRM: {crm_data['contact_status']} (NON incluso)")

        print(f"\n📅 CALLBACK: {crm_data['callback_info']['callback_note']} (NON incluso)")

        print(f"\n📊 ACTIVITY SUMMARY:")
        summary = crm_data["activity_summary"]
        print(f"   Chiamate: {summary['calls_made']} (risposte: {summary['calls_answered']})")
        print(f"   Ultima chiamata: {summary['last_call_date'][:10]} → {summary['last_call_outcome']}")
        print(f"   Note: {summary['notes_count']}, Email: {summary['emails_count']}")

        print("\n" + "=" * 70)
        print("  L'agente scrive il messaggio di riattivazione SENZA sapere nulla")
        print("  di quanto sopra. Opera solo con nome, email, rank checker,")
        print("  storico messaggi email e le etichette delle obiezioni.")
        print("=" * 70)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LIVE TESTS (chiamata reale all'agente)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class TestLive:
    """Richiedono il servizio agente attivo. Esegui con:
    AGENT_URL=http://localhost:8100 pytest tests/test_reactivation_e2e.py -v -s -k live
    """

    @pytest.fixture(autouse=True)
    def check_agent_running(self):
        try:
            r = httpx.get(f"{AGENT_URL}/health", timeout=5)
            if r.status_code != 200:
                pytest.skip(f"Agent service non raggiungibile su {AGENT_URL}")
        except Exception:
            pytest.skip(f"Agent service non raggiungibile su {AGENT_URL}")

    def test_live_reactivation_rich(self):
        """Chiama l'agente con un payload di riattivazione ricco."""
        payload = build_reactivation_payload_rich()

        print(f"\n🔄 Chiamata a {AGENT_URL}/agent/proactive ...")
        r = httpx.post(f"{AGENT_URL}/agent/proactive", json=payload, timeout=120)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text[:500]}"

        data = r.json()

        print("\n" + "=" * 70)
        print("  RISPOSTA AGENTE (riattivazione lead ricco)")
        print("=" * 70)
        print(f"Action: {data.get('action')}")
        print(f"Channel: {data.get('channel')}")
        print(f"Tokens: {data.get('total_tokens')}")
        print(f"Costo: ${data.get('estimated_cost_usd', 0):.4f}")
        print(f"Tempo: {data.get('processing_time_ms', 0)}ms")

        if data.get("strategy"):
            print(f"\nStrategia:")
            print(f"  Approccio: {data['strategy'].get('approach')}")
            print(f"  Angolo: {data['strategy'].get('main_angle')}")
            print(f"  Tono: {data['strategy'].get('tone')}")
            print(f"  Reasoning: {data['strategy'].get('reasoning', '')[:300]}")

        if data.get("draft"):
            print(f"\n📧 DRAFT MESSAGE:")
            print("-" * 50)
            print(data["draft"])
            print("-" * 50)

        if data.get("tool_intents"):
            print(f"\n🔧 Tool intents: {json.dumps(data['tool_intents'], indent=2)}")

        if data.get("thinking"):
            print(f"\n🧠 Thinking (troncato):")
            print(data["thinking"][:500])

        # Verifica che l'agente abbia prodotto qualcosa
        assert data.get("action") in ["draft_ready", "schedule_followup", "escalate_human", "system_action", "hibernated"]

    def test_live_reactivation_minimal(self):
        """Chiama l'agente con un payload minimale — caso peggiore."""
        payload = build_reactivation_payload_minimal()

        print(f"\n🔄 Chiamata a {AGENT_URL}/agent/proactive (minimal)...")
        r = httpx.post(f"{AGENT_URL}/agent/proactive", json=payload, timeout=120)
        assert r.status_code == 200, f"Status {r.status_code}: {r.text[:500]}"

        data = r.json()

        print("\n" + "=" * 70)
        print("  RISPOSTA AGENTE (riattivazione lead minimale)")
        print("=" * 70)
        print(f"Action: {data.get('action')}")

        if data.get("draft"):
            print(f"\n📧 DRAFT:")
            print(data["draft"])

        # Anche con dati minimi, l'agente dovrebbe produrre qualcosa
        assert data.get("action") is not None
