# accounts.py (FINAL VERSION — JSONL storage, OneDrive-safe)

from dotenv import load_dotenv
load_dotenv()

import io
import time
import base64
import secrets
import hashlib
import requests
import json
import traceback
from typing import Optional, Tuple

from one_drive import download_file, upload_small_file, acquire_token

# ================================================================
#                        CONFIGURATION
# ================================================================
ACCOUNTS_JSONL_PATH = "NBFKTPAPP/Admin/accounts.jsonl"

ALGO = "pbkdf2-sha256"
ITERATIONS = 310_000
DKLEN = 32


# ================================================================
#                BASE64 HELPERS — NO PADDING
# ================================================================
def _b64encode_nopad(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode("utf-8").rstrip("=")

def _b64decode_nopad(s: str) -> bytes:
    padding = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + padding)


# ================================================================
#                     JSONL READ / WRITE HELPERS
# ================================================================
def _read_jsonl(drive_id: str, path: str) -> list[dict]:
    """Download and parse accounts.jsonl from OneDrive."""
    b = download_file(drive_id, path)
    if not b:
        return []

    text = b.decode("utf-8", errors="replace")

    if not text.strip():
        return []

    rows = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        raw_line = line
        if not raw_line.strip():
            continue
        try:
            rows.append(json.loads(raw_line))
        except json.JSONDecodeError as e:
            continue
    return rows


def _write_jsonl(drive_id: str, path: str, rows: list[dict]) -> None:
    """Write rows back to OneDrive as JSONL."""
    txt = "\n".join(json.dumps(r, separators=(",", ":")) for r in rows)

    try:
        token = acquire_token()
    except Exception as ex:
        raise

    try:
        resp = requests.put(
            f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{path}:/content",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "text/plain"},
            data=txt.encode("utf-8"),
            timeout=120,
        )
        resp.raise_for_status()
    except Exception as ex:
        raise


# ================================================================
#                  PASSWORD HASHING (JSON WRAPPER)
# ================================================================
def _hash_password(password: str) -> dict:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, ITERATIONS, dklen=DKLEN
    )
    return {
        "algo": ALGO,
        "iter": ITERATIONS,
        "salt": _b64encode_nopad(salt),
        "key": _b64encode_nopad(dk),
    }


def _verify_password(password: str, record: dict) -> bool:
    try:
        algo = record.get("algo")
        iters = int(record.get("iter"))
        salt_b64 = record.get("salt")
        stored_key = record.get("key")

        if algo != ALGO:
            return False

        salt = _b64decode_nopad(salt_b64)

        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iters, dklen=DKLEN
        )
        calc = _b64encode_nopad(dk)
        
        try:
            equal = hashlib.compare_digest(calc, stored_key)
        except Exception as ex:
            equal = (calc == stored_key)

        return equal
    except Exception:
        return False


# ================================================================
#                 ACCOUNT MANAGEMENT FUNCTIONS
# ================================================================
import time as _time

def find_account(drive_id: str, email: str) -> Optional[dict]:
    email = (email or "").strip().lower()
    for attempt in range(3):
        rows = _read_jsonl(drive_id, ACCOUNTS_JSONL_PATH)
        if rows:
            pass
        for r in rows:
            if (r.get("email", "").strip().lower() == email):
                return r
        _time.sleep(0.6)
    return None



def create_account(
    drive_id: str,
    email: str,
    password: str,
    product_key: str | None = None,
    activated: bool = False,
) -> bool:

    email = (email or "").strip().lower()
    rows = _read_jsonl(drive_id, ACCOUNTS_JSONL_PATH)

    # Prevent duplicates
    if any(r.get("email", "").lower() == email for r in rows):
        return False

    ts = time.strftime("%Y-%m-%d %H:%M:%S")

    h = _hash_password(password)

    rows.append({
        "email": email,
        "password": h,
        "created_at": ts,
        "activated": activated,
        "product_key": product_key or "",
        "last_login_at": "",
        "role": "user",
    })

    try:
        _write_jsonl(drive_id, ACCOUNTS_JSONL_PATH, rows)
    except Exception as ex:
        return False

    try:
        new_rows = _read_jsonl(drive_id, ACCOUNTS_JSONL_PATH)
        found = any(r.get("email", "").strip().lower() == email for r in new_rows)
    except Exception as ex:
        pass

    return True


def set_activated(drive_id: str, email: str, product_key: str) -> None:
    email = (email or "").strip().lower()
    rows = _read_jsonl(drive_id, ACCOUNTS_JSONL_PATH)

    for r in rows:
        if r.get("email", "").lower() == email:
            r["activated"] = True
            r["product_key"] = product_key
            break

    _write_jsonl(drive_id, ACCOUNTS_JSONL_PATH, rows)


def record_login(drive_id: str, email: str) -> None:
    email = (email or "").strip().lower()
    rows = _read_jsonl(drive_id, ACCOUNTS_JSONL_PATH)

    for r in rows:
        if r.get("email", "").lower() == email:
            r["last_login_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
            break

    _write_jsonl(drive_id, ACCOUNTS_JSONL_PATH, rows)


def verify_login(drive_id: str, email: str, password: str) -> Tuple[bool, bool, str]:
    r = find_account(drive_id, email)
    if not r:
        return (False, False, "")

    pwrecord = r.get("password", {})

    ok = _verify_password(password, pwrecord)

    if not ok:
        return (False, False, "")

    activated = bool(r.get("activated", False))
    return (True, activated, r.get("product_key", ""))
