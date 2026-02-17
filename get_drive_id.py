
from dotenv import load_dotenv
load_dotenv()

import os
import requests
from msal import ConfidentialClientApplication

TENANT_ID = os.environ["TENANT_ID"]
CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]

# 🔁 Put YOUR work email (UPN) here; this is the OneDrive owner we want.
USER_UPN = os.environ.get("TARGET_UPN") or "sophie@bedfed.org.uk"

AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
SCOPES = ["https://graph.microsoft.com/.default"]

# Acquire token (application permissions)
app = ConfidentialClientApplication(
    client_id=CLIENT_ID,
    client_credential=CLIENT_SECRET,
    authority=AUTHORITY,
)
result = app.acquire_token_for_client(scopes=SCOPES)

if "access_token" not in result:
    print("ERROR acquiring token:", result)
    raise SystemExit(1)

token = result["access_token"]

def call(url: str):
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    print(f"GET {url} -> {r.status_code}")
    try:
        print(r.json())
    except Exception:
        print(r.text)
    return r

# ❌ Will fail with app-only (delegated-only endpoint)
# call("https://graph.microsoft.com/v1.0/me/drive")

# ✅ Works with app-only if permissions + tenant policy allow it
resp = call(f"https://graph.microsoft.com/v1.0/users/{USER_UPN}/drive")

# 🔁 Fallbacks you can try if the above still errors:
# 1) list drives for that user (rarely needed)
# call(f"https://graph.microsoft.com/v1.0/users/{USER_UPN}/drives")

# 2) If your OneDrive URL is known (my.sharepoint.com/personal/...),
#    you can also use the SharePoint path form:
# SP_HOST = "yourtenant-my.sharepoint.com"
# SP_PATH = "/personal/yourname_youruniversity_ac_uk"
# call(f"https://graph.microsoft.com/v1.0/sites/{SP_HOST}:{SP_PATH}:/drive")
