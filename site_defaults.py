"""Default public site copy (merged with MongoDB `site_settings`)."""

SITE_DOCUMENT_ID = "default"


def default_site_dict() -> dict:
    return {
        "hero_title": "AI Engineer.",
        "hero_subtitle": "RAG pipelines, computer vision APIs, and the cloud infra that makes them real.",
        "hero_stack_tags": ["Python", "FastAPI", "RAG", "YOLOv8", "AWS", "Kubernetes", "React"],
        "resume_url": "",
        "github_url": "https://github.com/inamshz",
        "linkedin_url": "https://linkedin.com/in/inamshz",
        "leetcode_url": "https://leetcode.com/inamshz",
        "email": "inam@example.com",
        "phone_tel": "+923000000000",
        "phone_display": "+92 300 0000000",
        "contact_heading": "Let's build something.",
        "contact_sub": "Open to AI engineering roles, internships, and interesting problems.",
        "footer_text": "Inam Ullah Shaikh · 2025",
        "about_bio": (
            "Final-year CS student at FAST-NUCES, Islamabad. I've built RAG systems, real-time CV APIs, "
            "and cloud microservices end-to-end. Currently AI Intern at Komatsu Pakistan Soft. I care "
            "about systems that work in production, not just notebooks."
        ),
        "about_facts": [
            {"k": "University", "v": "FAST-NUCES"},
            {"k": "Location", "v": "Islamabad, PK"},
            {"k": "Current role", "v": "AI Intern @ Komatsu"},
            {"k": "Open to", "v": "AI / ML roles"},
        ],
    }


def merge_site_doc(doc: dict | None) -> dict:
    out = default_site_dict()
    if not doc:
        return out
    for key, val in doc.items():
        if key.startswith("_"):
            continue
        out[key] = val
    return out
