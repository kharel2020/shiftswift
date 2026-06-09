"""Recruitment pipeline stage definitions (10-step chart)."""

from __future__ import annotations

POSTING_PLATFORMS = [
    {"value": "Indeed", "label": "Indeed"},
    {"value": "LinkedIn", "label": "LinkedIn"},
    {"value": "Reed", "label": "Reed"},
    {"value": "Glassdoor", "label": "Glassdoor"},
    {"value": "GOV.UK Find a Job", "label": "GOV.UK Find a Job"},
    {"value": "Company careers site", "label": "Company careers site"},
]

HIRING_DECISIONS = [
    {"value": "pending", "label": "Pending decision"},
    {"value": "hire", "label": "Proceed to offer"},
    {"value": "reject", "label": "Reject candidate"},
]

OFFER_STATUSES = [
    {"value": "draft", "label": "Draft"},
    {"value": "sent", "label": "Sent to candidate"},
    {"value": "accepted", "label": "Accepted"},
    {"value": "rejected", "label": "Declined"},
]

SECTION_ORDER = (
    "vacancy_identified",
    "job_description",
    "multi_channel_posting",
    "application_intake",
    "automated_screening",
    "candidate_pipeline",
    "interview_scheduling",
    "hiring_decision",
    "offer_management",
    "offer_accepted",
)

SECTION_STEPS = {key: idx + 1 for idx, key in enumerate(SECTION_ORDER)}

SECTION_LABELS = {
    "vacancy_identified": "Vacancy identified",
    "job_description": "Job description created",
    "multi_channel_posting": "Multi-channel posting",
    "application_intake": "Application intake",
    "automated_screening": "Automated screening",
    "candidate_pipeline": "Candidate pipeline",
    "interview_scheduling": "Interview scheduling",
    "hiring_decision": "Hiring decision",
    "offer_management": "Offer management",
    "offer_accepted": "Offer accepted",
}

SECTION_DESCRIPTIONS = {
    "vacancy_identified": "Job title, department, location.",
    "job_description": "Experience, skills, salary range.",
    "multi_channel_posting": "Job boards, company page, social.",
    "application_intake": "CV parsing, contact form, ATS data.",
    "automated_screening": "Keyword matching, knockout questions.",
    "candidate_pipeline": "Shortlist created, review, ratings.",
    "interview_scheduling": "Calendar sync, panel invites, video link.",
    "hiring_decision": "Final hire or reject decision.",
    "offer_management": "Portal letter and e-sign workflow.",
    "offer_accepted": "Trigger onboarding workflow.",
}

SECTION_BRANCHES = {
    "multi_channel_posting": "Indeed, LinkedIn, Reed, Glassdoor",
    "automated_screening": "Rejected — auto-email sent",
    "interview_scheduling": "Scorecard — candidate feedback",
    "offer_management": "Rejected — decline email",
    "offer_accepted": "Recruitment analytics — time-to-hire",
}

SECTION_KINDS = {
    "vacancy_identified": "form",
    "job_description": "form",
    "multi_channel_posting": "link",
    "application_intake": "form",
    "automated_screening": "form",
    "candidate_pipeline": "form",
    "interview_scheduling": "form",
    "hiring_decision": "form",
    "offer_management": "form",
    "offer_accepted": "action",
}

LINK_ONLY_SECTIONS = frozenset({"multi_channel_posting"})

SECTION_FIELDS: dict[str, tuple[str, ...]] = {
    "vacancy_identified": ("reference", "job_title", "department", "location", "worker_type"),
    "job_description": (
        "job_description",
        "required_skills",
        "salary_range_min",
        "salary_range_max",
    ),
    "application_intake": (
        "candidate_name",
        "candidate_email",
        "candidate_phone",
        "candidate_cv_url",
        "application_source",
    ),
    "automated_screening": ("screening_keywords", "knockout_questions"),
    "candidate_pipeline": ("pipeline_notes", "candidate_rating"),
    "interview_scheduling": ("interview_at", "interview_video_link", "scorecard_notes"),
    "hiring_decision": ("hiring_decision", "rejection_reason"),
    "offer_management": ("offer_letter_url", "offer_status"),
    "offer_accepted": ("offer_status",),
}
