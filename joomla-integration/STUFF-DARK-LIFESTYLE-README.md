# Stuff & Dark Lifestyle – Joomla-Einbindung

Diese Datei bindet das Nachtfragment-Verzeichnis direkt in Joomla ein – ohne iFrame.

## Datei
- `stuff-dark-lifestyle.html`

## Einbau
1. Datei öffnen und den gesamten HTML-Inhalt kopieren.
2. In Joomla einen Beitrag oder ein HTML-Modul für „Stuff & Dark Lifestyle“ öffnen.
3. Falls Joomla Skripte entfernt, den Code in einen Editor-/Modulbereich einfügen, der eigenes JavaScript erlaubt (z. B. ein geeignetes Custom-HTML-Modul mit passender Textfilter-Konfiguration).
4. Speichern und im Frontend testen.
5. Den Joomla-Menüpunkt auf den Beitrag bzw. das Modul zeigen lassen.

## Live-Daten
Die Einbindung lädt bei jedem Aufruf die aktuelle JSON-Datei:
`https://raw.githubusercontent.com/niehustorsten-del/nachtfragment-events/main/Stuff/nachtfragment-stuff.json`

Suche, Länderfilter und Kategorienfilter laufen im Browser. Externe Websites öffnen in einem neuen Tab.

## Hinweis
Die bestehende GitHub-Seite `Stuff/index.html`, die JSON-Datei und die GitHub-Automationen bleiben unverändert. Die Joomla-Seite ist eine zusätzliche Anzeige derselben Daten.