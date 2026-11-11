"""Tester databaseverktøyene uten API-nøkkel:  python test_db_tools.py"""
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

import seed_db
from db_tools import MAX_RADER, DatabaseVerktoy

with tempfile.TemporaryDirectory() as d:
    db = Path(d) / "test.db"
    seed_db.bygg(db, fra=date(2026, 1, 1), til=date(2026, 2, 28))
    v = DatabaseVerktoy(db)

    # --- normal bruk ---
    skjema = v.kjor("describe_schema", {})
    assert "CREATE TABLE bookings" in skjema and "rader" in skjema
    ut = v.kjor("run_sql", {"sql": "SELECT COUNT(*) AS antall FROM hotels"})
    assert "antall" in ut and "6" in ut
    assert "(ingen rader)" == v.kjor("run_sql", {"sql": "SELECT * FROM hotels WHERE id = -1"})
    assert "Feil" in v.kjor("run_sql", {"sql": "SELECT finnes_ikke FROM hotels"})  # feil sendes tilbake
    assert "ukjent" in v.kjor("slett_alt", {})

    # CTE og aggregering fungerer
    ut = v.kjor("run_sql", {"sql": "WITH x AS (SELECT hotel_id, COUNT(*) n FROM bookings GROUP BY hotel_id) SELECT * FROM x"})
    assert "Feil" not in ut

    # --- sikkerhet: alt som skriver eller er farlig skal avvises ---
    farlige = [
        "DROP TABLE hotels",
        "DELETE FROM bookings",
        "UPDATE hotels SET rooms = 0",
        "INSERT INTO hotels VALUES (99,'x','x','x',1)",
        "SELECT 1; DROP TABLE hotels",
        "ATTACH DATABASE 'annen.db' AS a",
        "PRAGMA writable_schema = 1",
        "CREATE TABLE x (a INT)",
        "WITH x AS (SELECT 1) DELETE FROM hotels",
        "VACUUM INTO 'kopi.db'",
    ]
    for sql in farlige:
        assert "Feil" in v.kjor("run_sql", {"sql": sql}), f"Skulle vært avvist: {sql}"
    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM hotels").fetchone()[0] == 6  # intakt
    con.close()
    assert not (Path(d) / "annen.db").exists() and not (Path(d) / "kopi.db").exists()

    # --- begrensninger ---
    ut = v.kjor("run_sql", {"sql": "SELECT * FROM bookings"})
    assert "avkortet" in ut and ut.count("\n") <= MAX_RADER + 3

    rask = DatabaseVerktoy(db, tidsgrense=0.5)
    ut = rask.kjor("run_sql", {"sql": "WITH RECURSIVE r(x) AS (SELECT 1 UNION ALL SELECT x+1 FROM r) SELECT COUNT(*) FROM r"})
    assert "Feil" in ut, "Løpsk spørring skulle vært avbrutt"

    # --- data er deterministiske (samme seed gir samme resultat) ---
    db2 = Path(d) / "test2.db"
    seed_db.bygg(db2, fra=date(2026, 1, 1), til=date(2026, 2, 28))
    q = "SELECT COUNT(*), SUM(nights) FROM bookings"
    assert v.kjor("run_sql", {"sql": q}) == DatabaseVerktoy(db2).kjor("run_sql", {"sql": q})

print("Alle tester OK")
