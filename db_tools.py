"""Sikre, skrivebeskyttede databaseverktøy.

Holdes adskilt fra agenten slik at samme verktøy kan gjenbrukes, for eksempel
i en MCP-server senere.

Forsvar i flere lag (hvis ett svikter, stopper neste):
  1. Databasen åpnes skrivebeskyttet (mode=ro).
  2. SQLite-authorizer tillater kun lesing (SELECT), ikke INSERT/DROP/ATTACH/PRAGMA osv.
  3. Kun ÉN setning som starter med SELECT eller WITH.
  4. Tidsgrense (avbryter løpske spørringer) og maks antall rader tilbake.
"""
import sqlite3
import time
from pathlib import Path

MAX_RADER = 100
TIDSGRENSE_SEK = 5.0
_SQLITE_RECURSIVE = 33  # tillater WITH RECURSIVE

_TILLATT = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION, _SQLITE_RECURSIVE}


def _authorizer(action, arg1, arg2, dbname, kilde):
    return sqlite3.SQLITE_OK if action in _TILLATT else sqlite3.SQLITE_DENY


TOOLS = [
    {
        "name": "describe_schema",
        "description": "Viser alle tabeller i databasen med kolonner, kommentarer og antall rader. "
        "Bruk denne før du skriver SQL hvis du er usikker på strukturen.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "run_sql",
        "description": "Kjører én skrivebeskyttet SQL-spørring (SQLite-dialekt, kun SELECT/WITH) og returnerer "
        f"resultatet som tabell. Maks {MAX_RADER} rader. Bruk aggregering (COUNT, SUM, AVG, GROUP BY) "
        "fremfor å hente mange rader.",
        "input_schema": {
            "type": "object",
            "properties": {"sql": {"type": "string", "description": "Én SELECT-spørring."}},
            "required": ["sql"],
        },
    },
]


class DatabaseVerktoy:
    def __init__(self, db_sti: Path, tidsgrense: float = TIDSGRENSE_SEK):
        self.db_sti = Path(db_sti).resolve()
        if not self.db_sti.is_file():
            raise FileNotFoundError(f"Finner ikke databasen: {self.db_sti}. Kjør 'python seed_db.py' først.")
        self.tidsgrense = tidsgrense

    def _koble(self) -> sqlite3.Connection:
        con = sqlite3.connect(f"file:{self.db_sti}?mode=ro", uri=True)
        con.set_authorizer(_authorizer)
        frist = time.monotonic() + self.tidsgrense
        con.set_progress_handler(lambda: time.monotonic() > frist, 10_000)  # True = avbryt
        return con

    def describe_schema(self) -> str:
        con = self._koble()
        try:
            deler = []
            for navn, sql in con.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall():
                antall = con.execute(f'SELECT COUNT(*) FROM "{navn}"').fetchone()[0]
                deler.append(f"{sql}\n-- {antall} rader")
            return "\n\n".join(deler)
        finally:
            con.close()

    def run_sql(self, sql: str) -> str:
        sql = sql.strip().rstrip(";").strip()
        if not sql.lower().startswith(("select", "with")):
            return "Feil: kun SELECT-spørringer er tillatt."
        con = self._koble()
        try:
            try:
                cur = con.execute(sql)
                rader = cur.fetchmany(MAX_RADER + 1)
            except sqlite3.Error as e:
                return f"Feil: {e}"
            except sqlite3.Warning as e:  # f.eks. flere setninger
                return f"Feil: {e}"
            kolonner = [d[0] for d in cur.description or []]
        finally:
            con.close()

        avkortet = len(rader) > MAX_RADER
        rader = rader[:MAX_RADER]
        if not rader:
            return "(ingen rader)"

        def fmt(v):
            return f"{v:.2f}" if isinstance(v, float) else str(v)

        linjer = [" | ".join(kolonner), " | ".join("---" for _ in kolonner)]
        linjer += [" | ".join(fmt(v) for v in r) for r in rader]
        if avkortet:
            linjer.append(f"... [avkortet til {MAX_RADER} rader, bruk aggregering eller LIMIT]")
        return "\n".join(linjer)

    def kjor(self, navn: str, args: dict) -> str:
        try:
            if navn == "describe_schema":
                return self.describe_schema()
            if navn == "run_sql":
                return self.run_sql(**args)
            return f"Feil: ukjent verktøy '{navn}'."
        except Exception as e:  # feil sendes tilbake til modellen så den kan rette seg
            return f"Feil: {e}"
