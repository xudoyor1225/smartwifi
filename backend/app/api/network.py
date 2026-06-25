"""Network monitoring API endpoints.

Provides real-time network statistics from the local machine and
discovers devices on the local network using ARP scanning.

Works WITHOUT a MikroTik router - perfect for development and basic monitoring.

Optimized: reads from BackgroundStatCollector in-memory cache.
API responses are always <1ms regardless of system load.
"""

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.tenant_middleware import get_current_tenant_id
from app.services.stat_collector import get_stat_collector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/network", tags=["network"])


# --- Schemas ---


class NetworkStatsResponse(BaseModel):
    """Real-time network statistics response."""

    download_mbps: float
    upload_mbps: float
    bytes_sent: int
    bytes_recv: int
    ping_ms: float
    jitter_ms: float
    local_ip: str
    subnet: str | None = None


class LocalDeviceResponse(BaseModel):
    """A local network device."""

    ip_address: str
    mac_address: str
    hostname: str | None = None
    manufacturer: str
    is_self: bool = False
    is_gateway: bool = False
    is_responsive: bool = False
    bytes_total: int = 0


class LocalDeviceListResponse(BaseModel):
    """List of local network devices."""

    devices: list[LocalDeviceResponse]
    total: int
    subnet: str | None = None


# --- Endpoints ---


@router.get("/stats", response_model=NetworkStatsResponse)
async def get_network_stats(
    _: str = Depends(get_current_tenant_id),
) -> NetworkStatsResponse:
    """Get real-time network statistics from the local machine.

    Returns current download/upload speed, ping latency, and jitter.
    Works without any router configuration.

    Performance: reads from in-memory cache (<1ms).
    """
    collector = get_stat_collector()
    snapshot = collector.snapshot
    stats = snapshot.stats
    monitor = collector._monitor

    return NetworkStatsResponse(
        download_mbps=stats.download_mbps,
        upload_mbps=stats.upload_mbps,
        bytes_sent=stats.bytes_sent,
        bytes_recv=stats.bytes_recv,
        ping_ms=stats.ping_ms,
        jitter_ms=stats.jitter_ms,
        local_ip=monitor.get_local_ip(),
        subnet=monitor.get_local_subnet(),
    )


@router.get("/devices", response_model=LocalDeviceListResponse)
async def get_local_devices(
    _: str = Depends(get_current_tenant_id),
) -> LocalDeviceListResponse:
    """Discover devices on the local network using ARP scanning.

    Returns all devices currently in the system's ARP table with
    their IP, MAC, hostname, and manufacturer information.

    Performance: reads from in-memory cache (<1ms).
    """
    collector = get_stat_collector()
    snapshot = collector.snapshot
    devices = snapshot.devices
    monitor = collector._monitor

    device_list = [
        LocalDeviceResponse(
            ip_address=d.ip_address,
            mac_address=d.mac_address,
            hostname=d.hostname,
            manufacturer=d.manufacturer or "Unknown",
            is_self=d.is_self,
            is_gateway=d.is_gateway,
            is_responsive=d.is_responsive,
            bytes_total=d.bytes_total,
        )
        for d in devices
    ]

    return LocalDeviceListResponse(
        devices=device_list,
        total=len(device_list),
        subnet=monitor.get_local_subnet(),
    )
