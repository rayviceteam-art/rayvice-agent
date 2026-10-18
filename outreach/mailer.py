"""SMTP send + IMAP scan (replies / unsubscribe / bounces). Plain-text, human-style."""
import email
import imaplib
import re
import smtplib
import ssl
from email.header import decode_header
from email.message import EmailMessage
from email.utils import parseaddr

import config
from outreach import store

UNSUB_WORDS = ("unsubscribe", "stop", "remove me", "take me off", "opt out", "opt-out",
               "don't contact", "do not contact", "no thanks", "not interested")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def configured():
    return bool(config.OUTREACH_FROM_EMAIL and config.OUTREACH_EMAIL_PASS)


def send_one(to_email, subject, body):
    frm = config.OUTREACH_FROM_EMAIL
    if not configured():
        return {"ok": False, "error": "email creds missing (OUTREACH_FROM_EMAIL / OUTREACH_EMAIL_PASS)"}
    msg = EmailMessage()
    msg["From"] = f"{config.OUTREACH_FROM_NAME} <{frm}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    if config.OUTREACH_REPLY_TO:
        msg["Reply-To"] = config.OUTREACH_REPLY_TO
    msg.set_content(body)
    try:
        ctx = ssl.create_default_context()
        if config.OUTREACH_SMTP_PORT == 465:
            with smtplib.SMTP_SSL(config.OUTREACH_SMTP_HOST, config.OUTREACH_SMTP_PORT, timeout=30, context=ctx) as s:
                s.login(frm, config.OUTREACH_EMAIL_PASS)
                s.send_message(msg)
        else:
            with smtplib.SMTP(config.OUTREACH_SMTP_HOST, config.OUTREACH_SMTP_PORT, timeout=30) as s:
                s.starttls(context=ctx)
                s.login(frm, config.OUTREACH_EMAIL_PASS)
                s.send_message(msg)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300]}


def _dec(s):
    if not s:
        return ""
    out = []
    for part, enc in decode_header(s):
        out.append(part.decode(enc or "utf-8", "ignore") if isinstance(part, bytes) else part)
    return "".join(out)


def _plain_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                try:
                    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "ignore")
                except Exception:
                    continue
        return ""
    try:
        return msg.get_payload(decode=True).decode(msg.get_content_charset() or "utf-8", "ignore")
    except Exception:
        return ""


def _handle(sender, subject, body, summary):
    low = (body or "").lower()
    is_bounce = any(x in sender for x in ("mailer-daemon", "postmaster", "@googlemail.com")) and "delivery" in (subject or "").lower()
    if not is_bounce:
        is_bounce = sender.startswith("mailer-daemon") or sender.startswith("postmaster")
    if is_bounce:
        for e in set(EMAIL_RE.findall(body or "")):
            e = e.lower()
            if e == (config.OUTREACH_FROM_EMAIL or "").lower():
                continue
            if store.lead_by_email(e):
                store.add_suppression(e, "bounce")
                store.record_reply(e, subject, (body or "")[:300], "bounce")
                store.set_lead_status(store.lead_by_email(e)["id"], "BOUNCED")
                summary["bounces"] += 1
        return

    lead = store.lead_by_email(sender)
    if not lead:
        # Hamare lead nahi (newsletters/marketing ke footer me bhi 'unsubscribe' hota hai).
        # Sirf chhota, saaf opt-out message ho to suppress karo.
        if len((body or "").split()) <= 40 and any(w in low for w in UNSUB_WORDS):
            store.add_suppression(sender, "unsubscribe (short opt-out)")
            summary["unsub"] += 1
        return

    kind = "unsub" if any(w in low for w in UNSUB_WORDS) else "reply"
    store.record_reply(sender, subject, (body or "")[:500], kind)
    if kind == "unsub":
        store.add_suppression(sender, "unsubscribe reply")
        store.set_lead_status(lead["id"], "UNSUB")
        summary["unsub"] += 1
    else:
        store.set_lead_status(lead["id"], "REPLIED")
        summary["replies"] += 1


def scan_inbox(limit=40):
    frm = config.OUTREACH_FROM_EMAIL
    if not configured():
        return {"ok": False, "error": "creds missing"}
    summary = {"scanned": 0, "replies": 0, "unsub": 0, "bounces": 0}
    try:
        im = imaplib.IMAP4_SSL(config.OUTREACH_IMAP_HOST, config.OUTREACH_IMAP_PORT, timeout=30)
        im.login(frm, config.OUTREACH_EMAIL_PASS)
        im.select("INBOX")
        typ, data = im.search(None, "UNSEEN")
        ids = (data[0].split() if data and data[0] else [])[-limit:]
        for num in ids:
            typ, msgdata = im.fetch(num, "(RFC822)")
            if typ != "OK" or not msgdata or not isinstance(msgdata[0], (tuple, list)):
                continue
            msg = email.message_from_bytes(msgdata[0][1])
            summary["scanned"] += 1
            sender = parseaddr(msg.get("From", ""))[1].lower()
            _handle(sender, _dec(msg.get("Subject", "")), _plain_body(msg), summary)
            im.store(num, "+FLAGS", "\\Seen")
        im.logout()
        return {"ok": True, **summary}
    except Exception as e:
        return {"ok": False, "error": str(e)[:300], **summary}
