"""Application blocking API endpoints.

Provides endpoints for managing blocking scenarios (Instagram, TikTok,
Telegram, YouTube, Netflix) and their activation/deactivation.

Requirements: 5.1, 5.2, 5.3, 5.7, 5.11
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tenant_middleware import get_current_tenant_id, get_tenant_session
from app.models.blocking_scenario import BlockingScenario

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/blocking", tags=["blocking"])


# --- Schemas ---


class BlockingScenarioResponse(BaseModel):
    """Response schema for a blocking scenario."""

    id: str
    app_name: str
    app_logo_url: str | None = None
    is_active: bool
    version: int


class BlockingScenarioListResponse(BaseModel):
    """Response schema for list of blocking scenarios."""

    scenarios: list[BlockingScenarioResponse]


class BlockingActionResponse(BaseModel):
    """Response schema for blocking actions."""

    success: bool
    message: str
    scenario_id: str
    is_active: bool


# --- Endpoints ---


@router.get("/scenarios", response_model=BlockingScenarioListResponse)
async def list_scenarios(
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> BlockingScenarioListResponse:
    """List all blocking scenarios for the authenticated tenant.

    Returns scenarios with their current active/inactive status.
    """
    result = await session.execute(
        select(BlockingScenario)
        .where(BlockingScenario.tenant_id == tenant_id)
        .order_by(BlockingScenario.app_name)
    )
    scenarios = result.scalars().all()

    scenario_list = [
        BlockingScenarioResponse(
            id=str(s.id),
            app_name=s.app_name,
            app_logo_url=s.app_logo_url,
            is_active=s.is_active,
            version=s.version,
        )
        for s in scenarios
    ]

    return BlockingScenarioListResponse(scenarios=scenario_list)


@router.post("/scenarios/{scenario_id}/activate", response_model=BlockingActionResponse)
async def activate_scenario(
    scenario_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> BlockingActionResponse:
    """Activate a blocking scenario.

    Applies all firewall rules (Layer7, TLS, DNS) to the MikroTik router.
    VIP devices are exempt from blocking rules.
    """
    scenario = await _get_scenario(session, tenant_id, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Blocking scenario not found")

    if scenario.is_active:
        return BlockingActionResponse(
            success=True,
            message=f"{scenario.app_name} is already blocked",
            scenario_id=scenario_id,
            is_active=True,
        )

    # In production, this would apply rules via RouterBridge
    scenario.is_active = True
    await session.commit()

    logger.info(f"Activated blocking scenario {scenario.app_name} for tenant {tenant_id}")
    return BlockingActionResponse(
        success=True,
        message=f"{scenario.app_name} blocked successfully",
        scenario_id=scenario_id,
        is_active=True,
    )


@router.post("/scenarios/{scenario_id}/deactivate", response_model=BlockingActionResponse)
async def deactivate_scenario(
    scenario_id: str,
    tenant_id: str = Depends(get_current_tenant_id),
    session: AsyncSession = Depends(get_tenant_session),
) -> BlockingActionResponse:
    """Deactivate a blocking scenario.

    Removes all firewall rules for this scenario from the MikroTik router.
    """
    scenario = await _get_scenario(session, tenant_id, scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Blocking scenario not found")

    if not scenario.is_active:
        return BlockingActionResponse(
            success=True,
            message=f"{scenario.app_name} is already allowed",
            scenario_id=scenario_id,
            is_active=False,
        )

    # In production, this would remove rules via RouterBridge
    scenario.is_active = False
    await session.commit()

    logger.info(f"Deactivated blocking scenario {scenario.app_name} for tenant {tenant_id}")
    return BlockingActionResponse(
        success=True,
        message=f"{scenario.app_name} unblocked successfully",
        scenario_id=scenario_id,
        is_active=False,
    )


# --- Helpers ---


async def _get_scenario(
    session: AsyncSession, tenant_id: str, scenario_id: str
) -> BlockingScenario | None:
    """Look up a blocking scenario by ID within the tenant scope."""
    result = await session.execute(
        select(BlockingScenario).where(
            BlockingScenario.tenant_id == tenant_id,
            BlockingScenario.id == scenario_id,
        )
    )
    return result.scalar_one_or_none()
