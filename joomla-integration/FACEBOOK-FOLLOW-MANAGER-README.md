# Facebook Follow Manager – Joomla-Einbindung

## Dateien
- `facebook-follow-manager.html` – responsiver Joomla-Block ohne iframe.
- Datenquelle: `data/facebook-artists.json` (derzeit 131 Artist-Einträge).

## Einbau in Joomla
1. HTML-Datei öffnen und den gesamten Inhalt kopieren.
2. In Joomla einen Beitrag oder ein eigenes HTML-Modul anlegen.
3. Den Inhalt in einen Bereich einfügen, der JavaScript zulässt. Falls Joomla oder der Editor Script-Tags entfernt, den passenden Custom-HTML-Ansatz verwenden.
4. Den Beitrag speichern und über einen Menüpunkt „Facebook Follow Manager“ erreichbar machen.

## Funktionen
- Lädt die Artist-Liste live aus dem GitHub-Repository.
- Suche und Filter für alle Artists, bereits gefolgte Artists und fehlende Facebook-Links.
- Direkte Links zu Facebook und zum Nachtfragment-Porträt.
- Fünf Projektlinks im oberen Navigationsbereich: Shop/Club/Bar, Magazine, Ambiente/Wohnen/Tattoos, Konzerte & Gigs und Nachtfragment.
- Status „Ich folge bereits“ wird ausschließlich in `localStorage` dieses Browsers gespeichert. Die Markierung wird nicht synchronisiert und ist nicht auf anderen Geräten verfügbar.
- Keine Anmeldung, kein Scraping von Facebook und keine automatisierten Follow-Aktionen.
- Die bestehende GitHub-Pages-Datei und alle Automationen bleiben unverändert.

## Datenschutz und redaktioneller Hinweis
Facebook-Treffer können veraltet oder falsch zugeordnet sein. Vor dem Folgen bitte prüfen, ob es wirklich die offizielle Seite des Artists ist. Die Joomla-Einbindung überträgt keine persönlichen Follow-Statusdaten an einen Server.
