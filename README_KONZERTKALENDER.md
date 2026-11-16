# Nachtfragment – Konzert- und Gig-Kalender

Der Konzertkalender ist eine eigenständige Erweiterung des Dark Scene Directory. Er verwendet die Künstlerliste und recherchiert öffentliche Konzert- und Kalenderseiten.

## Aktive Dateien

- `concerts_discovery.py` – Konzertrecherche
- `concerts.html` – Kalenderoberfläche
- `concerts.json` – veröffentlichte Konzertdaten (im Repository-Hauptverzeichnis)
- `data/artists.json` – erfasste Nachtfragment-Künstler
- `data/concert_sources.json` – öffentliche Konzert- und Szenekalender
- `data/concert_candidates.json` – unbestätigte Recherchefunde
- `data/concerts_status.json` – Statusinformationen
- `.github/workflows/concerts-update.yml` – automatische Recherche mittwochs und sonntags

## Ablauf

1. Der Workflow durchsucht öffentliche Künstler- und Szenekalender.
2. Treffer mit unzureichenden Belegen werden in `data/concert_candidates.json` abgelegt.
3. Nur ausreichend belegte Termine können in `concerts.json` veröffentlicht werden.
4. Der Artist-Activity-Workflow liest ausschließlich bestätigte Einträge aus `concerts.json` und erzeugt daraus `data/artist-activity.json`.

Ein Suchtreffer ist kein bestätigter Konzerttermin. Prüfe Datum, Künstler und Veranstaltungsort anhand einer Künstler-, Venue- oder Veranstalterquelle, bevor du einen Eintrag in den öffentlichen Datenbestand übernimmst.

## Manuelle Ausführung

GitHub → **Actions** → **Nachtfragment Concert Discovery** → **Run workflow**.

Der Workflow benötigt keinen SerpApi-Schlüssel. Die Recherche basiert auf öffentlich erreichbaren Seiten und konfigurierten Kalenderquellen.

Zusätzlich durchsucht die Recherche die Suchmaschinen-Indizes gezielt nach **öffentlich auffindbaren Facebook-Events** zu den Nachtfragment-Künstlern. Facebook-Treffer werden ausschließlich in `data/concert_candidates.json` als prüfpflichtige Kandidaten gespeichert. Sie werden nie automatisch veröffentlicht. Eine Veranstaltung muss ohne Login öffentlich erreichbar sein und vor der Übernahme anhand von Datum, Venue und Veranstalter-/Künstlerangaben geprüft werden. Nicht öffentlich zugängliche oder hinter einer Login-Schranke liegende Inhalte werden nicht umgangen.

## Konzertdaten – Beispiel

Ein bestätigter Eintrag in `concerts.json` verwendet beispielsweise diese Struktur:

```json
{
  "events": [
    {
      "artist": "Artist Name",
      "date": "2026-11-21",
      "time": "20:00",
      "venue": "Club Name",
      "city": "Hamburg",
      "country": "Deutschland",
      "title": "Artist Name live",
      "url": "https://example.org/event",
      "status": "confirmed"
    }
  ]
}
```

Die Website und das Artist Activity Feed verwenden den veröffentlichten Bestand `concerts.json`, nicht den Kandidatenbestand.
