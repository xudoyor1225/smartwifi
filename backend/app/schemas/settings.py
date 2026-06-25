"""Pydantic schemas for router configuration settings endpoints.

Provides request/response models with validation for IP addresses and port ranges.

Requirements: 9.1, 9.3
"""

import re
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class RouterConfigRequest(BaseModel):
    """Request schema for creating/updating router configuration.

    Validates IPv4 format and port range.
    """

    ip_address: str = Field(..., description="MikroTik router IPv4 address")
    api_port: int = Field(default=8728, description="API port (1-65535)")
    api_username: str = Field(..., max_length=128, description="API username")
    api_password: str = Field(..., max_length=128, description="API password")

    @field_validator("ip_address")
    @classmethod
    def validate_ipv4(cls, v: str) -> str:
        """Validate that the IP address is a valid IPv4 format."""
        pattern = r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$"
        match = re.match(pattern, v)
        if not match:
            raise ValueError("Invalid IPv4 address format")
        octets = [int(g) for g in match.groups()]
        for octet in octets:
            if octet < 0 or octet > 255:
                raise ValueError("Invalid IPv4 address: each octet must be 0-255")
        return v

    @field_validator("api_port")
    @classmethod
    def validate_port(cls, v: int) -> int:
        """Validate that the port is within valid range."""
        if v < 1 or v > 65535:
            raise ValueError("Port must be between 1 and 65535")
        return v


class RouterConfigResponse(BaseModel):
    """Response schema for router configuration (password masked)."""

    ip_address: str
    api_port: int
    api_username: str
    connection_status: str
    last_connected: datetime | None = None


class ConnectionTestResponse(BaseModel):
    """Response schema for connection test results."""

    status: str
    message: str
    latency_ms: float | None = None
