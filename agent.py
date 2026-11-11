"""Spør-dataene-dine-agent: svarer på spørsmål om hoteldata ved å skrive og kjøre SQL.

Bruk:  python agent.py [--db hotell.db]
Agenten har KUN lesetilgang til databasen (se db_tools.py for sikkerhetslagene).
"""
import json
import os
import sys
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from db_tools import TOOLS, DatabaseVerktoy

# Leser ANTHROPIC_API_KEY fra .env i prosjektmappen. En allerede satt miljøvariabel vinner.
load_dotenv(Path(__file__).with_name(".env"))

MODEL = "claude-sonnet-5-5"
MAX_STEG = 12  # sikkerhetsgrense mot endeløse løkker

SYSTEMPROMPT = """Du er en dataanalytiker for en hotellkjede. Du svarer på spørsmål ved å skrive SQL mot en SQLite-database.

Arbeidsmåte:
- Kall describe_schema først hvis du er usikker på tabeller og kolonner. Ikke gjett kolonnenavn.
- Bruk run_sql. Foretrekk aggregering (COUNT, SUM, AVG, GROUP BY) framfor å hente mange rader.
- Hvis en spørring feiler, les feilmeldingen og prøv igjen med rettet SQL.
- Svar bare med tall du faktisk har hentet. Hvis dataene ikke kan svare på spørsmålet, si det tydelig.

Definisjoner (bruk disse konsekvent):
- Kun bookinger med status 'bekreftet' regnes som opphold. 'kansellert' og 'uteblitt' teller ikke som belegg eller inntekt.
- Inntekt = nights * price_per_night_eur for bekreftede bookinger (i EUR).
- Belegg i en periode = solgte rom-netter / (hotellets rooms * antall netter i perioden).
  En booking dekker nettene fra og med checkin til dagen før checkout. For en periode må du bare telle
  nettene som faller innenfor perioden (bruk overlapp mellom oppholdet og perioden).
- Datoer er ISO-tekst (YYYY-MM-DD). Dataene dekker 2026-01-01 til 2026-10-31.

Svarformat: svar kort på norsk, nevn de viktigste tallene, og oppgi gjerne hvilken periode/definisjon du brukte.
Alle data er påfunne eksempeldata."""


def kjor_agent(oppgave: str, verktoy: DatabaseVerktoy, client: anthropic.Anthropic, historikk: list) -> None:
    historikk.append({"role": "user", "content": oppgave})
    for _ in range(MAX_STEG):
        r = client.messages.create(
            model=MODEL, max_tokens=2000, system=SYSTEMPROMPT, tools=TOOLS, messages=historikk
        )
        historikk.append({"role": "assistant", "content": r.content})

        for blokk in r.content:
            if blokk.type == "text" and blokk.text.strip():
                print(f"\n{blokk.text}")

        if r.stop_reason != "tool_use":
            return

        resultater = []
        for blokk in r.content:
            if blokk.type == "tool_use":
                if blokk.name == "run_sql":
                    print(f"\n  SQL: {blokk.input.get('sql', '').strip()}")  # vis alltid SQL (gjennomsiktighet)
                else:
                    print(f"  · {blokk.name}({json.dumps(blokk.input, ensure_ascii=False)})")
                resultater.append(
                    {"type": "tool_result", "tool_use_id": blokk.id, "content": verktoy.kjor(blokk.name, blokk.input)}
                )
        historikk.append({"role": "user", "content": resultater})
    print(f"\n(Stoppet etter {MAX_STEG} steg.)")


def main() -> None:
    args = sys.argv[1:]
    db = Path(__file__).with_name("hotell.db")
    if args[:1] == ["--db"] and len(args) == 2:
        db = Path(args[1])
    elif args:
        sys.exit("Bruk: python agent.py [--db sti/til/database.db]")

    try:
        verktoy = DatabaseVerktoy(db)
    except FileNotFoundError as e:
        sys.exit(str(e))
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("Mangler ANTHROPIC_API_KEY. Kopier .env.example til .env og legg inn nøkkelen din der.")
    client = anthropic.Anthropic()  # leser ANTHROPIC_API_KEY fra miljøet
    historikk: list = []
    print(f"Spør-dataene-dine-agent klar ({verktoy.db_sti.name}, kun lesetilgang).")
    print("Eksempel: «Hvilket hotell hadde høyest belegg i juli?»  Skriv 'avslutt' for å stoppe.")
    while True:
        oppgave = input("\nDu: ").strip()
        if oppgave.lower() in ("avslutt", "exit", "q"):
            break
        if oppgave:
            kjor_agent(oppgave, verktoy, client, historikk)


if __name__ == "__main__":
    main()
