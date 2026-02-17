
import base64, hashlib

def b64_nopad_decode(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def b64_nopad_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")

password = "sophietest"  # the exact password you used
salt_b64 = "xskOlLgB2DZh8IrdwWJl4Q"   # from current JSONL
stored_key = "W8i6uWeJra-TXp8WtrT04e5SgQ_6DsudaYYc_ebje1A"  # from current JSONL

salt = b64_nopad_decode(salt_b64)
dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 310000, dklen=32)
calc_key = b64_nopad_encode(dk)

print("CALC:", calc_key)
print("STOR:", stored_key)
print("MATCH:", calc_key == stored_key)
