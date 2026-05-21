from app.schemas.training import Training


def make_training(**kwargs):
    defaults = {
        "id": "t1", "tenant_id": "ten1", "title": "Test", "description": "desc",
        "is_published": False, "is_archived": False, "is_ready": False,
        "structure_type": "flat", "requires_recertification": False,
        "recertification_period_days": None, "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }
    defaults.update(kwargs)
    return Training(**defaults)


def test_lifecycle_status_draft():
    t = make_training()
    assert t.lifecycle_status == "draft"


def test_lifecycle_status_ready():
    t = make_training(is_ready=True)
    assert t.lifecycle_status == "ready"


def test_lifecycle_status_published():
    t = make_training(is_ready=True, is_published=True)
    assert t.lifecycle_status == "published"


def test_lifecycle_status_archived():
    t = make_training(is_ready=True, is_published=True, is_archived=True)
    assert t.lifecycle_status == "archived"


def test_lifecycle_status_archived_without_published():
    # is_archived=True should win even if is_published is False
    t = make_training(is_archived=True)
    assert t.lifecycle_status == "archived"
