# Magazine & Webzines – Joomla-Einbindung

Diese Datei bindet das Nachtfragment-Magazine-Verzeichnis direkt in Joomla ein, ohne iFrame.

## Einbau
1. `magazine-webzines.html` öffnen und den gesamten Inhalt kopieren.
2. In Joomla einen Beitrag oder ein HTML-Modul für „Magazine & Webzines“ öffnen.
3. Wenn Joomla Skripte entfernt, den Code in einen Editor-/Modulbereich einfügen, der eigenes JavaScript erlaubt.
4. Speichern, Frontend testen und den Joomla-Menüpunkt auf den Beitrag bzw. das Modul verweisen lassen.

## Live-Daten
Die Anzeige lädt die aktuelle Datei:
`https://raw.githubusercontent.com/niehustorsten-del/nachtfragment-events/main/Magazine/nachtfragment-magazine.json`

Aktuell umfasst die Datenbasis 65 Publikationen (Stand 2026-11-21). Suche und Filter nach Land, Format, Status und Genre laufen im Browser.

## Bestehende Automationen
Die ursprüngliche GitHub-Seite `Magazine/index.html`, die JSON-Daten und die GitHub-Automationen bleiben unverändert. Joomla zeigt dieselben Daten zusätzlich an.