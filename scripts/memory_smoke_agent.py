#!/usr/bin/env python3
"""
Smoke test memoria agente in produzione (o locale).

1. Imposta AGENT_URL (o AGENT_SERVICE_URL) al servizio deployato.
2. Esegui due volte con lo stesso MEMORY_TEST_EMAIL (default sotto).
3. Nei log Render cerca: "Memory recall complete"
   - 1ª chiamata: di solito "0 episodes, 0 contact memories" (DB vuoto)
   - 2ª chiamata: "N contact memories" con N >= 1 se lo storage contatto funziona

Uso:
  AGENT_URL=https://tuo-agent.onrender.com python scripts/memory_smoke_agent.py 1
  AGENT_URL=https://tuo-agent.onrender.com python scripts/memory_smoke_agent.py 2

Opzionale:
  MEMORY_TEST_EMAIL=prova@tuodominio.it
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_EMAIL = "memory-smoke-test@menuchat-verify.local"


def main() -> None:
    agent_url = (os.environ.get("AGENT_URL") or os.environ.get("AGENT_SERVICE_URL") or "").rstrip(
        "/"
    )
    if not agent_url:
        print(
            "Imposta AGENT_URL o AGENT_SERVICE_URL, es.\n"
            "  export AGENT_URL=https://menuchat-agent.onrender.com",
            file=sys.stderr,
        )
        sys.exit(1)

    run_label = sys.argv[1] if len(sys.argv) > 1 else "1"
    email = os.environ.get("MEMORY_TEST_EMAIL", DEFAULT_EMAIL)
    conv_id = os.environ.get(
        "MEMORY_TEST_CONV_ID",
        f"mem-smoke-run{run_label}-{int(time.time())}",
    )

    token = f"MEMORY_SMOKE_RUN{run_label}_{int(time.time())}"
    payload = {
        "contact": {
            "name": "Test memoria smoke",
            "email": email,
            "phone": "+390000000000",
            "city": "Roma",
            "rating": 4.2,
            "reviews": 88,
            "source": "memory_smoke_test",
            "category": "ristorante",
        },
        "conversation_id": conv_id,
        "messages": [],
        "stage": "initial_reply",
        "lead_source": "memory_smoke_test",
        "lead_message": (
            f"Ciao, volevo info su MenuChat. Riferimento interno {token}. "
            "Il mio dubbio è il costo mensile rispetto alle recensioni che abbiamo già."
        ),
        "classification": {"category": "INTERESTED", "confidence": 0.9, "extracted": {}},
        "existing_objections": ["costo"],
        "existing_pain_points": [],
        "is_first_contact": False,
        "agent_identity": {
            "name": "Marco",
            "surname": "Benvenuti",
            "role": "co-founder",
        },
    }

    url = f"{agent_url}/agent/process"
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )

    print("─" * 60)
    print(f"POST {url}")
    print(f"contact.email      = {email}")
    print(f"conversation_id    = {conv_id}")
    print(f"grep token (message)= {token}")
    print("─" * 60)

    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {err_body[:2000]}", file=sys.stderr)
        sys.exit(2)
    except Exception as e:
        print(f"ERRORE: {e}", file=sys.stderr)
        sys.exit(2)

    dt_ms = (time.perf_counter() - t0) * 1000
    draft = data.get("draft") or ""
    print(f"\nOK in {dt_ms:.0f} ms")
    print(f"action     = {data.get('action')}")
    print(f"draft_len  = {len(draft)}")
    if draft:
        print(f"\nDraft (primi 500 caratteri):\n{draft[:500]}\n")

    print("Nei log del servizio agent cerca:")
    print(f'  Memory recall complete: … contact memories … {email}')
    print("Atteso: run2 con STESSO email → contact memories >= 1 (se Qdrant+HF ok).")
    print("Per episodi: prima POST /memory/feedback simile, poi run con stesso tema.")


if __name__ == "__main__":
    main()
