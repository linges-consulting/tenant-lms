#!/usr/bin/env python3
"""
Email template preview generator for CPVMTraining Portal.

Renders all Jinja2 email templates with sample data and writes a browseable
preview page to scripts/email_preview/index.html.

Usage:
    pip install jinja2
    python scripts/preview_emails.py
    open scripts/email_preview/index.html
"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    sys.exit("jinja2 is required: pip install jinja2")

ROOT = Path(__file__).resolve().parent.parent
NOTIF_TEMPLATES = ROOT / "app" / "notification_service" / "app" / "worker" / "templates"
AUTH_TEMPLATES = ROOT / "app" / "auth_service" / "app" / "templates"
OUT_DIR = Path(__file__).resolve().parent / "email_preview"

FRONTEND_URL = "https://cpvmtraining.com"
CURRENT_YEAR = datetime.now().year

# ---------------------------------------------------------------------------
# Sample data per template
# ---------------------------------------------------------------------------

SAMPLES: list[dict] = [
    {
        "id": "invite_branded",
        "label": "Registration Invite — with tenant logo & color",
        "dir": NOTIF_TEMPLATES,
        "template": "registration_invite.html",
        "context": {
            "full_name": "Sarah Johnson",
            "registration_url": f"{FRONTEND_URL}/register?token=abc123xyz",
            "token": "abc123xyz",
            "tenant_name": "CellularPoint",
            "primary_color": "#1a73e8",
            "secondary_color": "#1557b0",
            "logo_url": "",  # leave empty to show name fallback by default; set a URL to test logo
            "frontend_url": FRONTEND_URL,
            "current_year": CURRENT_YEAR,
        },
    },
    {
        "id": "invite_no_logo",
        "label": "Registration Invite — no logo, different brand color",
        "dir": NOTIF_TEMPLATES,
        "template": "registration_invite.html",
        "context": {
            "full_name": "Michael Torres",
            "registration_url": f"{FRONTEND_URL}/register?token=def456uvw",
            "token": "def456uvw",
            "tenant_name": "ValueMobile",
            "primary_color": "#d93025",
            "secondary_color": "#b71c1c",
            "logo_url": None,
            "frontend_url": FRONTEND_URL,
            "current_year": CURRENT_YEAR,
        },
    },
    {
        "id": "training_assigned",
        "label": "New Training Assigned",
        "dir": NOTIF_TEMPLATES,
        "template": "new_training_assigned.html",
        "context": {
            "training_title": "Workplace Health & Safety Fundamentals",
            "due_date": "15 June 2026",
            "tenant_name": "CellularPoint",
            "primary_color": "#1a73e8",
            "secondary_color": "#1557b0",
            "frontend_url": FRONTEND_URL,
            "current_year": CURRENT_YEAR,
        },
    },
    {
        "id": "training_assigned_no_due",
        "label": "New Training Assigned — no due date",
        "dir": NOTIF_TEMPLATES,
        "template": "new_training_assigned.html",
        "context": {
            "training_title": "Customer Service Excellence",
            "due_date": None,
            "tenant_name": "ValueMobile",
            "primary_color": "#d93025",
            "secondary_color": "#b71c1c",
            "frontend_url": FRONTEND_URL,
            "current_year": CURRENT_YEAR,
        },
    },
    {
        "id": "due_reminder_7",
        "label": "Due Date Reminder — 7 days",
        "dir": NOTIF_TEMPLATES,
        "template": "due_date_reminder.html",
        "context": {
            "training_title": "Workplace Health & Safety Fundamentals",
            "due_date": "15 June 2026",
            "days_before": 7,
            "tenant_name": "CellularPoint",
            "primary_color": "#1a73e8",
            "secondary_color": "#1557b0",
            "frontend_url": FRONTEND_URL,
            "current_year": CURRENT_YEAR,
        },
    },
    {
        "id": "due_reminder_1",
        "label": "Due Date Reminder — 1 day (tomorrow)",
        "dir": NOTIF_TEMPLATES,
        "template": "due_date_reminder.html",
        "context": {
            "training_title": "Annual Compliance Review",
            "due_date": "Tomorrow",
            "days_before": 1,
            "tenant_name": "CellularPoint",
            "primary_color": "#1a73e8",
            "secondary_color": "#1557b0",
            "frontend_url": FRONTEND_URL,
            "current_year": CURRENT_YEAR,
        },
    },
    {
        "id": "overdue",
        "label": "Overdue Training",
        "dir": NOTIF_TEMPLATES,
        "template": "overdue_reminder.html",
        "context": {
            "training_title": "Fire Safety Procedures",
            "due_date": "1 May 2026",
            "tenant_name": "ValueMobile",
            "primary_color": "#d93025",
            "secondary_color": "#b71c1c",
            "frontend_url": FRONTEND_URL,
            "current_year": CURRENT_YEAR,
        },
    },
    {
        "id": "course_complete",
        "label": "Training Completed",
        "dir": NOTIF_TEMPLATES,
        "template": "course_completion.html",
        "context": {
            "full_name": "Sarah Johnson",
            "training_title": "Workplace Health & Safety Fundamentals",
            "dashboard_url": f"{FRONTEND_URL}/dashboard",
            "tenant_name": "CellularPoint",
            "primary_color": "#1a73e8",
            "secondary_color": "#1557b0",
            "frontend_url": FRONTEND_URL,
            "current_year": CURRENT_YEAR,
        },
    },
    {
        "id": "quiz_lockout",
        "label": "Quiz Lockout (to Manager)",
        "dir": NOTIF_TEMPLATES,
        "template": "quiz_lockout.html",
        "context": {
            "learner_name": "James Wilson",
            "learner_email": "james.wilson@cellularpoint.com",
            "training_title": "Annual Compliance Review",
            "tenant_name": "CellularPoint",
            "primary_color": "#1a73e8",
            "secondary_color": "#1557b0",
            "frontend_url": FRONTEND_URL,
            "current_year": CURRENT_YEAR,
        },
    },
    {
        "id": "password_reset_notif",
        "label": "Password Reset (notification service)",
        "dir": NOTIF_TEMPLATES,
        "template": "password_reset.html",
        "context": {
            "full_name": "Sarah Johnson",
            "reset_url": f"{FRONTEND_URL}/reset-password?token=reset_abc123",
            "expiration_hours": 2,
            "tenant_name": "CellularPoint",
            "primary_color": "#1a73e8",
            "secondary_color": "#1557b0",
            "frontend_url": FRONTEND_URL,
            "current_year": CURRENT_YEAR,
        },
    },
    # Auth service standalone templates
    {
        "id": "auth_invite",
        "label": "Registration Invite — auth service (employee invite)",
        "dir": AUTH_TEMPLATES,
        "template": "registration_invite.html",
        "context": {
            "full_name": "Emily Chen",
            "registration_url": f"{FRONTEND_URL}/register?token=emp789ghi",
            "token": "emp789ghi",
            "tenant_name": "CellularPoint",
            "frontend_url": FRONTEND_URL,
            "support_email": "support@cpvmtraining.com",
            "current_year": CURRENT_YEAR,
        },
    },
    {
        "id": "auth_password_reset",
        "label": "Password Reset — auth service",
        "dir": AUTH_TEMPLATES,
        "template": "password_reset.html",
        "context": {
            "full_name": "Emily Chen",
            "reset_url": f"{FRONTEND_URL}/reset-password?token=reset_emp789",
            "expiration_hours": 2,
            "frontend_url": FRONTEND_URL,
            "support_email": "support@cpvmtraining.com",
            "current_year": CURRENT_YEAR,
        },
    },
    {
        "id": "auth_token_regenerated",
        "label": "New Registration Link — auth service (resend invite)",
        "dir": AUTH_TEMPLATES,
        "template": "token_regenerated.html",
        "context": {
            "full_name": "Emily Chen",
            "registration_url": f"{FRONTEND_URL}/register?token=new_emp789",
            "token": "new_emp789",
            "expires_at": "June 3, 2026 at 09:00 AM UTC",
            "frontend_url": FRONTEND_URL,
            "support_email": "support@cpvmtraining.com",
            "current_year": CURRENT_YEAR,
        },
    },
]


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

def render(sample: dict) -> str:
    env = Environment(loader=FileSystemLoader(str(sample["dir"])))
    tmpl = env.get_template(sample["template"])
    return tmpl.render(**sample["context"])


# ---------------------------------------------------------------------------
# Index page
# ---------------------------------------------------------------------------

INDEX_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CPVMTraining Portal — Email Preview</title>
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; display: flex; height: 100vh; overflow: hidden; background: #f0f4f8; color: #1a202c; }}
    /* Sidebar */
    .sidebar {{
      width: 300px; min-width: 300px; background: #1e3a5f; color: #fff;
      display: flex; flex-direction: column; overflow: hidden;
    }}
    .sidebar-header {{
      padding: 20px 18px 14px;
      border-bottom: 1px solid rgba(255,255,255,0.1);
    }}
    .sidebar-header h1 {{ font-size: 14px; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; color: rgba(255,255,255,0.9); }}
    .sidebar-header p {{ font-size: 12px; color: rgba(255,255,255,0.5); margin-top: 4px; }}
    .sidebar-list {{ overflow-y: auto; flex: 1; padding: 10px 0; }}
    .sidebar-item {{
      display: block; padding: 10px 18px; font-size: 13px; color: rgba(255,255,255,0.75);
      text-decoration: none; cursor: pointer; border-left: 3px solid transparent;
      transition: background 0.15s, color 0.15s;
      line-height: 1.4;
    }}
    .sidebar-item:hover {{ background: rgba(255,255,255,0.07); color: #fff; }}
    .sidebar-item.active {{ background: rgba(255,255,255,0.12); color: #fff; border-left-color: #60a5fa; }}
    .sidebar-count {{ font-size: 11px; color: rgba(255,255,255,0.35); margin-top: 2px; }}
    /* Preview area */
    .preview {{
      flex: 1; display: flex; flex-direction: column; overflow: hidden;
    }}
    .preview-bar {{
      background: #fff; border-bottom: 1px solid #e2e8f0;
      padding: 12px 20px; display: flex; align-items: center; gap: 12px;
      flex-shrink: 0;
    }}
    .preview-label {{ font-size: 14px; font-weight: 600; color: #1e3a5f; }}
    .preview-sub {{ font-size: 12px; color: #9ca3af; }}
    .badge {{ font-size: 11px; background: #eff6ff; color: #1d4ed8; border: 1px solid #bfdbfe; border-radius: 4px; padding: 2px 8px; font-weight: 500; }}
    iframe {{
      flex: 1; border: none; background: #eef1f5;
    }}
  </style>
</head>
<body>
  <div class="sidebar">
    <div class="sidebar-header">
      <h1>Email Previews</h1>
      <p>{count} templates</p>
    </div>
    <div class="sidebar-list">
      {nav_items}
    </div>
  </div>
  <div class="preview">
    <div class="preview-bar">
      <span class="preview-label" id="preview-label">{first_label}</span>
      <span class="preview-sub" id="preview-sub">{first_file}</span>
    </div>
    <iframe id="frame" src="{first_file}"></iframe>
  </div>
  <script>
    const items = document.querySelectorAll('.sidebar-item');
    const frame = document.getElementById('frame');
    const label = document.getElementById('preview-label');
    const sub = document.getElementById('preview-sub');
    items.forEach(item => {{
      item.addEventListener('click', () => {{
        items.forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        frame.src = item.dataset.src;
        label.textContent = item.dataset.label;
        sub.textContent = item.dataset.src;
      }});
    }});
  </script>
</body>
</html>
"""


def build_nav_item(sample: dict, index: int) -> str:
    filename = f"{sample['id']}.html"
    active = " active" if index == 0 else ""
    source = "notification svc" if sample["dir"] == NOTIF_TEMPLATES else "auth svc"
    return (
        f'<a class="sidebar-item{active}" data-src="{filename}" '
        f'data-label="{sample["label"]}" onclick="">'
        f'{sample["label"]}'
        f'<div class="sidebar-count">{source} &rarr; {sample["template"]}</div>'
        f'</a>'
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    OUT_DIR.mkdir(parents=True)

    rendered: list[tuple[dict, str]] = []
    errors: list[str] = []

    for sample in SAMPLES:
        try:
            html = render(sample)
            out_path = OUT_DIR / f"{sample['id']}.html"
            out_path.write_text(html, encoding="utf-8")
            rendered.append((sample, f"{sample['id']}.html"))
            print(f"  OK  {sample['id']}.html  —  {sample['label']}")
        except Exception as exc:
            errors.append(f"  FAIL {sample['id']}: {exc}")
            print(errors[-1])

    nav_items = "\n      ".join(build_nav_item(s, i) for i, (s, _) in enumerate(rendered))
    first_label = rendered[0][0]["label"] if rendered else ""
    first_file = rendered[0][1] if rendered else ""

    index_html = INDEX_HTML.format(
        count=len(rendered),
        nav_items=nav_items,
        first_label=first_label,
        first_file=first_file,
    )
    (OUT_DIR / "index.html").write_text(index_html, encoding="utf-8")

    print(f"\nGenerated {len(rendered)} previews → {OUT_DIR / 'index.html'}")
    if errors:
        print(f"{len(errors)} template(s) failed — see above.")
    else:
        print("All templates rendered successfully.")
    print("\nOpen with:")
    print(f"  open {OUT_DIR / 'index.html'}")


if __name__ == "__main__":
    main()
