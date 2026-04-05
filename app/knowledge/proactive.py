"""
Knowledge for proactive agent flows:
outreach, follow-up, break-up, reactivation, seasonal.
"""

PROACTIVE_KNOWLEDGE = """
## FLUSSI PROATTIVI — PRINCIPI

### Rank Checker Outreach (Primo Contatto)
Il lead ha fatto un audit gratuito e ha visto il suo posizionamento su Google Maps.
Ora dobbiamo collegare il report al nostro servizio.

Struttura del messaggio:
1. APERTURA: Ringrazia per aver usato il Rank Checker. Personalizza con nome ristorante.
2. PROBLEMA: Usa i dati del rank checker (posizione, competitor, clienti persi/settimana).
   Se posizione bassa: "chi cerca '{keyword}' vede prima {competitor}"
   Se rating sotto 4.5: "con {rating} stelle, i clienti scelgono chi ha rating più alto"
3. DREAM OUTCOME: Stima concreta basata sui coperti.
   "Con {coperti} coperti/giorno, in 2 settimane puoi raccogliere ~{stima} recensioni"
4. SOCIAL PROOF: Cliente simile con dati REALI.
5. CTA: Conferma numero + 5 minuti per parlare della prova gratuita.

Regole:
- MAI citare il prezzo
- MAI spiegare il meccanismo tecnico (si spiega nella chiamata)
- Max 80 parole
- Solo email al primo contatto, MAI WhatsApp
- Firma col nome

### Follow-up No-Reply
Il lead non ha risposto dopo che l'agente ha mandato un messaggio.

Principi:
- Angolo DIVERSO dal messaggio precedente (non ripetere la stessa cosa)
- Se il primo messaggio era su social proof → follow-up su pain point
- Se il primo era su pain point → follow-up con insight drop
- Tono più leggero, meno push
- "Mi rendo conto che sei impegnato — volevo solo condividere un dato..."
- Max 2 follow-up prima del break-up

### Break-up Email
Ultimo tentativo prima di chiudere la conversazione.

Principi:
- Tono rispettoso, zero pressione
- Dare valore anche nell'addio (lasciare il rank checker gratuito)
- Creare FOMO leggero senza essere aggressivi
- "Se cambi idea, sai dove trovarmi"
- Esempio: "Capisco che non è il momento giusto. Il rank checker resta gratuito —
  puoi monitorare la tua posizione quando vuoi. Se in futuro vorrai parlarne, scrivi pure. In bocca al lupo!"

### Riattivazione Lead Dormienti (30+ giorni)
Il lead era in conversazione ma si è fermato.

Principi:
- Fare NUOVA ricerca (i dati potrebbero essere cambiati)
- Nuovo angolo basato su cosa è cambiato: nuove recensioni competitor? posizione cambiata?
- "È passato un po' di tempo dalla nostra ultima conversazione.
  Ho dato un'occhiata ai tuoi numeri e ho notato che..."
- Max 1 tentativo. Se non risponde, chiudere definitivamente.

### Riattivazione Stagionale
Il lead aveva detto "riapriamo a [mese]" e l'agente ha ibernato il workflow.

Principi:
- Personalizzare con il contesto originale ("Mi avevi detto che riaprivate a maggio")
- Ri-ricercare i dati (potrebbero essere cambiati durante la chiusura)
- Creare urgenza positiva: "Ora è il momento perfetto per iniziare a raccogliere recensioni
  prima che la stagione entri nel vivo"
- Ricordare la prova gratuita senza impegno
"""
