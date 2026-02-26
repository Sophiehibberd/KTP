import os
import base64
import requests

from one_drive import acquire_token

GRAPH_SENDER_UPN = os.environ.get("GRAPH_SENDER_UPN")  # e.g. "no-reply@yourdomain.com"

def send_results_email(
    to_email: str,
    subject: str,
    body_text: str,
    attachments: list[tuple[str, str, bytes]] | None = None,
) -> None:
    """
    Send an email via Microsoft Graph.
    Uses application token from acquire_token().

    Env required:
      - GRAPH_SENDER_UPN (mailbox to send as)
      - TENANT_ID / CLIENT_ID / CLIENT_SECRET (already used by one_drive.py)
    """
    if not GRAPH_SENDER_UPN:
        raise RuntimeError("GRAPH_SENDER_UPN env var not set.")

    token = acquire_token()

    msg = {
        "message": {
            "subject": subject,
            "body": {"contentType": "Text", "content": body_text},
            "toRecipients": [{"emailAddress": {"address": to_email}}],
        },
        "saveToSentItems": "false",
    }

    if attachments:
        msg["message"]["attachments"] = []
        for (name, content_type, b) in attachments:
            msg["message"]["attachments"].append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": name,
                "contentType": content_type,
                "contentBytes": base64.b64encode(b).decode("utf-8"),
            })

    url = f"https://graph.microsoft.com/v1.0/users/{GRAPH_SENDER_UPN}/sendMail"
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=msg,
        timeout=30,
    )
    r.raise_for_status()