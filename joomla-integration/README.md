# Joomla-Integration: Dark Scene Directory

Diese Datei enthält einen Joomla-fähigen HTML-Block für das Nachtfragment Dark Scene Directory.

## Einbau

1. In Joomla einen Beitrag oder ein **Eigenes HTML-Modul** für die Seite „Dark Scene Directory“ anlegen.
2. Den vollständigen Inhalt aus `dark-scene-directory.html` in den HTML-/Quellcode-Modus des Editors kopieren.
3. Speichern und die Seite im Frontend testen.
4. Falls Joomla das `<script>`-Element beim Speichern entfernt: Das Snippet in ein Modul bzw. einen Editor-Bereich einfügen, der JavaScript zulässt (ggf. Joomla-Textfilter/Berechtigung für Super Users prüfen).
5. Den Beitrag im Joomla-Menü unter dem gewünschten Alias verknüpfen, z. B. `dark-scene-directory`.

## Daten und Automationen

Das Modul lädt die aktuellen JSON-Dateien direkt von GitHub Raw:
- `data/nachtfragment.json`
- `data/candidates.json`
- `data/directory_candidates.json`

Die GitHub-Actions und die vorhandenen GitHub-Pages-Dateien werden nicht verändert. Sobald die Automationen die JSON-Dateien aktualisieren, zeigt die Joomla-Seite beim nächsten Laden die neuen Daten.

## Hinweise

- Kein iFrame: Besucher bleiben vollständig auf Nachtfragment.
- CSS und JavaScript sind auf `#nf-directory-embed` begrenzt, damit das Joomla-Template möglichst wenig beeinflusst wird.
- Die Seite ist responsiv und bietet Suche, Länder-, Typ-, Szenerelevanz- und Aktivitätsfilter sowie die optionale Kandidatenanzeige.
- Externe Eintragslinks öffnen in einem neuen Tab.
