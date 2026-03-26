import hashlib
import platform
import threading
import requests
from typing import Callable, Optional

# ── YOUR ngrok URL ─────────────────────────────────────────────────────────── #
SERVER_URL = "https://vasiliki-extensile-rita.ngrok-free.dev"

TIMEOUT = 6   # seconds to wait for ping response

# ── module-level state ────────────────────────────────────────────────────── #
is_online:                  bool  = False
check_complete:             bool  = False   # True only after BOTH ping AND /check have finished
server_username:            str   = ""      # username locked on server for this hwid
username_locked:            bool  = False   # whether server has locked the username
cooldown_remaining:         float = 0.0     # seconds remaining on report cooldown
upload_cooldown_remaining:  float = 0.0     # seconds remaining on upload cooldown
is_banned:                  bool  = False   # whether this hwid is banned
ban_reason:                 str   = ""      # reason for the ban


def get_hardware_id() -> str:
    """
    Generate a unique, anonymous hardware ID for this machine.
    Hashed with SHA-256 so no personal info is ever sent.
    """
    try:
        raw = (
            platform.node() +
            platform.machine() +
            platform.processor() +
            str(platform.version())
        )
        return hashlib.sha256(raw.encode()).hexdigest()
    except Exception:
        # fallback — still unique enough per machine
        import uuid
        return hashlib.sha256(str(uuid.getnode()).encode()).hexdigest()


# ── cached hwid so we only compute it once ────────────────────────────────── #
_hwid: Optional[str] = None

def hwid() -> str:
    global _hwid
    if _hwid is None:
        _hwid = get_hardware_id()
    return _hwid


def check_connection(
    on_success: Optional[Callable] = None,
    on_failure: Optional[Callable] = None,
    timeout: int = TIMEOUT
) -> None:
    """
    Ping the server and fetch this user's server-side state (cooldown, username).
    Calls on_success() or on_failure() with the result.
    """
    def _check():
        global is_online, check_complete, server_username, username_locked, cooldown_remaining, upload_cooldown_remaining, is_banned, ban_reason
        try:
            # 1. ping
            resp = requests.get(
                f"{SERVER_URL}/ping",
                timeout=timeout,
                headers={"ngrok-skip-browser-warning": "true"}
            )
            if resp.status_code != 200:
                raise ConnectionError(f"Ping returned {resp.status_code}")

            is_online = True

            # 2. fetch server-side user state
            resp2 = requests.post(
                f"{SERVER_URL}/check",
                data={"hwid": hwid()},
                timeout=timeout,
                headers={"ngrok-skip-browser-warning": "true"}
            )
            if resp2.status_code == 200:
                data                      = resp2.json()
                server_username           = data.get("username", "")
                username_locked           = data.get("username_locked", False)
                cooldown_remaining        = data.get("cooldown_remaining", 0.0)
                upload_cooldown_remaining = data.get("upload_cooldown_remaining", 0.0)
                is_banned                 = data.get("is_banned", False)
                ban_reason                = data.get("ban_reason", "")
                print(f"[CONNECTION] Server online ✓  username_locked={username_locked}  "
                      f"cooldown={cooldown_remaining:.0f}s  upload_cooldown={upload_cooldown_remaining:.0f}s  "
                      f"banned={is_banned}")

            # Both requests done — safe for UI to read state now
            check_complete = True

            if on_success:
                on_success()

        except Exception as e:
            print(f"[CONNECTION] Server unreachable: {e}")
            is_online      = False
            check_complete = True   # mark complete even on failure so poll doesn't hang
            if on_failure:
                on_failure()

    threading.Thread(target=_check, daemon=True).start()


def refresh_user_state(on_done: Optional[Callable] = None) -> None:
    """
    Re-fetch this user's server-side state (cooldown, username lock).
    Call this after a successful or failed report submission so the client
    always reflects what the SERVER has recorded — nothing is assumed locally.
    """
    def _refresh():
        global server_username, username_locked, cooldown_remaining, upload_cooldown_remaining, is_banned, ban_reason
        try:
            resp = requests.post(
                f"{SERVER_URL}/check",
                data={"hwid": hwid()},
                timeout=TIMEOUT,
                headers={"ngrok-skip-browser-warning": "true"}
            )
            if resp.status_code == 200:
                data                      = resp.json()
                server_username           = data.get("username", "")
                username_locked           = data.get("username_locked", False)
                cooldown_remaining        = data.get("cooldown_remaining", 0.0)
                upload_cooldown_remaining = data.get("upload_cooldown_remaining", 0.0)
                is_banned                 = data.get("is_banned", False)
                ban_reason                = data.get("ban_reason", "")
                print(f"[CONNECTION] State refreshed ✓  username={server_username!r}  "
                      f"locked={username_locked}  cooldown={cooldown_remaining:.0f}s  "
                      f"upload_cooldown={upload_cooldown_remaining:.0f}s  banned={is_banned}")
        except Exception as e:
            print(f"[CONNECTION] refresh_user_state failed: {e}")
        finally:
            if on_done:
                on_done()

    threading.Thread(target=_refresh, daemon=True).start()


def submit_report(
    username: str,
    title: str,
    description: str,
    attachment_path: Optional[str] = None,
    project_path: Optional[str] = None,
    timeout: int = 30
) -> tuple[bool, str, float]:
    """
    POST a report to the server with hardware ID.
    Returns (success: bool, message: str, cooldown_seconds: float).
    cooldown_seconds is the violation cooldown if one was applied, else 0.
    """
    if not is_online:
        return False, "Not connected to server", 0.0

    try:
        import os
        data = {
            "hwid":        hwid(),
            "username":    username,
            "title":       title,
            "description": description,
        }
        files = {}
        if attachment_path and os.path.exists(attachment_path):
            files["file"] = (os.path.basename(attachment_path), open(attachment_path, "rb"))
        if project_path and os.path.exists(project_path):
            files["project"] = (os.path.basename(project_path), open(project_path, "rb"))
        if not files:
            files = None

        resp = requests.post(
            f"{SERVER_URL}/report",
            data=data,
            files=files,
            timeout=timeout,
            headers={"ngrok-skip-browser-warning": "true"}
        )

        if resp.status_code == 200:
            return True, "ok", 0.0
        else:
            try:
                body     = resp.json()
                msg      = body.get("message") or body.get("error", f"HTTP {resp.status_code}")
                cooldown = float(body.get("cooldown", 0))
            except Exception:
                msg      = f"HTTP {resp.status_code}"
                cooldown = 0.0
            if resp.status_code == 403:
                try:
                    b = resp.json()
                    if b.get("error") == "banned":
                        global is_banned, ban_reason
                        is_banned  = True
                        ban_reason = b.get("ban_reason", "")
                        print("[CONNECTION] Ban detected via /report response")
                except Exception:
                    pass
            return False, msg, cooldown

    except Exception as e:
        return False, str(e), 0.0

def check_username_available(username: str) -> tuple[bool, str]:
    """
    Check if a username is available (not taken by another hwid).
    Returns (available: bool, error_message: str).
    """
    try:
        resp = requests.post(
            f"{SERVER_URL}/check_username",
            data={"hwid": hwid(), "username": username},
            timeout=TIMEOUT,
            headers={"ngrok-skip-browser-warning": "true"},
        )
        if resp.status_code == 200:
            return resp.json().get("available", True), ""
        return False, f"Could not verify username (HTTP {resp.status_code})"
    except Exception as e:
        return False, str(e)


def submit_suggestion(
    username: str,
    title: str,
    description: str,
    timeout: int = 15
) -> tuple[bool, str]:
    """
    POST a suggestion to the server.
    Returns (success: bool, message: str).
    """
    if not is_online:
        return False, "Not connected to server"
    try:
        resp = requests.post(
            f"{SERVER_URL}/suggest",
            data={"hwid": hwid(), "username": username, "title": title, "description": description},
            timeout=timeout,
            headers={"ngrok-skip-browser-warning": "true"},
        )
        if resp.status_code == 200:
            return True, "ok"
        try:
            body = resp.json()
            msg  = body.get("error", f"HTTP {resp.status_code}")
            if resp.status_code == 403 and body.get("error") == "banned":
                global is_banned, ban_reason
                is_banned  = True
                ban_reason = body.get("ban_reason", "")
                print("[CONNECTION] Ban detected via /suggest response")
        except Exception:
            msg = f"HTTP {resp.status_code}"
        return False, msg
    except Exception as e:
        return False, str(e)


def submit_username_change(
    username: str,
    new_username: str,
    reason: str,
    timeout: int = 15
) -> tuple[bool, str]:
    """
    POST a username change request to the server.
    Returns (success: bool, message: str).
    """
    if not is_online:
        return False, "Not connected to server"
    try:
        resp = requests.post(
            f"{SERVER_URL}/username_change",
            data={"hwid": hwid(), "username": username, "new_username": new_username, "reason": reason},
            timeout=timeout,
            headers={"ngrok-skip-browser-warning": "true"},
        )
        if resp.status_code == 200:
            return True, "ok"
        try:
            body = resp.json()
            msg  = body.get("error", f"HTTP {resp.status_code}")
            if resp.status_code == 403 and body.get("error") == "banned":
                global is_banned, ban_reason
                is_banned  = True
                ban_reason = body.get("ban_reason", "")
                print("[CONNECTION] Ban detected via /username_change response")
        except Exception:
            msg = f"HTTP {resp.status_code}"
        return False, msg
    except Exception as e:
        return False, str(e)


def update_username_on_server(
    hwid_target: str,
    old_username: str,
    new_username: str,
    timeout: int = 30
) -> tuple[bool, int, str]:
    """
    Notify the server to rename a user and patch their Discord posts.
    Returns (success: bool, posts_updated: int, error_message: str).
    Only call from dev tools — does not require is_online guard.
    """
    try:
        resp = requests.post(
            f"{SERVER_URL}/update_username",
            data={"hwid": hwid_target, "old_username": old_username, "new_username": new_username},
            timeout=timeout,
            headers={"ngrok-skip-browser-warning": "true"},
        )
        if resp.status_code == 200:
            data = resp.json()
            return True, data.get("posts_updated", 0), ""
        try:
            msg = resp.json().get("error", f"HTTP {resp.status_code}")
        except Exception:
            msg = f"HTTP {resp.status_code}"
        return False, 0, msg
    except Exception as e:
        return False, 0, str(e)


def submit_appeal(
    username: str,
    reason: str,
    timeout: int = 15
) -> tuple[bool, str]:
    """
    POST a ban appeal to the server.
    Returns (success: bool, message: str).
    """
    try:
        resp = requests.post(
            f"{SERVER_URL}/appeal",
            data={"hwid": hwid(), "username": username, "reason": reason},
            timeout=timeout,
            headers={"ngrok-skip-browser-warning": "true"},
        )
        if resp.status_code == 200:
            return True, "ok"
        try:
            msg = resp.json().get("error", f"HTTP {resp.status_code}")
        except Exception:
            msg = f"HTTP {resp.status_code}"
        return False, msg
    except Exception as e:
        return False, str(e)


def ban_user_on_server(target_hwid: str, reason: str, timeout: int = 10) -> tuple[bool, str]:
    """Ban a user by hwid. Returns (success, error_message)."""
    try:
        resp = requests.post(
            f"{SERVER_URL}/ban",
            data={"target_hwid": target_hwid, "reason": reason},
            timeout=timeout,
            headers={"ngrok-skip-browser-warning": "true"},
        )
        if resp.status_code == 200:
            return True, ""
        return False, resp.json().get("error", f"HTTP {resp.status_code}")
    except Exception as e:
        return False, str(e)


def unban_user_on_server(target_hwid: str, timeout: int = 10) -> tuple[bool, str]:
    """Unban a user by hwid. Returns (success, error_message)."""
    try:
        resp = requests.post(
            f"{SERVER_URL}/unban",
            data={"target_hwid": target_hwid},
            timeout=timeout,
            headers={"ngrok-skip-browser-warning": "true"},
        )
        if resp.status_code == 200:
            return True, ""
        return False, resp.json().get("error", f"HTTP {resp.status_code}")
    except Exception as e:
        return False, str(e)


def submit_rating(message_id: int, rating: int) -> tuple[bool, dict, str]:

    try:
        resp = requests.post(
            f"{SERVER_URL}/rate",
            data={"hwid": hwid(), "message_id": str(message_id), "rating": str(rating)},
            timeout=TIMEOUT,
            headers={"ngrok-skip-browser-warning": "true"},
        )
        if resp.status_code == 200:
            return True, resp.json(), ""
        body = resp.json()
        return False, {}, body.get("error", f"HTTP {resp.status_code}")
    except Exception as e:
        return False, {}, str(e)