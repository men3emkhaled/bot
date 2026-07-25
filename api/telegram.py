"""Vercel serverless endpoint for Telegram webhook updates."""

import asyncio
import hmac
import logging
import os

from flask import Flask, jsonify, request
from telegram import Update

from bot import build_application, check_and_send_azkar

app = Flask(__name__)
logger = logging.getLogger(__name__)


async def process_telegram_update(payload):
    application = build_application()
    try:
        await application.initialize()
        await check_and_send_azkar(application)
        update = Update.de_json(payload, application.bot)
        await application.process_update(update)
        # update_interval=0 persists user_data, bot_data and conversations now,
        # before this serverless invocation ends.
        await application.update_persistence()
    finally:
        await application.shutdown()


@app.route("/", methods=["GET", "POST"])
@app.route("/api/telegram", methods=["GET", "POST"])
def telegram_webhook():
    if request.method == "GET":
        return jsonify(status="ok")

    secret = os.getenv("TELEGRAM_WEBHOOK_SECRET")
    supplied_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if not secret or not hmac.compare_digest(supplied_secret, secret):
        logger.warning("Rejected Telegram webhook request with an invalid secret token")
        return jsonify(error="unauthorized"), 401

    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error="invalid update"), 400

    try:
        asyncio.run(process_telegram_update(payload))
        logger.info("Processed Telegram update_id=%s", payload.get("update_id"))
        return jsonify(ok=True), 200
    except Exception:
        # A 500 makes Telegram retry this update. Do not log message contents or secrets.
        logger.exception("Failed to process Telegram update_id=%s", payload.get("update_id"))
        return jsonify(error="update processing failed"), 500
