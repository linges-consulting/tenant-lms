#!/usr/bin/env python3
"""
seed_training.py — drop ONE realistic draft training into the core DB.

Each run picks a random topic from a curated pool and builds a complete
training with:
  - 3–5 modules
  - 2–4 RICH_TEXT / VIDEO chapters per module
  - One QUIZ chapter at the end of every module (multi-quiz by design)
  - Chapters are numbered training-wide (matches the unique-seq constraint)
  - is_published = is_ready = false  → lifecycle status: DRAFT

A random banner preset (ocean / sunset / forest / ember) is assigned, just
like the API does at /trainings POST.

Usage (host, Docker stack must be up — talks to postgres on :5433)
  python scripts/seed_training.py
  python scripts/seed_training.py --tenant-id tenant-vm --creator-email vm-creator@lms.com
  python scripts/seed_training.py --seed 42                  # reproducible output
  python scripts/seed_training.py --dry-run                  # print plan, don't insert

DB credentials follow the same precedence as scripts/seed.py:
  --auth-db-url / --core-db-url     (CLI flags)
  AUTH_DB_URL / CORE_DB_URL         (env vars)
  POSTGRES_* from project root .env (assembled URL)
  fallback: lms_user / lms_pass @ localhost:5433
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import random
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine


# ---------------------------------------------------------------------------
# .env loader — same shape as scripts/seed.py
# ---------------------------------------------------------------------------

def _load_dotenv(env_path: Path) -> None:
    if not env_path.exists():
        return
    for raw in env_path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv(Path(__file__).resolve().parent.parent / ".env")


def _ensure_asyncpg(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


# ---------------------------------------------------------------------------
# Content pool — realistic enough to publish, generic enough to reuse
# ---------------------------------------------------------------------------

BANNER_PRESETS = ("ocean", "sunset", "forest", "ember")

# Public-domain video URLs that have been around for years and are safe to
# embed. ReactPlayer accepts both YouTube and direct .mp4.
SAMPLE_VIDEO_URLS = [
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ElephantsDream.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/Sintel.mp4",
    "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/TearsOfSteel.mp4",
]

# Reusable paragraphs. Two get stitched together per RICH_TEXT chapter so
# the body changes between chapters without us hand-writing 100 of them.
RICH_TEXT_PARAGRAPHS = [
    "<p>In this lesson we cover the core concepts you'll apply day-to-day. "
    "Pay particular attention to the examples — they're drawn from real "
    "scenarios your colleagues have flagged in the past quarter.</p>",
    "<p>The frameworks below are intentionally simple. They are meant to be "
    "remembered under pressure, not just understood in a classroom.</p>",
    "<p>Take a moment to think about a recent situation where this material "
    "would have changed your decision. Write it down — you'll come back to "
    "it in the quiz at the end of the module.</p>",
    "<p>There is no single right answer in most of these situations. What "
    "matters is your ability to recognise the pattern early and choose a "
    "response that protects you and the team.</p>",
    "<p>Skim the bullet points first, then return to the prose. Most of the "
    "value sits in the worked example near the end.</p>",
    "<ul><li>Identify the trigger</li><li>Pause before responding</li>"
    "<li>Pick the smallest reversible action</li><li>Document what you did</li></ul>",
    "<p>By the time you finish this chapter you should be able to articulate "
    "the policy in your own words to a teammate who wasn't in the session.</p>",
    "<p>If anything here contradicts what your manager has told you, your "
    "manager's guidance wins. This material is the baseline, not the ceiling.</p>",
]

# Generic reusable quiz questions — one of every type the viewer supports.
# Mixed so each quiz pulls 3–6 at random and still feels varied.
QUIZ_POOL = [
    {
        "type": "multiple_choice",
        "text": "Which of the following is the FIRST step when you notice a workplace hazard?",
        "options": [
            {"id": "a", "text": "Take a photo and post it on Slack"},
            {"id": "b", "text": "Make the area safe, then report it"},
            {"id": "c", "text": "Continue working and bring it up at the next standup"},
            {"id": "d", "text": "Ignore it if no one is at immediate risk"},
        ],
        "correct_option_ids": ["b"],
    },
    {
        "type": "multiple_choice",
        "text": "What does 'least privilege' mean when granting system access?",
        "options": [
            {"id": "a", "text": "Give everyone admin so nothing blocks them"},
            {"id": "b", "text": "Give the minimum permissions needed to do the job"},
            {"id": "c", "text": "Block access by default and grant it via email request"},
            {"id": "d", "text": "Rotate permissions weekly between teammates"},
        ],
        "correct_option_ids": ["b"],
    },
    {
        "type": "multiple_choice",
        "text": "A customer is visibly upset. What's the most effective opening response?",
        "options": [
            {"id": "a", "text": "Tell them to calm down"},
            {"id": "b", "text": "Acknowledge their feelings and ask what would help"},
            {"id": "c", "text": "Escalate to your manager immediately"},
            {"id": "d", "text": "Offer a refund without asking questions"},
        ],
        "correct_option_ids": ["b"],
    },
    {
        "type": "multiple_select",
        "text": "Select ALL of the following that count as personal data under GDPR.",
        "options": [
            {"id": "a", "text": "Email address"},
            {"id": "b", "text": "IP address"},
            {"id": "c", "text": "Anonymous aggregate statistics"},
            {"id": "d", "text": "Photo of someone's face"},
            {"id": "e", "text": "Company registration number"},
        ],
        "correct_option_ids": ["a", "b", "d"],
    },
    {
        "type": "multiple_select",
        "text": "Which of the following make a password significantly stronger?",
        "options": [
            {"id": "a", "text": "Length (12+ characters)"},
            {"id": "b", "text": "Using a passphrase of unrelated words"},
            {"id": "c", "text": "Substituting letters with numbers (P@ssw0rd)"},
            {"id": "d", "text": "Reusing one strong password everywhere"},
            {"id": "e", "text": "Storing it in a password manager"},
        ],
        "correct_option_ids": ["a", "b", "e"],
    },
    {
        "type": "true_false",
        "text": "A phishing email can come from a legitimate-looking colleague's account that has been compromised.",
        "options": [
            {"id": "true", "text": "True"},
            {"id": "false", "text": "False"},
        ],
        "correct_option_ids": ["true"],
    },
    {
        "type": "true_false",
        "text": "It is acceptable to delete an audit log entry as long as you note why you removed it.",
        "options": [
            {"id": "true", "text": "True"},
            {"id": "false", "text": "False"},
        ],
        "correct_option_ids": ["false"],
    },
    {
        "type": "true_false",
        "text": "Active listening means waiting your turn to speak.",
        "options": [
            {"id": "true", "text": "True"},
            {"id": "false", "text": "False"},
        ],
        "correct_option_ids": ["false"],
    },
    {
        "type": "matching",
        "text": "Match each emergency to its first action.",
        "options": [],
        "left_items": [
            {"id": "L1", "text": "Small kitchen fire"},
            {"id": "L2", "text": "Suspected gas leak"},
            {"id": "L3", "text": "Colleague has fainted"},
            {"id": "L4", "text": "Suspicious package"},
        ],
        "right_items": [
            {"id": "R1", "text": "Smother with lid, do not use water"},
            {"id": "R2", "text": "Evacuate, then call from outside"},
            {"id": "R3", "text": "Check breathing, call medical, do not move them"},
            {"id": "R4", "text": "Move away and call security"},
        ],
        "correct_option_ids": ["L1::R1", "L2::R2", "L3::R3", "L4::R4"],
    },
    {
        "type": "matching",
        "text": "Match the role to its primary responsibility on an incident.",
        "options": [],
        "left_items": [
            {"id": "L1", "text": "Incident Commander"},
            {"id": "L2", "text": "Scribe"},
            {"id": "L3", "text": "Communications Lead"},
        ],
        "right_items": [
            {"id": "R1", "text": "Owns the response and final call"},
            {"id": "R2", "text": "Maintains the timeline of events"},
            {"id": "R3", "text": "Keeps stakeholders informed"},
        ],
        "correct_option_ids": ["L1::R1", "L2::R2", "L3::R3"],
    },
    {
        "type": "ordering",
        "text": "Order the steps of an effective de-escalation conversation.",
        "options": [
            {"id": "s1", "text": "Acknowledge the emotion you're seeing"},
            {"id": "s2", "text": "Ask an open question about what they need"},
            {"id": "s3", "text": "Restate the request in your own words"},
            {"id": "s4", "text": "Agree on a next step together"},
        ],
        "correct_option_ids": ["s1", "s2", "s3", "s4"],
    },
    {
        "type": "ordering",
        "text": "Order the standard fire-drill steps from first to last.",
        "options": [
            {"id": "s1", "text": "Raise the alarm"},
            {"id": "s2", "text": "Leave by the nearest safe exit"},
            {"id": "s3", "text": "Assemble at the muster point"},
            {"id": "s4", "text": "Wait for the all-clear before re-entry"},
        ],
        "correct_option_ids": ["s1", "s2", "s3", "s4"],
    },
]

# 10 curated topics with module + chapter structure. Each topic's chapter
# list is 8–14 entries; we randomly pick 2–4 per module.
TOPICS = [
    {
        "title": "Workplace Safety Fundamentals",
        "category": "safety",
        "description": "A practical primer on identifying hazards, using PPE correctly, and responding to common workplace incidents.",
        "modules": [
            "Spotting Workplace Hazards",
            "Personal Protective Equipment",
            "Incident Reporting & Documentation",
            "Emergency Response Basics",
        ],
        "chapters": [
            "Common Physical Hazards",
            "Ergonomic Risks at the Desk",
            "Risk Assessment in Five Minutes",
            "Selecting the Right PPE",
            "When PPE is Not Enough",
            "Filing a Near-Miss Report",
            "Documenting an Injury",
            "Calling for Help: The First Sixty Seconds",
            "Fire and Smoke",
            "Working with Electrical Equipment",
        ],
    },
    {
        "title": "Customer Service Excellence",
        "category": "soft_skills",
        "description": "Move from script-based service to genuine, confident interactions that resolve issues and build loyalty.",
        "modules": [
            "Setting the Tone",
            "Active Listening",
            "Handling Difficult Conversations",
            "Closing the Loop",
        ],
        "chapters": [
            "The First Ten Seconds",
            "Tone of Voice on Calls vs. Email",
            "What Active Listening Sounds Like",
            "Reading Between the Lines",
            "When the Customer is Wrong (and How to Tell Them)",
            "Recovering After a Mistake",
            "Following Up Without Being Annoying",
            "Closing Tickets That Stay Closed",
        ],
    },
    {
        "title": "Data Privacy & GDPR Compliance",
        "category": "compliance",
        "description": "Understand what personal data is, the rights data subjects have, and what to do when something goes wrong.",
        "modules": [
            "What Counts as Personal Data",
            "Lawful Basis & Consent",
            "Subject Access Requests",
            "Breach Response",
        ],
        "chapters": [
            "Definitions That Matter",
            "Special Category Data",
            "Choosing a Lawful Basis",
            "Designing a Valid Consent Form",
            "Receiving a Subject Access Request",
            "The 30-Day Clock",
            "Recognising a Breach",
            "First Hour of a Suspected Breach",
            "Notifying the Regulator",
        ],
    },
    {
        "title": "Cybersecurity Awareness",
        "category": "compliance",
        "description": "Practical hygiene that keeps you, your devices, and your data out of trouble.",
        "modules": [
            "Strong Authentication",
            "Phishing & Social Engineering",
            "Device Security",
            "Reporting & Recovery",
        ],
        "chapters": [
            "Passwords vs. Passphrases",
            "Setting Up MFA",
            "Spotting a Phishing Email",
            "Voice and Text Phishing",
            "Public Wi-Fi: When to Use It",
            "Laptop Encryption & Lost Devices",
            "USBs You Find in the Parking Lot",
            "Reporting a Suspected Compromise",
        ],
    },
    {
        "title": "Effective Communication Skills",
        "category": "soft_skills",
        "description": "Communicate clearly under pressure — in person, in writing, and in meetings that don't waste time.",
        "modules": [
            "Verbal & Non-Verbal",
            "Writing for the Reader",
            "Meetings That Move",
            "Difficult Messages",
        ],
        "chapters": [
            "What Your Body is Saying",
            "Slowing Down Without Losing Authority",
            "Email That Gets a Reply",
            "Async Updates That Stand Alone",
            "Running a 30-Minute Meeting in 22 Minutes",
            "Disagreeing in Public",
            "Delivering Bad News",
            "Writing for Skim Readers",
        ],
    },
    {
        "title": "Time Management & Productivity",
        "category": "soft_skills",
        "description": "Make better choices about where your hours go — without buying another app.",
        "modules": [
            "Prioritisation",
            "Deep Work & Focus",
            "Meetings & Async",
            "Delegation",
        ],
        "chapters": [
            "Urgent vs. Important",
            "Saying No With Grace",
            "Designing a 'No-Meeting' Block",
            "Recovering from Interruptions",
            "Should This Be a Meeting?",
            "Writing a Decision-Ready Doc",
            "Choosing What to Hand Off",
            "Following Up Without Micromanaging",
        ],
    },
    {
        "title": "Leadership Essentials",
        "category": "leadership",
        "description": "The first 90 days as a people leader — what to do, what to skip, and what nobody warned you about.",
        "modules": [
            "Setting Direction",
            "Coaching Conversations",
            "Giving Feedback",
            "Making Decisions",
        ],
        "chapters": [
            "Articulating a Team Vision",
            "Aligning on Outcomes",
            "Running a 1:1 That Matters",
            "Asking Better Questions",
            "Positive Feedback That Lands",
            "Constructive Feedback Without the Sting",
            "Reversible vs. Irreversible Decisions",
            "Disagree and Commit",
        ],
    },
    {
        "title": "Conflict Resolution at Work",
        "category": "soft_skills",
        "description": "Move past 'agree to disagree' and reach decisions that actually hold.",
        "modules": [
            "Where Conflict Comes From",
            "Listening to Understand",
            "Finding Common Ground",
            "Following Up",
        ],
        "chapters": [
            "Task vs. Relationship Conflict",
            "Triggers and Tells",
            "Reflective Listening",
            "Reframing the Disagreement",
            "Brainstorming Without Judgment",
            "Writing Up the Agreement",
            "Checking In After the Conversation",
        ],
    },
    {
        "title": "Inclusive Workplace Training",
        "category": "compliance",
        "description": "Build habits that make every colleague feel like a full participant.",
        "modules": [
            "Recognising Bias",
            "Everyday Inclusion",
            "Microaggressions",
            "Allyship in Practice",
        ],
        "chapters": [
            "What Bias Looks Like in Hiring",
            "Bias in Day-to-Day Decisions",
            "Inclusive Language Without the Tightrope",
            "Speaking Up When You Notice Something",
            "Microaggressions: Intent vs. Impact",
            "Allyship Beyond Performative Posts",
            "Sponsorship vs. Mentorship",
        ],
    },
    {
        "title": "Emergency Response Procedures",
        "category": "safety",
        "description": "The plan you hope you never need — practiced enough that you don't have to think.",
        "modules": [
            "Fire & Evacuation",
            "Medical Emergencies",
            "Security Incidents",
            "Communications During an Incident",
        ],
        "chapters": [
            "Sounding the Alarm",
            "Evacuation Routes & Muster Points",
            "Assisting People with Reduced Mobility",
            "Basic First Aid Until Help Arrives",
            "When to Call 911",
            "Suspicious Packages and Visitors",
            "Lockdown vs. Shelter-in-Place",
            "Keeping the Outside World Informed",
        ],
    },
]


# ---------------------------------------------------------------------------
# Content builders
# ---------------------------------------------------------------------------

def build_rich_text_content(rng: random.Random) -> dict:
    body = "\n".join(rng.sample(RICH_TEXT_PARAGRAPHS, k=rng.randint(2, 3)))
    return {
        "text": body,
        "description": "Read through, then move on to the next lesson when you're ready.",
    }


def build_video_content(rng: random.Random) -> dict:
    return {
        "url": rng.choice(SAMPLE_VIDEO_URLS),
        "description": "Watch the full clip. The quiz at the end of the module references this material.",
    }


def build_quiz_content(rng: random.Random, num_questions: int) -> dict:
    """Pick `num_questions` questions; if asked for 5+, ensure variety across types."""
    pool = list(QUIZ_POOL)
    rng.shuffle(pool)

    if num_questions >= 5:
        # Guarantee at least one of each type when we have the budget for it.
        by_type: dict[str, list[dict]] = {}
        for q in pool:
            by_type.setdefault(q["type"], []).append(q)
        selected: list[dict] = []
        for t, items in by_type.items():
            if items:
                selected.append(items[0])
        # Top up with random extras from the remaining pool.
        remaining = [q for q in pool if q not in selected]
        rng.shuffle(remaining)
        selected.extend(remaining[: max(0, num_questions - len(selected))])
        questions = selected[:num_questions]
    else:
        questions = pool[:num_questions]

    # Re-id question + option ids so two quizzes can't collide in stored JSON.
    out = []
    for q in questions:
        copy = json.loads(json.dumps(q))
        copy["id"] = f"q-{uuid.uuid4().hex[:8]}"
        out.append(copy)

    return {
        "questions": out,
        "passing_score": rng.choice([70, 75, 80, 85]),
        "max_attempts": rng.choice([0, 3, 5]),
    }


# ---------------------------------------------------------------------------
# DB inserts
# ---------------------------------------------------------------------------

async def validate_tenant_and_creator(
    auth_engine: AsyncEngine, *, tenant_id: str, email: str
) -> str:
    """Verify that:
      1. the tenant exists and is active
      2. the user exists (by email) and is not soft-deleted
      3. the user has an active, training-creator membership in that tenant

    Returns the user's id on success. Raises SystemExit with a clear message
    on any failure — no insert should ever land for an invalid combination.
    """
    async with auth_engine.connect() as conn:
        # 1. Tenant
        tenant_row = (await conn.execute(
            text("SELECT id, name, is_active FROM tenants WHERE id = :tid AND deleted_at IS NULL"),
            {"tid": tenant_id},
        )).first()
        if not tenant_row:
            available = [r[0] for r in (await conn.execute(
                text("SELECT id FROM tenants WHERE deleted_at IS NULL ORDER BY id LIMIT 10")
            )).all()]
            raise SystemExit(
                f"Error: tenant id {tenant_id!r} not found.\n"
                f"  Available tenants: {', '.join(available) or '(none — run scripts/seed.py first)'}"
            )
        if not tenant_row[2]:
            raise SystemExit(
                f"Error: tenant {tenant_id!r} ({tenant_row[1]}) exists but is_active=false."
            )

        # 2. User
        user_row = (await conn.execute(
            text("SELECT id, full_name, is_sysadmin FROM users WHERE email = :email AND deleted_at IS NULL"),
            {"email": email},
        )).first()
        if not user_row:
            raise SystemExit(
                f"Error: user with email {email!r} not found in auth_db.\n"
                f"  Run scripts/seed.py --mode mock first, or pass --creator-email."
            )
        user_id = user_row[0]
        if user_row[2]:
            raise SystemExit(
                f"Error: {email!r} is a SysAdmin. SysAdmins cannot hold tenant "
                f"memberships and so cannot own trainings. Pass a tenant-scoped "
                f"Training Creator user via --creator-email."
            )

        # 3. Membership + creator role
        membership = (await conn.execute(
            text("""
                SELECT is_training_creator, is_active, status::text
                FROM tenant_memberships
                WHERE user_id = :uid AND tenant_id = :tid AND deleted_at IS NULL
            """),
            {"uid": user_id, "tid": tenant_id},
        )).first()
        if not membership:
            raise SystemExit(
                f"Error: {email!r} has no membership in tenant {tenant_id!r}.\n"
                f"  Either add the user to that tenant (manager UI / seed config) "
                f"or pass a different --creator-email."
            )
        is_creator, mem_active, mem_status = membership
        if not mem_active or mem_status != "ACTIVE":
            raise SystemExit(
                f"Error: {email!r}'s membership in {tenant_id!r} is inactive "
                f"(is_active={mem_active}, status={mem_status!r})."
            )
        if not is_creator:
            raise SystemExit(
                f"Error: {email!r} is a member of {tenant_id!r} but does NOT have "
                f"the Training Creator role. Only Training Creators can own a training."
            )

        return user_id


async def insert_training(
    conn,
    *,
    tenant_id: str,
    creator_id: str,
    title: str,
    description: str,
    category: str,
    thumbnail: str,
) -> str:
    training_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await conn.execute(text("""
        INSERT INTO trainings (
            id, tenant_id, title, description, category, duration,
            thumbnail, version, is_published, is_ready, is_archived, is_active,
            requires_certificate, structure_type, tags, requires_recertification,
            created_by_id, created_at, updated_at
        ) VALUES (
            :id, :tid, :title, :desc, :cat, :dur,
            :thumb, 1, FALSE, FALSE, FALSE, TRUE,
            FALSE, 'modular', '{}', FALSE,
            :cby, :now, :now
        )
    """), {
        "id": training_id, "tid": tenant_id, "title": title, "desc": description,
        "cat": category, "dur": "1h", "thumb": thumbnail, "cby": creator_id, "now": now,
    })
    return training_id


async def insert_module(conn, *, training_id: str, tenant_id: str, title: str, seq: int) -> str:
    module_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await conn.execute(text("""
        INSERT INTO modules (id, tenant_id, training_id, title, sequence_order, created_at, updated_at)
        VALUES (:id, :tid, :trid, :title, :seq, :now, :now)
    """), {
        "id": module_id, "tid": tenant_id, "trid": training_id,
        "title": title, "seq": seq, "now": now,
    })
    return module_id


async def insert_chapter(
    conn,
    *,
    training_id: str,
    tenant_id: str,
    module_id: str,
    title: str,
    content_type: str,
    content_data: dict,
    seq: int,
) -> str:
    chapter_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await conn.execute(text("""
        INSERT INTO chapters (
            id, tenant_id, training_id, module_id, title,
            content_type, content_data, sequence_order, completion_mode,
            created_at, updated_at
        ) VALUES (
            :id, :tid, :trid, :mid, :title,
            :ctype, CAST(:cdata AS JSON), :seq, 'can_continue',
            :now, :now
        )
    """), {
        "id": chapter_id, "tid": tenant_id, "trid": training_id, "mid": module_id,
        "title": title, "ctype": content_type,
        "cdata": json.dumps(content_data), "seq": seq, "now": now,
    })
    return chapter_id


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def seed_one_training(
    *,
    core_url: str,
    auth_url: str,
    tenant_id: str,
    creator_email: str,
    rng_seed: Optional[int],
    dry_run: bool,
) -> None:
    rng = random.Random(rng_seed) if rng_seed is not None else random.Random()

    auth_engine = create_async_engine(auth_url)
    core_engine = create_async_engine(core_url)

    try:
        creator_id = await validate_tenant_and_creator(
            auth_engine, tenant_id=tenant_id, email=creator_email,
        )

        topic = rng.choice(TOPICS)
        suffix = uuid.uuid4().hex[:6]
        title = f"{topic['title']} #{suffix}"
        thumbnail = f"preset:{rng.choice(BANNER_PRESETS)}"

        # Build a plan first so we can print + dry-run without inserts.
        plan: list[dict] = []
        running_seq = 0
        chapter_pool = list(topic["chapters"])
        rng.shuffle(chapter_pool)
        pool_idx = 0

        for mod_idx, mod_title in enumerate(topic["modules"], start=1):
            num_chapters = rng.randint(2, 4)
            mod_plan = {"title": mod_title, "chapters": []}
            for _ in range(num_chapters):
                if pool_idx >= len(chapter_pool):
                    chapter_pool = list(topic["chapters"])
                    rng.shuffle(chapter_pool)
                    pool_idx = 0
                ch_title = chapter_pool[pool_idx]
                pool_idx += 1
                ctype = rng.choices(
                    ["RICH_TEXT", "VIDEO", "RICH_TEXT"],
                    weights=[6, 2, 6],
                    k=1,
                )[0]
                running_seq += 1
                mod_plan["chapters"].append(
                    {"title": ch_title, "type": ctype, "seq": running_seq}
                )
            # Every module ends with a quiz — that's how we hit "multi-quiz".
            running_seq += 1
            mod_plan["chapters"].append({
                "title": f"{mod_title} — Knowledge Check",
                "type": "QUIZ",
                "seq": running_seq,
                "num_questions": rng.randint(3, 6),
            })
            plan.append(mod_plan)

        # ---- Print plan ----
        print()
        print(f"Training: {title}")
        print(f"  Tenant:    {tenant_id}")
        print(f"  Creator:   {creator_email}  (id={creator_id[:8]}...)")
        print(f"  Status:    Draft  (is_published=false, is_ready=false)")
        print(f"  Banner:    {thumbnail}")
        print(f"  Modules:   {len(plan)}")
        print(f"  Chapters:  {running_seq}  (incl. {sum(1 for m in plan for c in m['chapters'] if c['type'] == 'QUIZ')} quizzes)")
        for m in plan:
            print(f"    Module {plan.index(m) + 1}: {m['title']}")
            for c in m["chapters"]:
                tag = c["type"]
                extra = f" ({c['num_questions']} qs)" if tag == "QUIZ" else ""
                print(f"      {c['seq']:2d}. [{tag}]{extra} {c['title']}")

        if dry_run:
            print("\nDry-run: no rows inserted.")
            return

        # ---- Insert ----
        async with core_engine.begin() as conn:
            training_id = await insert_training(
                conn,
                tenant_id=tenant_id,
                creator_id=creator_id,
                title=title,
                description=topic["description"],
                category=topic["category"],
                thumbnail=thumbnail,
            )
            for mod_idx, m in enumerate(plan, start=1):
                module_id = await insert_module(
                    conn,
                    training_id=training_id,
                    tenant_id=tenant_id,
                    title=m["title"],
                    seq=mod_idx,
                )
                for c in m["chapters"]:
                    if c["type"] == "RICH_TEXT":
                        cdata = build_rich_text_content(rng)
                    elif c["type"] == "VIDEO":
                        cdata = build_video_content(rng)
                    else:
                        cdata = build_quiz_content(rng, num_questions=c["num_questions"])
                    await insert_chapter(
                        conn,
                        training_id=training_id,
                        tenant_id=tenant_id,
                        module_id=module_id,
                        title=c["title"],
                        content_type=c["type"],
                        content_data=cdata,
                        seq=c["seq"],
                    )

        print()
        print(f"✓ Inserted training id: {training_id}")
        print(f"  Open it: http://localhost/manage/courses/{training_id}")
    finally:
        await auth_engine.dispose()
        await core_engine.dispose()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Insert one realistic draft training")
    parser.add_argument("--tenant-id", default="tenant-cp", help="Target tenant id (default: tenant-cp)")
    parser.add_argument("--creator-email", default="cp-creator@lms.com",
                        help="Email of an existing Training Creator user (default: cp-creator@lms.com)")
    parser.add_argument("--auth-db-url", default=None, help="Override AUTH_DB_URL")
    parser.add_argument("--core-db-url", default=None, help="Override CORE_DB_URL")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducible output")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan but don't insert")
    args = parser.parse_args()

    pg_user = os.environ.get("POSTGRES_USER", "lms_user")
    pg_pass = os.environ.get("POSTGRES_PASSWORD", "lms_pass")
    pg_host = os.environ.get("POSTGRES_HOST", "localhost")
    pg_port = os.environ.get("POSTGRES_PORT", "5433")
    default_auth = f"postgresql+asyncpg://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/auth_db"
    default_core = f"postgresql+asyncpg://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/core_db"

    auth_url = _ensure_asyncpg(args.auth_db_url or os.environ.get("AUTH_DB_URL", default_auth))
    core_url = _ensure_asyncpg(args.core_db_url or os.environ.get("CORE_DB_URL", default_core))

    try:
        asyncio.run(seed_one_training(
            core_url=core_url,
            auth_url=auth_url,
            tenant_id=args.tenant_id,
            creator_email=args.creator_email,
            rng_seed=args.seed,
            dry_run=args.dry_run,
        ))
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(130)


if __name__ == "__main__":
    main()
