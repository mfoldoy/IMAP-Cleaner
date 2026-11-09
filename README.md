# Outlook Cleaner for Hermes

A Hermes Skill that audits and cleans a ServeTheWorld IMAP mailbox. The first run is a **read-only** analysis, and all processing happens locally.

- IMAP: `imap1.stwcp.net`, port `993`, SSL/TLS, username = full email address (SMTP is not used).
- Requirements: Windows, Python 3.10+, Hermes. Optional: Ollama for a local LLM.

## Usage (in your own PowerShell)
```powershell
.\run-audit.ps1 -TestConnection     # tests login and folder structure, exports nothing
.\run-audit.ps1                     # export -> classify -> report
.\run-audit.ps1 -Llm ollama         # also use a local LLM for uncertain messages
```
The password is typed into a hidden prompt and is never stored or logged. Open `reports\report.md` and `reports\candidates.csv` yourself.

## Contents
| File | Purpose |
|---|---|
| `scripts/oc_common.py` | IMAP core (`SafeImap`: EXAMINE/SEARCH/FETCH BODY.PEEK only), UTF-7, parsing, logging |
| `scripts/imap_audit.py` | Export of all folders (UID + UIDVALIDITY), `--test-connection` |
| `scripts/classify.py`, `rules.py` | Rule engine (phishing, spam, marketing, newsletters) and protection of important mail |
| `scripts/llm_local.py` | Local LLM client (Ollama / OpenAI-compatible), loopback only |
| `scripts/report.py` | Markdown report and CSV; the console shows aggregate numbers only |
| `scripts/quarantine.py` | Approved cleanup: plan, dry run, move to `Hermes-Review` |
| `tests/` | Offline test suite against a mock IMAP server |

## Safety
- No permanent deletion, no unsubscribe, no flag changes during analysis.
- Protected messages (known correspondents, answered/flagged mail, work, finance, public services, account security) are never proposed for moving.
- All actions are logged to `logs/actions.jsonl` (no passwords or message content).
- `reports/` and `logs/` contain private data and are in `.gitignore`.
- No external LLM and no upload of mail content.

## Cleanup (after you have read the report)
```powershell
py -3 scripts\quarantine.py plan --category marketing
py -3 scripts\quarantine.py apply --user "you@example.com"             # verified dry run against the live mailbox
py -3 scripts\quarantine.py apply --user "you@example.com" --execute   # requires typing: MOVE <count>
```
Messages are moved to `Hermes-Review` using `UID MOVE` (or `UID COPY` + `\Deleted` + `UID EXPUNGE` of exactly the copied UIDs when UIDPLUS is available). UIDVALIDITY and Message-ID are re-checked before each move. Moves can be undone by moving the messages back.

## Local LLM
```powershell
winget install Ollama.Ollama
ollama pull qwen2.5:7b-instruct
```
Only uncertain messages are sent, and only to `127.0.0.1`; any other host is refused in code.

## Tests
```powershell
py -3 -W ignore -m unittest discover -s tests
```
The rule keywords are Norwegian and English, and the test fixtures are synthetic Norwegian mail. The rule weights are heuristic and have not been validated on real mail, so review the report before any cleanup.
