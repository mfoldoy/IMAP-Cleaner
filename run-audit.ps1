<#
.SYNOPSIS
  Read-only mailbox audit: export -> local classification -> report.
  The IMAP password is typed into a hidden prompt (getpass) and is never stored, logged or passed as an argument.
.EXAMPLE
  .\run-audit.ps1 -TestConnection
  .\run-audit.ps1
  .\run-audit.ps1 -Llm ollama -Model qwen2.5:7b-instruct
#>
param(
    [string]$User,
    [switch]$TestConnection,
    [ValidateSet("off", "ollama", "openai")][string]$Llm = "off",
    [string]$Model = "qwen2.5:7b-instruct",
    [string]$LlmUrl,
    [int]$LlmMax = 300,
    [int]$Limit = 0,
    [switch]$ExcludeTrashJunk
)
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot
$py = if (Get-Command py -ErrorAction SilentlyContinue) { @("py", "-3") } else { @("python") }
function Run-Py([string[]]$PyArgs) {
    & $py[0] @($py | Select-Object -Skip 1) @PyArgs
    if ($LASTEXITCODE -ne 0) { throw "Steg feilet (exit $LASTEXITCODE)" }
}

if (-not $User) { $User = Read-Host "Full e-postadresse" }
New-Item -ItemType Directory -Force reports, logs | Out-Null

$audit = @("scripts\imap_audit.py", "--user", $User, "--output", "reports\mailbox-audit.jsonl")
if ($TestConnection) {
    Run-Py ($audit + "--test-connection")
    return
}
if (-not $ExcludeTrashJunk) { $audit += "--include-trash-junk" }
if ($Limit -gt 0) { $audit += @("--limit", $Limit) }

Write-Host "`n[1/3] Skrivebeskyttet eksport (EXAMINE + BODY.PEEK). Skriv passordet nar du blir bedt om det."
Run-Py $audit

Write-Host "`n[2/3] Lokal klassifisering (ingen data forlater maskinen)"
$cls = @("scripts\classify.py", "--input", "reports\mailbox-audit.jsonl", "--output", "reports\classified.jsonl", "--llm", $Llm)
if ($Llm -ne "off") { $cls += @("--llm-model", $Model, "--llm-max", $LlmMax) }
if ($LlmUrl) { $cls += @("--llm-url", $LlmUrl) }
Run-Py $cls

Write-Host "`n[3/3] Rapport"
Run-Py @("scripts\report.py", "--classified", "reports\classified.jsonl")

Write-Host "`nFerdig. Apne reports\report.md og reports\candidates.csv selv. Ingenting i postkassen er endret."
