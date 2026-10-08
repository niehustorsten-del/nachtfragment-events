# Scene Discovery 4.1 – Korrektur

Diese Version behebt den V4-Filterfehler.

- Suchoperatoren wie `-events`, `-festival`, `-tickets` werden nicht mehr als Event-Signal gewertet.
- `scene_candidates.json` akzeptiert ausschließlich permanente Szene-Typen.
- Event-/Festival-Aggregatoren bleiben gesperrt.
- Event-/Festival-Begriffe werden für Titel und URL weiterhin hart abgewiesen.
- Der komplette Seitentext wird nicht mehr pauschal als Event-Signal gewertet, damit Clubs mit Veranstaltungskalender nicht verschwinden.
- Ortskonflikte werden nicht mehr stillschweigend als korrekt übernommen.
- Nominatim-Geocoding wird auf das erwartete Land geprüft.
- Alte Event/Festival-Kandidaten werden beim nächsten Lauf aus `scene_candidates.json` entfernt.
