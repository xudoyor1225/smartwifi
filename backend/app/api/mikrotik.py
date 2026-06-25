"""Advanced MikroTik API endpoints.

Provides access to advanced features such as Hotspot management,
Layer 7 Filtering, real-time interface monitoring, and DHCP leases.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from app.core.tenant_middleware import get_current_tenant_id
from app.services.router_bridge import RouterBridge

router = APIRouter(prefix="/mikrotik", tags=["mikrotik"])

def get_bridge() -> RouterBridge:
    return RouterBridge()

@router.get("/hotspot/active")
async def get_active_hotspot_users(
    tenant_id: str = Depends(get_current_tenant_id),
    bridge: RouterBridge = Depends(get_bridge)
) -> list[dict[str, Any]]:
    """Get all active Hotspot users on the router."""
    return await bridge.get_hotspot_active_users(tenant_id)

@router.post("/l7-filter")
async def add_l7_filter(
    name: str,
    regexp: str,
    comment: str | None = None,
    tenant_id: str = Depends(get_current_tenant_id),
    bridge: RouterBridge = Depends(get_bridge)
) -> dict[str, Any]:
    """Add a new Layer 7 protocol for application blocking."""
    res = await bridge.add_layer7_protocol(tenant_id, name, regexp, comment)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.error)
    return {"success": True, "message": f"L7 Filter {name} added"}

@router.get("/interface/{interface_name}/traffic")
async def monitor_interface_traffic(
    interface_name: str,
    tenant_id: str = Depends(get_current_tenant_id),
    bridge: RouterBridge = Depends(get_bridge)
) -> dict[str, int]:
    """Get real-time bandwidth traffic for an interface."""
    return await bridge.get_interface_traffic(tenant_id, interface_name)

@router.post("/dhcp/make-static/{mac_address}")
async def make_lease_static(
    mac_address: str,
    tenant_id: str = Depends(get_current_tenant_id),
    bridge: RouterBridge = Depends(get_bridge)
) -> dict[str, Any]:
    """Make a DHCP lease static for a given MAC address."""
    res = await bridge.make_dhcp_lease_static(tenant_id, mac_address)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.error)
    return {"success": True, "message": f"Lease for {mac_address} made static"}

@router.post("/wireguard/server")
async def create_wireguard(
    name: str,
    listen_port: int,
    tenant_id: str = Depends(get_current_tenant_id),
    bridge: RouterBridge = Depends(get_bridge)
) -> dict[str, Any]:
    """Create a new WireGuard VPN interface."""
    res = await bridge.create_wireguard_server(tenant_id, name, listen_port)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.error)
    return {"success": True, "message": f"WireGuard {name} created on {listen_port}"}

@router.post("/wireguard/peer")
async def add_wg_peer(
    interface: str,
    public_key: str,
    allowed_address: str,
    tenant_id: str = Depends(get_current_tenant_id),
    bridge: RouterBridge = Depends(get_bridge)
) -> dict[str, Any]:
    """Add a new peer to a WireGuard interface."""
    res = await bridge.add_wireguard_peer(tenant_id, interface, public_key, allowed_address)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.error)
    return {"success": True, "message": f"Peer added to {interface}"}

@router.post("/parental-control")
async def add_parental_control(
    mac_address: str,
    time: str,
    days: str,
    tenant_id: str = Depends(get_current_tenant_id),
    bridge: RouterBridge = Depends(get_bridge)
) -> dict[str, Any]:
    """Add a time-based parental control rule for a MAC address."""
    res = await bridge.add_parental_control_rule(tenant_id, mac_address, time, days)
    if not res.success:
        raise HTTPException(status_code=400, detail=res.error)
    return {"success": True, "message": f"Parental Control set for {mac_address} ({time})"}
