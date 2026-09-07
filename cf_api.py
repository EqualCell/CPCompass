"""Shared Codeforces client with request pacing and friendly API errors."""
import time
from threading import Lock
import requests


class CodeforcesError(ValueError):
    pass


_lock = Lock()
_last_request = 0.0


def api_get(method, **params):
    global _last_request
    with _lock:
        time.sleep(max(0, 2.1 - (time.monotonic() - _last_request)))
        try:
            response = requests.get(
                f"https://codeforces.com/api/{method}", params=params, timeout=30
            )
            data = response.json()
            if data.get("status") == "FAILED":
                raise CodeforcesError(data.get("comment", "Codeforces could not complete the request."))
            response.raise_for_status()
            if data.get("status") != "OK" or "result" not in data:
                raise CodeforcesError("Codeforces returned an unexpected response. Please try again.")
            return data["result"]
        except requests.exceptions.JSONDecodeError as exc:
            raise CodeforcesError("Codeforces returned an unreadable response. Please try again.") from exc
        except requests.RequestException as exc:
            raise CodeforcesError("Could not reach Codeforces. Please try again shortly.") from exc
        finally:
            _last_request = time.monotonic()
