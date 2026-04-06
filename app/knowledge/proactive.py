"""
Knowledge for proactive agent flows.
Context and facts, not templates.
"""

PROACTIVE_KNOWLEDGE = """
## FLUSSI PROATTIVI

### Rank Checker Outreach (Primo Contatto)

CONTESTO IMPORTANTE: il lead ha volontariamente usato il nostro Rank Checker sul sito. Ha inserito il nome del suo ristorante, ha visto la sua posizione su Google Maps, i competitor, e i dati. Non è un lead freddo — ha già interagito con noi e conosce il problema.

Questo cambia tutto:
- RICONOSCI che ha usato il rank checker ("Grazie per aver usato il nostro Rank Checker", "Ho visto i risultati del tuo report")
- Collegati ai DATI che ha già visto (posizione, competitor)
- Offrigli la PROVA ESCLUSIVA: per chi ha fatto il rank checker, offriamo 2 settimane gratis senza impegno del nostro sistema. Non è la prova standard — è un'offerta esclusiva per chi ha fatto l'audit.

Non spiegare come funziona il sistema al primo contatto — si spiega nella chiamata.
Non citare il prezzo.

### Outreach multicanale (CRM)
Se il contatto ha un numero di telefono valido e il CRM è configurato per l'invio proattivo, il messaggio principale resta su email; il follow-up parallelo su WhatsApp passa dalla coda template (fuori finestra 24h) ed è gestito dal backend, non serve che tu lo duplichi nel testo email.
Per i task proattivi storici: priorità al canale indicato in strategia; il dual-channel effettivo dipende dalle variabili d'ambiente del CRM (PROACTIVE_DUAL_CHANNEL_WHATSAPP).

### Follow-up No-Reply
Il lead non ha risposto. Cambia angolo. Se il primo messaggio usava la social proof, il follow-up usa il pain point. Se usava il pain, usa un insight nuovo. Tono più leggero, non ripetere le stesse cose.

### Break-up Email
Ultimo tentativo. Zero pressione. Dare valore anche nell'addio (il rank checker resta gratuito). Se cambia idea, sa dove trovarci.

### Riattivazione Lead Dormienti
FONDAMENTALE: questo NON è un contatto freddo. C'è già stata una relazione. Il messaggio DEVE:
- Riferirsi esplicitamente ai contatti precedenti ("ci siamo sentiti a ottobre", "avevamo parlato di...")
- Usare informazioni emerse nelle chiamate o conversazioni passate (nomi, dettagli, obiezioni superate)
- Mostrare che ti ricordi di lui e della sua situazione specifica
- NON ripetere la presentazione iniziale — sa già chi sei e cosa fai
- Trovare un NUOVO angolo basato su dati aggiornati (ranking cambiato, recensioni nuove, competitor)
- Se ci sono trascrizioni di chiamate, usa i dettagli personali emersi (nome di contatto, n° locali, budget, tempistiche)
Max 1 tentativo. Se non risponde, schedule follow-up con angolo diverso.

### Riattivazione Stagionale
Personalizzare col contesto originale. Ri-ricercare. Creare urgenza positiva ("ora è il momento perfetto per iniziare prima che la stagione entri nel vivo"). Riferirsi SEMPRE alla conversazione precedente.
"""
