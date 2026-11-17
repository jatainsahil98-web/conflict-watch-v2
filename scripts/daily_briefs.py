"""Daily 0600 IST job: build every theatre's brief, raise FLASH alerts, and "send" them.

    python scripts/daily_briefs.py                 # build briefs for the latest data day + 6 days of history
    python scripts/daily_briefs.py --date 2026-11-12 --days 7
    python scripts/daily_briefs.py --send-email    # also send by SMTP (needs the CW_SMTP_* variables below)

Demo mode (default) sends nothing: it writes the in-app inbox (outputs/theatre/briefs.json), a Markdown and an
HTML e-mail per theatre per day (outputs/theatre/briefs/<date>/), and .eml files in outputs/theatre/outbox/
that any mail client opens.

Real e-mail (optional). Set, then pass --send-email:
    CW_SMTP_HOST, CW_SMTP_PORT (587), CW_SMTP_USER, CW_SMTP_PASS, CW_MAIL_FROM,
    CW_MAIL_TO_WTC, CW_MAIL_TO_NTC, CW_MAIL_TO_MTC, CW_MAIL_TO_CDS   (comma-separated addresses)
SMS / WhatsApp are mock previews only (a gateway such as an SMS aggregator would be wired here).

Scheduling 0600 IST = 0030 UTC:
    Windows:  schtasks /Create /SC DAILY /ST 06:00 /TN ConflictWatchBriefs /TR "python <repo>\\scripts\\daily_briefs.py"
    Linux:    30 0 * * *  cd <repo> && python scripts/daily_briefs.py       (crontab, UTC clock)
    GitHub:   .github/workflows/daily-briefs.yml (cron "30 0 * * *"), uploads the briefs as an artefact
"""
from __future__ import annotations

import argparse
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src import theatre as TH  # noqa: E402


def _message(b: dict, to: list[str]) -> EmailMessage:
    m = EmailMessage()
    m["Subject"] = f"[CONFLICT WATCH] {b['code']} daily brief {b['dtg']}: {b['rating']} {b['arrow']} (NOTIONAL)"
    m["From"] = os.environ.get("CW_MAIL_FROM", "conflict-watch@localhost")
    m["To"] = ", ".join(to) or "commander@example.invalid"
    m.set_content(TH.to_markdown(b))
    m.add_alternative(TH.to_email_html(b), subtype="html")
    return m


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="last data day (default: latest GDELT day)")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--send-email", action="store_true")
    ap.add_argument("--figs", action="store_true", help="also write outputs/figures/34-38_theatre_* (needs kaleido)")
    a = ap.parse_args()
    out = TH.run(a.date, a.days)
    meta = out["meta"]
    print(f"Built {len(TH.ROLES)} x {a.days} briefs in {meta['build_seconds']} s; data to {meta['data_end']}; "
          f"brief {meta['brief_dtg']}; {meta['n_flash']} FLASH alerts")
    outbox = TH.OUT / "outbox"
    outbox.mkdir(exist_ok=True)
    today = {k: out["briefs"][k][-1] for k in TH.ROLES}
    sender = None
    if a.send_email:
        host = os.environ.get("CW_SMTP_HOST")
        if not host:
            sys.exit("--send-email needs CW_SMTP_HOST (and CW_SMTP_USER / CW_SMTP_PASS); nothing sent.")
        sender = smtplib.SMTP(host, int(os.environ.get("CW_SMTP_PORT", "587")), timeout=30)
        sender.starttls()
        if os.environ.get("CW_SMTP_USER"):
            sender.login(os.environ["CW_SMTP_USER"], os.environ.get("CW_SMTP_PASS", ""))
    for k, b in today.items():
        to = [x.strip() for x in os.environ.get(f"CW_MAIL_TO_{k}", "").split(",") if x.strip()]
        msg = _message(b, to)
        (outbox / f"{b['date']}_{k}.eml").write_bytes(bytes(msg))
        (outbox / f"{b['date']}_{k}_sms.txt").write_text(TH.to_sms(b), encoding="utf-8")
        (outbox / f"{b['date']}_{k}_whatsapp.txt").write_text(TH.to_whatsapp(b), encoding="utf-8")
        if sender and to:
            sender.send_message(msg)
            print(f"  sent {k} to {len(to)} recipient(s)")
        print(f"  {k}: {b['bluf']}")
    for f in out["flashes"]:
        if f["date"] == meta["data_end"]:
            print(f"  {f['text']}")
    if sender:
        sender.quit()
    if a.figs:
        from src import theatre_viz as TV
        print("  figures:", ", ".join(TV.export_figures(out)))


if __name__ == "__main__":
    main()
