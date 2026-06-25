"""Settings API endpoints for router configuration management.

Provides endpoints to get, update, and test MikroTik router connections.
Passwords are encrypted at rest using AES-256-GCM.

Requirements: 9.1, 9.2, 9.3, 9.4, 9.5
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_middleware import get_current_tenant_id, get_tenant_session
from app.models.router_config import RouterConfig
from app.schemas.settings import (
    ConnectionTestResponse,
    RouterConfigRequest,
    RouterConfigResponse,
)
from app.services.crypto_service import decrypt_password, encrypt_password
from app.services.router_bridge import (
    ConnectionStatus,
    RouterBridge,
    RouterConfig as RouterBridgeConfig,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/router", response_model=RouterConfigResponse)
async def get_router_config(
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> RouterConfigResponse:
    """Get the current router configuration for the authenticated tenant.

    Returns the router config with the password masked.
    """
    result = await session.execute(
        select(RouterConfig).where(RouterConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Router configuration not found",
        )

    return RouterConfigResponse(
        ip_address=config.ip_address,
        api_port=config.api_port,
        api_username=config.api_username,
        connection_status=config.connection_status,
        last_connected=config.last_connected,
    )


@router.put("/router", response_model=RouterConfigResponse)
async def update_router_config(
    config_request: RouterConfigRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> RouterConfigResponse:
    """Update the router configuration for the authenticated tenant.

    Encrypts the password using AES-256-GCM before storing.
    Creates a new config if none exists, otherwise updates the existing one.
    """
    # Encrypt the password
    encrypted_password, iv = encrypt_password(config_request.api_password)

    # Check if config already exists
    result = await session.execute(
        select(RouterConfig).where(RouterConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()

    if config is None:
        # Create new config
        config = RouterConfig(
            tenant_id=tenant_id,
            ip_address=config_request.ip_address,
            api_port=config_request.api_port,
            api_username=config_request.api_username,
            encrypted_password=encrypted_password,
            encryption_iv=iv,
            connection_status="disconnected",
        )
        session.add(config)
    else:
        # Update existing config
        config.ip_address = config_request.ip_address
        config.api_port = config_request.api_port
        config.api_username = config_request.api_username
        config.encrypted_password = encrypted_password
        config.encryption_iv = iv

    await session.commit()
    await session.refresh(config)

    return RouterConfigResponse(
        ip_address=config.ip_address,
        api_port=config.api_port,
        api_username=config.api_username,
        connection_status=config.connection_status,
        last_connected=config.last_connected,
    )


@router.post("/router/test", response_model=ConnectionTestResponse)
async def test_router_connection(
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> ConnectionTestResponse:
    """Test the connection to the configured MikroTik router.

    Uses the stored configuration to attempt a connection with a 10-second timeout.
    Updates the connection status and last_connected timestamp on success.
    """
    # Get the stored config
    result = await session.execute(
        select(RouterConfig).where(RouterConfig.tenant_id == tenant_id)
    )
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Router configuration not found. Please configure the router first.",
        )

    # Decrypt the password
    try:
        password = decrypt_password(config.encrypted_password, config.encryption_iv)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt router credentials",
        )

    # Build the bridge config
    bridge_config = RouterBridgeConfig(
        host=config.ip_address,
        port=config.api_port,
        username=config.api_username,
        password=password,
    )

    # Test connection using RouterBridge
    bridge = RouterBridge()
    connection_result = await bridge.test_connection(bridge_config)

    # Update connection status
    if connection_result.status == ConnectionStatus.SUCCESS:
        config.connection_status = "connected"
        config.last_connected = datetime.now(timezone.utc)
    else:
        config.connection_status = "disconnected"

    await session.commit()

    return ConnectionTestResponse(
        status=connection_result.status.value,
        message=connection_result.message,
        latency_ms=connection_result.latency_ms,
    )
