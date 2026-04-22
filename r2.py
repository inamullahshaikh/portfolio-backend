"""Upload files to Cloudflare R2 (S3-compatible API)."""

import uuid
from typing import BinaryIO

import boto3
from botocore.config import Config

from db import get_settings


def r2_configured() -> bool:
    s = get_settings()
    return bool(
        s.R2_ACCOUNT_ID.strip()
        and s.R2_ACCESS_KEY_ID.strip()
        and s.R2_SECRET_ACCESS_KEY.strip()
        and s.R2_BUCKET_NAME.strip()
        and s.R2_PUBLIC_BASE_URL.strip()
    )


def upload_resume_pdf(fileobj: BinaryIO, *, filename_hint: str = "resume") -> str:
    """Upload PDF to R2. Returns public URL. Raises RuntimeError if R2 is not configured."""
    if not r2_configured():
        raise RuntimeError("R2 is not configured (set R2_* env vars).")

    settings = get_settings()
    safe = "".join(c for c in filename_hint if c.isalnum() or c in "._-")[:80] or "resume"
    if not safe.lower().endswith(".pdf"):
        safe = f"{safe}.pdf"
    key = f"resumes/{uuid.uuid4().hex}-{safe}"

    endpoint = f"https://{settings.R2_ACCOUNT_ID.strip()}.r2.cloudflarestorage.com"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID.strip(),
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY.strip(),
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )
    client.upload_fileobj(
        fileobj,
        settings.R2_BUCKET_NAME.strip(),
        key,
        ExtraArgs={"ContentType": "application/pdf", "ContentDisposition": 'attachment; filename="resume.pdf"'},
    )
    base = settings.R2_PUBLIC_BASE_URL.strip().rstrip("/")
    return f"{base}/{key}"
