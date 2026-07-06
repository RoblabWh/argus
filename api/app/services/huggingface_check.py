import logging
import requests

logger = logging.getLogger(__name__)


def try_hf_token(token: str, model_id: str, timeout: float = 8.0) -> tuple[bool, str, str | None]:
    """
    Validate a Hugging Face access token and check that it can reach the
    (license-gated) re-ID model. Returns (success, message, detail).
    Does not read or write config.
    """
    if not token:
        return False, "Hugging Face token is empty", None

    headers = {"Authorization": f"Bearer {token}"}
    try:
        who = requests.get(
            "https://huggingface.co/api/whoami-v2", headers=headers, timeout=timeout
        )
    except requests.exceptions.Timeout:
        return False, f"Connection timed out after {timeout}s", "timeout"
    except requests.exceptions.ConnectionError as e:
        return False, "Could not connect to huggingface.co", str(e)
    except requests.exceptions.RequestException as e:
        return False, "Request failed", str(e)

    if who.status_code == 401:
        return False, "Hugging Face rejected the token", "HTTP 401"
    if who.status_code != 200:
        return (
            False,
            f"Unexpected response from Hugging Face (HTTP {who.status_code})",
            who.text[:200],
        )
    username = who.json().get("name", "unknown")

    # Token itself is valid — now check access to the gated model weights.
    try:
        access = requests.head(
            f"https://huggingface.co/{model_id}/resolve/main/config.json",
            headers=headers,
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.exceptions.RequestException as e:
        return False, "Token is valid, but the model access check failed", str(e)

    # A redirect to the CDN also means access is granted.
    if access.status_code in (200, 302, 307):
        return True, f"Token is valid (user: {username}) with access to {model_id}", None
    if access.status_code in (401, 403):
        return (
            False,
            f"Token is valid (user: {username}), but has no access to {model_id}. "
            f"Accept the model license on https://huggingface.co/{model_id} "
            "with the account this token belongs to.",
            f"HTTP {access.status_code}",
        )
    return (
        False,
        f"Unexpected response checking model access (HTTP {access.status_code})",
        access.text[:200] if access.text else None,
    )
