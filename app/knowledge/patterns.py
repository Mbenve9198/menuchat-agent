"""
Response patterns from outbound campaigns + rank checker inbound.
NOT scripts — examples and strategic principles for each situation.
The strategist uses these as reference material, not as templates to follow.
"""

RESPONSE_PATTERNS = """
## PATTERN DI RISPOSTA LEAD — RIFERIMENTO STRATEGICO

Questi sono i pattern di risposta più comuni. L'agente NON segue script.
Usa questi come contesto per capire la situazione e decidere autonomamente.

### LEAD INTERESSATI

**I1 — Numero Diretto** (potenziale: MOLTO ALTO)
Esempi: "Chiama pure 3206650364", "3772310816 paolo"
Principio: Il lead ha dato il telefono → passa immediatamente a operatore umano.
Azione: tool_intent escalate_human con telefono estratto.

**I2 — WhatsApp** (potenziale: MOLTO ALTO)
Esempi: "Se mi scrivi su WhatsApp 3343305397", "Mandami un messaggio whatsapp"
Principio: Rispettare la preferenza del canale. Scrivere su WhatsApp in modo naturale,
presentarsi, chiedere 5 minuti al telefono. Gestire obiezioni se arrivano.
Poi passare a umano per la chiamata.

**I3 — Curiosità / Dimmi di più** (potenziale: ALTO)
Esempi: "Dimmi pure qua caro", "Che tipo di proposta ha per noi?", "Sono curioso come funziona e a che costi"
Principio: Questo lead VUOLE sapere. Fare deep research (SerpAPI, reviews recenti, similar clients).
Leggere l'email Smartlead originale per sapere cosa gli abbiamo scritto.
Costruire messaggio: problema (posizione, competitor, recensioni negative recenti) →
dream outcome (primi su Google, 600-1000 recensioni/anno) →
social proof (cliente simile con dati REALI) →
sistema semplice (se ha già menu digitale, ancora più semplice) →
prova gratis senza impegno → CTA: numero di telefono + 5 minuti.

**I4 — Vieni al ristorante** (potenziale: ALTO)
Esempi: "Venga in ristorante e ne parliamo"
Principio: Fare la stessa deep research di I3. Spiegare che siamo a Firenze e
non facciamo visite. Usare i dati trovati per dimostrare valore e ottenere
numero di telefono + 5 minuti al telefono.

**I5 — Scheduling diretto** (potenziale: MOLTO ALTO)
Esempi: "Lunedì dopo le 9:30 può andar bene?"
Principio: Il lead è pronto. Se manca telefono o nome, chiederli.
Confermare appuntamento con book_callback.

### NON CATEGORIZZATI

**U1 — Auto-Responder** (potenziale: MOLTO ALTO per ricontatto)
Esempi: "Per prenotazioni chiamare il numero...", "RISPOSTA AUTOMATICA"
Principio: Categorizzare come risposta automatica. Nessuna azione AI necessaria.

**U2 — Chiusura Stagionale** (potenziale: ALTO)
Esempi: "Siamo chiusi per ferie dal 22 Dicembre al 12 Febbraio"
Principio: Estrarre la data di riapertura. Schedulare riattivazione
pochi giorni PRIMA dell'apertura con hibernate_workflow (durable execution).

**U3 — Email Cambiata** (potenziale: ALTO)
Esempi: "Questa mail è in fase di dismissione, scrivere a info@lariva.net"
Principio: Estrarre la nuova email. Aggiornare Smartlead con update_smartlead_email.
Inviare messaggio di conferma alla nuova email.

**U4 — Risposta Cordiale Generica** (potenziale: MEDIO)
Esempi: "Grazie per averci contattato, ti risponderemo nel tempo più breve possibile"
Principio: Categorizzare come risposta automatica.

### RICHIESTE INFORMAZIONI

**IR1 — Mandami materiale** (potenziale: MOLTO ALTO)
Esempi: "Se vuole può inviarci una presentazione"
Principio: L'email È il materiale. Deep research completa, poi messaggio ricco:
problema con dati concreti → dream outcome → social proof → sistema semplice →
link a un menu bello di un cliente simile → prova gratis → numero + 5 minuti.

**IR2 — Quanto costa?** (potenziale: MOLTO ALTO)
Esempi: "Può dirmi il costo del servizio?"
Principio: Deep research per ancorare il prezzo al valore.
Framing: "1.290€ annuale = poco più di 100€/mese per 100+ recensioni/mese".
Ma prima: smuovere il problema, dream outcome, prova gratis.
"Siamo molto flessibili, prima provate senza impegno, poi ne parliamo."

**IR3 — È legale? / Trust** (potenziale: ALTO)
Esempi: "Mi assicura che sia legale?", "Are these fake reviews?"
Principio: Deep research per avere tutti i dati. Spiegare: recensioni vere,
clienti reali che hanno mangiato, GDPR compliant, nessuna falsificazione.
Schedulare follow-up se non risponde + break-up email.

**IR4 — Dopo la prova gratis?** (potenziale: MOLTO ALTO)
Esempi: "Dopo la prova gratis come funziona?"
Principio: Come IR2. Prezzo con framing giusto + prova senza impegno.

**IR5 — Rimandiamo a dopo** (potenziale: ALTO)
Esempi: "La cosa potrebbe interessare ma rimanderei il tutto a gennaio"
Principio: Rispettare il timing. Hibernate workflow con riattivazione nel periodo indicato.

### OBIEZIONI

**B — Già Seguiti** (potenziale: MEDIO-ALTO)
Esempi: "Abbiamo già chi ci cura la pagina e le recensioni"
Principio: Deep research. NON siamo un'agenzia. Per essere primi su Google Maps
serve raccogliere più recensioni degli altri con continuità.
Citare competitor con dati reali. Prova gratis, complementare a chi li segue già.

**C — Dati Sbagliati** (potenziale: MEDIO)
Esempi: "Stai confrontando realtà diverse", "Hai sbagliato locale"
Principio: SCUSARSI. Ri-fare la ricerca con SerpAPI con i dati corretti.
Riformulare con gentilezza usando i nuovi dati.
Problema → dream outcome → prova → numero.

**F — Rifiuto Educato Argomentato** (potenziale: MEDIO)
Esempi: "Grazie per l'analisi — stiamo già lavorando internamente"
Principio: Sfida analitica gentile: "Pensate di poter raccogliere 1000 recensioni
vere nei prossimi 12 mesi? Se sì vi saluto, altrimenti provatelo gratis."

**E — Targeting Sbagliato** (potenziale: ZERO)
Esempi: "Noi non abbiamo nessun ristorante"
Principio: Nessuna azione. Archiviare.

**Obiezione Stagionalità** (potenziale: MEDIO-ALTO)
Esempi: "Siamo stagionali, apriamo a maggio"
Principio: Come U2. Hibernate workflow per riattivazione prima della stagione.

**Obiezione Esclusività** (potenziale: MEDIO)
Esempi: "Lo stesso messaggio è attivato ad altri ristoratori a Stintino"
Principio: Ricercare se ci sono clienti MenuChat nella zona.
Se non ci sono: "Al momento non abbiamo clienti a Stintino.
Chi primo arriva, primo inizia a raccogliere."
"""
