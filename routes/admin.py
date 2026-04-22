"""Admin authentication and CRUD for portfolio content."""

import asyncio
import os
from datetime import datetime, timezone
from io import BytesIO
from typing import Annotated

from bson import ObjectId
from bson.errors import InvalidId
from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from pydantic import EmailStr, ValidationError

from auth import create_access_token, get_current_admin_email, verify_password
from db import get_db
from mail import send_reply_email
from models import (
    AdminLoginIn,
    CertificationCreate,
    CertificationOut,
    CertificationUpdate,
    ExperienceCreate,
    ExperienceOut,
    ExperienceUpdate,
    MessageOut,
    MessageReplyIn,
    ProjectCreate,
    ProjectBulkUpsertIn,
    ProjectOut,
    ProjectUpdate,
    SitePublicOut,
    SiteUpdate,
    SkillCategoryCreate,
    SkillCategoryOut,
    SkillCategoryUpdate,
    TokenOut,
)
from r2 import r2_configured, upload_resume_pdf
from site_defaults import SITE_DOCUMENT_ID
from site_service import get_site_public

router = APIRouter(prefix="/api/admin", tags=["admin"])


def oid(id_str: str) -> ObjectId:
    try:
        return ObjectId(id_str)
    except InvalidId as e:
        raise HTTPException(status_code=400, detail="Invalid id") from e


@router.post("/login", response_model=TokenOut)
async def admin_login(body: AdminLoginIn):
    db = get_db()
    email = str(body.email).lower().strip()
    user = await db.admin_users.find_one({"email": email})
    if not user or not verify_password(body.password, user.get("password_hash", "")):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    token = create_access_token(subject=user["email"])
    return TokenOut(access_token=token)


@router.get("/messages", response_model=list[MessageOut])
async def list_messages(_admin: Annotated[str, Depends(get_current_admin_email)]):
    db = get_db()
    cursor = db.messages.find().sort("created_at", -1)
    docs = await cursor.to_list(500)
    return [MessageOut.model_validate(d) for d in docs]


@router.get("/messages/{message_id}", response_model=MessageOut)
async def get_message(
    message_id: str,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    doc = await db.messages.find_one({"_id": oid(message_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Message not found")
    return MessageOut.model_validate(doc)


@router.post("/messages/{message_id}/reply")
async def reply_to_message(
    message_id: str,
    body: MessageReplyIn,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    msg = await db.messages.find_one({"_id": oid(message_id)})
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")
    raw_to = str(msg.get("email", "")).strip()
    if not raw_to:
        raise HTTPException(status_code=400, detail="Message has no sender email")
    try:
        to_email = str(EmailStr(raw_to))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail="Message has invalid sender email") from e
    text = body.body.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Reply body is required")
    subject = (body.subject or "").strip() or f"Re: Your message to {msg.get('name', 'portfolio')}"
    try:
        await send_reply_email(
            to_email=to_email,
            subject=subject,
            body=text,
            visitor_name=msg.get("name", "there"),
            original_message=msg.get("message", ""),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email: {e!s}") from e
    await db.messages.update_one(
        {"_id": oid(message_id)},
        {"$set": {"replied_at": datetime.now(timezone.utc)}},
    )
    return {"status": "ok"}


@router.delete("/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_message(
    message_id: str,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    result = await db.messages.delete_one({"_id": oid(message_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")


@router.get("/site", response_model=SitePublicOut)
async def admin_get_site(_admin: Annotated[str, Depends(get_current_admin_email)]):
    return await get_site_public()


@router.put("/site", response_model=SitePublicOut)
async def admin_put_site(
    body: SiteUpdate,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    updates = body.model_dump(exclude_unset=True)
    if updates:
        await db.site_settings.update_one(
            {"_id": SITE_DOCUMENT_ID},
            {"$set": updates},
            upsert=True,
        )
    return await get_site_public()


@router.post("/upload/resume")
async def admin_upload_resume(
    file: UploadFile,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    if not r2_configured():
        raise HTTPException(
            status_code=503,
            detail="R2 is not configured. Set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME, R2_PUBLIC_BASE_URL.",
        )
    if (file.content_type or "") != "application/pdf":
        raise HTTPException(status_code=400, detail="Only application/pdf is allowed.")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Maximum file size is 5 MB.")
    hint = os.path.basename(file.filename or "resume.pdf") or "resume.pdf"
    buf = BytesIO(data)
    buf.seek(0)
    try:
        public_url = await asyncio.to_thread(upload_resume_pdf, buf, filename_hint=hint)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    db = get_db()
    await db.site_settings.update_one(
        {"_id": SITE_DOCUMENT_ID},
        {"$set": {"resume_url": public_url}},
        upsert=True,
    )
    return {"resume_url": public_url}


# ——— Projects ———
@router.post("/projects", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
async def admin_create_project(
    body: ProjectCreate,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    data = body.model_dump(exclude={"id"}, exclude_none=False)
    data.pop("id", None)
    res = await db.projects.insert_one(data)
    doc = await db.projects.find_one({"_id": res.inserted_id})
    return ProjectOut.model_validate(doc)


@router.get("/projects", response_model=list[ProjectOut])
async def admin_list_projects(_admin: Annotated[str, Depends(get_current_admin_email)]):
    db = get_db()
    cursor = db.projects.find().sort([("sort_order", 1), ("featured", -1), ("name", 1)])
    docs = await cursor.to_list(1000)
    return [ProjectOut.model_validate(d) for d in docs]


@router.post("/projects/bulk-upsert", response_model=list[ProjectOut])
async def admin_bulk_upsert_projects(
    body: ProjectBulkUpsertIn,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    if not body.projects:
        raise HTTPException(status_code=400, detail="projects array is required")

    slugs: set[str] = set()
    normalized: list[dict] = []
    for idx, p in enumerate(body.projects):
        row = p.model_dump(exclude={"id"}, exclude_none=False)
        row.pop("id", None)
        slug = (row.get("slug") or "").strip()
        if not slug:
            raise HTTPException(status_code=400, detail=f"Project at index {idx} is missing slug")
        if slug in slugs:
            raise HTTPException(status_code=400, detail=f"Duplicate slug in payload: {slug}")
        slugs.add(slug)
        row["slug"] = slug
        row["sort_order"] = idx if row.get("sort_order") is None else int(row["sort_order"])
        normalized.append(row)

    if body.clear_existing:
        await db.projects.delete_many({"slug": {"$nin": list(slugs)}})

    for row in normalized:
        await db.projects.update_one(
            {"slug": row["slug"]},
            {"$set": row},
            upsert=True,
        )

    docs = await db.projects.find({"slug": {"$in": list(slugs)}}).to_list(len(normalized))
    by_slug = {d.get("slug"): d for d in docs}
    ordered = [by_slug[s] for s in [r["slug"] for r in normalized] if s in by_slug]
    return [ProjectOut.model_validate(d) for d in ordered]


@router.get("/projects/{item_id}", response_model=ProjectOut)
async def admin_get_project(
    item_id: str,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    doc = await db.projects.find_one({"_id": oid(item_id)})
    if not doc:
        raise HTTPException(404, "Project not found")
    return ProjectOut.model_validate(doc)


@router.put("/projects/{item_id}", response_model=ProjectOut)
async def admin_update_project(
    item_id: str,
    body: ProjectUpdate,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        doc = await db.projects.find_one({"_id": oid(item_id)})
        if not doc:
            raise HTTPException(404, "Project not found")
        return ProjectOut.model_validate(doc)
    result = await db.projects.update_one({"_id": oid(item_id)}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Project not found")
    doc = await db.projects.find_one({"_id": oid(item_id)})
    return ProjectOut.model_validate(doc)


@router.delete("/projects/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_project(
    item_id: str,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    result = await db.projects.delete_one({"_id": oid(item_id)})
    if result.deleted_count == 0:
        raise HTTPException(404, "Project not found")


# ——— Experience ———
@router.post("/experience", response_model=ExperienceOut, status_code=status.HTTP_201_CREATED)
async def admin_create_experience(
    body: ExperienceCreate,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    data = body.model_dump(exclude={"id"}, exclude_none=False)
    data.pop("id", None)
    res = await db.experience.insert_one(data)
    doc = await db.experience.find_one({"_id": res.inserted_id})
    return ExperienceOut.model_validate(doc)


@router.get("/experience", response_model=list[ExperienceOut])
async def admin_list_experience(_admin: Annotated[str, Depends(get_current_admin_email)]):
    db = get_db()
    cursor = db.experience.find().sort([("start_date", -1)])
    docs = await cursor.to_list(500)
    return [ExperienceOut.model_validate(d) for d in docs]


@router.get("/experience/{item_id}", response_model=ExperienceOut)
async def admin_get_experience(
    item_id: str,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    doc = await db.experience.find_one({"_id": oid(item_id)})
    if not doc:
        raise HTTPException(404, "Experience not found")
    return ExperienceOut.model_validate(doc)


@router.put("/experience/{item_id}", response_model=ExperienceOut)
async def admin_update_experience(
    item_id: str,
    body: ExperienceUpdate,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        doc = await db.experience.find_one({"_id": oid(item_id)})
        if not doc:
            raise HTTPException(404, "Experience not found")
        return ExperienceOut.model_validate(doc)
    result = await db.experience.update_one({"_id": oid(item_id)}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Experience not found")
    doc = await db.experience.find_one({"_id": oid(item_id)})
    return ExperienceOut.model_validate(doc)


@router.delete("/experience/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_experience(
    item_id: str,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    result = await db.experience.delete_one({"_id": oid(item_id)})
    if result.deleted_count == 0:
        raise HTTPException(404, "Experience not found")


# ——— Certifications ———
@router.post("/certifications", response_model=CertificationOut, status_code=status.HTTP_201_CREATED)
async def admin_create_certification(
    body: CertificationCreate,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    data = body.model_dump(exclude={"id"}, exclude_none=False)
    data.pop("id", None)
    res = await db.certifications.insert_one(data)
    doc = await db.certifications.find_one({"_id": res.inserted_id})
    return CertificationOut.model_validate(doc)


@router.get("/certifications", response_model=list[CertificationOut])
async def admin_list_certifications(_admin: Annotated[str, Depends(get_current_admin_email)]):
    db = get_db()
    cursor = db.certifications.find().sort([("year", -1), ("name", 1)])
    docs = await cursor.to_list(500)
    return [CertificationOut.model_validate(d) for d in docs]


@router.get("/certifications/{item_id}", response_model=CertificationOut)
async def admin_get_certification(
    item_id: str,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    doc = await db.certifications.find_one({"_id": oid(item_id)})
    if not doc:
        raise HTTPException(404, "Certification not found")
    return CertificationOut.model_validate(doc)


@router.put("/certifications/{item_id}", response_model=CertificationOut)
async def admin_update_certification(
    item_id: str,
    body: CertificationUpdate,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        doc = await db.certifications.find_one({"_id": oid(item_id)})
        if not doc:
            raise HTTPException(404, "Certification not found")
        return CertificationOut.model_validate(doc)
    result = await db.certifications.update_one({"_id": oid(item_id)}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Certification not found")
    doc = await db.certifications.find_one({"_id": oid(item_id)})
    return CertificationOut.model_validate(doc)


@router.delete("/certifications/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_certification(
    item_id: str,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    result = await db.certifications.delete_one({"_id": oid(item_id)})
    if result.deleted_count == 0:
        raise HTTPException(404, "Certification not found")


# ——— Skills ———
@router.post("/skills", response_model=SkillCategoryOut, status_code=status.HTTP_201_CREATED)
async def admin_create_skill_category(
    body: SkillCategoryCreate,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    data = body.model_dump(exclude={"id"}, exclude_none=False)
    data.pop("id", None)
    res = await db.skills.insert_one(data)
    doc = await db.skills.find_one({"_id": res.inserted_id})
    return SkillCategoryOut.model_validate(doc)


@router.get("/skills", response_model=list[SkillCategoryOut])
async def admin_list_skill_categories(_admin: Annotated[str, Depends(get_current_admin_email)]):
    db = get_db()
    cursor = db.skills.find().sort([("sort_order", 1), ("category", 1)])
    docs = await cursor.to_list(200)
    return [SkillCategoryOut.model_validate(d) for d in docs]


@router.get("/skills/{item_id}", response_model=SkillCategoryOut)
async def admin_get_skill_category(
    item_id: str,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    doc = await db.skills.find_one({"_id": oid(item_id)})
    if not doc:
        raise HTTPException(404, "Skill category not found")
    return SkillCategoryOut.model_validate(doc)


@router.put("/skills/{item_id}", response_model=SkillCategoryOut)
async def admin_update_skill_category(
    item_id: str,
    body: SkillCategoryUpdate,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        doc = await db.skills.find_one({"_id": oid(item_id)})
        if not doc:
            raise HTTPException(404, "Skill category not found")
        return SkillCategoryOut.model_validate(doc)
    result = await db.skills.update_one({"_id": oid(item_id)}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(404, "Skill category not found")
    doc = await db.skills.find_one({"_id": oid(item_id)})
    return SkillCategoryOut.model_validate(doc)


@router.delete("/skills/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_delete_skill_category(
    item_id: str,
    _admin: Annotated[str, Depends(get_current_admin_email)],
):
    db = get_db()
    result = await db.skills.delete_one({"_id": oid(item_id)})
    if result.deleted_count == 0:
        raise HTTPException(404, "Skill category not found")
