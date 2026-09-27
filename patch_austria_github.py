#!/usr/bin/env python3
# Nachtfragment – Österreich-Patch für data/nachtfragment.json
# Entfernt Black Rose/Wien, ergänzt Café LiBella und die geprüften Österreich-Einträge.
# Bestehende Datensätze bleiben erhalten; bei ID-Kollision gewinnt der vorhandene Datensatz.
import json
from pathlib import Path

DATA=Path("data/nachtfragment.json")
BACKUP=Path("data/nachtfragment.before_austria_patch.json")
if not DATA.exists():
    raise SystemExit("FEHLER: data/nachtfragment.json wurde nicht gefunden.")
data=json.loads(DATA.read_text(encoding="utf-8"))
if not isinstance(data,list):
    raise SystemExit("FEHLER: data/nachtfragment.json muss eine JSON-Liste sein.")
BACKUP.write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

ADDITIONS = [
  {
    "id": "asmalia",
    "name": "Asmalia – Corsets & Dark Fashion",
    "city": "Vienna",
    "country": "Austria",
    "country_name": "Österreich",
    "address": "Hermanngasse 7/3, 1070 Wien",
    "type": [
      "shop",
      "online"
    ],
    "categories": [
      "Gothic Fashion",
      "Dark Fashion",
      "Accessories"
    ],
    "description": "Gothic- und Dark-Fashion-Shop mit Korsetts, Kleidung, Schmuck und Accessoires; Ladengeschäft in Wien.",
    "url": "https://www.asmalia.at/",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Offizielle Website bestätigt Ladengeschäft und Gothic/Dark-Fashion-Sortiment.",
    "place_type": "shop",
    "is_physical": true,
    "map_category": "shop",
    "map_marker_type": "shop",
    "map_visible": true,
    "icon_category": "shop",
    "scene_relevance": [
      "gothic_core",
      "alternative_darkrock"
    ]
  },
  {
    "id": "rattlesnake-vienna",
    "name": "Rattlesnake",
    "city": "Vienna",
    "country": "Austria",
    "country_name": "Österreich",
    "address": "Kirchengasse 3, 1070 Wien",
    "type": [
      "shop"
    ],
    "categories": [
      "Rock",
      "Punk",
      "Metal",
      "Merch"
    ],
    "description": "Wiener Shop für Metal-, Rock- und Punk-Merch. Als Szene-Shop geführt; nicht ausschließlich Gothic.",
    "url": "https://www.rattlesnake.co.at/",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Schattenwelt führt Rattlesnake als lokalen Szene-Shop; aktueller Standort über Business-Daten bestätigt.",
    "place_type": "shop",
    "is_physical": true,
    "map_category": "shop",
    "map_marker_type": "shop",
    "map_visible": true,
    "icon_category": "shop",
    "scene_relevance": [
      "alternative_darkrock",
      "gothic_core"
    ]
  },
  {
    "id": "totem-records",
    "name": "Totem Records",
    "city": "Vienna",
    "country": "Austria",
    "country_name": "Österreich",
    "address": "Zollergasse 18-20, 1070 Wien",
    "type": [
      "shop"
    ],
    "categories": [
      "Metal",
      "Goth",
      "Industrial",
      "Ambient",
      "Neo-Folk"
    ],
    "description": "Unabhängiger Musikladen mit Sortiment aus Metal, Goth, Industrial, Ambient und verwandten Underground-Stilen.",
    "url": "https://www.totem-records.com/",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Schattenwelt nennt Totem Records als unabhängigen Musikladen in Wien; aktuelle Standortangabe zusätzlich in Musikladen-Verzeichnissen.",
    "place_type": "shop",
    "is_physical": true,
    "map_category": "shop",
    "map_marker_type": "shop",
    "map_visible": true,
    "icon_category": "shop",
    "scene_relevance": [
      "gothic_core",
      "darkwave_wave",
      "ebm_industrial"
    ]
  },
  {
    "id": "musikversorgung-steiner",
    "name": "Musikversorgung Steiner",
    "city": "Vienna",
    "country": "Austria",
    "country_name": "Österreich",
    "address": "Westbahnstraße 25/2/R1, 1070 Wien",
    "type": [
      "shop"
    ],
    "categories": [
      "Synth",
      "Wave",
      "Post-Punk",
      "Indie",
      "Alternative",
      "Punk",
      "Metal"
    ],
    "description": "Underground-Plattenladen mit Schwerpunkt auf Punk, Hardcore, Metal, Garage, Synth, Wave, Post-Punk, Indie und Alternative; Vinyl, Tapes, Bücher und Merch.",
    "url": "https://firmen.wko.at/",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Aktueller Gewerbeeintrag nennt Standort und Sortiment ausdrücklich.",
    "place_type": "shop",
    "is_physical": true,
    "map_category": "shop",
    "map_marker_type": "shop",
    "map_visible": true,
    "icon_category": "shop",
    "scene_relevance": [
      "darkwave_wave",
      "postpunk_deathrock",
      "alternative_darkrock"
    ]
  },
  {
    "id": "viper-room-vienna",
    "name": "Viper Room",
    "city": "Vienna",
    "country": "Austria",
    "country_name": "Österreich",
    "address": "Landstraßer Hauptstraße 38, 1030 Wien",
    "type": [
      "club",
      "bar"
    ],
    "categories": [
      "Gothic",
      "Darkwave",
      "EBM",
      "Industrial",
      "Dark Electro",
      "Post-Punk"
    ],
    "description": "Wiener Club mit regelmäßigem Programm der Schwarzen Szene, darunter Near Dark, Vienna Decay Night und Dark-Electro/EBM-Veranstaltungen.",
    "url": "https://www.viper-room.at/",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Aktuelle Szene-Termine 2026 sind bei gothic.at und Schattenwelt dokumentiert.",
    "place_type": "club",
    "is_physical": true,
    "map_category": "club",
    "map_marker_type": "club",
    "map_visible": true,
    "icon_category": "club",
    "scene_relevance": [
      "gothic_core",
      "darkwave_wave",
      "ebm_industrial",
      "dark_electro_futurepop",
      "postpunk_deathrock"
    ]
  },
  {
    "id": "replugged-vienna",
    "name": "Replugged",
    "city": "Vienna",
    "country": "Austria",
    "country_name": "Österreich",
    "address": "Lerchenfelder Straße 23, 1070 Wien",
    "type": [
      "club",
      "concert_venue"
    ],
    "categories": [
      "Gothic",
      "Darkwave",
      "EBM",
      "Industrial",
      "Synthpop"
    ],
    "description": "Wiener Veranstaltungsort mit wiederkehrenden Gothic-, Dark-Electro-, EBM- und Industrial-Veranstaltungen, darunter Electronic Fallout und das Schattenwelt Festival.",
    "url": "https://www.replugged.at/",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Aktuelle 2026-Termine für Dark Electro/EBM/Industrial und Schattenwelt Festival bestätigt.",
    "place_type": "club",
    "is_physical": true,
    "map_category": "club",
    "map_marker_type": "club",
    "map_visible": true,
    "icon_category": "club",
    "scene_relevance": [
      "gothic_core",
      "darkwave_wave",
      "ebm_industrial",
      "dark_electro_futurepop"
    ]
  },
  {
    "id": "the-chamber-vienna",
    "name": "The Chamber",
    "city": "Vienna",
    "country": "Austria",
    "country_name": "Österreich",
    "address": "Hernalser Gürtel 18, 1080 Wien",
    "type": [
      "club",
      "concert_venue"
    ],
    "categories": [
      "Industrial",
      "Electro",
      "Gothic",
      "Deathrock",
      "Post-Punk"
    ],
    "description": "Wiener Veranstaltungsort mit aktuellen Industrial/Electro- sowie Gothic/Deathrock/Post-Punk-Terminen.",
    "url": "https://www.the-chamber.at/",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Aktuelle 2026-Termine über gothic.at dokumentiert.",
    "place_type": "club",
    "is_physical": true,
    "map_category": "club",
    "map_marker_type": "club",
    "map_visible": true,
    "icon_category": "club",
    "scene_relevance": [
      "gothic_core",
      "ebm_industrial",
      "postpunk_deathrock"
    ]
  },
  {
    "id": "das-lot-vienna",
    "name": "Das Lot",
    "city": "Vienna",
    "country": "Austria",
    "country_name": "Österreich",
    "address": "Absberggasse 31, 1100 Wien",
    "type": [
      "club",
      "concert_venue"
    ],
    "categories": [
      "Darkwave",
      "Post-Punk",
      "Gothic",
      "Alternative"
    ],
    "description": "Wiener Veranstaltungsort mit wiederkehrenden Konzerten und Clubnächten aus dem dunklen Underground, darunter Noir Club Night.",
    "url": "https://daslot.at/",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Aktuelle 2026-Termine über gothic.at dokumentiert.",
    "place_type": "club",
    "is_physical": true,
    "map_category": "club",
    "map_marker_type": "club",
    "map_visible": true,
    "icon_category": "club",
    "scene_relevance": [
      "darkwave_wave",
      "postpunk_deathrock",
      "gothic_core"
    ]
  },
  {
    "id": "ppc-graz",
    "name": "p.p.c.",
    "city": "Graz",
    "country": "Austria",
    "country_name": "Österreich",
    "address": "Neubaugasse 6, 8020 Graz",
    "type": [
      "club",
      "concert_venue"
    ],
    "categories": [
      "Gothic",
      "Darkwave",
      "Post-Punk",
      "Alternative"
    ],
    "description": "Graz venue mit dokumentierten Dark-Szene-Konzerten, darunter Ductape 2026 und Traitrs/Whispers In The Shadow 2027.",
    "url": "https://www.ppc.co.at/",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Schattenwelt und gothic.at führen aktuelle bzw. angekündigte Szene-Termine am p.p.c.",
    "place_type": "club",
    "is_physical": true,
    "map_category": "club",
    "map_marker_type": "club",
    "map_visible": true,
    "icon_category": "club",
    "scene_relevance": [
      "gothic_core",
      "darkwave_wave",
      "postpunk_deathrock",
      "alternative_darkrock"
    ]
  },
  {
    "id": "goththing-innsbruck",
    "name": "GothThing / Bühne Innsbruck",
    "city": "Innsbruck",
    "country": "Austria",
    "country_name": "Österreich",
    "address": "Innsbruck, Tirol",
    "type": [
      "event_series"
    ],
    "categories": [
      "Gothic",
      "EBM",
      "Dark Electro",
      "Industrial"
    ],
    "description": "GothThing ist eine Innsbrucker Veranstaltungsreihe mit Gothic-, EBM-, Electro- und Industrial-Schwerpunkt; 2026 sind mehrere Termine dokumentiert.",
    "url": "https://pmk.or.at/de/clubs/bhne-innsbruck/events/",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Offizielle PMK-Veranstaltungsseite nennt GothThing 2026 und ordnet die Termine Gothic/EBM/Electro/Industrial zu.",
    "place_type": "event_series",
    "is_physical": true,
    "map_category": "event",
    "map_marker_type": "event",
    "map_visible": true,
    "icon_category": "event",
    "scene_relevance": [
      "gothic_core",
      "ebm_industrial",
      "dark_electro_futurepop"
    ]
  },
  {
    "id": "schlachthaus-dornbirn",
    "name": "Kulturcafé Schlachthaus",
    "city": "Dornbirn",
    "country": "Austria",
    "country_name": "Österreich",
    "address": "Schlachthausstraße 11, 6850 Dornbirn",
    "type": [
      "concert_venue",
      "bar"
    ],
    "categories": [
      "Alternative",
      "Dark Rock",
      "Underground"
    ],
    "description": "Kulturcafé und Bühne in Dornbirn. Gothic.at führt das Schlachthaus als Veranstaltungsort für eine Szene-Reihe; aktuelle 2026-Programme sind auf der Betreiberseite dokumentiert.",
    "url": "https://www.ojad.at/",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "yellow",
    "audit_label": "🟡 Szeneprogramm vorhanden, Schwerpunkt nicht ausschließlich Gothic",
    "audit_note": "Aktiver Kulturort mit Underground- und Metal-Programm; Gothic-Spezifik sollte bei späterer Pflege einzeln über Veranstaltungen geprüft werden.",
    "place_type": "club",
    "is_physical": true,
    "map_category": "club",
    "map_marker_type": "club",
    "map_visible": true,
    "icon_category": "club",
    "scene_relevance": [
      "alternative_darkrock"
    ]
  },
  {
    "id": "schattenwelt-festival-2026",
    "name": "Schattenwelt Festival 2026",
    "city": "Vienna",
    "country": "Austria",
    "country_name": "Österreich",
    "address": "Replugged & Szene Wien",
    "type": [
      "festival"
    ],
    "categories": [
      "Gothic",
      "Dark Electro",
      "EBM",
      "Industrial",
      "Darkwave",
      "Synthpop",
      "Post-Punk"
    ],
    "description": "Österreichisches Gothic- und Dark-Electro-Festival am 6.–7. November 2026.",
    "url": "https://schattenwelt.at/events/schattenwelt-festival-2026/",
    "date_start": "2026-11-06",
    "date_end": "2026-11-07",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Offizielle Schattenwelt-Festival-Seite.",
    "scene_relevance": [
      "gothic_core",
      "darkwave_wave",
      "ebm_industrial",
      "dark_electro_futurepop",
      "postpunk_deathrock"
    ]
  },
  {
    "id": "near-dark-2026-10",
    "name": "Near Dark",
    "city": "Vienna",
    "country": "Austria",
    "country_name": "Österreich",
    "type": [
      "recurring_event"
    ],
    "categories": [
      "Gothic",
      "Darkwave",
      "New Goth",
      "Dark 80s"
    ],
    "description": "Wiederkehrende Dark-Party im Viper Room; 3.–4. Oktober 2026 laut aktuellem Schattenwelt/Gothic-Programm.",
    "url": "https://schattenwelt.at/events/categories/gothic-party/",
    "date_start": "2026-10-03",
    "date_end": "2026-10-04",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Aktueller Veranstaltungseintrag bei Schattenwelt.",
    "scene_relevance": [
      "gothic_core",
      "darkwave_wave"
    ]
  },
  {
    "id": "electronic-fallout-2026-10",
    "name": "Electronic Fallout – Grendel & System Noire Afterparty",
    "city": "Vienna",
    "country": "Austria",
    "country_name": "Österreich",
    "address": "Replugged, Lerchenfelder Straße 23, 1070 Wien",
    "type": [
      "party"
    ],
    "categories": [
      "Dark Electro",
      "EBM",
      "Industrial"
    ],
    "description": "Dark-Electro/EBM/Industrial-Party am 3. Oktober 2026 im Anschluss an das Konzert von Grendel und System Noire.",
    "url": "https://schattenwelt.at/events/categories/gothic-party/",
    "date_start": "2026-10-03",
    "date_end": "2026-10-03",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Aktueller Schattenwelt-Eintrag.",
    "scene_relevance": [
      "ebm_industrial",
      "dark_electro_futurepop"
    ]
  },
  {
    "id": "schwarzer-reigen-2026",
    "name": "Schwarzer Reigen – Götterdämmerung",
    "city": "Vienna",
    "country": "Austria",
    "country_name": "Österreich",
    "address": "Schloss Neugebäude, Wien",
    "type": [
      "party"
    ],
    "categories": [
      "Gothic",
      "Darkwave",
      "EBM",
      "Industrial",
      "Synthpop",
      "Post-Punk"
    ],
    "description": "Schwarzer Reigen am 17. Oktober 2026 mit Classic & New Goth Sounds, Goth- und Industrial-Rock, Dark 80s, Synth/New Wave und Post-Punk.",
    "url": "https://schattenwelt.at/events/schwarzer-reigen-goetterdaemmerung-4/",
    "date_start": "2026-10-17",
    "date_end": "2026-10-18",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Offizielle Veranstaltungsseite.",
    "scene_relevance": [
      "gothic_core",
      "darkwave_wave",
      "ebm_industrial",
      "postpunk_deathrock"
    ]
  },
  {
    "id": "goththing-summer-2026",
    "name": "GothThing – Summer Edition",
    "city": "Innsbruck",
    "country": "Austria",
    "country_name": "Österreich",
    "type": [
      "party"
    ],
    "categories": [
      "Gothic",
      "EBM",
      "Electro",
      "Industrial"
    ],
    "description": "GothThing Summer Edition am 11. September 2026 in Innsbruck.",
    "url": "https://pmk.or.at/de/clubs/bhne-innsbruck/events/",
    "date_start": "2026-09-11",
    "date_end": "2026-09-11",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Offizielle PMK-Veranstaltungsseite.",
    "scene_relevance": [
      "gothic_core",
      "ebm_industrial",
      "dark_electro_futurepop"
    ]
  },
  {
    "id": "cafe-libella",
    "name": "Café LiBella",
    "city": "Altenmarkt an der Alz",
    "country": "Germany",
    "country_name": "Deutschland",
    "address": "Trostberger Str. 6, 83352 Altenmarkt an der Alz",
    "lat": 48.0018,
    "lng": 12.5347,
    "type": [
      "club",
      "bar"
    ],
    "categories": [
      "Darkwave",
      "EBM",
      "Industrial",
      "Dark Electro",
      "Alternative"
    ],
    "description": "Café LiBella mit regelmäßigem Dark-Szene-Programm. Club Bizarre: Dark Wave, Industrial, Dark Classics, Cold Wave und Future Pop. Schwarzlicht: Dark Wave, Dark Pop, EBM und Industrial.",
    "url": "https://www.cafe-libella.de/",
    "verified": true,
    "verified_date": "2026-09-17",
    "audit_status": "green",
    "audit_label": "🟢 aktuell bestätigt",
    "audit_note": "Offizielle Website mit aktuellem Dark-Szene-Programm.",
    "place_type": "club",
    "is_physical": true,
    "map_category": "club",
    "map_marker_type": "club",
    "map_visible": true,
    "icon_category": "club",
    "scene_relevance": [
      "darkwave_wave",
      "ebm_industrial",
      "dark_electro_futurepop",
      "alternative_darkrock"
    ]
  }
]

def norm(v): return str(v or "").strip().lower()

result=[]; removed=[]
for item in data:
    iid=norm(item.get("id")); name=norm(item.get("name")); city=norm(item.get("city"))
    if iid=="black-rose" or (name=="black rose" and city in {"vienna","wien"}):
        removed.append(item)
        continue
    result.append(item)

existing_ids={norm(x.get("id")) for x in result if x.get("id")}
added=[]
for item in ADDITIONS:
    iid=norm(item.get("id"))
    if iid and iid not in existing_ids:
        result.append(item)
        existing_ids.add(iid)
        added.append(item["name"])

DATA.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("Nachtfragment Österreich-Patch erfolgreich.")
print("Vorher:",len(data),"Einträge")
print("Black Rose entfernt:",len(removed))
print("Neu hinzugefügt:",len(added))
print("Nachher:",len(result),"Einträge")
print("Backup:",BACKUP)
