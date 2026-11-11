"""Tester MCP-serveren ende-til-ende: starter den som egen prosess og snakker MCP med den.

Kjør:  python test_mcp_server.py    (krever hotell.db, ingen API-nøkkel)
"""
import asyncio
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

HER = Path(__file__).parent


def tekst(resultat) -> str:
    return "\n".join(b.text for b in resultat.content if getattr(b, "type", "") == "text")


async def main() -> None:
    server = StdioServerParameters(command=sys.executable, args=[str(HER / "mcp_server.py")], cwd=str(HER))
    async with Client(server) as klient:
        # --- oppdagelse ---
        verktoy = {t.name: t for t in (await klient.list_tools()).tools}
        assert set(verktoy) == {"describe_schema", "run_sql"}, verktoy.keys()
        for t in verktoy.values():
            assert t.annotations and t.annotations.read_only_hint is True, f"{t.name} mangler read_only_hint"

        ressurser = [str(r.uri) for r in (await klient.list_resources()).resources]
        assert "hotell://skjema" in ressurser, ressurser

        # --- normal bruk ---
        skjema = tekst(await klient.call_tool("describe_schema", {}))
        assert "CREATE TABLE bookings" in skjema

        ut = tekst(await klient.call_tool("run_sql", {"sql": "SELECT COUNT(*) AS antall FROM hotels"}))
        assert "antall" in ut and "6" in ut, ut

        les = await klient.read_resource("hotell://skjema")
        assert "CREATE TABLE hotels" in "".join(c.text for c in les.contents), les

        # --- sikkerhet gjelder også via MCP ---
        for farlig in ["DROP TABLE hotels", "DELETE FROM bookings", "SELECT 1; DROP TABLE hotels",
                       "ATTACH DATABASE 'x.db' AS x", "PRAGMA writable_schema = 1"]:
            svar = tekst(await klient.call_tool("run_sql", {"sql": farlig}))
            assert "Feil" in svar, f"Skulle vært avvist: {farlig} -> {svar}"

        ut = tekst(await klient.call_tool("run_sql", {"sql": "SELECT COUNT(*) FROM hotels"}))
        assert "6" in ut  # databasen er intakt etter angrepsforsøkene

    print("Alle MCP-tester OK")


asyncio.run(main())
