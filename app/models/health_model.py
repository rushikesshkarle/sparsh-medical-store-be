from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class ComponentHealth(BaseModel):
    status: str
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class HealthReport(BaseModel):
    status: str
    version: str
    checked_at: datetime
    components: dict[str, ComponentHealth]
