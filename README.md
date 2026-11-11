# Hotell-dataagent

En AI-agent som svarer på spørsmål om hoteldata på vanlig språk. Den skriver og kjører SQL
mot en database, og viser alltid SQL-en den brukte, så svarene kan etterprøves.

> Alle data er **påfunne** (ingen ekte kunder eller persondata).

## Hva det viser
- **Agent med verktøybruk** (Claude): modellen velger selv når den skal utforske skjemaet og kjøre SQL.
- **Trygg databasetilgang**: se under.
- **Gjennomsiktighet**: SQL vises for brukeren, og definisjoner (belegg, inntekt) er eksplisitte.
- **Testbarhet**: sikkerhetslagene har automatiske tester som kjører uten API-nøkkel.

## Oppsett
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python seed_db.py              # lager hotell.db med påfunne data
python test_db_tools.py        # tester uten API-nøkkel
export ANTHROPIC_API_KEY="sk-ant-..."
python agent.py
```

## Eksempler på spørsmål
- «Hvilket hotell hadde høyest belegg i juli?»

  <img width="1317" height="363" alt="image" src="https://github.com/user-attachments/assets/0882e013-b34a-411e-b9ed-b53d0c50d58b" />

- «Hva er gjennomsnittsprisen per romtype i Bergen?»

  <img width="1310" height="310" alt="image" src="https://github.com/user-attachments/assets/9ac54550-68e2-4715-a01b-d3f0e8307d17" />

- «Hvilken bookingkanal har høyest kanselleringsrate, og er det forskjell mellom byene?»
- «Hvilket hotell har lavest gjennomsnittlig vurdering, og hva klager gjestene på?»

## Sikkerhet (flere lag)
Agenten får aldri skrive til databasen. Hvert lag stopper angrep selv om de andre skulle svikte:
1. Databasen åpnes **skrivebeskyttet** (`mode=ro`).
2. En **SQLite-authorizer** tillater kun lesing. `INSERT`, `DROP`, `ATTACH`, `PRAGMA` osv. avvises.
3. Kun **én setning** som starter med `SELECT` eller `WITH`.
4. **Tidsgrense** (5 s) mot løpske spørringer, og **maks 100 rader** tilbake.

## MCP-server
De samme sikre verktøyene er også tilgjengelige som en **MCP-server** ([Model Context Protocol](https://modelcontextprotocol.io)),
slik at hvilken som helst MCP-klient (Claude Desktop, Claude Code, egne agenter) kan spørre dataene.

Serveren tilbyr:
- verktøyet `describe_schema`
- verktøyet `run_sql` (kun lesing, samme sikkerhetslag som agenten)
- ressursen `hotell://skjema`

Begge verktøyene er merket `read_only_hint`, så klienter vet at de ikke endrer noe.

```bash
python test_mcp_server.py      # starter serveren og tester den ende-til-ende
```

**Koble til Claude Code:**
```bash
claude mcp add hotell-data -- /full/sti/til/.venv/bin/python /full/sti/til/mcp_server.py
```

**Koble til Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "hotell-data": {
      "command": "/full/sti/til/.venv/bin/python",
      "args": ["/full/sti/til/mcp_server.py"]
    }
  }
}
```
Bruk hele stier. Start klienten på nytt etterpå. En stdio-server må aldri skrive til stdout (`print`),
siden det er selve protokollkanalen.

## Struktur
| Fil | Innhold |
|---|---|
| `seed_db.py` | Lager databasen med påfunne data (deterministisk) |
| `db_tools.py` | Sikre databaseverktøy, delt av agenten og MCP-serveren |
| `agent.py` | Agentløkken og systemprompten |
| `mcp_server.py` | MCP-server som eksponerer verktøyene |
| `test_db_tools.py` | Tester for verktøy og sikkerhet |
| `test_mcp_server.py` | Ende-til-ende-test av MCP-serveren |

## Videre arbeid
- Et **dashboard** med chat-boks ved siden av.
- **Datakvalitet og personvern**: sjekk for feil og maskering av persondata.
- Utrulling på **Azure**.
