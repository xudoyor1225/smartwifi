"""Main API router aggregating all endpoint modules.

All API routes are registered under the /api prefix via this router.
Sub-routers are organized by domain: auth, devices, blocking, bandwidth,
analytics, reports, and settings.
"""

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.api.auth import router as auth_router
from app.api.settings import router as settings_router
from app.api.devices import router as devices_router
from app.api.blocking import router as blocking_router
from app.api.bandwidth import router as bandwidth_router
from app.api.analytics import router as analytics_router
from app.api.network import router as network_router
from app.api.mikrotik import router as mikrotik_router
from app.services.websocket_manager import authenticate_ws_token, get_ws_manager
from app.services.stat_collector import get_stat_collector

api_router = APIRouter()

# Register sub-routers
api_router.include_router(auth_router)
api_router.include_router(settings_router)
api_router.include_router(devices_router)
api_router.include_router(blocking_router)
api_router.include_router(bandwidth_router)
api_router.include_router(analytics_router)
api_router.include_router(network_router)
api_router.include_router(mikrotik_router)


@api_router.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint for load balancer probes.

    Returns a simple status response indicating the service is running.
    Used by ALB/Nginx for instance health monitoring.
    """
    return {"status": "healthy", "service": "smart-wifi-dashboard"}


@api_router.get("/health/ready", tags=["health"])
async def readiness_probe():
    """Readiness probe checking background services.

    Verifies that the stat collector and database are ready.
    """
    collector = get_stat_collector()
    ws_manager = get_ws_manager()
    
    return {
        "status": "ready" if collector.is_running else "not_ready",
        "service": "smart-wifi-dashboard",
        "components": {
            "stat_collector": {
                "status": "running" if collector.is_running else "stopped",
                "uptime_seconds": collector.uptime_seconds,
            },
            "websocket": {
                "total_connections": ws_manager.total_connections,
                "tenant_count": ws_manager.tenant_count,
            }
        }
    }


@api_router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT authentication token"),
):
    """WebSocket endpoint for real-time push notifications.
    
    Requires JWT token passed via query parameter.
    """
    auth_data = authenticate_ws_token(token)
    if not auth_data:
        await websocket.close(code=1008, reason="Invalid or missing token")
        return
        
    admin_id, tenant_id = auth_data
    manager = get_ws_manager()
    
    conn = await manager.connect(websocket, tenant_id, admin_id)
    try:
        while True:
            # We expect occasional heartbeats (ping)
            data = await websocket.receive_text()
            await manager.handle_client_message(conn, data)
    except WebSocketDisconnect:
        manager.disconnect(conn)
    except Exception:
        manager.disconnect(conn)
