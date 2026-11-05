"""Read the public Happy catalogue; notify through repository issues, without paid APIs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

HOME = "https://happy.andromeda.18tickets.it/"
HOSTS = {"happy.andromeda.18tickets.it", "happy.andromeda.andromedacinema.it"}
EVENT = re.compile(r"^/film/(\d+)/([0-9a-fA-F-]{36})/?$")
FILM = re.compile(r"^/film/(\d+)/?$")
TICKET_MARKER = "<!-- happy-imax-tickets -->"
BLOCK_MARKER = "<!-- happy-imax-blocked -->"
TEST_MARKER = "<!-- happy-imax-notification-test -->"


class CatalogueError(RuntimeError):
    pass


class Catalogue(HTMLParser):
    """Only headings identify films; a global IMAX menu must never trigger an alert."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.titles = {}
        self.links = []
        self.heading_depth = 0
        self.anchor = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "h6":
            self.heading_depth += 1
        if tag == "a":
            self.anchor = {"attrs": attrs, "heading": self.heading_depth > 0, "text": []}

    def handle_data(self, data):
        if self.anchor is not None:
            self.anchor["text"].append(data)

    def handle_endtag(self, tag):
        if tag == "h6":
            self.heading_depth = max(0, self.heading_depth - 1)
        if tag != "a" or self.anchor is None:
            return
        anchor, self.anchor = self.anchor, None
        attrs = anchor["attrs"]
        url = urlsplit(urljoin(HOME, attrs.get("href", "")))
        if url.scheme != "https" or url.hostname not in HOSTS:
            return
        text = " ".join(anchor["text"]).split()
        text = " ".join(text)
        film = FILM.fullmatch(url.path)
        if anchor["heading"] and film:
            self.titles[film[1]] = text
        event = EVENT.fullmatch(url.path)
        if event:
            self.links.append({"film": event[1], "id": event[2].lower(),
                               "url": f"https://{url.hostname}{url.path}#theater-init",
                               "text": text, "timestamp": attrs.get("data-time"),
                               "disabled": "disabled" in attrs or attrs.get("aria-disabled") == "true"})


def parse_catalogue(html, now=None):
    parser = Catalogue()
    parser.feed(html)
    now = now or datetime.now(timezone.utc)
    avengers = {key: title for key, title in parser.titles.items()
                if "AVENGERS" in title.upper() and "DOOMSDAY" in title.upper()}
    if not avengers or not parser.links:
        raise CatalogueError("Catalogo incompleto, struttura cambiata o verifica anti-bot: controllo non riuscito.")
    if not any(link["film"] in avengers for link in parser.links):
        raise CatalogueError("Scheda Avengers trovata ma nessun collegamento agli spettacoli leggibile.")
    shows = {}
    for link in parser.links:
        if link["film"] not in avengers or not re.search(r"\bIMAX\b", link["text"], re.I):
            continue
        if link["disabled"] or re.search(r"esaurit|sold\s*out|non\s+disponibil", link["text"], re.I):
            continue
        try:
            when = datetime.fromtimestamp(int(link["timestamp"]) / 1000, timezone.utc)
        except (TypeError, ValueError, OverflowError, OSError) as exc:
            raise CatalogueError("Spettacolo IMAX trovato ma data e ora non verificabili.") from exc
        local = when.astimezone(ZoneInfo("Europe/Rome"))
        if local.strftime("%H:%M") not in link["text"]:
            raise CatalogueError("Ora dello spettacolo IMAX incoerente con il catalogo.")
        if when <= now:
            continue
        shows[link["id"]] = {"id": link["id"], "title": avengers[link["film"]],
                              "date": local.strftime("%d/%m/%Y"), "time": local.strftime("%H:%M"),
                              "url": link["url"]}
    return sorted(shows.values(), key=lambda item: (item["date"], item["time"], item["id"]))


def collect():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        context = browser.new_context(locale="it-IT", timezone_id="Europe/Rome")
        page = context.new_page()
        try:
            response = page.goto(HOME, wait_until="domcontentloaded", timeout=60000)
            if response is None or response.status >= 400:
                raise CatalogueError("Il catalogo ha restituito un errore HTTP.")
            page.locator('h6 a[href*="/film/"]').first.wait_for(timeout=30000)
            page.locator('a[data-time][href*="#theater-init"]').first.wait_for(state="attached", timeout=30000)
            shows = parse_catalogue(page.content())
            # Read linked pages only. Login may gate the seat map: never claim free seats.
            for show in shows:
                response = page.goto(show["url"], wait_until="domcontentloaded", timeout=45000)
                if response is None or response.status >= 400:
                    raise CatalogueError("Un collegamento IMAX non e accessibile: disponibilita non confermata.")
                page.get_by_role("heading", name=re.compile("AVENGERS.*DOOMSDAY", re.I)).first.wait_for(timeout=20000)
                if not re.search(r"\bIMAX\b", page.locator("body").inner_text()):
                    raise CatalogueError("Il collegamento dello spettacolo non conferma il formato IMAX.")
            return shows
        finally:
            browser.close()


class GitHub:
    def __init__(self):
        self.repo = os.environ["GITHUB_REPOSITORY"]
        self.token = os.environ["GITHUB_TOKEN"]
        self.owner = self.repo.split("/")[0]

    def request(self, method, path, payload=None):
        request = Request("https://api.github.com/repos/" + self.repo + path,
                          data=json.dumps(payload).encode() if payload is not None else None,
                          method=method, headers={"Authorization": "Bearer " + self.token,
                          "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                          "Content-Type": "application/json", "User-Agent": "happy-imax-monitor"})
        with urlopen(request, timeout=30) as response:
            return json.load(response)

    def issues(self):
        result = []
        for page in range(1, 101):
            batch = self.request("GET", f"/issues?state=all&per_page=100&page={page}")
            result.extend(issue for issue in batch if not issue.get("pull_request")
                          and issue.get("user", {}).get("login") == "github-actions[bot]")
            if len(batch) < 100:
                return result
        raise RuntimeError("Storico avvisi troppo grande: impossibile garantire la deduplicazione.")

    def create(self, title, body):
        return self.request("POST", "/issues", {"title": title, "body": body, "assignees": [self.owner]})


def seen_ids(issues):
    return {value for issue in issues if TICKET_MARKER in (issue.get("body") or "")
            for value in re.findall(r"<!-- event:([0-9a-f-]{36}) -->", issue["body"])}


def ticket_body(shows, owner):
    lines = [TICKET_MARKER, f"@{owner} Il catalogo ufficiale pubblica questi spettacoli:",
             "", "**Avengers: Doomsday — IMAX — Happy MaxiCinema Afragola**", ""]
    for show in shows:
        lines += [f"- **{show['date']} alle {show['time']}** — [Apri lo spettacolo]({show['url']})",
                  f"<!-- event:{show['id']} -->"]
    lines += ["", "Il collegamento e stato aperto dal browser automatico. La scelta posti puo richiedere login;",
              "la disponibilita dei singoli posti e il pagamento vanno verificati sul sito del cinema.",
              "Nessuna prenotazione o acquisto e stato effettuato."]
    return "\n".join(lines)


def summary(message):
    print(message)
    if path := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(path, "a", encoding="utf-8") as stream:
            stream.write(message + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Read only, without GitHub notifications")
    parser.add_argument("--test-notification", action="store_true")
    args = parser.parse_args()
    github = None if args.dry_run else GitHub()
    issues = [] if github is None else github.issues()
    if args.test_notification:
        if github is None:
            raise RuntimeError("Il test notifiche richiede GitHub; non usare --dry-run.")
        if not any(TEST_MARKER in (issue.get("body") or "") for issue in issues):
            github.create("Test notifiche monitor IMAX", TEST_MARKER +
                          f"\n@{github.owner} Il canale di avviso GitHub e configurato. Questo e un test, non un avviso biglietti.")
        summary("Test notifiche registrato; la consegna email dipende dalle preferenze GitHub.")
        return
    try:
        shows = collect()
    except Exception as exc:
        # Report one open incident, not one notification every hour.
        if github is None:
            raise
        if not any(BLOCK_MARKER in (issue.get("body") or "") and issue["state"] == "open" for issue in issues):
            github.create("Monitor IMAX: catalogo non verificabile", BLOCK_MARKER +
                          f"\n@{github.owner} Il controllo non riesce a leggere il catalogo o a verificare i collegamenti.\n"
                          "Questo NON significa che manchino biglietti. Nessun CAPTCHA viene aggirato.\n"
                          f"Tipo di errore: `{type(exc).__name__}`. Vedi il riepilogo Actions per lo stato del controllo.")
        summary("**BLOCCATO — catalogo NON verificato.** Controllare l'incidente aperto nelle Issues.")
        return
    new = [show for show in shows if show["id"] not in seen_ids(issues)]
    if github and new:
        github.create("Avengers: Doomsday — nuovi spettacoli IMAX ad Afragola", ticket_body(new, github.owner))
    if github:
        for issue in issues:
            if BLOCK_MARKER in (issue.get("body") or "") and issue["state"] == "open":
                github.request("PATCH", f"/issues/{issue['number']}", {"state": "closed"})
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    summary(f"**VERIFICATO** alle {stamp}: {len(shows)} spettacoli IMAX futuri; {len(new)} nuovi. "
            + ("Modalita sola lettura." if args.dry_run else "Nessun messaggio se non ci sono novita."))
    Path("last-result.json").write_text(json.dumps({"checkedAt": stamp, "status": "verified", "shows": shows},
                                                  ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
