"""Pydantic schemas for device management endpoints.

Requirements: 4.1, 4.5, 4.6
"""

from datetime import datetime

from pydantic import BaseModel, Field


class DeviceResponse(BaseModel):
    """Schema for a single device in the device list."""

    id: str = Field(..., description="Device UUID")
    mac_address: str = Field(..., description="Device MAC address (e.g., AA:BB:CC:DD:EE:FF)")
    ip_address: str | None = Field(None, description="Current IP address")
    hostname: str | None = Field(None, description="Device hostname or name")
    manufacturer: str | None = Field(None, description="Manufacturer name from OUI lookup")
    manufacturer_logo_url: str | None = Field(
        None, description="URL to manufacturer logo image"
    )
    status: str = Field(..., description="Device status: active or blocked")
    is_vip: bool = Field(False, description="Whether the device is on the VIP list")
    total_bytes: int = Field(0, description="Total bytes transferred by this device")
    first_seen: datetime = Field(..., description="Timestamp when device was first seen")
    last_seen: datetime = Field(..., description="Timestamp when device was last seen")

    model_config = {"from_attributes": True}


class DeviceListResponse(BaseModel):
    """Schema for the device list endpoint response."""

    devices: list[DeviceResponse] = Field(
        default_factory=list, description="List of devices for the tenant"
    )
    total: int = Field(0, description="Total number of devices")
