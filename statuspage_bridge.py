import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Optional

from fastapi import FastAPI, HTTPException, Request

from app.bridge import StatuspageBridge
from app.config import BridgeConfig

config = BridgeConfig.from_env()

logging.basicConfig(level=getattr(logging, config.log_level, logging.INFO), format="%(asctime)s | %(levelname)-8s | %(message)s")

logger = logging.getLogger("statuspage_bridge")

bridge = StatuspageBridge(config)


@asynccontextmanager
async def lifespan(app: FastAPI):

    # START OF THE PROGRAM

    logger.info("\n" + "=" * 50)
    logger.info(" STATUSPAGE BRIDGE IS LIVE AND RUNNING ")
    logger.info(f" Target Page ID: {config.statuspage_page_id}")
    logger.info(" Listening for Alertmanager webhooks...")
    logger.info("=" * 50 + "\n")

    bridge.startup()

    reconcile_task = asyncio.create_task(periodic_reconciliation_loop())

    yield

    # END OF THE PROGRAM

    reconcile_task.cancel()
    try:
        await reconcile_task
    except asyncio.CancelledError:
        pass

    logger.info("\n" + "=" * 50)
    logger.info(" SHUTTING DOWN STATUSPAGE BRIDGE... ")
    logger.info("=" * 50 + "\n")


app = FastAPI(lifespan=lifespan)


async def periodic_reconciliation_loop():
    """
    Periodically re-checks Alertmanager for alerts that resolved without the
    bridge receiving (or successfully processing) the corresponding
    "resolved" webhook, so an incident never stays open forever just because
    a single webhook delivery was lost.
    """
    while True:
        await asyncio.sleep(config.alertmanager_poll_interval_seconds)
        try:
            bridge.reconcile_with_alertmanager()
        except Exception as e:
            logger.error(f"Unexpected error during Alertmanager reconciliation: {e}")


@app.get("/health")
async def health_check():
    # Hit repeatedly by Docker/orchestrator health probes: kept at DEBUG so it
    # doesn't drown the real signal out of the default production log level.
    logger.debug("Healthcheck endpoint was hit!")
    if not bridge.ready:
        raise HTTPException(status_code=HTTPStatus.SERVICE_UNAVAILABLE, detail="Bridge is not ready")
    return {"status": "healthy", "statuspage_page": bridge.page_name}


def _extract_token(request: Request, token: Optional[str]) -> Optional[str]:
    """
    Accept the webhook token either as a query parameter (simplest
    Alertmanager `webhook_configs.url` setup) or as a
    `Authorization: Bearer <token>` header (keeps the secret out of URLs
    and access logs, matches Alertmanager's `http_config.authorization`).
    The header takes precedence when both are present.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[len("bearer ") :].strip()
    return token


@app.post("/webhook")
async def handle_alertmanager_webhook(request: Request, token: Optional[str] = None) -> dict:
    provided_token = _extract_token(request, token)
    if not provided_token or not hmac.compare_digest(provided_token, config.secret_webhook):
        logger.warning("Rejected webhook request: invalid or missing token.")
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid token")

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid JSON payload")

    if not isinstance(data, dict):
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid JSON payload")

    alerts = data.get("alerts", [])

    if not alerts:
        logger.info("Received webhook request with no alerts; ignoring.")
        return {"status": "ignored", "message": "No alerts found"}

    logger.info(f"Received webhook request with {len(alerts)} alert(s).")

    for alert in alerts:
        try:
            bridge.process_alert(alert)
        except RuntimeError:
            raise HTTPException(status_code=500, detail="Failed to update Statuspage")

    return {"status": "success"}
