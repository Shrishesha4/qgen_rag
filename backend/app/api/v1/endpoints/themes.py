"""Custom themes API endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import uuid

from app.api.v1.deps import get_current_user
from app.core.auth_database import get_auth_db
from app.models.custom_theme import CustomTheme
from app.models.user import ROLE_ADMIN, User


router = APIRouter()


class ThemeCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50, pattern=r"^[a-z0-9_-]+$")
    label: str = Field(..., min_length=1, max_length=100)
    icon: str = Field(default="🎨", max_length=10)
    bgImage: str = Field(default="", max_length=500)
    wallpaperOverlay: str = Field(default="", max_length=1000)
    bg: str = Field(default="", max_length=2000)
    bgColor: str = Field(default="#1a1a2e", max_length=20)
    primary: str = Field(default="#6366f1", max_length=20)
    primaryHover: str = Field(default="#818cf8", max_length=20)
    accentGradient: str = Field(default="#a855f7", max_length=20)
    primaryRgb: str = Field(default="99, 102, 241", max_length=20)
    text: str = Field(default="#f8fafc", max_length=20)
    textMuted: str = Field(default="#94a3b8", max_length=60)
    textPrimary: str = Field(default="#1e293b", max_length=20)
    textSecondary: str = Field(default="rgba(0,0,0,0.55)", max_length=60)
    glassBg: str = Field(default="rgba(255, 255, 255, 0.55)", max_length=100)
    glassBorder: str = Field(default="rgba(255, 255, 255, 0.7)", max_length=100)
    navGlass: str = Field(default="rgba(255, 255, 255, 0.5)", max_length=100)
    border: str = Field(default="rgba(255,255,255,0.14)", max_length=60)
    glow: str = Field(default="rgba(99,102,241,0.35)", max_length=60)
    isActive: bool = True


class ThemeUpdate(BaseModel):
    label: Optional[str] = Field(None, min_length=1, max_length=100)
    icon: Optional[str] = Field(None, max_length=10)
    bgImage: Optional[str] = Field(None, max_length=500)
    wallpaperOverlay: Optional[str] = Field(None, max_length=1000)
    bg: Optional[str] = Field(None, max_length=2000)
    bgColor: Optional[str] = Field(None, max_length=20)
    primary: Optional[str] = Field(None, max_length=20)
    primaryHover: Optional[str] = Field(None, max_length=20)
    accentGradient: Optional[str] = Field(None, max_length=20)
    primaryRgb: Optional[str] = Field(None, max_length=20)
    text: Optional[str] = Field(None, max_length=20)
    textMuted: Optional[str] = Field(None, max_length=60)
    textPrimary: Optional[str] = Field(None, max_length=20)
    textSecondary: Optional[str] = Field(None, max_length=60)
    glassBg: Optional[str] = Field(None, max_length=100)
    glassBorder: Optional[str] = Field(None, max_length=100)
    navGlass: Optional[str] = Field(None, max_length=100)
    border: Optional[str] = Field(None, max_length=60)
    glow: Optional[str] = Field(None, max_length=60)
    isActive: Optional[bool] = None


class ThemeResponse(BaseModel):
    id: str
    name: str
    label: str
    icon: str
    bgImage: str
    wallpaperOverlay: str
    bg: str
    bgColor: str
    primary: str
    primaryHover: str
    accentGradient: str
    primaryRgb: str
    text: str
    textMuted: str
    textPrimary: str
    textSecondary: str
    glassBg: str
    glassBorder: str
    navGlass: str
    border: str
    glow: str
    isActive: bool
    isBuiltin: bool = False
    isCustom: bool = True
    createdAt: Optional[str] = None
    updatedAt: Optional[str] = None


class ThemeListResponse(BaseModel):
    themes: list[ThemeResponse]


def _ensure_admin(current_user: User) -> None:
    if current_user.role != ROLE_ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins can manage themes",
        )


def _theme_to_response(theme: CustomTheme) -> ThemeResponse:
    return ThemeResponse(**theme.to_dict())


@router.get("", response_model=ThemeListResponse)
async def list_custom_themes(
    db: AsyncSession = Depends(get_auth_db),
):
    """Get all custom themes (public endpoint)."""
    result = await db.execute(
        select(CustomTheme)
        .where(CustomTheme.is_active == True)
        .order_by(CustomTheme.created_at)
    )
    themes = result.scalars().all()
    return ThemeListResponse(themes=[_theme_to_response(t) for t in themes])


@router.get("/all", response_model=ThemeListResponse)
async def list_all_themes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Get all custom themes including inactive (admin only)."""
    _ensure_admin(current_user)
    result = await db.execute(
        select(CustomTheme).order_by(CustomTheme.created_at)
    )
    themes = result.scalars().all()
    return ThemeListResponse(themes=[_theme_to_response(t) for t in themes])


@router.get("/{theme_id}", response_model=ThemeResponse)
async def get_custom_theme(
    theme_id: str,
    db: AsyncSession = Depends(get_auth_db),
):
    """Get a single custom theme by ID."""
    result = await db.execute(
        select(CustomTheme).where(CustomTheme.id == theme_id)
    )
    theme = result.scalar_one_or_none()
    if not theme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Theme not found",
        )
    return _theme_to_response(theme)


@router.post("", response_model=ThemeResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_theme(
    data: ThemeCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Create a new custom theme (admin only)."""
    _ensure_admin(current_user)

    # Check for duplicate name
    normalized_name = data.name.lower().strip()
    result = await db.execute(
        select(CustomTheme).where(CustomTheme.name == normalized_name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A theme with name '{data.name}' already exists",
        )

    theme = CustomTheme(
        id=str(uuid.uuid4()),
        name=normalized_name,
        label=data.label,
        icon=data.icon,
        bg_image=data.bgImage,
        wallpaper_overlay=data.wallpaperOverlay,
        bg=data.bg,
        bg_color=data.bgColor,
        primary=data.primary,
        primary_hover=data.primaryHover,
        accent_gradient=data.accentGradient,
        primary_rgb=data.primaryRgb,
        text=data.text,
        text_muted=data.textMuted,
        text_primary=data.textPrimary,
        text_secondary=data.textSecondary,
        glass_bg=data.glassBg,
        glass_border=data.glassBorder,
        nav_glass=data.navGlass,
        border=data.border,
        glow=data.glow,
        is_active=data.isActive,
        created_by=current_user.id,
    )

    db.add(theme)
    await db.commit()
    await db.refresh(theme)

    return _theme_to_response(theme)


@router.put("/{theme_id}", response_model=ThemeResponse)
async def update_custom_theme(
    theme_id: str,
    data: ThemeUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Update a custom theme (admin only)."""
    _ensure_admin(current_user)

    result = await db.execute(
        select(CustomTheme).where(CustomTheme.id == theme_id)
    )
    theme = result.scalar_one_or_none()
    if not theme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Theme not found",
        )

    # Update only provided fields
    update_data = data.model_dump(exclude_unset=True)
    field_mapping = {
        "label": "label",
        "icon": "icon",
        "bgImage": "bg_image",
        "wallpaperOverlay": "wallpaper_overlay",
        "bg": "bg",
        "bgColor": "bg_color",
        "primary": "primary",
        "primaryHover": "primary_hover",
        "accentGradient": "accent_gradient",
        "primaryRgb": "primary_rgb",
        "text": "text",
        "textMuted": "text_muted",
        "textPrimary": "text_primary",
        "textSecondary": "text_secondary",
        "glassBg": "glass_bg",
        "glassBorder": "glass_border",
        "navGlass": "nav_glass",
        "border": "border",
        "glow": "glow",
        "isActive": "is_active",
    }

    for api_field, db_field in field_mapping.items():
        if api_field in update_data:
            setattr(theme, db_field, update_data[api_field])

    await db.commit()
    await db.refresh(theme)

    return _theme_to_response(theme)


@router.delete("/{theme_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_custom_theme(
    theme_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Delete a custom theme (admin only)."""
    _ensure_admin(current_user)

    result = await db.execute(
        select(CustomTheme).where(CustomTheme.id == theme_id)
    )
    theme = result.scalar_one_or_none()
    if not theme:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Theme not found",
        )

    await db.delete(theme)
    await db.commit()


# Default built-in themes to seed into the database
DEFAULT_THEMES = [
    {
        "name": "aurora",
        "label": "Aurora",
        "icon": "🌌",
        "bg_image": "/theme-pictures/auroranew.webp",
        "wallpaper_overlay": "linear-gradient(180deg, rgba(2,10,18,0.16) 0%, rgba(2,10,18,0.08) 50%, rgba(1,8,14,0.22) 100%)",
        "bg": "radial-gradient(ellipse at 72% 24%, rgba(73, 255, 148, 0.3) 0%, transparent 44%), radial-gradient(ellipse at 36% 62%, rgba(38, 214, 190, 0.24) 0%, transparent 52%), radial-gradient(ellipse at 18% 90%, rgba(68, 148, 214, 0.22) 0%, transparent 50%), linear-gradient(173deg, #04111d 0%, #0a2434 24%, #12384d 46%, #11495f 66%, #0e3147 82%, #081e2f 100%)",
        "bg_color": "#0f3347",
        "primary": "#006a45",
        "primary_hover": "#0ea371",
        "accent_gradient": "#008b81",
        "primary_rgb": "23, 166, 115",
        "text": "#e7f6f4",
        "text_muted": "#a5c8cd",
        "text_primary": "#0f2533",
        "text_secondary": "rgba(10, 28, 38, 0.64)",
        "glass_bg": "rgba(245, 255, 254, 0.56)",
        "glass_border": "rgba(224, 246, 245, 0.74)",
        "nav_glass": "rgba(237, 252, 251, 0.48)",
        "border": "rgba(255,255,255,0.18)",
        "glow": "rgba(39, 212, 200, 0.36)",
    },
    {
        "name": "water",
        "label": "Ocean",
        "icon": "🌊",
        "bg_image": "/theme-pictures/deep-ocean-new.webp",
        "wallpaper_overlay": "linear-gradient(180deg, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0.0) 50%, rgba(0,0,0,0.15) 100%)",
        "bg": "radial-gradient(ellipse at 30% 80%, rgba(20,80,160,0.35) 0%, transparent 50%), radial-gradient(ellipse at 70% 20%, rgba(30,100,180,0.25) 0%, transparent 45%), linear-gradient(175deg, #0a1e38 0%, #152e50 20%, #1f4268 40%, #2a5680 60%, #356a98 80%, #407eb0 100%)",
        "bg_color": "#1f4268",
        "primary": "#14619c",
        "primary_hover": "#2888d4",
        "accent_gradient": "#2dd4bf",
        "primary_rgb": "56, 152, 224",
        "text": "#e0e8f4",
        "text_muted": "#8aa8c8",
        "text_primary": "#1a1a2e",
        "text_secondary": "rgba(0,0,0,0.55)",
        "glass_bg": "rgba(255, 255, 255, 0.55)",
        "glass_border": "rgba(255, 255, 255, 0.7)",
        "nav_glass": "rgba(255, 255, 255, 0.5)",
        "border": "rgba(255,255,255,0.14)",
        "glow": "rgba(56,152,224,0.35)",
    },
    {
        "name": "fire",
        "label": "Landscape",
        "icon": "🌄",
        "bg_image": "/theme-pictures/landscape.webp",
        "wallpaper_overlay": "linear-gradient(180deg, rgba(20,10,6,0.12) 0%, rgba(12,8,10,0.06) 48%, rgba(16,10,12,0.2) 100%)",
        "bg": "radial-gradient(ellipse at 72% 18%, rgba(255, 112, 66, 0.26) 0%, transparent 46%), radial-gradient(ellipse at 22% 84%, rgba(121, 70, 184, 0.2) 0%, transparent 50%), linear-gradient(172deg, #261321 0%, #3b1834 22%, #5b2340 42%, #7f2f37 62%, #a4492f 80%, #cb6a2f 100%)",
        "bg_color": "#7f2f37",
        "primary": "#cf5a29",
        "primary_hover": "#e57a48",
        "accent_gradient": "#ff9f43",
        "primary_rgb": "207, 90, 41",
        "text": "#f8efe8",
        "text_muted": "#d8b9aa",
        "text_primary": "#2e1914",
        "text_secondary": "rgba(38, 20, 18, 0.66)",
        "glass_bg": "rgba(255, 250, 247, 0.58)",
        "glass_border": "rgba(255, 233, 223, 0.78)",
        "nav_glass": "rgba(255, 244, 238, 0.5)",
        "border": "rgba(255,255,255,0.14)",
        "glow": "rgba(224, 105, 62, 0.38)",
    },
    {
        "name": "earth",
        "label": "Forest",
        "icon": "🌿",
        "bg_image": "/theme-pictures/dark-forest.webp",
        "wallpaper_overlay": "linear-gradient(180deg, rgba(0,0,0,0.1) 0%, rgba(0,0,0,0.05) 50%, rgba(0,0,0,0.15) 100%)",
        "bg": "radial-gradient(ellipse at 25% 75%, rgba(40,120,50,0.25) 0%, transparent 50%), radial-gradient(ellipse at 75% 25%, rgba(50,140,60,0.2) 0%, transparent 40%), linear-gradient(175deg, #0e1c0e 0%, #1a3018 20%, #264624 40%, #325c30 60%, #3e723c 80%, #4a8848 100%)",
        "bg_color": "#325c30",
        "primary": "#0c7713",
        "primary_hover": "#38b040",
        "accent_gradient": "#40916c",
        "primary_rgb": "72, 192, 80",
        "text": "#e4f4e6",
        "text_muted": "#90b894",
        "text_primary": "#1b2e1b",
        "text_secondary": "rgba(0,0,0,0.55)",
        "glass_bg": "rgba(255, 255, 255, 0.55)",
        "glass_border": "rgba(255, 255, 255, 0.7)",
        "nav_glass": "rgba(255, 255, 255, 0.5)",
        "border": "rgba(255,255,255,0.14)",
        "glow": "rgba(72,192,80,0.35)",
    },
    {
        "name": "night",
        "label": "Midnight",
        "icon": "🌙",
        "bg_image": "/theme-pictures/midnight.webp",
        "wallpaper_overlay": "linear-gradient(180deg, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0.1) 50%, rgba(0,0,0,0.2) 100%)",
        "bg": "radial-gradient(ellipse at 20% 60%, rgba(80,40,140,0.25) 0%, transparent 50%), radial-gradient(ellipse at 80% 80%, rgba(40,20,100,0.2) 0%, transparent 45%), linear-gradient(175deg, #08081a 0%, #0e0e2a 20%, #14143a 40%, #1a1a4a 60%, #12123a 80%, #181842 100%)",
        "bg_color": "#14143a",
        "primary": "#981e32",
        "primary_hover": "#d83550",
        "accent_gradient": "#560bad",
        "primary_rgb": "233, 69, 96",
        "text": "#e8e8f4",
        "text_muted": "#9a9ac0",
        "text_primary": "#1a1a2e",
        "text_secondary": "rgba(0,0,0,0.5)",
        "glass_bg": "rgba(255, 255, 255, 0.45)",
        "glass_border": "rgba(255, 255, 255, 0.6)",
        "nav_glass": "rgba(255, 255, 255, 0.4)",
        "border": "rgba(255,255,255,0.12)",
        "glow": "rgba(233,69,96,0.35)",
    },
    {
        "name": "dusk",
        "label": "Dusk",
        "icon": "🌆",
        "bg_image": "/theme-pictures/dusk.webp",
        "wallpaper_overlay": "linear-gradient(180deg, rgba(16,10,42,0.16) 0%, rgba(12,8,28,0.08) 50%, rgba(12,8,26,0.22) 100%)",
        "bg": "radial-gradient(ellipse at 74% 22%, rgba(255, 108, 168, 0.3) 0%, transparent 45%), radial-gradient(ellipse at 22% 78%, rgba(138, 109, 255, 0.24) 0%, transparent 52%), linear-gradient(174deg, #1b1944 0%, #2a2f6f 24%, #444199 46%, #6f4aa8 66%, #99509c 82%, #cf6f9f 100%)",
        "bg_color": "#444199",
        "primary": "#c15175",
        "primary_hover": "#f07cbc",
        "accent_gradient": "#8b6cff",
        "primary_rgb": "225, 90, 167",
        "text": "#f5edff",
        "text_muted": "#cfb8ec",
        "text_primary": "#251a36",
        "text_secondary": "rgba(38, 30, 58, 0.62)",
        "glass_bg": "rgba(252, 246, 255, 0.54)",
        "glass_border": "rgba(242, 223, 255, 0.72)",
        "nav_glass": "rgba(246, 234, 255, 0.46)",
        "border": "rgba(255,255,255,0.12)",
        "glow": "rgba(225, 90, 167, 0.36)",
    },
    {
        "name": "sunset",
        "label": "Sunset",
        "icon": "🌅",
        "bg_image": "/theme-pictures/sunset.webp",
        "wallpaper_overlay": "linear-gradient(180deg, rgba(22,14,8,0.12) 0%, rgba(18,14,18,0.06) 52%, rgba(14,10,12,0.2) 100%)",
        "bg": "radial-gradient(ellipse at 16% 18%, rgba(255, 199, 71, 0.4) 0%, transparent 40%), radial-gradient(ellipse at 78% 82%, rgba(36, 145, 219, 0.22) 0%, transparent 48%), linear-gradient(172deg, #173761 0%, #1f4f7a 20%, #3c6f8e 38%, #d1783e 58%, #f09d3e 77%, #ffd172 100%)",
        "bg_color": "#d1783e",
        "primary": "#de7a2a",
        "primary_hover": "#ee9546",
        "accent_gradient": "#3ea0d8",
        "primary_rgb": "222, 122, 42",
        "text": "#fff4e2",
        "text_muted": "#e7cba7",
        "text_primary": "#2f1d11",
        "text_secondary": "rgba(43, 27, 16, 0.64)",
        "glass_bg": "rgba(255, 250, 240, 0.58)",
        "glass_border": "rgba(255, 236, 208, 0.76)",
        "nav_glass": "rgba(255, 246, 230, 0.5)",
        "border": "rgba(255,255,255,0.12)",
        "glow": "rgba(222, 122, 42, 0.36)",
    },
    {
        "name": "purplesands",
        "label": "Purple Sands",
        "icon": "🏜️",
        "bg_image": "/theme-pictures/purple-sands.webp",
        "wallpaper_overlay": "linear-gradient(180deg, rgba(15,12,40,0.16) 0%, rgba(12,10,34,0.08) 50%, rgba(9,8,24,0.24) 100%)",
        "bg": "radial-gradient(ellipse at 55% 24%, rgba(255, 123, 196, 0.28) 0%, transparent 45%), radial-gradient(ellipse at 80% 70%, rgba(104, 108, 255, 0.25) 0%, transparent 50%), linear-gradient(174deg, #121532 0%, #1e2a5a 24%, #38438a 44%, #6f5ea5 62%, #9f63a5 80%, #d67cb5 100%)",
        "bg_color": "#38438a",
        "primary": "#c35bb5",
        "primary_hover": "#d77ac7",
        "accent_gradient": "#5d7dff",
        "primary_rgb": "195, 91, 181",
        "text": "#f2ecff",
        "text_muted": "#c5b8e8",
        "text_primary": "#231d3d",
        "text_secondary": "rgba(33, 26, 56, 0.62)",
        "glass_bg": "rgba(247, 242, 255, 0.54)",
        "glass_border": "rgba(229, 220, 255, 0.72)",
        "nav_glass": "rgba(236, 228, 255, 0.46)",
        "border": "rgba(255,255,255,0.12)",
        "glow": "rgba(195, 91, 181, 0.36)",
    },
]


class SeedResponse(BaseModel):
    message: str
    seeded: int
    skipped: int


@router.post("/seed", response_model=SeedResponse)
async def seed_default_themes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_auth_db),
):
    """Seed default built-in themes into the database (admin only)."""
    _ensure_admin(current_user)

    seeded = 0
    skipped = 0

    for theme_data in DEFAULT_THEMES:
        # Check if theme already exists
        result = await db.execute(
            select(CustomTheme).where(CustomTheme.name == theme_data["name"])
        )
        if result.scalar_one_or_none():
            skipped += 1
            continue

        theme = CustomTheme(
            id=str(uuid.uuid4()),
            is_builtin=True,
            is_active=True,
            **theme_data,
        )
        db.add(theme)
        seeded += 1

    await db.commit()

    return SeedResponse(
        message=f"Seeded {seeded} default themes, skipped {skipped} existing themes",
        seeded=seeded,
        skipped=skipped,
    )
