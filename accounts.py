# accounts.py (FINAL VERSION — JSONL storage, OneDrive-safe)
# Patched with extra diagnostics for password verification & file IO

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
        print("ACCOUNTS DEBUG _read_jsonl: download_file returned empty")
        return []

    text = b.decode("utf-8", errors="replace")
    
    print("ACCOUNTS DEBUG _read_jsonl: bytes=", len(b), "chars=", len(text))
    # show a safe preview (escaped newlines) so we can detect truncation
    print("ACCOUNTS DEBUG _read_jsonl peek:", text[:400].replace("\n","\\n"))

    # BOM detection
    if text.startswith("\ufeff"):
        print("ACCOUNTS DEBUG _read_jsonl: UTF-8 BOM detected at file start")

    if not text.strip():
        return []

    rows = []
    lines = text.splitlines()
    print(f"ACCOUNTS DEBUG _read_jsonl line_count={len(lines)}")
    for i, line in enumerate(lines):
        # do not strip inner JSON content; only trim leading/trailing whitespace of the line
        raw_line = line
        if not raw_line.strip():
            continue
        # show the first few line previews for diagnostics
        if i < 6:
            print(f"ACCOUNTS DEBUG line {i} len={len(raw_line)} repr[:120]:", repr(raw_line[:120]))
        try:
            rows.append(json.loads(raw_line))
        except json.JSONDecodeError as e:
            print("ACCOUNTS DEBUG _read_jsonl JSON error:", e, "on line index", i)
            print("LINE repr (truncated):", repr(raw_line[:400]))
            continue
    return rows


def _write_jsonl(drive_id: str, path: str, rows: list[dict]) -> None:
    """Write rows back to OneDrive as JSONL."""
    txt = "\n".join(json.dumps(r, separators=(",", ":")) for r in rows)
    print("ACCOUNTS DEBUG _write_jsonl: preparing to save bytes=", len(txt))
    print("ACCOUNTS DEBUG _write_jsonl preview:", txt[:300].replace("\n","\\n"))

    try:
        token = acquire_token()
    except Exception as ex:
        print("ACCOUNTS DEBUG _write_jsonl: acquire_token failed:", ex)
        raise

    try:
        resp = requests.put(
            f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{path}:/content",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "text/plain"},
            data=txt.encode("utf-8"),
            timeout=120,
        )
        # show status and body on failure to help debug OneDrive issues
        if not resp.ok:
            print("ACCOUNTS DEBUG _write_jsonl: PUT failed", resp.status_code)
            try:
                print("ACCOUNTS DEBUG _write_jsonl response:", resp.text[:1000])
            except Exception:
                pass
        resp.raise_for_status()
    except Exception as ex:
        print("ACCOUNTS DEBUG _write_jsonl: exception during upload", ex)
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

        # Debug prints for diagnostics:
        print("ACCOUNTS DEBUG _verify_password record keys:", sorted(list(record.keys())))
        print("ACCOUNTS DEBUG _verify_password algo:", repr(algo))
        print("ACCOUNTS DEBUG _verify_password iter type/value:", type(record.get("iter")), repr(record.get("iter")))
        print("ACCOUNTS DEBUG _verify_password salt repr:", repr(salt_b64))
        print("ACCOUNTS DEBUG _verify_password stored_key repr (start):", repr(stored_key[:60]) if isinstance(stored_key, str) else repr(stored_key))

        if algo != ALGO:
            print("ACCOUNTS DEBUG _verify_password: unexpected algo", algo)
            return False

        # Ensure salt decodes correctly (will raise if invalid)
        salt = _b64decode_nopad(salt_b64)

        dk = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iters, dklen=DKLEN
        )
        calc = _b64encode_nopad(dk)
        
        # detailed compare output
        try:
            equal = hashlib.compare_digest(calc, stored_key)
        except Exception as ex:
            print("ACCOUNTS DEBUG _verify_password: compare_digest error", ex)
            equal = (calc == stored_key)

        print("ACCOUNTS DEBUG _verify_password lengths:",
            "stored_len=", len(stored_key) if isinstance(stored_key, str) else None,
            "calc_len=", len(calc),
            "equal=", equal,
            "stored[:6]=", (stored_key[:6] if isinstance(stored_key, str) else None),
            "calc[:6]=", calc[:6])

        return equal
    except Exception:
        # Print full traceback to help debugging (but not exposing secrets beyond logs)
        print("ACCOUNTS DEBUG _verify_password: exception during verification:")
        traceback.print_exc()
        return False


# ================================================================
#                 ACCOUNT MANAGEMENT FUNCTIONS
# ================================================================
import time as _time

def find_account(drive_id: str, email: str) -> Optional[dict]:
    email = (email or "").strip().lower()
    for attempt in range(3):  # small retry helps if OneDrive read lags after write
        rows = _read_jsonl(drive_id, ACCOUNTS_JSONL_PATH)
        print(f"ACCOUNTS DEBUG find_account attempt={attempt} rows={len(rows)}")
        if rows:
            print("ACCOUNTS DEBUG emails:", [r.get("email") for r in rows])
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
        print("ACCOUNTS DEBUG create_account: duplicate detected for", email)
        return False

    ts = time.strftime("%Y-%m-%d %H:%M:%S")

    
    h = _hash_password(password)
    print("ACCOUNTS DEBUG create_account:",
          "pwd_len=", len(password),
          "salt[:6]=", h["salt"][:6],
          "key[:6]=", h["key"][:6])


    rows.append({
        "email": email,
        "password": h,
        "created_at": ts,
        "activated": activated,
        "product_key": product_key or "",
        "last_login_at": "",
        "role": "user",
    })

    # Write and then re-read to confirm
    try:
        _write_jsonl(drive_id, ACCOUNTS_JSONL_PATH, rows)
        print("ACCOUNTS DEBUG create_account saved, rows_after=", len(rows))
    except Exception as ex:
        print("ACCOUNTS DEBUG create_account: write failed", ex)
        return False

    # short verification read to ensure the record is present
    try:
        new_rows = _read_jsonl(drive_id, ACCOUNTS_JSONL_PATH)
        found = any(r.get("email", "").strip().lower() == email for r in new_rows)
        print("ACCOUNTS DEBUG create_account post-read found=", found, "rows_now=", len(new_rows))
    except Exception as ex:
        print("ACCOUNTS DEBUG create_account post-read failed", ex)

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
    print("ACCOUNTS DEBUG verify_login() email=", repr(email))
    r = find_account(drive_id, email)
    print("ACCOUNTS DEBUG find_account found:", bool(r))
    if not r:
        return (False, False, "")

    pwrecord = r.get("password", {})
    print("ACCOUNTS DEBUG pwrecord keys:", sorted(list(pwrecord.keys())))

    ok = _verify_password(password, pwrecord)
    print("ACCOUNTS DEBUG _verify_password returned:", ok)

    if not ok:
        # when failing, print some additional context for debugging
        print("ACCOUNTS DEBUG verify_login: failed verification for", email)
        return (False, False, "")

    activated = bool(r.get("activated", False))
    return (True, activated, r.get("product_key", ""))


