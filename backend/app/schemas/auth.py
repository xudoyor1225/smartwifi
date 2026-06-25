"""Pydantic schemas for authentication endpoints."""

from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    """Schema for login request body."""

    username: str = Field(..., max_length=64, description="Admin username (max 64 characters)")
    password: str = Field(..., max_length=128, description="Admin password (max 128 characters)")


class LoginResponse(BaseModel):
    """Schema for successful login response."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field(default="bearer", description="Token type (always 'bearer')")


class SessionResponse(BaseModel):
    """Schema for session validation response."""

    admin_id: str = Field(..., description="Admin UUID")
    tenant_id: str = Field(..., description="Tenant UUID")
    username: str = Field(..., description="Admin username")
    expires_at: datetime = Field(..., description="Token expiration timestamp")


class LogoutResponse(BaseModel):
    """Schema for logout response."""

    message: str = Field(default="Successfully logged out", description="Logout confirmation")


class AdminPasswordUpdate(BaseModel):
    """Schema for updating admin dashboard password."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=6, max_length=128, description="New password")
