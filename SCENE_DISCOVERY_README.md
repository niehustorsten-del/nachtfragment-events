# Nachtfragment Scene Discovery

Erweiterung der bestehenden Nachtfragment Auto Discovery.

## Automatisch gesucht werden

- Gothic-/Darkwave-/EBM-/Industrial-Clubs
- Bars und Lounges mit erkennbarem Szeneprogramm
- Gothic-/Dark-Fashion-/Alternative-Shops
- Plattenläden mit relevantem Dark-/Gothic-Schwerpunkt
- Szene-Veranstalter und Promoter

## Veröffentlichungslogik

### Grün
Ein Treffer wird nur automatisch veröffentlicht, wenn:

- eine erreichbare Originalseite vorhanden ist
- ein eindeutiger Szene-Bezug gefunden wurde
- ein Ort/eine Stadt erkannt wurde
- der Treffer ausreichend hoch bewertet wird
- der Ort geocodiert werden kann

### Gelb

Unsichere Treffer landen in:

`data/scene_candidates.json`

Sie werden nicht auf der Karte veröffentlicht.

## Bestehende Daten

Die vorhandene `data/nachtfragment.json` wird nur ergänzt.
Bestehende IDs gewinnen; es werden keine vorhandenen Datensätze überschrieben.

## Ablauf

Der Workflow läuft täglich um 05:17 UTC.

Manuell:

GitHub → Actions → Nachtfragment Scene Discovery → Run workflow

## Benötigtes Secret

Bereits vorhandenes Repository Secret:

`SERPAPI_KEY`

Der Schlüssel wird nicht in Dateien gespeichert.
