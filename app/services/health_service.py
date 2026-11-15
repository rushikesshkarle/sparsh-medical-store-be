import logging
import time
from datetime import datetime, timezone

from app.models.health_model import ComponentHealth, HealthReport
from app.shared.constants import GlobalConstants, HealthConstants
from app.shared.db_connections.mongo import mongodb


class HealthService:
    """Liveness of the API and its one dependency, MongoDB."""

    async def check(self) -> HealthReport:
        mongo = await self._probe_mongo()
        status = (
            HealthConstants.STATUS_HEALTHY
            if mongo.status == HealthConstants.STATUS_UP
            else HealthConstants.STATUS_DEGRADED
        )
        return HealthReport(
            status=status,
            version=GlobalConstants.app_version,
            checked_at=datetime.now(timezone.utc),
            components={"server": ComponentHealth(status=HealthConstants.STATUS_UP), "mongodb": mongo},
        )

    @staticmethod
    async def _probe_mongo() -> ComponentHealth:
        """Ping MongoDB. Never raises; publishes only the exception class name."""
        started = time.perf_counter()
        try:
            await mongodb.ping()
        except Exception as e:  # noqa: BLE001 — a probe must never fail the request
            logging.warning("MongoDB health probe failed: %s", e)
            return ComponentHealth(status=HealthConstants.STATUS_DOWN, error=type(e).__name__)
        latency = round((time.perf_counter() - started) * 1000, HealthConstants.LATENCY_DECIMALS)
        return ComponentHealth(status=HealthConstants.STATUS_UP, latency_ms=latency)
