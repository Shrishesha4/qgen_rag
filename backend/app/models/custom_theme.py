"""
Custom theme model for user-defined application themes.

Stored in SQLite (auth.db) alongside user data.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column
import uuid

from app.core.auth_database import AuthBase


class CustomTheme(AuthBase):
    """User-defined custom themes."""
    
    __tablename__ = "custom_themes"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    icon: Mapped[str] = mapped_column(String(10), default="🎨")
    
    # Background settings
    bg_image: Mapped[Optional[str]] = mapped_column(String(500))  # URL or path
    wallpaper_overlay: Mapped[Optional[str]] = mapped_column(String(1000))
    bg: Mapped[Optional[str]] = mapped_column(String(2000))  # Gradient fallback
    bg_color: Mapped[str] = mapped_column(String(20), default="#1a1a2e")
    
    # Colors
    primary: Mapped[str] = mapped_column(String(20), default="#6366f1")
    primary_hover: Mapped[str] = mapped_column(String(20), default="#818cf8")
    accent_gradient: Mapped[str] = mapped_column(String(20), default="#a855f7")
    primary_rgb: Mapped[str] = mapped_column(String(20), default="99, 102, 241")
    
    # Text colors
    text: Mapped[str] = mapped_column(String(20), default="#f8fafc")
    text_muted: Mapped[str] = mapped_column(String(60), default="#94a3b8")
    text_primary: Mapped[str] = mapped_column(String(20), default="#1e293b")
    text_secondary: Mapped[str] = mapped_column(String(60), default="rgba(0,0,0,0.55)")
    
    # Glass effects
    glass_bg: Mapped[str] = mapped_column(String(100), default="rgba(255, 255, 255, 0.55)")
    glass_border: Mapped[str] = mapped_column(String(100), default="rgba(255, 255, 255, 0.7)")
    nav_glass: Mapped[str] = mapped_column(String(100), default="rgba(255, 255, 255, 0.5)")
    border: Mapped[str] = mapped_column(String(60), default="rgba(255,255,255,0.14)")
    glow: Mapped[str] = mapped_column(String(60), default="rgba(99,102,241,0.35)")
    
    # Metadata
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, default=False)  # True for default themes
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    created_by: Mapped[Optional[str]] = mapped_column(String(36))

    def __repr__(self) -> str:
        return f"<CustomTheme {self.name}>"

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "label": self.label,
            "icon": self.icon,
            "bgImage": self.bg_image or "",
            "wallpaperOverlay": self.wallpaper_overlay or "",
            "bg": self.bg or "",
            "bgColor": self.bg_color,
            "primary": self.primary,
            "primaryHover": self.primary_hover,
            "accentGradient": self.accent_gradient,
            "primaryRgb": self.primary_rgb,
            "text": self.text,
            "textMuted": self.text_muted,
            "textPrimary": self.text_primary,
            "textSecondary": self.text_secondary,
            "glassBg": self.glass_bg,
            "glassBorder": self.glass_border,
            "navGlass": self.nav_glass,
            "border": self.border,
            "glow": self.glow,
            "isActive": self.is_active,
            "isBuiltin": self.is_builtin,
            "isCustom": not self.is_builtin,
            "createdAt": self.created_at.isoformat() if self.created_at else None,
            "updatedAt": self.updated_at.isoformat() if self.updated_at else None,
        }
