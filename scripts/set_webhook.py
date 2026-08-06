#!/usr/bin/env python3
"""Register, inspect, or delete the Telegram webhook after deployment."""

import argparse
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def telegram_api(method: str, payload=None):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN must be configured")
    request = Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--delete", action="store_true", help="Delete the current webhook")
    parser.add_argument("--info", action="store_true", help="Print getWebhookInfo")
    parser.add_argument("--drop-pending-updates", action="store_true")
    args = parser.parse_args()

    try:
        if args.info:
            result = telegram_api("getWebhookInfo")
        elif args.delete:
            result = telegram_api("deleteWebhook", {"drop_pending_updates": args.drop_pending_updates})
        else:
            webhook_url = os.getenv("TELEGRAM_WEBHOOK_URL")
            secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
            if not webhook_url or not secret:
                raise RuntimeError("TELEGRAM_WEBHOOK_URL and TELEGRAM_WEBHOOK_SECRET must be configured")
            allowed = os.getenv(
                "TELEGRAM_ALLOWED_UPDATES", "message,callback_query"
            )
            result = telegram_api(
                "setWebhook",
                {
                    "url": webhook_url,
                    "secret_token": secret,
                    "allowed_updates": [item.strip() for item in allowed.split(",") if item.strip()],
                    "drop_pending_updates": args.drop_pending_updates,
                },
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result.get("ok"):
            sys.exit(1)
    except (RuntimeError, HTTPError, URLError) as error:
        print(f"Webhook operation failed: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
