# Artist News – Nachtfragment

## Ablauf
- discover_artist_news.py durchsucht für alle Künstler in data/artists.json öffentliche Google-News- und Bing-News-Suchergebnisse der letzten 45 Tage.
- Nur Treffer mit expliziter Künstlernennung und Musik-/Szenenbezug werden als Kandidaten gespeichert.
- Kandidaten landen in data/artist-news-candidates.json mit status needs_review. Sie werden NICHT automatisch auf Nachtfragment veröffentlicht.
- Nach redaktioneller Prüfung werden geeignete Einträge in data/artist-news.json übernommen und auf status approved gesetzt.
- build_artist_activity.py verbindet freigegebene Meldungen mit bestätigten Konzertdaten in data/artist-activity.json.
- artist-activity.js zeigt News und Konzerttermine auf der passenden Joomla-Künstlerseite. Ohne freigegebene News und bestätigte Termine verschwindet der Block.

## Meldung freigeben
Kopiere einen passenden Eintrag aus data/artist-news-candidates.json in das Feld items in data/artist-news.json. Prüfe:
1. Betrifft die Meldung tatsächlich den genannten Act?
2. Sind Datum und Artikel aktuell und erreichbar?
3. Ist es eine echte Musik-/Szenenmeldung und keine Namensgleichheit?
4. Ist die Quelle für eine Verlinkung geeignet?

Setze danach status auf approved. Die nächste Artist Activity Workflow-Ausführung übernimmt die Meldung in den Live-Feed. Für sofortige Aktualisierung kann der Workflow manuell gestartet werden.

## Grenzen
„Alle News im Internet“ kann kein Suchsystem vollständig garantieren. Die Suche kombiniert öffentliche News-Indizes und ist kostenlos sowie ohne API-Schlüssel nutzbar. Nicht indexierte Social-Media-Posts, geschlossene Plattformen und nicht öffentlich zugängliche Inhalte werden nicht zuverlässig erfasst. Die Konzertsuche bleibt davon getrennt und unverändert.
