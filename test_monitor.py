from datetime import datetime, timezone
import unittest

from monitor import CatalogueError, TICKET_MARKER, parse_catalogue, seen_ids, ticket_body

NOW = datetime(2026, 11, 5, tzinfo=timezone.utc)
ID1 = "afb44807-0a89-423f-9e99-44d62d66658b"
ID2 = "d5871d21-5ca2-48e4-a5ba-8b5cda348a48"


def card(film="81401", title="AVENGERS: DOOMSDAY", label="00:01 IMAX", event=ID1,
         timestamp="1797375660000", host="happy.andromeda.18tickets.it", disabled=""):
    return f'''<div class="row"><div><h6><a href="https://{host}/film/{film}">{title}</a></h6></div>
    <div id="schedule-{film}"><a {disabled} data-time="{timestamp}"
    href="https://{host}/film/{film}/{event}#theater-init"><li>{label}</li></a></div></div>'''


class MonitorTests(unittest.TestCase):
    def test_numbered_rooms_and_other_imax_films_do_not_trigger(self):
        html = '<nav>IMAX</nav>' + card(label="00:01 Sala 10") + card("87110", "HOPE IMAX")
        self.assertEqual(parse_catalogue(html, NOW), [])

    def test_new_separate_imax_card_is_found(self):
        html = card(label="00:01 Sala 10") + card("99999", "AVENGERS: DOOMSDAY - IMAX 2D", event=ID2)
        shows = parse_catalogue(html, NOW)
        self.assertEqual([s["id"] for s in shows], [ID2])
        self.assertEqual((shows[0]["date"], shows[0]["time"]), ("16/12/2026", "00:01"))

    def test_mirror_and_duplicate_ids_are_deduplicated(self):
        shows = parse_catalogue(card() + card(host="happy.andromeda.andromedacinema.it"), NOW)
        self.assertEqual(len(shows), 1)

    def test_sold_out_and_disabled_are_excluded(self):
        self.assertEqual(parse_catalogue(card(label="00:01 IMAX esaurito") +
                                         card(event=ID2, disabled='aria-disabled="true"'), NOW), [])

    def test_old_shows_are_excluded(self):
        self.assertEqual(parse_catalogue(card(), datetime(2027, 1, 1, tzinfo=timezone.utc)), [])

    def test_missing_or_inconsistent_date_is_blocked(self):
        for html in (card(timestamp=""), card(label="21:30 IMAX")):
            with self.subTest(html=html), self.assertRaises(CatalogueError):
                parse_catalogue(html, NOW)

    def test_antibot_is_not_treated_as_no_tickets(self):
        with self.assertRaises(CatalogueError):
            parse_catalogue("<h1>JavaScript is disabled</h1>Verify you are not a robot", NOW)

    def test_missing_avengers_schedule_is_blocked(self):
        with self.assertRaises(CatalogueError):
            parse_catalogue(card("87110", "HOPE IMAX"), NOW)

    def test_untrusted_destination_does_not_trigger(self):
        self.assertEqual(parse_catalogue(card(label="00:01 Sala 10") +
                                         card(host="example.com", event=ID2), NOW), [])

    def test_closed_issues_preserve_seen_ids(self):
        shows = parse_catalogue(card(), NOW)
        body = ticket_body(shows, "owner")
        self.assertEqual(seen_ids([{"body": body, "state": "closed"}]), {ID1})
        self.assertIn(TICKET_MARKER, body)
        self.assertEqual(seen_ids([{"body": None}]), set())


if __name__ == "__main__":
    unittest.main()
