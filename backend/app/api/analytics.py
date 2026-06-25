"""Analytics API endpoints.

Provides endpoints for traffic distribution, time-series data,
anomaly alerts, and AI baseline status.

Requirements: 7.3, 7.4, 7.6, 8.1
"""

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_middleware import get_current_tenant_id, get_tenant_session
from app.models.anomaly_alert import AnomalyAlert
from app.models.traffic_data import TrafficData
from app.ai.engine import get_ai_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


# --- Schemas ---


class TrafficCategoryData(BaseModel):
    """Traffic distribution by category."""

    category: str
    bytes_total: int
    percentage: float


class TrafficDistributionResponse(BaseModel):
    """Response for traffic distribution."""

    categories: list[TrafficCategoryData]
    period: str


class TimelinePoint(BaseModel):
    """A single point in the traffic timeline."""

    timestamp: datetime
    bytes_in: int
    bytes_out: int


class TrafficTimelineResponse(BaseModel):
    """Response for traffic timeline."""

    points: list[TimelinePoint]
    period: str


class AnomalyAlertResponse(BaseModel):
    """Response for a single anomaly alert."""

    id: str
    severity: str
    anomaly_type: str
    description: str | None = None
    observed_value: float
    baseline_value: float
    deviation_std: float
    is_read: bool
    detected_at: datetime


class AnomalyListResponse(BaseModel):
    """Response for anomaly alerts list."""

    alerts: list[AnomalyAlertResponse]
    total: int


class BaselineStatusResponse(BaseModel):
    """Response for AI baseline learning status."""

    has_baseline: bool
    days_of_data: int
    required_days: int = 7
    message: str


# --- Endpoints ---


@router.get("/traffic", response_model=TrafficDistributionResponse)
async def get_traffic_distribution(
    period: str = Query(default="24h", regex="^(live|24h|7d)$"),
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> TrafficDistributionResponse:
    """Get traffic distribution by category for the selected period."""
    if period == "live":
        ai_engine = get_ai_engine()
        dist = ai_engine.get_traffic_distribution()
        return TrafficDistributionResponse(
            categories=[TrafficCategoryData(**c) for c in dist["categories"]],
            period="live"
        )

    since = _get_period_start(period)

    result = await session.execute(
        select(
            TrafficData.category,
            func.sum(TrafficData.bytes_transferred).label("total_bytes"),
        )
        .where(
            TrafficData.tenant_id == tenant_id,
            TrafficData.collected_at >= since,
        )
        .group_by(TrafficData.category)
    )
    rows = result.all()

    total_bytes = sum(r.total_bytes or 0 for r in rows)
    categories = [
        TrafficCategoryData(
            category=r.category or "Other",
            bytes_total=r.total_bytes or 0,
            percentage=round((r.total_bytes or 0) / total_bytes * 100, 1) if total_bytes > 0 else 0,
        )
        for r in rows
    ]

    # If no data, return default categories with 0
    if not categories:
        default_cats = ["Video", "Social Media", "Web Browsing", "Gaming", "File Transfer", "Other"]
        categories = [
            TrafficCategoryData(category=c, bytes_total=0, percentage=0)
            for c in default_cats
        ]

    return TrafficDistributionResponse(categories=categories, period=period)


@router.get("/timeline", response_model=TrafficTimelineResponse)
async def get_traffic_timeline(
    period: str = Query(default="24h", regex="^(24h|7d)$"),
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> TrafficTimelineResponse:
    """Get time-series traffic data for the selected period."""
    since = _get_period_start(period)
    _ = since # Fix unused variable for now until implemented

    # For now return empty - in production this would aggregate hourly data
    return TrafficTimelineResponse(points=[], period=period)


@router.get("/anomalies", response_model=AnomalyListResponse)
async def get_anomalies(
    period: str = Query(default="24h", regex="^(24h|7d)$"),
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> AnomalyListResponse:
    """Get anomaly alerts for the selected period."""
    since = _get_period_start(period)

    result = await session.execute(
        select(AnomalyAlert)
        .where(
            AnomalyAlert.tenant_id == tenant_id,
            AnomalyAlert.detected_at >= since,
        )
        .order_by(AnomalyAlert.detected_at.desc())
        .limit(50)
    )
    alerts = result.scalars().all()

    alert_list = [
        AnomalyAlertResponse(
            id=str(a.id),
            severity=a.severity,
            anomaly_type=a.anomaly_type,
            description=a.description,
            observed_value=a.observed_value,
            baseline_value=a.baseline_value,
            deviation_std=a.deviation_std,
            is_read=a.is_read,
            detected_at=a.detected_at,
        )
        for a in alerts
    ]

    return AnomalyListResponse(alerts=alert_list, total=len(alert_list))


@router.get("/baseline-status", response_model=BaselineStatusResponse)
async def get_baseline_status(
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> BaselineStatusResponse:
    """Get the AI baseline learning status for the tenant."""
    # Since this is local mode, we'll check the live AI engine first
    ai_engine = get_ai_engine()
    live_status = ai_engine.get_baseline_status()
    
    if live_status["has_baseline"]:
        return BaselineStatusResponse(
            has_baseline=True,
            days_of_data=live_status["days_of_data"],
            message=live_status["message"],
        )
        
    # Check how many days of traffic data exist in DB
    result = await session.execute(
        select(func.min(TrafficData.collected_at))
        .where(TrafficData.tenant_id == tenant_id)
    )
    earliest = result.scalar_one_or_none()

    if earliest is None:
        return BaselineStatusResponse(
            has_baseline=False,
            days_of_data=0,
            message="No traffic data collected yet. AI analysis requires at least 7 days of data.",
        )

    days = (datetime.now(timezone.utc) - earliest).days

    if days < 7:
        return BaselineStatusResponse(
            has_baseline=False,
            days_of_data=days,
            message=f"Collecting baseline data: {days}/7 days complete.",
        )

    return BaselineStatusResponse(
        has_baseline=True,
        days_of_data=days,
        message="AI baseline established. Anomaly detection is active.",
    )


# --- Helpers ---


def _get_period_start(period: str) -> datetime:
    """Convert period string to start datetime."""
    now = datetime.now(timezone.utc)
    if period == "7d":
        return now - timedelta(days=7)
    return now - timedelta(hours=24)
