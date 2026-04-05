"""
Proactive strategist prompt additions — injected when the agent initiates contact.
"""

from app.knowledge.proactive import PROACTIVE_KNOWLEDGE


PROACTIVE_CONTEXT = f"""
## CONTESTO AZIONE PROATTIVA

Stai iniziando TU il contatto con il lead. Non stai rispondendo a un messaggio.
Questo cambia la dinamica: devi catturare l'attenzione e creare valore IMMEDIATO.

{PROACTIVE_KNOWLEDGE}
"""
