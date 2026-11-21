# Joomla-Integration – zentrale Navigation und Status

## Joomla-Module
Die HTML-Fragmente der sechs Bereiche liegen in diesem Ordner. Sie laden ihre Daten direkt aus den bestehenden GitHub-JSON-Dateien. Die GitHub-Pages und Automationen bleiben unverändert.

## Bereits auf Nachtfragment vorhandene Joomla-Beiträge
Diese vier internen URLs wurden über die Startseite bzw. deren „Neue Beiträge“ verifiziert:

- Followmanager: https://nachtfragment.de/index.php/followmanager
- Konzerte & Gigs: https://nachtfragment.de/index.php/konzerte-gigs
- Magazine: https://nachtfragment.de/index.php/magazine
- Stuff: https://nachtfragment.de/index.php/ambiente-wohnen-tattoos

## Noch anzulegen
Für die beiden vorbereiteten HTML-Fragmente sind Joomla-Beiträge mit diesen Menü-Aliasen vorgesehen:

- Dark Scene Directory: `dark-scene-directory`
- Music Charts: `music-charts`

Nach dem Anlegen lauten die internen URLs:
- `/index.php/dark-scene-directory`
- `/index.php/music-charts`

## Startseiten-Navigation
`homepage-network.html` ist ein responsiver, interner Linkblock für das Joomla-Eigenes-HTML-Modul oder den HTML-Quellcode des Startseitenbeitrags. Er verlinkt alle sechs Bereiche intern, ohne GitHub-Pages-Weiterleitungen.

## Wichtige Joomla-Hinweise
- Dieses Repository kann die Joomla-Datenbank bzw. Beiträge nicht direkt ändern. Die HTML-Blöcke müssen im Joomla-Backend eingefügt und gespeichert werden.
- Bei „Eigenes HTML“ sicherstellen, dass Joomla den HTML-Code und ggf. JavaScript nicht entfernt.
- Nach Einbau die sechs Seiten im Browser testen; die statischen GitHub-Seiten bleiben als Backup verfügbar.
- Die Konzertdatenbank enthält auch unbestätigte Kandidaten. Das Joomla-Modul blendet diese standardmäßig aus.
