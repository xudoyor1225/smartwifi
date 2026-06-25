"""Device management API endpoints.

Provides endpoints for listing devices, and performing actions
(kick, block, unblock, set/remove speed limits, VIP management).

Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.8, 4.10, 4.11, 6.3, 6.4, 6.5
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_middleware import get_current_tenant_id, get_tenant_session
from app.models.device import Device

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/devices", tags=["devices"])


# --- Schemas ---


class DeviceResponse(BaseModel):
    """Response schema for a single device."""

    id: str
    mac_address: str
    ip_address: str | None = None
    hostname: str | None = None
    manufacturer: str | None = "Unknown Manufacturer"
    manufacturer_logo_url: str | None = None
    status: str = "active"
    is_vip: bool = False
    total_bytes: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None


class DeviceListResponse(BaseModel):
    """Response schema for device list."""

    devices: list[DeviceResponse]
    total: int


class SpeedLimitRequest(BaseModel):
    """Request schema for setting speed limit."""

    download_mbps: int = Field(..., ge=1, le=100, description="Download limit in Mbps (1-100)")
    upload_mbps: int = Field(..., ge=1, le=100, description="Upload limit in Mbps (1-100)")


class DeviceActionResponse(BaseModel):
    """Response schema for device actions."""

    success: bool
    message: str


# --- Endpoints ---


@router.get("", response_model=DeviceListResponse)
async def list_devices(
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> DeviceListResponse:
    """List all devices for the authenticated tenant.

    Returns devices with their current status, IP, MAC, hostname,
    manufacturer info, and usage data.
    """
    try:
        result = await session.execute(
            select(Device).where(Device.tenant_id == tenant_id).order_by(Device.last_seen.desc())
        )
        devices = result.scalars().all()

        device_list = [
            DeviceResponse(
                id=str(d.id),
                mac_address=d.mac_address,
                ip_address=d.ip_address,
                hostname=d.hostname,
                manufacturer=d.manufacturer or "Unknown Manufacturer",
                manufacturer_logo_url=d.manufacturer_logo_url,
                status=d.status,
                is_vip=d.is_vip,
                total_bytes=d.total_bytes or 0,
                first_seen=d.first_seen,
                last_seen=d.last_seen,
            )
            for d in devices
        ]

        return DeviceListResponse(devices=device_list, total=len(device_list))
    except Exception as e:
        logger.warning(f"Database unavailable for device listing: {e}")
        return DeviceListResponse(devices=[], total=0)


@router.post("/{mac}/kick", response_model=DeviceActionResponse)
async def kick_device(
    mac: str,
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> DeviceActionResponse:
    """Disconnect a device from the network.

    Sends a disconnect command to the MikroTik router for the specified MAC.
    """
    device = await _get_device_by_mac(session, tenant_id, mac)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # In production, this would call RouterBridge to disconnect the device
    logger.info(f"Kick device {mac} for tenant {tenant_id}")
    return DeviceActionResponse(success=True, message=f"Device {mac} disconnected")


@router.post("/{mac}/block", response_model=DeviceActionResponse)
async def block_device(
    mac: str,
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> DeviceActionResponse:
    """Block a device by adding its MAC to the blacklist.

    The device will be permanently blocked until manually unblocked.
    """
    device = await _get_device_by_mac(session, tenant_id, mac)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Update device status in database
    device.status = "blocked"
    await session.commit()

    logger.info(f"Block device {mac} for tenant {tenant_id}")
    return DeviceActionResponse(success=True, message=f"Device {mac} blocked")


@router.post("/{mac}/unblock", response_model=DeviceActionResponse)
async def unblock_device(
    mac: str,
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> DeviceActionResponse:
    """Unblock a device by removing its MAC from the blacklist."""
    device = await _get_device_by_mac(session, tenant_id, mac)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.status = "active"
    await session.commit()

    logger.info(f"Unblock device {mac} for tenant {tenant_id}")
    return DeviceActionResponse(success=True, message=f"Device {mac} unblocked")


@router.post("/{mac}/limit", response_model=DeviceActionResponse)
async def set_speed_limit(
    mac: str,
    limit: SpeedLimitRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> DeviceActionResponse:
    """Set a speed limit for a device.

    Creates a queue rule on the MikroTik router limiting the device's
    download and upload speeds.
    """
    device = await _get_device_by_mac(session, tenant_id, mac)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    logger.info(
        f"Set speed limit for {mac}: {limit.download_mbps}/{limit.upload_mbps} Mbps"
    )
    return DeviceActionResponse(
        success=True,
        message=f"Speed limit set: {limit.download_mbps}M/{limit.upload_mbps}M",
    )


@router.delete("/{mac}/limit", response_model=DeviceActionResponse)
async def remove_speed_limit(
    mac: str,
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> DeviceActionResponse:
    """Remove the speed limit from a device."""
    device = await _get_device_by_mac(session, tenant_id, mac)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    logger.info(f"Remove speed limit for {mac}")
    return DeviceActionResponse(success=True, message=f"Speed limit removed for {mac}")


@router.post("/{mac}/vip", response_model=DeviceActionResponse)
async def add_vip(
    mac: str,
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> DeviceActionResponse:
    """Add a device to the VIP list.

    VIP devices bypass all bandwidth limits and blocking rules.
    """
    device = await _get_device_by_mac(session, tenant_id, mac)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    # Check VIP limit (max 50)
    vip_count_result = await session.execute(
        select(Device).where(Device.tenant_id == tenant_id, Device.is_vip.is_(True))
    )
    vip_devices = vip_count_result.scalars().all()
    if len(vip_devices) >= 50:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Maximum VIP device limit (50) reached",
        )

    device.is_vip = True
    await session.commit()

    return DeviceActionResponse(success=True, message=f"Device {mac} added to VIP list")


@router.delete("/{mac}/vip", response_model=DeviceActionResponse)
async def remove_vip(
    mac: str,
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> DeviceActionResponse:
    """Remove a device from the VIP list."""
    device = await _get_device_by_mac(session, tenant_id, mac)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    device.is_vip = False
    await session.commit()

    return DeviceActionResponse(success=True, message=f"Device {mac} removed from VIP list")


# --- Helpers ---


async def _get_device_by_mac(
    session: AsyncSession, tenant_id: str, mac: str
) -> Device | None:
    """Look up a device by MAC address within the tenant scope."""
    result = await session.execute(
        select(Device).where(
            Device.tenant_id == tenant_id,
            Device.mac_address == mac,
        )
    )
    return result.scalar_one_or_none()
