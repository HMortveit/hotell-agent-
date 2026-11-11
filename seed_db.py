"""Lager en SQLite-database med PÅFUNNE hoteldata (ingen persondata, ingen ekte kunder).

Bruk:  python seed_db.py          -> lager hotell.db
Samme seed gir alltid samme data, så resultater kan sammenlignes mellom kjøringer.
"""
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB = Path(__file__).with_name("hotell.db")

SCHEMA = """
CREATE TABLE hotels (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    rooms INTEGER NOT NULL              -- antall rom i hotellet
);
CREATE TABLE bookings (
    id INTEGER PRIMARY KEY,
    hotel_id INTEGER NOT NULL REFERENCES hotels(id),
    room_type TEXT NOT NULL,            -- 'standard', 'dobbel' eller 'familie'
    checkin DATE NOT NULL,              -- innsjekk, ISO-dato YYYY-MM-DD
    checkout DATE NOT NULL,             -- utsjekk (siste natt er dagen før)
    nights INTEGER NOT NULL,            -- antall netter
    guests INTEGER NOT NULL,            -- antall gjester
    price_per_night_eur REAL NOT NULL,  -- pris per natt i euro
    channel TEXT NOT NULL,              -- 'direkte', 'booking_com', 'expedia' eller 'bedrift'
    status TEXT NOT NULL                -- 'bekreftet', 'kansellert' eller 'uteblitt'
);
CREATE TABLE reviews (
    id INTEGER PRIMARY KEY,
    hotel_id INTEGER NOT NULL REFERENCES hotels(id),
    review_date DATE NOT NULL,          -- ISO-dato YYYY-MM-DD
    rating INTEGER NOT NULL,            -- 1 (dårligst) til 10 (best)
    comment TEXT NOT NULL
);
CREATE INDEX idx_bookings_hotel_checkin ON bookings(hotel_id, checkin);
CREATE INDEX idx_reviews_hotel_date ON reviews(hotel_id, review_date);
"""

# (navn, by, land, rom, prisnivå EUR, belegg-faktor, snittvurdering)
HOTELLER = [
    ("Hotell Bergen Sentrum", "Bergen", "Norge", 120, 89, 0.95, 8.3),
    ("Hotell Oslo Havn", "Oslo", "Norge", 150, 99, 1.00, 7.9),
    ("Hotell Stockholm Norr", "Stockholm", "Sverige", 100, 85, 0.92, 8.0),
    ("Hotell København Vest", "København", "Danmark", 130, 95, 0.97, 8.1),
    ("Hotell Berlin Mitte", "Berlin", "Tyskland", 180, 79, 1.02, 7.0),
    ("Hotell Amsterdam Kanal", "Amsterdam", "Nederland", 110, 109, 1.05, 7.8),
]
SESONG = {1: .55, 2: .60, 3: .65, 4: .70, 5: .78, 6: .88, 7: .93, 8: .90, 9: .80, 10: .72, 11: .65, 12: .70}
ROMTYPER = {"standard": 1.0, "dobbel": 1.15, "familie": 1.45}
KANALER = ["direkte", "booking_com", "expedia", "bedrift"]

POSITIVE = ["Rent og pent, veldig fornøyd.", "Flott beliggenhet og hyggelig betjening.",
            "Great value for money, will return.", "Enkelt, men alt vi trengte.",
            "Rask innsjekk og komfortabel seng."]
BLANDEDE = ["Greit rom, men litt trangt.", "Fin beliggenhet, men frokosten var middels.",
            "Okay stay, wifi was slow.", "Rommet var rent, men litt slitt."]
NEGATIVE = ["Mye støy om natten.", "Rommet var ikke klart ved innsjekk.",
            "Too noisy, hard to sleep.", "Dårlig ventilasjon og tynne vegger."]


def bygg(db_sti: Path = DB, fra: date = date(2026, 1, 1), til: date = date(2026, 10, 31), seed: int = 42) -> None:
    rng = random.Random(seed)
    if Path(db_sti).exists():
        Path(db_sti).unlink()
    con = sqlite3.connect(db_sti)
    con.executescript(SCHEMA)

    bookinger, anmeldelser = [], []
    for hid, (navn, by, land, rom, pris, belegg, snitt) in enumerate(HOTELLER, start=1):
        con.execute("INSERT INTO hotels VALUES (?,?,?,?,?)", (hid, navn, by, land, rom))
        dag = fra
        while dag <= til:
            occ = min(0.97, SESONG[dag.month] * belegg * (1.10 if dag.weekday() in (4, 5) else 1.0))
            # Snitt oppholdslengde er ca. 2,48 netter og ca. 88 % av bookingene blir bekreftet.
            # Faktoren 0,9 holder beleggingen realistisk under 100 %.
            snitt_innsjekk = rom * occ * 0.9 / 2.48 / 0.88
            n = max(0, round(rng.gauss(snitt_innsjekk, snitt_innsjekk ** 0.5)))
            for _ in range(n):
                romtype = rng.choices(list(ROMTYPER), [45, 40, 15])[0]
                netter = rng.choices([1, 2, 3, 4, 5, 7], [30, 30, 20, 10, 6, 4])[0]
                gjester = {"standard": rng.choice([1, 2]), "dobbel": 2, "familie": rng.choice([3, 4])}[romtype]
                kanal = rng.choices(KANALER, [30, 40, 15, 15])[0]
                sesongpris = 0.9 + 0.3 * (SESONG[dag.month] - 0.55) / 0.4
                p = pris * ROMTYPER[romtype] * sesongpris * rng.uniform(0.92, 1.08)
                if kanal == "bedrift":
                    p *= 0.92
                # Amsterdam har flere kanselleringer via booking_com
                kansell = 0.18 if (by == "Amsterdam" and kanal == "booking_com") else 0.09
                status = rng.choices(["bekreftet", "kansellert", "uteblitt"], [1 - kansell - 0.03, kansell, 0.03])[0]
                ut = dag + timedelta(days=netter)
                bookinger.append((hid, romtype, dag.isoformat(), ut.isoformat(), netter, gjester, round(p, 2), kanal, status))
                if status == "bekreftet" and ut <= til and rng.random() < 0.07:
                    karakter = int(min(10, max(1, round(rng.gauss(snitt, 1.3)))))
                    tekst = rng.choice(POSITIVE if karakter >= 8 else BLANDEDE if karakter >= 5 else NEGATIVE)
                    anm_dato = min(til, ut + timedelta(days=rng.randint(0, 3)))
                    anmeldelser.append((hid, anm_dato.isoformat(), karakter, tekst))
            dag += timedelta(days=1)

    con.executemany(
        "INSERT INTO bookings (hotel_id, room_type, checkin, checkout, nights, guests, price_per_night_eur, channel, status) "
        "VALUES (?,?,?,?,?,?,?,?,?)", bookinger)
    con.executemany("INSERT INTO reviews (hotel_id, review_date, rating, comment) VALUES (?,?,?,?)", anmeldelser)
    con.commit()
    con.close()


if __name__ == "__main__":
    bygg()
    con = sqlite3.connect(DB)
    for t in ("hotels", "bookings", "reviews"):
        print(f"{t}: {con.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]} rader")
    print(f"Laget {DB}")
