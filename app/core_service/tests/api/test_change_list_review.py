"""
Regression tests for items closed in change_list.md (2026-05-20 review).

Covers:
  - Banner upload no longer 500s (eager-loaded collaborators)
  - complete_chapter invalidates training_detail / training_structure caches
    using tenant_id (previously passed training_id, silently missing all keys)
  - Quiz content_data roundtrip for all 5 question types
  - Cross-module sequential gating: cannot complete module 2's chapter until
    module 1's chapter is complete

Auth pattern:
  Override get_current_user AND get_current_tenant_id via app.dependency_overrides.
"""

import io
import uuid
from datetime import datetime, timezone
import pytest
from unittest.mock import patch

from app.main import app
from app.api.deps import get_current_user, get_current_tenant_id
from app.models.training import Training
from app.models.module import Module
from app.models.chapter import Chapter, ContentType
from tests.conftest import override_current_user, make_user_auth


# ---------------------------------------------------------------------------
# Helpers (mirror the conventions used in the surrounding test files)
# ---------------------------------------------------------------------------

def _make_creator(tenant_id: str, user_id: str = None):
    return make_user_auth(
        user_id=user_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Training Creator"],
    )


def _make_learner(tenant_id: str, user_id: str = None):
    return make_user_auth(
        user_id=user_id or str(uuid.uuid4()),
        tenant_id=tenant_id,
        roles=["Employee"],
    )


def _set_user(user):
    app.dependency_overrides[get_current_user] = override_current_user(user)

    async def _tenant_id():
        return user.tenant_id

    app.dependency_overrides[get_current_tenant_id] = _tenant_id


def _clear_overrides():
    app.dependency_overrides.pop(get_current_user, None)
    app.dependency_overrides.pop(get_current_tenant_id, None)


def _make_draft_training(tenant_id: str, created_by_id: str, **kwargs) -> Training:
    defaults = dict(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Draft Training",
        description="desc",
        category="Safety",
        structure_type="flat",
        is_published=False,
        is_active=True,
        is_archived=False,
        is_ready=False,
        requires_certificate=False,
        created_by_id=created_by_id,
        version=1,
    )
    defaults.update(kwargs)
    return Training(**defaults)


def _make_published_training(tenant_id: str, created_by_id: str, **kwargs) -> Training:
    defaults = dict(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        title="Published Training",
        description="desc",
        category="Safety",
        structure_type="modular",
        is_published=True,
        is_active=True,
        is_archived=False,
        is_ready=True,
        requires_certificate=False,
        created_by_id=created_by_id,
        version=1,
    )
    defaults.update(kwargs)
    return Training(**defaults)


def _make_chapter(training_id: str, tenant_id: str, seq: int = 1, module_id: str = None, **kwargs) -> Chapter:
    defaults = dict(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        training_id=training_id,
        title=f"Chapter {seq}",
        content_type=ContentType.RICH_TEXT,
        content_data={"text": f"content {seq}"},
        sequence_order=seq,
        module_id=module_id,
    )
    defaults.update(kwargs)
    return Chapter(**defaults)


def _make_module(training_id: str, tenant_id: str, seq: int = 1, **kwargs) -> Module:
    defaults = dict(
        id=str(uuid.uuid4()),
        tenant_id=tenant_id,
        training_id=training_id,
        title=f"Module {seq}",
        sequence_order=seq,
    )
    defaults.update(kwargs)
    return Module(**defaults)


# ===========================================================================
# TC-BAN — Banner upload (change_list item 1)
# ===========================================================================

@pytest.mark.asyncio
async def test_ban_01_banner_upload_returns_200_with_thumbnail(client, db_session):
    """Banner upload must succeed and return the new thumbnail URL.

    Regression: previously returned 500 because the response was an ORM model
    with a lazy `collaborators` relationship; Pydantic's getattr access during
    serialization triggered MissingGreenlet under async SQLAlchemy.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    training = _make_draft_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    fake_url = f"/storage/banners/{tenant_id}/{training.id}.png"
    files = {"file": ("banner.png", io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32), "image/png")}

    _set_user(creator)
    try:
        with patch("app.utils.storage.save_banner_image", return_value=fake_url):
            resp = await client.post(
                f"/api/v1/trainings/{training.id}/banner",
                files=files,
            )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["thumbnail"] == fake_url
        assert data["id"] == training.id
        # Eager-loaded collaborators must be present (empty list is fine, just not error)
        assert "collaborators" in data
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_ban_02_banner_rejects_invalid_mime_type(client, db_session):
    """Non-image content_type → 400 from server."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    training = _make_draft_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    files = {"file": ("script.txt", io.BytesIO(b"not an image"), "text/plain")}

    _set_user(creator)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/banner",
            files=files,
        )
        assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_ban_03_banner_requires_creator_role(client, db_session):
    """Plain employee may not upload a banner → 403."""
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    training = _make_draft_training(tenant_id, creator_id)
    db_session.add(training)
    await db_session.commit()

    files = {"file": ("banner.png", io.BytesIO(b"\x89PNG"), "image/png")}

    learner = _make_learner(tenant_id)
    _set_user(learner)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/banner",
            files=files,
        )
        assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"
    finally:
        _clear_overrides()


# ===========================================================================
# TC-CCH — Cache invalidation after chapter complete (change_list item 5a)
# ===========================================================================

@pytest.mark.asyncio
async def test_cch_01_complete_chapter_invalidates_caches_with_tenant_id(client, db_session):
    """complete_chapter must invalidate caches keyed by tenant_id, not training_id.

    Regression: invalidate_cache was passing training_id, which silently failed
    to bust any keys (cache_response keys by tenant_id), so learners saw stale
    progress for up to 5 minutes (TTL).
    """
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training = _make_published_training(tenant_id, creator_id)
    chapter = _make_chapter(training.id, tenant_id, seq=1)
    db_session.add(training)
    db_session.add(chapter)
    await db_session.commit()

    training_id = training.id
    chapter_id = chapter.id

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        with patch("app.api.v1.endpoints.trainings.invalidate_cache") as mock_invalidate:
            resp = await client.post(
                f"/api/v1/trainings/{training_id}/chapters/{chapter_id}/complete"
            )
            assert resp.status_code in (200, 201), (
                f"Expected 200/201, got {resp.status_code}: {resp.text}"
            )

        # Collect the (key_prefix, tid_arg) pairs the endpoint asked to invalidate.
        invalidated = {(c.args[0], c.args[1]) for c in mock_invalidate.call_args_list}

        # The endpoint must invalidate training_detail and training_structure
        # using tenant_id (NOT training_id) so the keys actually match.
        assert ("training_detail", tenant_id) in invalidated, (
            f"training_detail must be invalidated with tenant_id; got: {invalidated}"
        )
        assert ("training_structure", tenant_id) in invalidated, (
            f"training_structure must be invalidated with tenant_id; got: {invalidated}"
        )

        # Defensive check — the buggy version passed training_id; ensure that
        # form does NOT appear anywhere in the calls.
        for prefix, tid in invalidated:
            if prefix in ("training_detail", "training_structure"):
                assert tid != training_id, (
                    f"{prefix} invalidation must use tenant_id, not training_id"
                )
    finally:
        _clear_overrides()


# ===========================================================================
# TC-QRT — Quiz roundtrip for all 5 types (change_list item 3)
# ===========================================================================

QUIZ_TYPES = [
    "multiple_choice",
    "multiple_select",
    "true_false",
    "matching",
    "ordering",
]


def _sample_questions():
    """One question of each supported type, with the data shapes the viewer expects."""
    return [
        {
            "id": "q-mc",
            "text": "Which is a primary color?",
            "type": "multiple_choice",
            "options": [
                {"id": "o1", "text": "Red"},
                {"id": "o2", "text": "Green"},
                {"id": "o3", "text": "Orange"},
            ],
            "correct_option_ids": ["o1"],
        },
        {
            "id": "q-ms",
            "text": "Select all even numbers.",
            "type": "multiple_select",
            "options": [
                {"id": "o1", "text": "2"},
                {"id": "o2", "text": "3"},
                {"id": "o3", "text": "4"},
                {"id": "o4", "text": "5"},
            ],
            "correct_option_ids": ["o1", "o3"],
        },
        {
            "id": "q-tf",
            "text": "Water boils at 100°C at sea level.",
            "type": "true_false",
            "options": [
                {"id": "true", "text": "True"},
                {"id": "false", "text": "False"},
            ],
            "correct_option_ids": ["true"],
        },
        {
            "id": "q-mt",
            "text": "Match the capital to its country.",
            "type": "matching",
            "options": [],
            "left_items": [
                {"id": "L1", "text": "France"},
                {"id": "L2", "text": "Japan"},
            ],
            "right_items": [
                {"id": "R1", "text": "Paris"},
                {"id": "R2", "text": "Tokyo"},
            ],
            "correct_option_ids": ["L1::R1", "L2::R2"],
        },
        {
            "id": "q-or",
            "text": "Order the planets by distance from the Sun.",
            "type": "ordering",
            "options": [
                {"id": "p-mercury", "text": "Mercury"},
                {"id": "p-venus", "text": "Venus"},
                {"id": "p-earth", "text": "Earth"},
            ],
            "correct_option_ids": ["p-mercury", "p-venus", "p-earth"],
        },
    ]


@pytest.mark.asyncio
async def test_qrt_01_all_quiz_types_roundtrip_through_structure(client, db_session):
    """Create a chapter with each of the 5 supported question types via POST
    and verify GET /structure returns the questions intact, preserving type
    discriminators and type-specific fields (left/right items, ordering).
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    training = _make_draft_training(tenant_id, creator.id)
    db_session.add(training)
    await db_session.commit()

    training_id = training.id
    questions = _sample_questions()
    chapter_payload = {
        "title": "Mixed Quiz",
        "content_type": "QUIZ",
        "content_data": {
            "questions": questions,
            "passing_score": 80,
            "max_attempts": 0,
        },
        "sequence_order": 1,
    }

    _set_user(creator)
    try:
        create_resp = await client.post(
            f"/api/v1/trainings/{training_id}/chapters",
            json=chapter_payload,
        )
        assert create_resp.status_code in (200, 201), (
            f"Chapter create failed: {create_resp.status_code} {create_resp.text}"
        )

        struct_resp = await client.get(f"/api/v1/trainings/{training_id}/structure")
        assert struct_resp.status_code == 200, struct_resp.text

        structure = struct_resp.json()
        all_chapters = list(structure.get("orphan_chapters") or [])
        for mod in structure.get("modules") or []:
            all_chapters.extend(mod.get("chapters") or [])

        quiz_chapter = next((c for c in all_chapters if c["content_type"] == "QUIZ"), None)
        assert quiz_chapter is not None, "Expected the quiz chapter in structure"

        stored = quiz_chapter["content_data"]["questions"]
        stored_by_type = {q["type"]: q for q in stored}
        for t in QUIZ_TYPES:
            assert t in stored_by_type, f"Missing question type '{t}' in roundtrip"

        mc = stored_by_type["multiple_choice"]
        assert mc["correct_option_ids"] == ["o1"]

        ms = stored_by_type["multiple_select"]
        assert set(ms["correct_option_ids"]) == {"o1", "o3"}

        tf = stored_by_type["true_false"]
        assert tf["correct_option_ids"] == ["true"]
        assert {o["id"] for o in tf["options"]} == {"true", "false"}

        mt = stored_by_type["matching"]
        assert mt["left_items"][0]["text"] == "France"
        assert mt["right_items"][1]["text"] == "Tokyo"
        assert "L1::R1" in mt["correct_option_ids"]
        assert "L2::R2" in mt["correct_option_ids"]

        order = stored_by_type["ordering"]
        # Ordering preserves the option order as the correct answer
        assert order["correct_option_ids"] == ["p-mercury", "p-venus", "p-earth"]
    finally:
        _clear_overrides()


# ===========================================================================
# TC-CMU — Cross-module progressive unlock (change_list item 5c)
# ===========================================================================

# ===========================================================================
# TC-PDF — PDF chapter upload (2026-05-26)
# ===========================================================================

_PDF_MINIMAL_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\n"
    b"xref\n0 3\n0000000000 65535 f\n0000000010 00000 n\n0000000056 00000 n\ntrailer<</Size 3/Root 1 0 R>>\nstartxref\n98\n%%EOF\n"
)


@pytest.mark.asyncio
async def test_pdf_01_upload_succeeds_and_sets_content_url(client, db_session):
    """Uploading a valid PDF to a PDF chapter persists a URL and filename
    on content_data, and returns 200. Regression for the "PDF chapter
    type added 2026-05-26" feature.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    training = _make_draft_training(tenant_id, creator.id)
    chapter = _make_chapter(
        training.id, tenant_id, seq=1, title="Reference doc",
        content_type=ContentType.PDF, content_data={"description": "Read this."},
    )
    db_session.add(training)
    db_session.add(chapter)
    await db_session.commit()

    training_id = training.id
    chapter_id = chapter.id
    fake_url = f"/storage/pdfs/{tenant_id}/{training_id}/{chapter_id}.pdf"
    files = {"file": ("doc.pdf", io.BytesIO(_PDF_MINIMAL_BYTES), "application/pdf")}

    _set_user(creator)
    try:
        with patch("app.utils.storage.save_pdf_file", return_value=fake_url):
            resp = await client.post(
                f"/api/v1/trainings/{training_id}/chapters/{chapter_id}/upload",
                files=files,
            )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data["content_data"]["url"] == fake_url
        assert data["content_data"]["original_filename"] == "doc.pdf"
        # Description set at chapter creation is preserved
        assert data["content_data"]["description"] == "Read this."
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_pdf_02_rejects_wrong_mime_type(client, db_session):
    """A PDF chapter must reject non-PDF MIME types with a 400."""
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    training = _make_draft_training(tenant_id, creator.id)
    chapter = _make_chapter(
        training.id, tenant_id, seq=1, title="Doc",
        content_type=ContentType.PDF, content_data={},
    )
    db_session.add(training)
    db_session.add(chapter)
    await db_session.commit()

    files = {"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00"), "application/x-msdownload")}

    _set_user(creator)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/upload",
            files=files,
        )
        assert resp.status_code == 400, resp.text
        assert "PDF" in resp.json()["detail"]
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_pdf_03_video_chapter_rejects_pdf_upload(client, db_session):
    """The upload endpoint only accepts SCORM and PDF — a VIDEO chapter
    that someone tries to drop a PDF into should get 400 with a clear
    message, not 200.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    training = _make_draft_training(tenant_id, creator.id)
    chapter = _make_chapter(
        training.id, tenant_id, seq=1, title="Vid",
        content_type=ContentType.VIDEO, content_data={"url": "https://example.com/v.mp4"},
    )
    db_session.add(training)
    db_session.add(chapter)
    await db_session.commit()

    files = {"file": ("doc.pdf", io.BytesIO(_PDF_MINIMAL_BYTES), "application/pdf")}

    _set_user(creator)
    try:
        resp = await client.post(
            f"/api/v1/trainings/{training.id}/chapters/{chapter.id}/upload",
            files=files,
        )
        assert resp.status_code == 400, resp.text
        assert "SCORM and PDF" in resp.json()["detail"]
    finally:
        _clear_overrides()


# ===========================================================================
# TC-BNR — Auto-assigned banner preset on create (2026-05-21)
# ===========================================================================

@pytest.mark.asyncio
async def test_bnr_01_create_training_auto_assigns_random_preset(client, db_session):
    """Creating a training without a `thumbnail` must result in one of the
    four preset banner gradients being assigned server-side. The picker UI
    was removed from the editor; every training gets a visual identity at
    creation time.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    _set_user(creator)
    try:
        resp = await client.post(
            "/api/v1/trainings",
            json={
                "title": "Auto Banner Training",
                "description": "desc",
                "category": "Safety",
                "structure_type": "flat",
                "requires_certificate": False,
            },
        )
        assert resp.status_code in (200, 201), resp.text
        thumbnail = resp.json().get("thumbnail")
        assert thumbnail is not None, "Expected an auto-assigned preset thumbnail, got None"
        assert thumbnail.startswith("preset:"), f"Expected a preset:* string, got {thumbnail!r}"
        assert thumbnail.split(":", 1)[1] in {"ocean", "sunset", "forest", "ember"}, (
            f"Unexpected preset value: {thumbnail!r}"
        )
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_bnr_02_explicit_thumbnail_overrides_auto_assignment(client, db_session):
    """If the caller does send a thumbnail (e.g. an existing uploaded URL),
    the server must respect it rather than overwriting with a preset.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)
    _set_user(creator)
    try:
        custom_url = "/storage/banners/tenant-x/some-id.png"
        resp = await client.post(
            "/api/v1/trainings",
            json={
                "title": "Custom Banner Training",
                "description": "desc",
                "category": "Safety",
                "structure_type": "flat",
                "requires_certificate": False,
                "thumbnail": custom_url,
            },
        )
        assert resp.status_code in (200, 201), resp.text
        assert resp.json().get("thumbnail") == custom_url
    finally:
        _clear_overrides()


# ===========================================================================
# TC-SEQ — Chapter sequence_order is training-wide unique (2026-05-20 finding)
# ===========================================================================

@pytest.mark.asyncio
async def test_seq_01_create_chapter_assigns_training_wide_sequence(client, db_session):
    """New chapters across two modules must get DISTINCT, training-wide
    sequence_order values. Regression for the 2026-05-20 browser-smoke
    finding: the frontend used to compute seq per-module/per-orphan, so
    two chapters in different modules could share seq=1 and the gating
    check in complete_chapter would pick non-deterministically.
    """
    tenant_id = str(uuid.uuid4())
    creator = _make_creator(tenant_id)

    training = _make_draft_training(tenant_id, creator.id)
    module1 = _make_module(training.id, tenant_id, seq=1)
    module2 = _make_module(training.id, tenant_id, seq=2)
    db_session.add(training)
    db_session.add(module1)
    db_session.add(module2)
    await db_session.commit()

    training_id = training.id
    module1_id = module1.id
    module2_id = module2.id

    _set_user(creator)
    try:
        # Create two chapters in Module 1
        m1_a = await client.post(
            f"/api/v1/trainings/{training_id}/chapters",
            json={"title": "M1 A", "content_type": "RICH_TEXT", "content_data": {}, "sequence_order": 1, "module_id": module1_id},
        )
        m1_b = await client.post(
            f"/api/v1/trainings/{training_id}/chapters",
            json={"title": "M1 B", "content_type": "RICH_TEXT", "content_data": {}, "sequence_order": 2, "module_id": module1_id},
        )
        # Now create one in Module 2 — the client would have re-used seq=1, but
        # the server must override it to be training-wide unique (= 3).
        m2_a = await client.post(
            f"/api/v1/trainings/{training_id}/chapters",
            json={"title": "M2 A", "content_type": "RICH_TEXT", "content_data": {}, "sequence_order": 1, "module_id": module2_id},
        )

        assert m1_a.status_code in (200, 201)
        assert m1_b.status_code in (200, 201)
        assert m2_a.status_code in (200, 201)

        seqs = sorted([m1_a.json()["sequence_order"], m1_b.json()["sequence_order"], m2_a.json()["sequence_order"]])
        assert seqs == [1, 2, 3], (
            f"Expected training-wide [1,2,3] sequence — got {seqs}. Two chapters share a seq value."
        )
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_seq_02_total_chapters_in_detail_matches_structure(client, db_session):
    """GET /trainings/{id} and GET /trainings/{id}/structure must agree on
    chapter count. Regression for the 2026-05-20 finding: the detail count
    didn't filter deleted_at, so soft-deleted chapters skewed it higher.
    """
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner = _make_learner(tenant_id, str(uuid.uuid4()))

    training = _make_published_training(tenant_id, creator_id)
    module1 = _make_module(training.id, tenant_id, seq=1)
    db_session.add(training)
    db_session.add(module1)
    await db_session.flush()

    live1 = _make_chapter(training.id, tenant_id, seq=1, module_id=module1.id, title="Live 1")
    live2 = _make_chapter(training.id, tenant_id, seq=2, module_id=module1.id, title="Live 2")
    # A soft-deleted chapter must NOT be counted by either endpoint.
    deleted_ch = _make_chapter(
        training.id, tenant_id, seq=99, module_id=module1.id, title="Removed",
        deleted_at=datetime.now(timezone.utc),
    )
    db_session.add(live1)
    db_session.add(live2)
    db_session.add(deleted_ch)
    await db_session.commit()

    training_id = training.id

    _set_user(learner)
    try:
        detail = await client.get(f"/api/v1/trainings/{training_id}")
        assert detail.status_code == 200, detail.text
        detail_total = detail.json().get("total_chapters")

        struct = await client.get(f"/api/v1/trainings/{training_id}/structure")
        assert struct.status_code == 200, struct.text
        struct_body = struct.json()
        struct_chapter_count = sum(len(m.get("chapters") or []) for m in struct_body.get("modules") or [])
        struct_chapter_count += len(struct_body.get("orphan_chapters") or [])

        assert detail_total == struct_chapter_count == 2, (
            f"Detail says {detail_total}, structure has {struct_chapter_count}. "
            f"Both must equal 2 (the live chapters; the soft-deleted one is excluded)."
        )
        assert struct_body.get("total_chapters") == 2
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_seq_03_complete_chapter_deterministic_when_seq_unique(client, db_session):
    """With training-wide unique seq, the previous-chapter lookup is
    deterministic — completing Module 1 unlocks Module 2 with no false 403s.
    """
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training = _make_published_training(tenant_id, creator_id)
    module1 = _make_module(training.id, tenant_id, seq=1)
    module2 = _make_module(training.id, tenant_id, seq=2)
    db_session.add(training)
    db_session.add(module1)
    db_session.add(module2)
    await db_session.flush()

    # The new contract: seq is training-wide unique.
    m1_chapter = _make_chapter(training.id, tenant_id, seq=1, module_id=module1.id, title="M1 ch")
    m2_chapter = _make_chapter(training.id, tenant_id, seq=2, module_id=module2.id, title="M2 ch")
    db_session.add(m1_chapter)
    db_session.add(m2_chapter)
    await db_session.commit()

    training_id = training.id
    m1_chapter_id = m1_chapter.id
    m2_chapter_id = m2_chapter.id

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        first = await client.post(
            f"/api/v1/trainings/{training_id}/chapters/{m1_chapter_id}/complete"
        )
        assert first.status_code in (200, 201), first.text

        # No flakiness — module 2 chapter must complete cleanly the first try.
        second = await client.post(
            f"/api/v1/trainings/{training_id}/chapters/{m2_chapter_id}/complete"
        )
        assert second.status_code in (200, 201), (
            f"Module 2 chapter should complete deterministically once Module 1 is done; "
            f"got {second.status_code}: {second.text}"
        )
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_cmu_01_cannot_complete_module2_chapter_before_module1(client, db_session):
    """A learner cannot complete a chapter in module 2 if module 1's chapter
    is not yet completed. Sequential gating uses chapter.sequence_order, which
    is global across modules — so this also enforces module-level ordering.
    """
    tenant_id = str(uuid.uuid4())
    creator_id = str(uuid.uuid4())
    learner_id = str(uuid.uuid4())

    training = _make_published_training(tenant_id, creator_id)
    module1 = _make_module(training.id, tenant_id, seq=1)
    module2 = _make_module(training.id, tenant_id, seq=2)
    db_session.add(training)
    db_session.add(module1)
    db_session.add(module2)
    await db_session.flush()

    m1_chapter = _make_chapter(training.id, tenant_id, seq=1, module_id=module1.id, title="M1 Ch")
    m2_chapter = _make_chapter(training.id, tenant_id, seq=2, module_id=module2.id, title="M2 Ch")
    db_session.add(m1_chapter)
    db_session.add(m2_chapter)
    await db_session.commit()

    training_id = training.id
    m1_chapter_id = m1_chapter.id
    m2_chapter_id = m2_chapter.id

    learner = _make_learner(tenant_id, learner_id)
    _set_user(learner)
    try:
        # Attempting to complete module 2's chapter first must be rejected
        blocked = await client.post(
            f"/api/v1/trainings/{training_id}/chapters/{m2_chapter_id}/complete"
        )
        assert blocked.status_code in (400, 403), (
            f"Expected 400/403 — module 2 chapter is locked until module 1's chapter "
            f"is complete; got {blocked.status_code}: {blocked.text}"
        )

        # Completing module 1's chapter first should succeed
        first = await client.post(
            f"/api/v1/trainings/{training_id}/chapters/{m1_chapter_id}/complete"
        )
        assert first.status_code in (200, 201), (
            f"Expected 200/201 for module 1 first chapter, got {first.status_code}: {first.text}"
        )

        # Now module 2's chapter unlocks
        second = await client.post(
            f"/api/v1/trainings/{training_id}/chapters/{m2_chapter_id}/complete"
        )
        assert second.status_code in (200, 201), (
            f"Expected 200/201 for module 2 chapter after module 1 complete, "
            f"got {second.status_code}: {second.text}"
        )
    finally:
        _clear_overrides()
