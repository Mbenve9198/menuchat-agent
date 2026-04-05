"""Test PII scanner in reviewer node."""

from app.graph.nodes.reviewer import _scan_pii


def test_detects_api_key():
    text = "Ecco la chiave: sk-ant-api03-abcdef123456"
    violations = _scan_pii(text)
    assert any("api_key" in v for v in violations)


def test_detects_internal_email():
    text = "Puoi scrivere a marco@menuchat.com per info"
    violations = _scan_pii(text)
    assert any("Internal email" in v for v in violations)


def test_clean_text_passes():
    text = "Ciao Mario, ti scrivo per la prova gratuita. A presto, Marco"
    violations = _scan_pii(text)
    assert len(violations) == 0


def test_detects_iban():
    text = "Il pagamento va fatto su IT60X0542811101000000123456"
    violations = _scan_pii(text)
    assert any("iban" in v for v in violations)
