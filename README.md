# Avengers: Doomsday IMAX — Afragola

Controllo gratuito del catalogo pubblico Happy MaxiCinema Afragola, con Chromium sui server GitHub Actions. Non richiede un PC acceso, Firecrawl, chiavi esterne o un abbonamento a un servizio di monitoraggio.

## Comportamento

- Ogni ora alle :03 (anche nell'orario italiano, perché la cadenza è oraria). GitHub può ritardare o saltare esecuzioni in periodi di carico.
- Cerca tutte le schede intitolate Avengers: Doomsday nel catalogo generale, comprese nuove schede con un ID diverso.
- Accetta solo collegamenti a spettacoli futuri con etichetta IMAX, data e ora coerenti. Gli altri film IMAX e le sale tradizionali sono esclusi.
- Apre i collegamenti prima di segnalarli. Non effettua login al cinema, non risolve CAPTCHA, non sceglie posti e non acquista biglietti. La mappa posti può richiedere un account: l'avviso segnala lo spettacolo con link di vendita e non garantisce singoli posti liberi.
- Pubblica una Issue assegnata al proprietario solo per nuovi spettacoli. Le Issue conservano gli ID già segnalati, anche se chiuse: non cancellarle se vuoi preservare la deduplicazione.
- Se il catalogo non è leggibile, apre un solo incidente; lo chiude al ripristino. Un controllo bloccato non viene considerato assenza di biglietti. Leggere VERIFICATO/BLOCCATO nel riepilogo: il solo segno verde della procedura non prova l'accesso al catalogo.
- Nessun messaggio iniziale per la sola creazione della pagina di riferimento.

## Attivazione

1. Pubblica questi file in un repository personale **pubblico**, sul ramo `main`. Il codice usa risorse standard di GitHub Actions e non carica file di grandi dimensioni o artefatti persistenti.
2. Apri **Actions → Avengers IMAX Afragola → Run workflow**. Il primo invio dei file avvia già un controllo.
3. Verifica il riepilogo: deve riportare **VERIFICATO**. Una pagina anti-bot deve invece produrre **BLOCCATO**.
4. Per provare gli avvisi, avvia una volta il workflow con **test_notification**. Il test genera una Issue assegnata al proprietario, distinta dagli avvisi biglietti.
5. Nelle impostazioni personali GitHub, abilita le notifiche email per assegnazioni/menzioni e scegli un indirizzo verificato. Gli avvisi arrivano tramite GitHub, non tramite un invio diretto a un indirizzo scritto nel codice. Il recapito desiderato va verificato nell'account.
6. Solo dopo il collaudo dal cloud, sospendi il monitor Firecrawl precedente per evitare duplicati e consumo crediti.

Il token temporaneo `GITHUB_TOKEN` è fornito da Actions e può leggere il codice e gestire le Issue di questo solo progetto. Nessun indirizzo email, password o token personale deve essere aggiunto ai file. Il progetto contiene solo codice e link pubblici del cinema.

## Costi e limiti

Le risorse standard GitHub-hosted sono gratuite nei repository pubblici secondo le condizioni correnti di GitHub. Il browser può comunque essere bloccato dal cinema: il collaudo dal server è indispensabile. I workflow pianificati nei repository pubblici possono essere disabilitati dopo 60 giorni senza attività; verificare periodicamente la sezione Actions e disabilitare il workflow quando il monitoraggio non serve più.

Fonti: [costi Actions](https://docs.github.com/en/actions/concepts/billing-and-usage), [pianificazione](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [browser su CI](https://playwright.dev/python/docs/ci).

## Verifica locale

`python -m unittest -v` verifica i casi di filtro e deduplicazione senza chiamare siti o inviare messaggi.

Per una lettura senza notifiche, dopo aver installato i requisiti e Chromium: `python monitor.py --dry-run`.
