# Nachtfragment: Live & Konzerte — additive Erweiterung

Diese Dateien sind als **zusätzliche** Erweiterung für `nachtfragment-events` gedacht. Sie überschreiben weder `updater.py` noch `data/nachtfragment.json` oder den vorhandenen Workflow.

## Dateien hinzufügen

Die ZIP-Struktur entspricht dem Repository. Entpacke den Inhalt in das Repository und lade die neuen Dateien über GitHub hoch:

- `concerts_discovery.py` — sammelt Artist-Seiten und Suchtreffer
- `concerts.html` — eigenständige dunkle Kalenderansicht
- `data/artists.json` — erkannte Artists
- `data/concerts.json` — nur manuell/extern bestätigte Termine für die öffentliche Anzeige
- `data/concert_candidates.json` — unbestätigte Suchtreffer
- `.github/workflows/concerts-update.yml` — täglicher und manueller Lauf

## API-Schlüssel

Der bestehende `SERPAPI_KEY` kann verwendet werden. Er muss in GitHub unter **Settings → Secrets and variables → Actions** liegen. Niemals den Schlüssel in HTML, JSON oder Python eintragen.

## Ablauf

1. GitHub → Actions → **Nachtfragment Concert Discovery** → **Run workflow**.
2. Der erste Lauf aktualisiert die Künstlerliste und sammelt Suchtreffer.
3. Roh-Suchtreffer landen ausschließlich in `data/concert_candidates.json` und werden nicht automatisch als bestätigte Konzerte veröffentlicht.
4. Erst nach Prüfung dürfen Termine in `data/concerts.json` eingetragen werden, mit mindestens:
   `artist`, `date` (`YYYY-MM-DD`), `status: "confirmed"` und `source_url`.
   Optional: `time`, `venue`, `city`, `country`, `title`.

Beispiel eines bestätigten Eintrags:

```json
{
  "artist": "Artist Name",
  "date": "2026-11-21",
  "time": "20:00",
  "venue": "Club Name",
  "city": "Hamburg",
  "country": "Deutschland",
  "title": "Artist Name live",
  "source_url": "https://example.org/event",
  "status": "confirmed"
}
```

## Grenzen und nächste Ausbaustufe

- Der Importer hängt von einer öffentlich erreichbaren Sitemap und passenden URL-Strukturen für Künstlerporträts ab. Falls Nachtfragment andere URL-Muster nutzt, müssen die Filter angepasst werden.
- Google-Suchergebnisse sind Hinweise, keine verlässliche Bestätigung von Datum oder Venue. Die erste Version markiert alle Treffer als `needs_review`.
- Die automatische Erkennung einzelner Artists aus Übersichtsseiten ist bewusst konservativ; Übersichtsseiten mit vielen Künstlern sollten später mit einem spezifischen Parser ergänzt werden.
- Das Skript verändert keine bereits vorhandenen bestätigten Termine und veröffentlicht keine unbestätigten Treffer.
- `concerts.html` ist zunächst eine eigenständige Seite im GitHub-Pages-Projekt. Eine Joomla-Einbindung erfolgt anschließend über einen Link oder iframe, abhängig von deiner gewünschten Navigation.
