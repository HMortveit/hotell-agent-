"""MCP-server for hoteldata.

Gjør samme sikre, skrivebeskyttede databaseverktøy som agenten bruker tilgjengelige for
hvilken som helst MCP-klient (Claude Desktop, Claude Code, egne agenter ...).

Kjør:  python mcp_server.py          (stdio, startes normalt av klienten)
Bruk annen database:  HOTELL_DB=/sti/til/db python mcp_server.py

VIKTIG: En stdio-server må aldri skrive til stdout (print), fordi stdout er selve
protokollkanalen. Bruk stderr eller logging hvis du trenger feilsøking.
"""
import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from db_tools import DatabaseVerktoy

DB = Path(os.environ.get("HOTELL_DB", Path(__file__).with_name("hotell.db")))
db = DatabaseVerktoy(DB)  # feiler tidlig med tydelig melding hvis databasen mangler

mcp = MCPServer(
    "hotell-data",
    instructions=(
        "Skrivebeskyttet tilgang til påfunne hoteldata (hoteller, bookinger, anmeldelser) i SQLite. "
        "Kall describe_schema først hvis du er usikker på strukturen, og bruk deretter run_sql. "
        "Kun bookinger med status 'bekreftet' regnes som opphold. Datoer er ISO-tekst (YYYY-MM-DD)."
    ),
)

LES_KUN = ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True, open_world_hint=False)


@mcp.tool(annotations=LES_KUN)
def describe_schema() -> str:
    """Viser alle tabeller med kolonner, kommentarer og antall rader."""
    return db.describe_schema()


@mcp.tool(annotations=LES_KUN)
def run_sql(sql: str) -> str:
    """Kjører én skrivebeskyttet SQL-spørring (SQLite, kun SELECT/WITH). Maks 100 rader tilbake.

    Bruk aggregering (COUNT, SUM, AVG, GROUP BY) fremfor å hente mange rader.
    """
    return db.run_sql(sql)


@mcp.resource("hotell://skjema", mime_type="text/plain")
def skjema() -> str:
    """Databaseskjemaet som en ressurs klienten kan lese uten å kalle et verktøy."""
    return db.describe_schema()


if __name__ == "__main__":
    mcp.run()  # stdio
