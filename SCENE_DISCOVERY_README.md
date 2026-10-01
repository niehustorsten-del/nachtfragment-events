# Nachtfragment Scene Discovery V2

Korrigierte automatische Discovery für Clubs, Bars, Gothic-/Dark-Fashion-Shops und Veranstalter.

## Wichtige Korrekturen
- Keine Stadtmittelpunkt-Koordinaten mehr.
- Neue Karten-Pins benötigen eine konkrete gefundene Adresse und erfolgreiches Geocoding.
- Online-Shops bekommen keine künstliche Kartenposition.
- Generische Clubs ohne konkreten Gothic/Dark/EBM-Bezug werden nicht automatisch veröffentlicht.
- Normale Fashion-Shops werden stärker gefiltert.
- Aggregatoren/redaktionelle Seiten werden nicht automatisch übernommen.
- Bestehende Datensätze werden nicht überschrieben.
- Deduplizierung über URL und Name/Stadt/Land.
- Unsichere Treffer landen in `data/scene_candidates.json`.
- SerpApi wird über drei tägliche Query-Batches mit je 12 Anfragen begrenzt.
- Gemeinsame GitHub-Concurrency-Gruppe verhindert parallele Schreibvorgänge, sofern auch der Haupt-Workflow diese Gruppe verwendet.

## Haupt-Workflow
In `.github/workflows/update.yml` ergänzen:
```yaml
concurrency:
  group: nachtfragment-auto-update
  cancel-in-progress: false
```
