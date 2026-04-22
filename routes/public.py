"""Public read endpoints and contact form."""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from db import get_db
from mail import send_contact_email
from models import (
    CertificationOut,
    ContactIn,
    ExperienceOut,
    ProjectOut,
    SitePublicOut,
    SkillCategoryOut,
)
from site_service import get_site_public

router = APIRouter(prefix="/api", tags=["public"])


@router.get("/site", response_model=SitePublicOut)
async def public_site():
    return await get_site_public()


@router.get("/projects", response_model=list[ProjectOut])
async def list_projects():
    db = get_db()
    cursor = db.projects.find().sort([("sort_order", 1), ("featured", -1), ("name", 1)])
    docs = await cursor.to_list(1000)
    return [ProjectOut.model_validate(d) for d in docs]


@router.get("/projects/{slug}", response_model=ProjectOut)
async def get_project_by_slug(slug: str):
    db = get_db()
    doc = await db.projects.find_one({"slug": slug})
    if not doc:
        raise HTTPException(status_code=404, detail="Project not found")
    if not doc.get("published", True):
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectOut.model_validate(doc)


@router.get("/experience", response_model=list[ExperienceOut])
async def list_experience():
    db = get_db()
    cursor = db.experience.find().sort([("start_date", -1)])
    docs = await cursor.to_list(500)
    return [ExperienceOut.model_validate(d) for d in docs]


@router.get("/certifications", response_model=list[CertificationOut])
async def list_certifications():
    db = get_db()
    cursor = db.certifications.find().sort([("year", -1), ("name", 1)])
    docs = await cursor.to_list(500)
    return [CertificationOut.model_validate(d) for d in docs]


@router.get("/skills", response_model=list[SkillCategoryOut])
async def list_skills():
    db = get_db()
    cursor = db.skills.find().sort([("sort_order", 1), ("category", 1)])
    docs = await cursor.to_list(200)
    return [SkillCategoryOut.model_validate(d) for d in docs]


@router.post("/contact")
async def submit_contact(payload: ContactIn):
    db = get_db()

    doc = {
        "name": payload.name.strip(),
        "email": str(payload.email).strip(),
        "message": payload.message.strip(),
        "created_at": datetime.now(timezone.utc),
    }
    if not doc["message"]:
        raise HTTPException(status_code=400, detail="Message is required")

    await db.messages.insert_one(doc)

    try:
        await send_contact_email(
            sender_name=doc["name"],
            sender_email=doc["email"],
            body_text=doc["message"],
        )
        notified = True
    except Exception:
        notified = False

    return {"status": "ok", "notified": notified}
