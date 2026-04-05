"""Test that knowledge base modules load correctly and contain key content."""

from app.knowledge.product import PRODUCT_KNOWLEDGE
from app.knowledge.patterns import RESPONSE_PATTERNS
from app.knowledge.strategies import STRATEGIC_PRINCIPLES
from app.knowledge.objections import OBJECTION_PRINCIPLES
from app.knowledge.proactive import PROACTIVE_KNOWLEDGE


def test_product_knowledge_has_key_sections():
    assert "MenuChat" in PRODUCT_KNOWLEDGE
    assert "1.290" in PRODUCT_KNOWLEDGE
    assert "prova gratuita" in PRODUCT_KNOWLEDGE.lower()
    assert "GDPR" in PRODUCT_KNOWLEDGE


def test_patterns_has_all_categories():
    assert "I1" in RESPONSE_PATTERNS
    assert "I3" in RESPONSE_PATTERNS
    assert "U2" in RESPONSE_PATTERNS
    assert "IR2" in RESPONSE_PATTERNS
    assert "Già Seguiti" in RESPONSE_PATTERNS


def test_strategies_has_pattern_interrupt():
    assert "Ugly Spear" in STRATEGIC_PRINCIPLES
    assert "Empatia Tattica" in STRATEGIC_PRINCIPLES
    assert "Insight Drop" in STRATEGIC_PRINCIPLES


def test_objections_has_key_principles():
    assert "2 Tentativi" in OBJECTION_PRINCIPLES
    assert "prova gratis" in OBJECTION_PRINCIPLES.lower()
    assert "GDPR" in OBJECTION_PRINCIPLES


def test_proactive_has_flows():
    assert "Rank Checker" in PROACTIVE_KNOWLEDGE
    assert "Follow-up" in PROACTIVE_KNOWLEDGE
    assert "Break-up" in PROACTIVE_KNOWLEDGE
    assert "Riattivazione" in PROACTIVE_KNOWLEDGE
