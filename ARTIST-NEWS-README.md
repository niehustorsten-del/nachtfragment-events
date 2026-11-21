# Artist Activity – Nachtfragment

## Gemeinsame Artist-Datenbasis

`data/artists.json` ist die zentrale Liste aller Nachtfragment-Künstlerseiten. Sie enthält den Artist-Namen und die zugehörige Joomla-URL. Die aktuelle Liste umfasst 131 Artists. Für die Aufnahme in die automatische Recherche müssen Bands keine zusätzlichen Konten, API-Schlüssel oder Nachtfragment-Formulare einrichten.

Öffentlich verlinkte offizielle Webseiten und Terminseiten auf den Artist-Profilen helfen der Konzertrecherche, passende Kalender und Veranstaltungsseiten zu finden. Die News-Recherche sucht zusätzlich nach dem Artist-Namen in öffentlichen News-Indizes.

## Gemeinsamer Ablauf

1. **Artist-Bestand:** `data/artists.json` liefert Namen und Künstlerseiten für beide Recherchen.
2. **News-Recherche:** `discover_artist_news.py` durchsucht öffentliche Google-News- und Bing-News-Ergebnisse der letzten 45 Tage für alle Artists. Treffer werden als Kandidaten gespeichert.
3. **Konzert-Recherche:** `concerts_discovery.py` durchsucht Künstlerseiten und öffentliche Veranstaltungs-/Kalenderquellen. Ungeprüfte Kandidaten bleiben im Review-Bestand; nur die bereits definierten belastbaren Event-Nachweise können in `concerts.json` übernommen werden.
4. **Gemeinsamer Feed:** `build_artist_activity.py` verbindet bestätigte zukünftige Konzerttermine und redaktionell freigegebene News in `data/artist-activity.json`.
5. **Artist-Seiten:** `artist-activity.js` lädt diesen Feed und zeigt die passenden News und Termine auf der Joomla-Seite des jeweiligen Artists.

## News freigeben

Neue Suchtreffer landen in `data/artist-news-candidates.json` mit `status: needs_review`. Sie werden nicht automatisch auf Nachtfragment veröffentlicht.

Für eine Freigabe:
1. Prüfen, ob die Meldung tatsächlich den genannten Artist betrifft.
2. Datum und Originalartikel auf Erreichbarkeit und Aktualität prüfen.
3. Musik-/Szenenbezug und Quelle prüfen.
4. Den geprüften Eintrag in `data/artist-news.json` übernehmen und `status: approved` setzen.

Nur Einträge mit `status: approved` erscheinen im Artist Activity Feed.

## Konzertfreigabe

Der Artist Activity Feed übernimmt ausschließlich Konzertdaten mit einem der freigegebenen Statuswerte `confirmed`, `date_confirmed`, `lineup_announced` oder `date_confirmed_lineup_pending`. Ungeprüfte Kandidaten aus `data/concert_candidates.json` werden nicht direkt auf Artist-Seiten angezeigt.

## Aktualisierung

- Konzertrecherche: Mittwoch und Sonntag, 05:35 UTC.
- News-Recherche und Feed: Mittwoch und Sonntag, 06:45 UTC.
- Nach einer Konzertrecherche wird der gemeinsame Artist Activity Feed jetzt unmittelbar neu gebaut. Ein manueller Start des Konzert-Workflows aktualisiert damit ebenfalls die Artist-Seiten-Daten.
- Beide Workflows verwenden dieselbe GitHub-Concurrency-Gruppe, damit parallele Schreibvorgänge im Repository vermieden werden.

## Grenzen

Die Suche ist kostenlos und benötigt keine zusätzlichen API-Schlüssel. Sie kann nicht das gesamte Internet oder geschlossene Social-Media-Inhalte vollständig erfassen. Öffentliche News-Indizes können Meldungen übersehen oder unpassende Treffer liefern; deshalb bleiben News redaktionell prüfpflichtig.
