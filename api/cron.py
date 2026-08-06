"""Vercel serverless endpoint for scheduled Cron jobs (Azkar, etc.)."""

import asyncio
import logging
import os

from flask import Flask, jsonify, request

from bot import build_application, check_and_send_azkar

app = Flask(__name__)
logger = logging.getLogger(__name__)


async def run_cron_tasks():
    application = build_application()
    try:
        await application.initialize()
        await check_and_send_azkar(application)
        await application.update_persistence()
    finally:
        await application.shutdown()


@app.route("/", methods=["GET", "POST"])
@app.route("/api/cron", methods=["GET", "POST"])
def cron_endpoint():
    cron_secret = os.getenv("CRON_SECRET")
    if cron_secret:
        auth_header = request.headers.get("Authorization", "")
        if auth_header != f"Bearer {cron_secret}":
            return jsonify(error="unauthorized"), 401

    try:
        asyncio.run(run_cron_tasks())
        return jsonify(ok=True, message="Cron executed successfully"), 200
    except Exception:
        logger.exception("Failed to execute cron tasks")
        return jsonify(error="cron execution failed"), 500
