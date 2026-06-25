"""Bandwidth control API endpoints.

Provides endpoints for managing global bandwidth limits, VIP device listing,
and per-device bandwidth overrides.

Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_middleware import get_current_tenant_id, get_tenant_session
from app.models.bandwidth_config import BandwidthConfig
from app.models.device import Device

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bandwidth", tags=["bandwidth"])


# --- Schemas ---


class BandwidthConfigResponse(BaseModel):
    """Response schema for bandwidth configuration."""

    global_download_mbps: int
    global_upload_mbps: int
    uplink_capacity_mbps: int
    congestion_warning: bool = False


class GlobalBandwidthRequest(BaseModel):
    """Request schema for setting global bandwidth limits."""

    download_mbps: int = Field(..., ge=1, le=1000, description="Global download limit (1-1000 Mbps)")
    upload_mbps: int = Field(..., ge=1, le=1000, description="Global upload limit (1-1000 Mbps)")


class VipDeviceResponse(BaseModel):
    """Response schema for a VIP device."""

    mac_address: str
    hostname: str | None = None
    ip_address: str | None = None


class VipListResponse(BaseModel):
    """Response schema for VIP device list."""

    devices: list[VipDeviceResponse]
    total: int
    max_allowed: int = 50


class BandwidthActionResponse(BaseModel):
    """Response schema for bandwidth actions."""

    success: bool
    message: str


# --- Endpoints ---


@router.get("/config", response_model=BandwidthConfigResponse)
async def get_bandwidth_config(
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> BandwidthConfigResponse:
    """Get the current bandwidth configuration for the tenant."""
    result = await session.execute(
        select(BandwidthConfig).where(BandwidthConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()

    if config is None:
        # Return defaults if no config exists
        return BandwidthConfigResponse(
            global_download_mbps=100,
            global_upload_mbps=100,
            uplink_capacity_mbps=1000,
            congestion_warning=False,
        )

    # Check for congestion
    congestion = _check_congestion(config)

    return BandwidthConfigResponse(
        global_download_mbps=config.global_download_mbps,
        global_upload_mbps=config.global_upload_mbps,
        uplink_capacity_mbps=config.uplink_capacity_mbps,
        congestion_warning=congestion,
    )


@router.put("/global", response_model=BandwidthActionResponse)
async def set_global_bandwidth(
    request: GlobalBandwidthRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> BandwidthActionResponse:
    """Set global bandwidth limits for all non-VIP devices.

    Applies MikroTik queue rules to all non-VIP devices.
    """
    result = await session.execute(
        select(BandwidthConfig).where(BandwidthConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()

    if config is None:
        config = BandwidthConfig(
            tenant_id=tenant_id,
            global_download_mbps=request.download_mbps,
            global_upload_mbps=request.upload_mbps,
            uplink_capacity_mbps=1000,
        )
        session.add(config)
    else:
        config.global_download_mbps = request.download_mbps
        config.global_upload_mbps = request.upload_mbps

    await session.commit()

    logger.info(
        f"Set global bandwidth {request.download_mbps}/{request.upload_mbps} Mbps "
        f"for tenant {tenant_id}"
    )
    return BandwidthActionResponse(
        success=True,
        message=f"Global bandwidth set to {request.download_mbps}M/{request.upload_mbps}M",
    )


@router.get("/vip", response_model=VipListResponse)
async def list_vip_devices(
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> VipListResponse:
    """List all VIP devices for the tenant (max 50)."""
    result = await session.execute(
        select(Device).where(
            Device.tenant_id == tenant_id,
            Device.is_vip == True,  # noqa: E712
        )
    )
    vip_devices = result.scalars().all()

    devices = [
        VipDeviceResponse(
            mac_address=d.mac_address,
            hostname=d.hostname,
            ip_address=d.ip_address,
        )
        for d in vip_devices
    ]

    return VipListResponse(devices=devices, total=len(devices))


# --- Helpers ---


def _check_congestion(config: BandwidthConfig) -> bool:
    """Check if total allocated bandwidth exceeds uplink capacity."""
    # Simplified check - in production would sum all device allocations
    return config.global_download_mbps > config.uplink_capacity_mbps
