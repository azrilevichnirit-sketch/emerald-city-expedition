"""Shutterstock DOWNLOADER — simple executor #2.

Licenses and downloads exactly one image, exactly per the master's format +
size, exactly to the saved_path the orchestrator specified. Does not choose.
Does not process. Bytes-in-bytes-out.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parent.parent
KEYS = PROJECT / "keys"
SS_API = "https://api.shutterstock.com/v2"


def _load_key(env_var: str, file_path: Path) -> str:
    v = os.environ.get(env_var)
    if v:
        return v.strip()
    if file_path.exists():
        return file_path.read_text("utf-8").strip()
    raise RuntimeError(f"missing {env_var} env var or file {file_path}")


SS_TOKEN = _load_key("SHUTTERSTOCK_TOKEN", KEYS / "shutterstock" / "access_token.txt")
_SUBSCRIPTION_ID: str | None = None


def _headers() -> dict:
    return {"Authorization": f"Bearer {SS_TOKEN}", "Accept": "application/json"}


def _get_json(url: str, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, headers=_headers(), method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _post_json(url: str, body: dict, timeout: int = 90) -> dict:
    h = dict(_headers())
    h["Content-Type"] = "application/json"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=h, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def subscription_id() -> str:
    global _SUBSCRIPTION_ID
    if _SUBSCRIPTION_ID:
        return _SUBSCRIPTION_ID
    data = _get_json(f"{SS_API}/user/subscriptions")
    subs = data.get("data", [])
    if not subs:
        raise RuntimeError("no active Shutterstock subscription on this token")
    _SUBSCRIPTION_ID = subs[0]["id"]
    return _SUBSCRIPTION_ID


def license_and_download(image_id: str, fmt: str, size: str,
                          saved_path: Path) -> dict:
    """License the image, download the binary, write to saved_path.

    Returns a report dict. On failure sets status=FAIL_* and leaves no file.
    """
    report: dict = {
        "image_id": image_id,
        "format": fmt,
        "size": size,
        "saved_path": str(saved_path),
        "status": "PENDING",
    }

    # License.
    try:
        sub = subscription_id()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        report["status"] = f"FAIL_subscription_http_{e.code}"
        report["error"] = body
        return report
    except Exception as e:
        report["status"] = "FAIL_subscription_exception"
        report["error"] = f"{type(e).__name__}: {e}"
        return report

    lic_url = f"{SS_API}/images/licenses?subscription_id={sub}&format={fmt}&size={size}"
    try:
        lic = _post_json(lic_url, {"images": [{"image_id": image_id}]})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        report["status"] = f"FAIL_license_http_{e.code}"
        report["error"] = body
        return report
    except Exception as e:
        report["status"] = "FAIL_license_exception"
        report["error"] = f"{type(e).__name__}: {e}"
        return report

    entry = lic.get("data", [{}])[0]
    if "download" not in entry or "url" not in entry.get("download", {}):
        report["status"] = "FAIL_license_no_url"
        report["error"] = json.dumps(entry)[:400]
        return report

    report["license_id"] = entry.get("license_id")
    download_url = entry["download"]["url"]

    # Download the bytes — 1:1, no processing.
    try:
        req = urllib.request.Request(download_url, headers={"Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=180) as r:
            data = r.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:200]
        report["status"] = f"FAIL_download_http_{e.code}"
        report["error"] = body
        return report
    except Exception as e:
        report["status"] = "FAIL_download_exception"
        report["error"] = f"{type(e).__name__}: {e}"
        return report

    # Write.
    try:
        saved_path.parent.mkdir(parents=True, exist_ok=True)
        saved_path.write_bytes(data)
    except Exception as e:
        report["status"] = "FAIL_write"
        report["error"] = f"{type(e).__name__}: {e}"
        return report

    report["saved_bytes"] = len(data)
    report["sha256"] = hashlib.sha256(data).hexdigest()
    report["status"] = "OK"
    return report


def main(argv: list[str]) -> int:
    if len(argv) < 5:
        print("usage: shutterstock_downloader.py <image_id> <format> <size> <saved_path>")
        return 1
    image_id, fmt, size, saved_path = argv[1:5]
    report = license_and_download(image_id, fmt, size, Path(saved_path))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
