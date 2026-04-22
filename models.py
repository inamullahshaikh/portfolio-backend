"""Pydantic v2 models and application settings."""

from datetime import datetime
from pathlib import Path
from typing import Any

from bson import ObjectId
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env next to this package (cwd differs under uvicorn --reload workers).
_BACKEND_DIR = Path(__file__).resolve().parent
_ENV_FILES: tuple[str, ...] = tuple(
    str(p)
    for p in (_BACKEND_DIR.parent / ".env", _BACKEND_DIR / ".env")
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_ENV_FILES,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    MONGODB_URI: str
    DB_NAME: str
    JWT_SECRET: str
    JWT_EXPIRE_HOURS: float = 24
    GMAIL_USER: str
    GMAIL_APP_PASSWORD: str
    ADMIN_EMAIL: EmailStr
    CORS_ORIGINS: str = "http://localhost:5173"
    # Cloudflare R2 (optional — resume upload disabled until all are set)
    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = ""
    R2_PUBLIC_BASE_URL: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


def oid_str(v: Any) -> str:
    if isinstance(v, ObjectId):
        return str(v)
    return str(v)


# ——— Projects ———
class ProjectBase(BaseModel):
    slug: str
    name: str
    category: str = "OTHER"
    short_description: str = ""
    long_description: str = ""
    what_it_does: str = ""
    tech_breakdown: dict[str, str] = Field(default_factory=dict)
    challenges: str = ""
    stack_tags: list[str] = Field(default_factory=list)
    github_url: str = ""
    live_url: str = ""
    start_date: str = ""
    end_date: str = ""
    screenshots: list[str] = Field(default_factory=list)
    sort_order: int = 0
    featured: bool = False
    published: bool = True


class ProjectCreate(ProjectBase):
    id: str = ""


class ProjectUpdate(BaseModel):
    slug: str | None = None
    name: str | None = None
    category: str | None = None
    short_description: str | None = None
    long_description: str | None = None
    what_it_does: str | None = None
    tech_breakdown: dict[str, str] | None = None
    challenges: str | None = None
    stack_tags: list[str] | None = None
    github_url: str | None = None
    live_url: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    screenshots: list[str] | None = None
    sort_order: int | None = None
    featured: bool | None = None
    published: bool | None = None


class ProjectOut(ProjectBase):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = Field(validation_alias="_id")

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: Any) -> str:
        return oid_str(v)


class ProjectBulkUpsertIn(BaseModel):
    projects: list[ProjectCreate] = Field(default_factory=list)
    clear_existing: bool = False


# ——— Experience ———
class ExperienceBase(BaseModel):
    company: str
    role: str
    location: str = ""
    start_date: str = ""
    end_date: str = ""
    bullets: list[str] = Field(default_factory=list)


class ExperienceCreate(ExperienceBase):
    id: str = ""


class ExperienceUpdate(BaseModel):
    company: str | None = None
    role: str | None = None
    location: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    bullets: list[str] | None = None


class ExperienceOut(ExperienceBase):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = Field(validation_alias="_id")

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: Any) -> str:
        return oid_str(v)


# ——— Certifications ———
class CertificationBase(BaseModel):
    name: str
    issuer: str = ""
    year: str = ""
    url: str = ""
    in_progress: bool = False


class CertificationCreate(CertificationBase):
    id: str = ""


class CertificationUpdate(BaseModel):
    name: str | None = None
    issuer: str | None = None
    year: str | None = None
    url: str | None = None
    in_progress: bool | None = None


class CertificationOut(CertificationBase):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = Field(validation_alias="_id")

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: Any) -> str:
        return oid_str(v)


# ——— Skills (grouped category + tags) ———
class SkillCategoryBase(BaseModel):
    category: str
    tags: list[str] = Field(default_factory=list)
    sort_order: int = 0


class SkillCategoryCreate(SkillCategoryBase):
    id: str = ""


class SkillCategoryUpdate(BaseModel):
    category: str | None = None
    tags: list[str] | None = None
    sort_order: int | None = None


class SkillCategoryOut(SkillCategoryBase):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = Field(validation_alias="_id")

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: Any) -> str:
        return oid_str(v)


# ——— Messages ———
class ContactIn(BaseModel):
    name: str
    email: EmailStr
    message: str


class MessageOut(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    id: str = Field(validation_alias="_id")
    name: str
    email: str
    message: str
    created_at: datetime
    replied_at: datetime | None = None

    @field_validator("id", mode="before")
    @classmethod
    def coerce_id(cls, v: Any) -> str:
        return oid_str(v)


class MessageReplyIn(BaseModel):
    body: str
    subject: str | None = None


# ——— Site settings (single document in `site_settings`) ———
class AboutFact(BaseModel):
    k: str
    v: str


class SitePublicOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    hero_title: str
    hero_subtitle: str
    hero_stack_tags: list[str]
    resume_url: str
    github_url: str
    linkedin_url: str
    leetcode_url: str
    email: str
    phone_tel: str
    phone_display: str
    contact_heading: str
    contact_sub: str
    footer_text: str
    about_bio: str
    about_facts: list[AboutFact]


class SiteUpdate(BaseModel):
    hero_title: str | None = None
    hero_subtitle: str | None = None
    hero_stack_tags: list[str] | None = None
    resume_url: str | None = None
    github_url: str | None = None
    linkedin_url: str | None = None
    leetcode_url: str | None = None
    email: str | None = None
    phone_tel: str | None = None
    phone_display: str | None = None
    contact_heading: str | None = None
    contact_sub: str | None = None
    footer_text: str | None = None
    about_bio: str | None = None
    about_facts: list[AboutFact] | None = None


# ——— Admin ———
class AdminLoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminUserInDb(BaseModel):
    model_config = ConfigDict(extra="ignore")

    email: str
    password_hash: str
