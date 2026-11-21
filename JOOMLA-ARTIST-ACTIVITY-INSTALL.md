# Nachtfragment – Artist Activity auf Joomla-Künstlerseiten

## Was das System macht

Das gemeinsame Artist-System verarbeitet die zentrale Liste `data/artists.json` (aktuell 131 Einträge). Auf den zugehörigen Joomla-Künstlerseiten kann automatisch ein gemeinsamer Block erscheinen:

- **News & Veröffentlichungen:** ausschließlich redaktionell freigegebene Meldungen aus `data/artist-news.json`.
- **Konzerte & Termine:** ausschließlich zukünftige, veröffentlichte und bestätigte Termine aus `concerts.json`.

Die Artists müssen sich dafür nirgends anmelden und keine Formulare ausfüllen. Öffentliche offizielle Webseiten, Bandcamp-Seiten und Veranstaltungskalender helfen der Recherche, sind aber keine technische Voraussetzung für die Anzeige.

## Einmalige Joomla-Einbindung

Die GitHub-Automatisierung und die Anzeige-Datei sind vorbereitet. Damit der Block tatsächlich auf den Artist-Seiten erscheint, muss das JavaScript einmalig in Joomla eingebunden werden. Das kann nicht allein durch eine Änderung im GitHub-Repository auf der Joomla-Website installiert werden.

1. Im Joomla-Backend **Inhalt → Site-Module** öffnen.
2. Ein Modul vom Typ **Eigenes Modul / Custom** anlegen.
3. Titel: `Nachtfragment Artist Activity`.
4. Menüzuweisung: **Auf allen Seiten**. Das Script erkennt selbstständig Artist-Seiten und bleibt auf allen anderen Seiten unsichtbar.
5. Im Editor in die HTML-/Quelltextansicht wechseln und ausschließlich diesen Code einfügen:

```html
<script src="https://niehustorsten-del.github.io/nachtfragment-events/artist-activity.js" defer></script>
```

6. **Vorbereitung von Inhalten / Prepare Content: Nein** einstellen.
7. Modul speichern und veröffentlichen.
8. Joomla- und gegebenenfalls Template-/CDN-Cache leeren.

Das Script erzeugt den Ausgabeblock selbst und setzt ihn direkt unter die Artist-Überschrift. Ein zusätzlicher Platzhalter ist nicht erforderlich.

Wenn Joomla oder der Editor das Script-Element beim Speichern entfernt, nicht wiederholt in den Editor einfügen. Stattdessen das Script über die Template-Funktion für benutzerdefinierten Code oder ein geeignetes Custom-Code-Modul laden. Keine Zugangsdaten oder FTP-Passwörter weitergeben.

## Prüfen

Nach der Joomla-Einbindung diese Seiten aufrufen und gegebenenfalls mit Strg+F5 neu laden:

- `https://nachtfragment.de/index.php/artists/hinfort`
- `https://nachtfragment.de/index.php/artists/thalie-nemesis`

Auf anderen Seiten wird kein Artist-Block angezeigt.

## News-Freigabe

Die automatische Recherche sammelt öffentliche News-Treffer für die Artists und speichert sie als Kandidaten in `data/artist-news-candidates.json`. Suchtreffer werden **nicht ungeprüft veröffentlicht**.

Nach redaktioneller Prüfung wird eine Meldung in `data/artist-news.json` übernommen und mit `status: approved` freigegeben. Erst dann erscheint sie im Artist-Feed. Das verhindert, dass falsche Zuordnungen, unpassende Suchtreffer oder bloße Erwähnungen als Artist-News ausgegeben werden.

## Konzert-Freigabe

Die Konzertrecherche sammelt Kandidaten. Auf Artist-Seiten erscheinen nur zukünftige Termine, die bereits im veröffentlichten `concerts.json` stehen und einen bestätigten Status besitzen. Ungeprüfte Kandidaten werden nicht angezeigt.

## Aktualisierung

- Konzertrecherche: Mittwoch und Sonntag, 05:35 UTC.
- News-Recherche und Artist Activity Feed: Mittwoch und Sonntag, 06:45 UTC.
- Nach der Konzertrecherche wird der gemeinsame Artist Activity Feed neu gebaut.
- Beide Workflows verwenden dieselbe Concurrency-Gruppe, um parallele Repository-Schreibvorgänge zu vermeiden.

Manuelle Starts sind über **GitHub → Actions** möglich.

## Grenzen

Die Recherche nutzt öffentliche, kostenlose Quellen und benötigt keine zusätzlichen API-Schlüssel. Sie kann geschlossene Social-Media-Inhalte oder das gesamte Internet nicht vollständig erfassen. Öffentliche News-Indizes können Meldungen übersehen. News bleiben deshalb redaktionell prüfpflichtig.
