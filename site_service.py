"""Load merged site settings from MongoDB."""

from db import get_db
from models import SitePublicOut
from site_defaults import SITE_DOCUMENT_ID, merge_site_doc


async def get_site_public() -> SitePublicOut:
    db = get_db()
    doc = await db.site_settings.find_one({"_id": SITE_DOCUMENT_ID})
    return SitePublicOut.model_validate(merge_site_doc(doc))
