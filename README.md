# Outlook Cleaner for Hermes

Hermes Skill for å analysere og rydde en ServeTheWorld IMAP-postkasse. Første leveranse er en **skrivebeskyttet** analyse. All behandling skjer lokalt.

- IMAP: `imap1.stwcp.net`, port `993`, SSL/TLS, brukernavn = full e-postadresse (SMTP brukes ikke).
- Krav: Windows, Python 3.10+, Hermes. Valgfritt: Ollama for lokal LLM.

## Kjøring (i din egen PowerShell)
```powershell
.\run-audit.ps1 -TestConnection     # tester innlogging og mappestruktur, eksporterer ingenting
.\run-audit.ps1                     # eksport -> klassifisering -> rapport
.\run-audit.ps1 -Llm ollama         # i tillegg lokal LLM for usikre meldinger
```
Passordet skrives i en skjult prompt og lagres/logges aldri. Åpne `reports\report.md` og `reports\candidates.csv` selv.

## Innhold
| Fil | Formål |
|---|---|
| `scripts/oc_common.py` | IMAP-kjerne (`SafeImap`: kun EXAMINE/SEARCH/FETCH BODY.PEEK), UTF-7, parsing, logging |
| `scripts/imap_audit.py` | Eksport av alle mapper (UID + UIDVALIDITY), `--test-connection` |
| `scripts/classify.py`, `rules.py` | Regelmotor (phishing, spam, markedsføring, nyhetsbrev) + beskyttelse av viktig e-post |
| `scripts/llm_local.py` | Lokal LLM (Ollama/OpenAI-kompatibel), kun loopback |
| `scripts/report.py` | Rapport (norsk) og CSV; konsollen viser kun aggregerte tall |
| `scripts/quarantine.py` | Godkjent opprydding: plan, tørrkjøring, flytting til `Hermes-Review` |
| `tests/` | Offline testsuite mot mock-IMAP-server |

## Sikkerhet
Ingen permanent sletting, ingen unsubscribe, ingen flagg-endringer i analysen. Beskyttede meldinger (kjente korrespondenter, besvarte/flaggede, jobb, økonomi, det offentlige, kontosikkerhet) foreslås aldri flyttet. Alle handlinger logges i `logs/actions.jsonl` (uten passord og innhold). `reports/` og `logs/` inneholder private data og er i `.gitignore`.

## Opprydding (etter at du har lest rapporten)
```powershell
py -3 scripts\quarantine.py plan --category marketing
py -3 scripts\quarantine.py apply --user "din@adresse"             # tørrkjøring mot live postkasse
py -3 scripts\quarantine.py apply --user "din@adresse" --execute   # krever at du skriver: FLYTT <antall>
```

## Lokal LLM
```powershell
winget install Ollama.Ollama
ollama pull qwen2.5:7b-instruct
```
Bare usikre meldinger sendes (til `127.0.0.1`). Andre verter avvises i koden.

## Test
```powershell
py -3 -W ignore -m unittest discover -s tests
```
Regelvektene er heuristiske og ikke validert på din ekte e-post; gjennomgå rapporten før opprydding.
