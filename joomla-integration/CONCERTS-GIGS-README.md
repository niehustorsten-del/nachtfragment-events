# Konzerte & Gigs – Joomla-Einbindung

Diese Datei bindet die Nachtfragment-Konzertübersicht als responsiven HTML-/CSS-/JavaScript-Block in Joomla ein.

## Datei
- `concerts.html` – vollständiger Quellstand der eigenständigen GitHub-Pages-Seite.
- `joomla-integration/concerts-gigs.html` – Joomla-Einbindung ohne iframe.
- Datenquelle: [data/concert_candidates.json](../data/concert_candidates.json)

## Einbau
1. `concerts-gigs.html` öffnen und den gesamten Inhalt kopieren.
2. In Joomla einen Beitrag oder ein eigenes HTML-Modul anlegen.
3. Den Code in einen Editor-/Modulbereich einfügen, der JavaScript zulässt. Joomla-Textfilter oder Editor können Script-Tags entfernen; gegebenenfalls einen geeigneten Custom-HTML-Ansatz verwenden.
4. Beitrag speichern und einen Menüpunkt „Konzerte & Gigs“ darauf verweisen lassen.

## Datenlogik und redaktionelle Sicherheit
- Die Einbindung lädt `data/concert_candidates.json` direkt aus dem GitHub-Repository.
- Standardmäßig werden nur Einträge mit `status: "verified"` und `review_required: false` angezeigt.
- Ungeprüfte Hinweise bleiben standardmäßig verborgen. Über die optionale Checkbox können sie eingeblendet werden; sie sind dann ausdrücklich als nicht redaktionell bestätigt markiert.
- Vergangene oder ungültige Datumsangaben werden nicht angezeigt.
- Die Einbindung veröffentlicht oder verändert keine Daten und greift nicht in GitHub Actions oder Updater ein.
- Es gibt derzeit keine separate `concerts.json`; daher verwendet das Joomla-Modul bewusst die vorhandene Kandidatendatei.

## Hinweise
Die Anzeige kann nur so aktuell und vollständig sein wie die zugrunde liegende Datenquelle. Termine vor Ticketkauf und Anreise immer über die verlinkte Künstler-, Veranstalter- oder Venue-Seite prüfen. Die eigenständige GitHub-Pages-Seite bleibt unverändert.
