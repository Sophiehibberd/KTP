

# activation_context.py
from shiny import session as Session

# Per-session store: session.id -> email
_session_emails: dict[str, str] = {}

def set_user_email(email: str):
    s = Session.get_current_session()
    if s is None:
        return
    sid = s.id                      # every session has a unique id  [2](https://deepwiki.com/posit-dev/py-shiny/2.2-session-management)
    _session_emails[sid] = (email or "").strip()

    # Ensure we clean up when the browser session ends
    def _cleanup():
        _session_emails.pop(sid, None)
    s.on_ended(_cleanup)            # run cleanup on session end       [2](https://deepwiki.com/posit-dev/py-shiny/2.2-session-management)

def get_user_email() -> str | None:
    s = Session.get_current_session()
    if s is None:
        return None
    return _session_emails.get(s.id)


    
