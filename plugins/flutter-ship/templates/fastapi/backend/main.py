"""Thin FastAPI app: /health plus optional Firebase App Check."""

from __future__ import annotations

import logging
import os

import firebase_admin
from fastapi import Depends, FastAPI, HTTPException, Request
from firebase_admin import app_check, credentials

logger = logging.getLogger("uvicorn.error")

APP_CHECK_ENABLED = os.environ.get("FIREBASE_APP_CHECK_ENABLED", "false").lower() == "true"

app = FastAPI(title="{{APP_NAME}} API")


def _init_firebase() -> None:
    if firebase_admin._apps:
        return
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path:
        cred = credentials.Certificate(cred_path)
        project_id = cred.project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
        options = {"projectId": project_id} if project_id else {}
        firebase_admin.initialize_app(cred, options=options)
    else:
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
        options = {"projectId": project_id} if project_id else {}
        firebase_admin.initialize_app(options=options)


if APP_CHECK_ENABLED:
    try:
        _init_firebase()
        logger.info("Firebase App Check enforcement is ENABLED")
    except Exception as e:
        logger.error("Firebase init failed while App Check enforcement was requested: %s", e)
        raise RuntimeError(
            "Firebase Admin SDK initialization failed while "
            "FIREBASE_APP_CHECK_ENABLED=true"
        ) from e
else:
    logger.info("Firebase App Check enforcement is DISABLED")


async def verify_app_check(request: Request) -> None:
    """Verify the Firebase App Check token, or no-op when enforcement is off."""
    if not APP_CHECK_ENABLED:
        return

    token = request.headers.get("X-Firebase-AppCheck")
    if not token:
        logger.warning("App Check: missing token")
        raise HTTPException(status_code=401, detail="Missing App Check token")

    try:
        app_check.verify_token(token)
    except Exception as e:
        logger.warning("App Check: invalid token — %s", e)
        raise HTTPException(status_code=401, detail="Invalid App Check token") from e


@app.get("/health")
async def health(_app_check: None = Depends(verify_app_check)) -> dict[str, str]:
    return {"status": "ok"}
