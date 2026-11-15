# Nachtfragment – Dark Scene Directory & Live

Dieses Repository betreibt die Daten- und Kalenderbereiche von [Nachtfragment](https://nachtfragment.de) sowie die zugehörigen automatischen Aktualisierungen.

## Bereiche

- `index.html` – Dark Scene Directory / Veranstaltungen und Szene-Orte
- `concerts.html` und `concerts.json` – Konzert- und Gig-Kalender
- `Stuff/index.html` und `Stuff/nachtfragment-stuff.json` – Stuff & Dark Lifestyle
- `Magazine/index.html` und `Magazine/nachtfragment-magazine.json` – Magazine-Verzeichnis
- `data/artist-activity.json` und `artist-activity.js` – Konzerttermine auf den Nachtfragment-Künstlerseiten

## Automatische Aktualisierungen

Alle Zeitangaben der GitHub Actions sind **UTC**. Die Workflows können zusätzlich jederzeit über **Actions → Workflow auswählen → Run workflow** manuell gestartet werden.

| Workflow | Zeitplan | Aufgabe |
|---|---|---|
| Nachtfragment Auto Update – Events & Festivals | Sonntag, 04:17 UTC | Aktualisiert Szene-Orte, Events, Festivals, Kandidaten und Geodaten |
| Nachtfragment Stuff & Magazine Auto Update | Sonntag, 04:17 UTC | Sucht neue Szene-Shops und Magazine; neue Funde werden zunächst geprüft |
| Nachtfragment Concert Discovery | Mittwoch und Sonntag, 05:35 UTC | Recherchiert Konzert- und Gig-Hinweise für die erfassten Künstler |
| Nachtfragment Artist Activity Feed | Mittwoch und Sonntag, 06:45 UTC | Baut den Künstlerseiten-Feed aus bestätigten Einträgen in `concerts.json` |

Die vier Workflows verwenden dieselbe GitHub-Actions-Concurrency-Gruppe. Damit laufen automatische Repository-Schreibvorgänge nacheinander und überschreiben sich nicht gegenseitig. Vor dem Push wird außerdem der aktuelle Stand des Hauptbranches eingebunden.

## Wichtige Daten- und Skriptdateien

### Dark Scene Directory
- `updater.py` – Hauptprogramm für Verzeichnis, Events und Festivals
- `discovery_sources.json`, `search_queries.json`, `directory_sources.json` – Quellen und Suchkonfiguration
- `data/nachtfragment.json` – veröffentlichter Datenbestand
- `data/candidates.json`, `data/directory_candidates.json` – noch zu prüfende Funde
- `data/changes.json`, `data/status.json`, `data/geocache.json` – Änderungsprotokoll, Status und Geocoding-Cache

### Konzerte und Künstleraktivität
- `concerts_discovery.py` – Konzertrecherche
- `data/artists.json` – Künstlerliste
- `data/concert_sources.json` – öffentliche Kalender- und Szenquellen
- `data/concert_candidates.json` – unbestätigte Konzert-Hinweise
- `concerts.json` – veröffentlichte bzw. bestätigte Konzertdaten
- `build_artist_activity.py` – erzeugt `data/artist-activity.json`

**Wichtig:** Recherchetreffer sind nicht automatisch bestätigte Konzerte. Ungeprüfte Kandidaten werden nicht im öffentlichen Artist Activity Feed angezeigt.

### Stuff & Magazine
- `stuff_magazine_updater.py` – Recherche und Aktualisierung
- `stuff_magazine_queries.json` – Suchabfragen
- `data/stuff-magazine-review.json` – Prüfbestand
- `Stuff/nachtfragment-stuff.json`, `Magazine/nachtfragment-magazine.json` – veröffentlichte Verzeichnisse

## Zugangsdaten

Der Stuff-/Magazine-Suchlauf benötigt ein GitHub Actions Secret namens `SERPAPI_KEY`. Der Schlüssel wird ausschließlich unter **Settings → Secrets and variables → Actions** hinterlegt und gehört niemals in Dateien des Repositories.

Der Haupt-Updater kann ohne zusätzliche Such-API weiterhin seine kuratierten Quellen prüfen. Konzertrecherche und Artist Activity verwenden keinen SerpApi-Schlüssel.

## Dokumentation

- `README_KONZERTKALENDER.md` – Hinweise zum Konzertkalender
- `JOOMLA-ARTIST-ACTIVITY-INSTALL.md` – Einbindung des Artist Activity Feeds in Joomla

## Pflegehinweise

- Dateien unter `data/` sind zum Teil laufende Datenbestände und dürfen nicht pauschal gelöscht oder durch leere Beispieldateien ersetzt werden.
- `*.example.json`-Dateien sind Vorlagen, keine Live-Daten.
- Veraltete Einmal-Patches und nicht eingebundene Discovery-Skripte gehören nicht in die aktive Pipeline.
