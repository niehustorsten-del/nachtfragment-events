# Nachtfragment Auto Discovery v4

Das System erweitert das bisherige Quellen-Update um eine echte Websuche.

## Pipeline

1. Kuratierte Gothic-/Dark-Szenequellen werden geprüft.
2. Eine Websuche über SerpApi sucht zusätzlich nach neuen Veranstaltungen und Festivals außerhalb der bekannten Quellen.
3. Suchtreffer werden nicht blind übernommen.
4. Die Originalseite des Suchtreffers wird abgerufen und erneut auf Datum, Szene und Ort geprüft.
5. Ort/Stadt werden erkannt.
6. Koordinaten werden – soweit möglich – über Nominatim ermittelt und zwischengespeichert.
7. Google-Maps-Such- und Routenlinks werden erzeugt.
8. Duplikate werden anhand Name + Ort + Land entfernt.
9. Starke Treffer können automatisch veröffentlicht werden.
10. Unsichere Treffer bleiben in `data/candidates.json`.
11. Alle Änderungen werden in `data/changes.json` protokolliert.

## Such-API

Die breite Websuche verwendet SerpApi. SerpApi stellt eine Google-Search-API mit strukturierten `organic_results` bereit.

Im GitHub Repository muss unter:

**Settings → Secrets and variables → Actions → New repository secret**

ein Secret angelegt werden:

`SERPAPI_KEY`

Ohne dieses Secret läuft das normale Quellen-Update weiterhin; die zusätzliche Websuche wird übersprungen.

## Sicherheit

Der API-Key gehört ausschließlich in GitHub Secrets und niemals in `search_queries.json`, `updater.py` oder die Website.

## Dateien

- `data/nachtfragment.json` – veröffentlichte Daten
- `data/candidates.json` – noch nicht ausreichend bestätigte Funde
- `data/changes.json` – Änderungsprotokoll
- `data/geocache.json` – Geocoding-Cache
- `discovery_sources.json` – kuratierte Quellen
- `search_queries.json` – Suchstrategien
- `updater.py` – Discovery- und Prüfprogramm
- `.github/workflows/update.yml` – täglicher und manueller Lauf
- `index.html` – Frontend

## Zeitplan

GitHub Actions startet den Workflow täglich um 04:17 UTC. Der Workflow kann außerdem über **Actions → Nachtfragment Auto Update → Run workflow** manuell gestartet werden.


## V4.2 – strenge Websuche

Die Websuche ist bewusst konservativ: alte Termine, redaktionelle Artikel, Wörterbuch-/Lexikonseiten, Reviews, Magazine und Fashion-Seiten werden nicht veröffentlicht. Ein Webtreffer wird nur veröffentlicht, wenn die Originalseite erreichbar ist und ein zukünftiges/aktuelles Datum, ein konkreter Ort, Szene-Bezug und eindeutige Veranstaltungsmerkmale erkannt werden. Unsichere Treffer bleiben in `data/candidates.json`.
