"""Pydantic schemas for application blocking endpoints.

Provides request/response models for blocking scenario management.

Requirements: 5.1, 5.7
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RuleDefinition(BaseModel):
    """A single rule definition within a blocking scenario."""

    rule_type: str = Field(..., description="Type of rule: layer7, tls, or dns")
    pattern: str = Field(..., description="Pattern to match (regexp, hostname, or domain)")


class BlockingScenarioResponse(BaseModel):
    """Response schema for a single blocking scenario."""

    id: uuid.UUID
    app_name: str
    app_logo_url: str | None = None
    version: int
    is_active: bool
    rule_definitions: dict = Field(
        default_factory=dict,
        description="Versioned rule definitions containing Layer7, TLS, and DNS rules",
    )
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BlockingScenarioListResponse(BaseModel):
    """Response schema for listing all blocking scenarios."""

    scenarios: list[BlockingScenarioResponse]
