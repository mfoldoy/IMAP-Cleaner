#!/usr/bin/env python3
"""Build the human-readable review report (Markdown + CSV) from classified.jsonl.

The console output contains aggregate numbers only (no senders/subjects), so it is safe
to relay through an agent that uses a remote model. The report files themselves contain
private details and must stay on this machine.
"""
import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime

CAT_NO = {
    "important_or_personal": "Viktig/personlig", "work": "Jobb", "financial_or_receipt": "Økonomi/kvittering",
    "government_or_legal": "Offentlig/juridisk", "security_or_account": "Sikkerhet/konto",
    "newsletter": "Nyhetsbrev", "marketing": "Markedsføring", "automated_notification": "Automatisk varsling",
    "spam_or_phishing": "Spam/phishing", "low_value": "Lav verdi", "uncertain": "Usikker",
}
ACT_NO = {"keep": "Behold", "review": "Se over", "archive_candidate": "Arkivkandidat",
          "quarantine_candidate": "Karantenekandidat"}


def load(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def cell(s, n=90):
    s = " ".join(str(s if s is not None else "").split()).replace("|", "¦")
    return s if len(s) <= n else s[:n - 1] + "…"


def csv_safe(s):
    s = str(s if s is not None else "")
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(cell(c, 90) for c in r) + " |" for r in rows]
    return "\n".join(out) + "\n"


def sender_rows(items, top=None):
    g = defaultdict(list)
    for r in items:
        g[r["from_addr"]].append(r)
    rows = []
    for addr, rs in sorted(g.items(), key=lambda kv: -len(kv[1])):
        cats = Counter(r["category"] for r in rs).most_common(1)[0][0]
        acts = Counter(r["action"] for r in rs).most_common(1)[0][0]
        unseen = sum(1 for r in rs if not r["seen"])
        rows.append([addr or "(ukjent)", len(rs), unseen, CAT_NO.get(cats, cats), ACT_NO.get(acts, acts)])
    return rows[:top] if top else rows


def msg_rows(items, limit):
    items = sorted(items, key=lambda r: (r["folder"], str(r.get("date") or "")))
    return [[r["folder"], r["uid"], (r.get("date") or "")[:10], r["from_addr"], r["subject"],
             "%.2f" % r["confidence"], r["reason"]] for r in items[:limit]]


MSG_HEAD = ["Mappe", "UID", "Dato", "Avsender", "Emne", "Konf.", "Begrunnelse"]


def build_markdown(res, meta):
    own = [r for r in res if r.get("own_message")]
    inc = [r for r in res if not r.get("own_message")]
    cats = Counter(r["category"] for r in inc)
    acts = Counter(r["action"] for r in inc)
    total = len(inc)
    md = []
    md.append("# Postkasserapport (kun lesing)\n")
    md.append("Generert %s. Ingen e-poster er flyttet, slettet eller endret.\n" % datetime.now().strftime("%Y-%m-%d %H:%M"))
    md.append("> Denne filen inneholder private opplysninger. Behold den lokalt; ikke last den opp eller lim den inn i en nettbasert tjeneste.\n")

    md.append("## 1. Sammendrag\n")
    md.append("- Innkommende/lagrede meldinger analysert: **%d** (pluss %d egne sendte/utkast som alltid beholdes)\n" % (total, len(own)))
    md.append("- Lokal LLM brukt på %d meldinger.\n" % sum(1 for r in res if r.get("llm_used")))
    md.append("\n### Per kategori\n")
    md.append(table(["Kategori", "Antall", "Andel"], [[CAT_NO.get(c, c), n, "%.1f%%" % (100 * n / total if total else 0)]
                                                      for c, n in cats.most_common()]))
    md.append("\n### Per mappe og kategori\n")
    per_folder = defaultdict(Counter)
    for r in inc:
        per_folder[r["folder"]][r["category"]] += 1
    md.append(table(["Mappe", "Totalt", "Beskyttet", "Bulk (nyhetsbrev/markedsføring)", "Spam/phishing", "Usikker"],
                    [[f, sum(c.values()),
                      sum(v for k, v in c.items() if k in ("important_or_personal", "work", "financial_or_receipt", "government_or_legal", "security_or_account")),
                      c["newsletter"] + c["marketing"], c["spam_or_phishing"], c["uncertain"]]
                     for f, c in sorted(per_folder.items())]))

    md.append("\n## 2. Avsendere med størst volum (topp 25)\n")
    md.append(table(["Avsender", "Antall", "Uleste", "Hovedkategori", "Hovedhandling"], sender_rows(inc, 25)))

    bulk = [r for r in inc if r["category"] in ("newsletter", "marketing") and not r["protected"]]
    md.append("\n## 3. Nyhetsbrev- og markedsføringskandidater\n")
    md.append("%d meldinger fra %d avsendere. «Uleste» viser hvor mange du aldri har åpnet.\n\n" %
              (len(bulk), len({r['from_addr'] for r in bulk})))
    md.append(table(["Avsender", "Antall", "Uleste", "Hovedkategori", "Hovedhandling"], sender_rows(bulk, 60)))

    threats = [r for r in inc if r["category"] == "spam_or_phishing"]
    phish = [r for r in threats if r.get("threat_kind") == "phishing"]
    md.append("\n## 4. Spam- og phishingkandidater\n")
    md.append("**Phishing (%d):** ikke åpne lenker eller vedlegg i disse meldingene.\n\n" % len(phish))
    md.append(table(MSG_HEAD, msg_rows(phish, 200)))
    md.append("\n**Øvrig spam (%d):**\n\n" % (len(threats) - len(phish)))
    md.append(table(MSG_HEAD, msg_rows([r for r in threats if r not in phish], 200)))

    junk_ok = [r for r in inc if r["folder_role"] == "junk" and r["protected"]]
    md.append("\n## 5. Mulige falske positiver i søppelpost (beskyttet innhold)\n")
    md.append("%d meldinger i søppelpost ser legitime ut og bør vurderes flyttet tilbake manuelt.\n\n" % len(junk_ok))
    md.append(table(MSG_HEAD, msg_rows(junk_ok, 100)))
    md.append("\n### Beskyttede meldinger totalt\n")
    md.append(table(["Kategori", "Antall"], [[CAT_NO[c], cats[c]] for c in
               ("important_or_personal", "work", "financial_or_receipt", "government_or_legal", "security_or_account")]))

    unc = [r for r in inc if r["category"] == "uncertain" or r["action"] == "review"]
    md.append("\n## 6. Usikre meldinger som krever manuell vurdering (%d)\n" % len(unc))
    md.append(table(MSG_HEAD, msg_rows(unc, 200)))
    if len(unc) > 200:
        md.append("\n(Viser 200 av %d; se candidates.csv for alle.)\n" % len(unc))

    md.append("\n## 7. Anbefalte handlinger og estimert effekt\n")
    q = [r for r in inc if r["action"] == "quarantine_candidate"]
    a = [r for r in inc if r["action"] == "archive_candidate"]
    md.append(table(["Handling", "Meldinger", "Andel av postkassen"],
                    [[ACT_NO[k], acts[k], "%.1f%%" % (100 * acts[k] / total if total else 0)] for k in ACT_NO]))
    md.append("\n1. **Karantene (%d):** flyttes til `Hermes-Review` etter din godkjenning – kan angres ved å flytte tilbake.\n" % len(q))
    md.append("2. **Arkiv (%d):** lav risiko; kan flyttes til `Hermes-Review` eller arkivmappe etter godkjenning.\n" % len(a))
    md.append("3. **Se over (%d):** ingen automatisk handling anbefales.\n" % acts["review"])
    md.append("4. **Behold (%d):** viktig/beskyttet – røres ikke.\n" % acts["keep"])
    md.append("5. Avmelding og permanent sletting krever egen, separat godkjenning og er ikke gjort.\n")
    md.append("\nEstimert effekt hvis 1 og 2 godkjennes: **%d** færre meldinger i aktive mapper (%.1f%%).\n" %
              (len(q) + len(a), 100 * (len(q) + len(a)) / total if total else 0))
    md.append("\n## 8. Metode og sikkerhet\n")
    md.append("- Klassifisering er gjort lokalt (regelmotor + valgfri lokal LLM). Ingen e-postinnhold er sendt til eksterne tjenester.\n"
              "- Beskyttelse: meldinger du har besvart/flagget, avsendere du har skrevet til, eget domene, samtaletråder, "
              "banker/offentlige/sikkerhetsmeldinger har forrang og blir aldri foreslått for karantene.\n"
              "- Alle handlinger er loggført i `logs/actions.jsonl` (uten passord).\n")
    return "\n".join(md)


def write_csv(res, path):
    cols = ["folder", "uid", "uidvalidity", "date", "from_addr", "subject", "category", "confidence",
            "action", "threat_kind", "reason"]
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in res:
            if r["action"] != "keep":
                w.writerow([csv_safe(r.get(c)) for c in cols])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--classified", default="reports/classified.jsonl")
    ap.add_argument("--output-dir", default="reports")
    args = ap.parse_args(argv)
    res = load(args.classified)
    os.makedirs(args.output_dir, exist_ok=True)
    md_path = os.path.join(args.output_dir, "report.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(build_markdown(res, None))
    csv_path = os.path.join(args.output_dir, "candidates.csv")
    write_csv(res, csv_path)
    inc = [r for r in res if not r.get("own_message")]
    cats, acts = Counter(r["category"] for r in inc), Counter(r["action"] for r in inc)
    print("Rapport skrevet (kun aggregerte tall vises her):")
    print("  Meldinger analysert: %d" % len(inc))
    for c, n in cats.most_common():
        print("  %-24s %d" % (c, n))
    print("  Anbefalte handlinger:", dict(acts))
    print("  Rapport:    %s" % md_path)
    print("  Kandidater: %s" % csv_path)
    print("Ingen e-post er endret. Filene inneholder private data og skal bli lokalt.")


if __name__ == "__main__":
    main()
