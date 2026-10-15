# =============================================================================
# app.py  -  Linrco Quality Assurance ERP  (SINGLE FILE - copy once, replace app.py)
#
# Stack: Python + Streamlit + SQLAlchemy.  Everything lives in this one file.
#
# ---- requirements.txt (create separately, pin as needed) -------------------
#   streamlit>=1.40
#   SQLAlchemy>=2.0,<2.1
#   pandas>=2.0
#   openpyxl>=3.1
#   psycopg2-binary>=2.9      # only needed for PostgreSQL
#   pyotp>=2.9                # two-factor authentication
#   qrcode[pil]>=7.4          # QR code for 2FA enrolment
#   Pillow>=10.0
#   requests>=2.31            # Looker Studio short-link resolution (optional)
#   pytest>=8.0               # tests:  pytest app.py
#
# ---- .gitignore (create separately) -----------------------------------------
#   data/
#   *.db
#   .streamlit/secrets.toml
#   __pycache__/
#
# ---- Streamlit secrets (App settings -> Secrets) ----------------------------
#   DATABASE_URL = "postgresql://user:password@host:5432/dbname"   # REQUIRED for real use
#   BOOTSTRAP_ADMIN_EMAIL = "admin@yourcompany.com"                # optional, first run only
#   BOOTSTRAP_ADMIN_PASSWORD = "a-strong-password-123"            # optional, first run only
#   MAX_UPLOAD_MB = 10
#   SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / SMTP_FROM  # optional e-mail alerts
#
# ---- HONEST LIMITATIONS -------------------------------------------------------
# * Without DATABASE_URL the app falls back to a local SQLite file (./data).
#   On Streamlit Community Cloud that disk is EPHEMERAL: data is lost on reboot or
#   redeploy and is not shared safely. Use a hosted PostgreSQL for production.
# * Uploaded files are stored as bytes INSIDE the database (never in GitHub), so
#   they persist exactly as well as your database does. Large files bloat the DB.
# * Trusted-device cookies for 2FA are not implemented (Streamlit has no secure
#   cookie API); TOTP is requested at every login for users who enabled it.
# * PDF export is not implemented; CSV and Excel exports are.
# * E-mail notifications are sent only if SMTP secrets are configured.
# * Sessions live in st.session_state (per browser tab); business data never does.
# * This is "Odoo-inspired" in navigation and workflow, not an Odoo equivalent.
# =============================================================================
import ast
import base64
import hashlib
import hmac
import html
import io
import json
import math
import operator
import os
import re
import smtplib
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from typing import Callable, Optional

import pandas as pd
import streamlit as st
from sqlalchemy import (Boolean, Date, DateTime, Float, ForeignKey, Integer,
                        LargeBinary, String, Text, UniqueConstraint, create_engine,
                        event, func, or_, select, text)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (DeclarativeBase, Mapped, Session, mapped_column, relationship)

try:
    import pyotp
except Exception:  # noqa: BLE001
    pyotp = None
try:
    import qrcode
except Exception:  # noqa: BLE001
    qrcode = None
try:
    import requests
except Exception:  # noqa: BLE001
    requests = None

st.set_page_config(page_title="Linrco QA ERP", page_icon="📊", layout="wide")

esc = html.escape
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


# =============================================================================
# 1. CONFIGURATION
# =============================================================================
def secret(name, default=""):
    try:
        if name in st.secrets:
            return st.secrets[name]
    except Exception:  # noqa: BLE001
        pass
    return os.environ.get(name, default)


def db_url():
    url = str(secret("DATABASE_URL", "") or "").strip()
    if not url:
        os.makedirs(DATA_DIR, exist_ok=True)
        return "sqlite:///" + os.path.join(DATA_DIR, "qa_erp.db").replace("\\", "/")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


MAX_UPLOAD = int(secret("MAX_UPLOAD_MB", 10) or 10) * 1024 * 1024
ALLOWED_EXT = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".txt", ".png", ".jpg",
               ".jpeg", ".pptx", ".msg", ".vsdx"}
SIGNATURES = {".pdf": [b"%PDF"], ".png": [b"\x89PNG"], ".jpg": [b"\xff\xd8\xff"],
              ".jpeg": [b"\xff\xd8\xff"], ".docx": [b"PK\x03\x04"],
              ".xlsx": [b"PK\x03\x04"], ".pptx": [b"PK\x03\x04"]}
SESSION_MINUTES = 60
MAX_FAILED = 5
LOCK_MINUTES = 15
MIN_PW = 10
PAGE_SIZE = 15
DEFAULT_COMPANY_LOGO = "https://raw.githubusercontent.com/ahmedgouda2727/QA-Dashboard-APP/main/Linrco-Egypt.PNG"
DEFAULT_QA_LOGO = "https://raw.githubusercontent.com/ahmedgouda2727/QA-Dashboard-APP/main/QA.png"
DEFAULT_NEWS_IMAGE = "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=800&auto=format&fit=crop&q=60"

DEFAULT_LISTS = {
    "review_types": ["process_adherence", "documentation", "compliance", "follow_up"],
    "doc_categories": ["SOP", "Policy", "Work Instruction", "Regulation", "Guideline", "Manual", "Form"],
    "classifications": ["public", "internal", "confidential"],
    "root_causes": ["Training gap", "Unclear procedure", "System limitation", "Human error",
                    "Missing documentation", "Resource constraint"],
    "job_titles": ["QA Manager", "QA Reviewer", "Department Manager", "Process Owner", "Specialist"],
}


# =============================================================================
# 2. LABELS / I18N
# =============================================================================
def lang():
    return st.session_state.get("lang", "ar")


def L(ar, en):
    return ar if lang() == "ar" else en


LABELS = {
    # review
    "draft": ("مسودة", "Draft"), "scheduled": ("مجدولة", "Scheduled"),
    "in_progress": ("قيد التنفيذ", "In Progress"), "under_review": ("قيد المراجعة", "Under Review"),
    "passed": ("ناجحة", "Passed"), "failed": ("راسبة", "Failed"),
    "requires_modification": ("تتطلب تعديل", "Requires Modification"),
    "requires_process_validation": ("تتطلب التحقق من العملية", "Requires Process Validation"),
    "awaiting_approval": ("بانتظار الاعتماد", "Awaiting Approval"),
    "closed": ("مغلقة", "Closed"), "cancelled": ("ملغاة", "Cancelled"),
    # documents
    "compliant": ("مطابق", "Compliant"), "pending_review": ("بانتظار المراجعة", "Pending Review"),
    "pending_approval": ("بانتظار الموافقة", "Pending Approval"), "expired": ("منتهي", "Expired"),
    "obsolete": ("ملغى", "Obsolete"),
    # capa
    "open": ("مفتوح", "Open"), "assigned": ("مُسند", "Assigned"),
    "awaiting_evidence": ("بانتظار الدليل", "Awaiting Evidence"),
    "awaiting_qa_verification": ("بانتظار تحقق الجودة", "Awaiting QA Verification"),
    "effectiveness_review": ("مراجعة الفعالية", "Effectiveness Review"),
    "rejected": ("مرفوض", "Rejected"), "overdue": ("متأخر", "Overdue"),
    # tasks
    "todo": ("للتنفيذ", "To Do"), "blocked": ("معطل", "Blocked"), "done": ("منجز", "Done"),
    # validation decisions
    "pending": ("معلّق", "Pending"), "validated": ("تم التحقق", "Validated"),
    "validated_with_deviations": ("تحقق مع انحرافات", "Validated w/ Deviations"),
    "not_validated": ("لم يتم التحقق", "Not Validated"),
    # priorities / risk
    "low": ("منخفض", "Low"), "medium": ("متوسط", "Medium"), "high": ("عالٍ", "High"),
    "critical": ("حرج", "Critical"),
    # kpi
    "on_target": ("محقق", "On Target"), "warning": ("تحذير", "Warning"),
    "off_target": ("غير محقق", "Off Target"),
    "monthly": ("شهري", "Monthly"), "quarterly": ("ربع سنوي", "Quarterly"), "annual": ("سنوي", "Annual"),
    # question types
    "yes_no": ("نعم/لا", "Yes/No"), "pass_fail": ("نجاح/رسوب", "Pass/Fail"),
    "multiple_choice": ("اختيار متعدد", "Multiple Choice"),
    "numeric_score": ("درجة رقمية", "Numeric Score"), "text": ("نص", "Text"),
    "date": ("تاريخ", "Date"), "evidence_required": ("دليل مطلوب", "Evidence Required"),
    "effective": ("فعّال", "Effective"), "ineffective": ("غير فعّال", "Ineffective"),
    # roles
    "system_admin": ("مدير النظام", "System Administrator"), "qa_manager": ("مدير الجودة", "QA Manager"),
    "qa_reviewer": ("مراجع جودة", "QA Reviewer"), "department_manager": ("مدير قسم", "Department Manager"),
    "process_owner": ("مالك عملية", "Process Owner"), "viewer": ("قراءة فقط", "Read-Only Viewer"),
    "public": ("عام", "Public"), "internal": ("داخلي", "Internal"), "confidential": ("سري", "Confidential"),
}


def lab(code):
    if code in (None, ""):
        return "—"
    v = LABELS.get(code)
    return (v[0] if lang() == "ar" else v[1]) if v else str(code)


GOOD = {"passed", "compliant", "closed", "done", "validated", "on_target", "effective"}
BAD = {"failed", "rejected", "expired", "overdue", "critical", "not_validated", "off_target",
       "blocked", "ineffective", "high"}
NEUTRAL = {"draft", "cancelled", "obsolete", "scheduled", "todo", "low", "pending", "open"}


def badge(code):
    cls = "b-good" if code in GOOD else "b-bad" if code in BAD else "b-neutral" if code in NEUTRAL else "b-warn"
    return f'<span class="badge {cls}">{esc(lab(code))}</span>'


# =============================================================================
# 3. DATABASE MODELS
# =============================================================================
def now():
    return datetime.utcnow()


class Base(DeclarativeBase):
    pass


class Std:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    value: Mapped[str] = mapped_column(Text, default="")


class Sequence(Base):
    __tablename__ = "sequences"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)
    value: Mapped[int] = mapped_column(Integer, default=0)


class User(Std, Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(200))
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(30), default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    totp_secret: Mapped[Optional[str]] = mapped_column(String(64))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    employee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"))


class UserDept(Base):
    __tablename__ = "user_departments"
    __table_args__ = (UniqueConstraint("user_id", "department_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id", ondelete="CASCADE"))


class Department(Std, Base):
    __tablename__ = "departments"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    name_ar: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Employee(Std, Base):
    __tablename__ = "employees"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_no: Mapped[str] = mapped_column(String(50), unique=True)
    full_name: Mapped[str] = mapped_column(String(200), index=True)
    email: Mapped[str] = mapped_column(String(255), default="")
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), index=True)
    job_title: Mapped[str] = mapped_column(String(200), default="")
    is_reviewer: Mapped[bool] = mapped_column(Boolean, default=False)
    is_owner: Mapped[bool] = mapped_column(Boolean, default=False)
    is_manager: Mapped[bool] = mapped_column(Boolean, default=False)
    responsibilities: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Process(Std, Base):
    __tablename__ = "processes"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(250), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"))
    responsible_role: Mapped[str] = mapped_column(String(200), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    sla_hours: Mapped[Optional[float]] = mapped_column(Float)
    validation_interval_days: Mapped[Optional[int]] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Checklist(Std, Base):
    __tablename__ = "checklists"
    __table_args__ = (UniqueConstraint("code", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40))
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text, default="")
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"))
    process_id: Mapped[Optional[int]] = mapped_column(ForeignKey("processes.id"))
    pass_threshold: Mapped[float] = mapped_column(Float, default=80.0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    items: Mapped[list["ChecklistItem"]] = relationship(
        cascade="all, delete-orphan", order_by="ChecklistItem.sequence")


class ChecklistItem(Base):
    __tablename__ = "checklist_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    checklist_id: Mapped[int] = mapped_column(ForeignKey("checklists.id", ondelete="CASCADE"), index=True)
    sequence: Mapped[int] = mapped_column(Integer, default=10)
    question: Mapped[str] = mapped_column(Text)
    criteria: Mapped[str] = mapped_column(Text, default="")
    question_type: Mapped[str] = mapped_column(String(30), default="yes_no")
    choices: Mapped[str] = mapped_column(Text, default="")
    is_mandatory: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence_required: Mapped[bool] = mapped_column(Boolean, default=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    max_score: Mapped[float] = mapped_column(Float, default=1.0)
    is_scored: Mapped[bool] = mapped_column(Boolean, default=True)


class Document(Std, Base):
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(primary_key=True)
    doc_code: Mapped[str] = mapped_column(String(60), unique=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    category: Mapped[str] = mapped_column(String(60), default="SOP")
    classification: Mapped[str] = mapped_column(String(40), default="internal")
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    process_id: Mapped[Optional[int]] = mapped_column(ForeignKey("processes.id"))
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"))
    process_owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="pending_review", index=True)
    current_version_no: Mapped[str] = mapped_column(String(20), default="1.0")
    effective_date: Mapped[Optional[date]] = mapped_column(Date)
    review_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    expiration_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    review_interval_days: Mapped[Optional[int]] = mapped_column(Integer)
    external_link: Mapped[str] = mapped_column(String(500), default="")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class DocVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_no"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[str] = mapped_column(String(20))
    change_description: Mapped[str] = mapped_column(Text, default="")
    author_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    approved_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    attachment_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Review(Std, Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    process_id: Mapped[Optional[int]] = mapped_column(ForeignKey("processes.id"), index=True)
    responsible_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"))
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), index=True)
    review_type: Mapped[str] = mapped_column(String(60), default="process_adherence")
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(40), default="draft", index=True)
    review_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    checklist_id: Mapped[Optional[int]] = mapped_column(ForeignKey("checklists.id"))
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("documents.id"))
    comments: Mapped[str] = mapped_column(Text, default="")
    observations: Mapped[str] = mapped_column(Text, default="")
    compliance_score: Mapped[Optional[float]] = mapped_column(Float)
    final_outcome: Mapped[str] = mapped_column(String(60), default="")
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer)
    updated_by_id: Mapped[Optional[int]] = mapped_column(Integer)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class ReviewAnswer(Base):
    __tablename__ = "review_answers"
    __table_args__ = (UniqueConstraint("review_id", "item_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("checklist_items.id"))
    answer: Mapped[Optional[str]] = mapped_column(Text)
    comment: Mapped[str] = mapped_column(Text, default="")
    fraction: Mapped[Optional[float]] = mapped_column(Float)
    answered_by_id: Mapped[Optional[int]] = mapped_column(Integer)
    answered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class ProcessValidation(Std, Base):
    __tablename__ = "process_validations"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True)
    process_id: Mapped[int] = mapped_column(ForeignKey("processes.id"), index=True)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"))
    reviewer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"))
    responsible_role: Mapped[str] = mapped_column(String(200), default="")
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("documents.id"))
    checklist_id: Mapped[Optional[int]] = mapped_column(ForeignKey("checklists.id"))
    criteria: Mapped[str] = mapped_column(Text, default="")
    expected_result: Mapped[str] = mapped_column(Text, default="")
    actual_result: Mapped[str] = mapped_column(Text, default="")
    deviations: Mapped[str] = mapped_column(Text, default="")
    reviewer_comments: Mapped[str] = mapped_column(Text, default="")
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    score: Mapped[Optional[float]] = mapped_column(Float)
    validation_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    next_validation_date: Mapped[Optional[date]] = mapped_column(Date)
    decision: Mapped[str] = mapped_column(String(40), default="pending")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Capa(Std, Base):
    __tablename__ = "nonconformities"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    review_id: Mapped[Optional[int]] = mapped_column(ForeignKey("reviews.id"), index=True)
    process_id: Mapped[Optional[int]] = mapped_column(ForeignKey("processes.id"))
    validation_id: Mapped[Optional[int]] = mapped_column(ForeignKey("process_validations.id"))
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.id"), index=True)
    root_cause_category: Mapped[str] = mapped_column(String(150), default="")
    root_cause: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    impact: Mapped[str] = mapped_column(Text, default="")
    risk_assessment: Mapped[str] = mapped_column(Text, default="")
    immediate_correction: Mapped[str] = mapped_column(Text, default="")
    corrective_action: Mapped[str] = mapped_column(Text, default="")
    preventive_action: Mapped[str] = mapped_column(Text, default="")
    action_owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), index=True)
    target_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    implementation_evidence: Mapped[str] = mapped_column(Text, default="")
    verification_notes: Mapped[str] = mapped_column(Text, default="")
    verified_by_id: Mapped[Optional[int]] = mapped_column(Integer)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    effectiveness_result: Mapped[str] = mapped_column(String(30), default="")
    effectiveness_notes: Mapped[str] = mapped_column(Text, default="")
    qa_approved_by_id: Mapped[Optional[int]] = mapped_column(Integer)
    qa_approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    closure_date: Mapped[Optional[date]] = mapped_column(Date)
    rejection_reason: Mapped[str] = mapped_column(Text, default="")
    escalation_level: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="open", index=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class Task(Std, Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    review_id: Mapped[Optional[int]] = mapped_column(ForeignKey("reviews.id"))
    document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("documents.id"))
    capa_id: Mapped[Optional[int]] = mapped_column(ForeignKey("nonconformities.id"))
    assignee_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"), index=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    status: Mapped[str] = mapped_column(String(30), default="todo", index=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date)
    due_date: Mapped[Optional[date]] = mapped_column(Date, index=True)
    reminder_date: Mapped[Optional[date]] = mapped_column(Date)
    percent_complete: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_by_id: Mapped[Optional[int]] = mapped_column(Integer)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class KPI(Std, Base):
    __tablename__ = "kpis"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(250))
    description: Mapped[str] = mapped_column(Text, default="")
    department_id: Mapped[Optional[int]] = mapped_column(ForeignKey("departments.id"), index=True)
    process_id: Mapped[Optional[int]] = mapped_column(ForeignKey("processes.id"))
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("employees.id"))
    unit: Mapped[str] = mapped_column(String(30), default="%")
    target: Mapped[float] = mapped_column(Float)
    higher_is_better: Mapped[bool] = mapped_column(Boolean, default=True)
    warning_threshold: Mapped[float] = mapped_column(Float, default=0.9)
    frequency: Mapped[str] = mapped_column(String(20), default="monthly")
    calculation_method: Mapped[str] = mapped_column(Text, default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)


class KPIValue(Base):
    __tablename__ = "kpi_values"
    __table_args__ = (UniqueConstraint("kpi_id", "period_start"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    kpi_id: Mapped[int] = mapped_column(ForeignKey("kpis.id", ondelete="CASCADE"), index=True)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    actual: Mapped[float] = mapped_column(Float)
    notes: Mapped[str] = mapped_column(Text, default="")
    recorded_by_id: Mapped[Optional[int]] = mapped_column(Integer)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class StatusHistory(Base):
    __tablename__ = "status_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    from_status: Mapped[str] = mapped_column(String(40), default="")
    to_status: Mapped[str] = mapped_column(String(40), default="")
    note: Mapped[str] = mapped_column(Text, default="")
    user_id: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Attachment(Base):
    __tablename__ = "attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    original_name: Mapped[str] = mapped_column(String(300))
    stored_name: Mapped[str] = mapped_column(String(80), unique=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    uploaded_by_id: Mapped[Optional[int]] = mapped_column(Integer)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, index=True)
    user_email: Mapped[str] = mapped_column(String(255), default="")
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    record_ref: Mapped[str] = mapped_column(String(120), default="")
    old_values: Mapped[str] = mapped_column(Text, default="")
    new_values: Mapped[str] = mapped_column(Text, default="")
    workflow_event: Mapped[str] = mapped_column(String(120), default="")


@event.listens_for(AuditLog, "before_update")
def _audit_no_update(*_a):
    raise PermissionError("Audit entries are append-only.")


@event.listens_for(AuditLog, "before_delete")
def _audit_no_delete(*_a):
    raise PermissionError("Audit entries are append-only.")


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("dedupe_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    entity_type: Mapped[str] = mapped_column(String(40), default="")
    entity_id: Mapped[Optional[int]] = mapped_column(Integer)
    dedupe_key: Mapped[str] = mapped_column(String(220))
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class PortalProject(Std, Base):
    """Looker Studio dashboards / projects preserved from the original portal."""
    __tablename__ = "portal_projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(String(600), default="")
    embed_url: Mapped[str] = mapped_column(String(600), default="")
    category: Mapped[str] = mapped_column(String(100), default="عام")


class News(Std, Base):
    __tablename__ = "news"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text, default="")
    image_url: Mapped[str] = mapped_column(String(600), default="")


# =============================================================================
# 4. DATABASE ENGINE / SESSIONS / INIT
# =============================================================================
@st.cache_resource(show_spinner=False)
def get_engine():
    url = db_url()
    if url.startswith("sqlite"):
        eng = create_engine(url, connect_args={"check_same_thread": False})

        @event.listens_for(eng, "connect")
        def _pragma(conn, _):
            cur = conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()
        return eng
    return create_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=5, pool_recycle=1800)


@contextmanager
def S():
    """Transactional scope. Commits on success, rolls back on errors.
    Streamlit control-flow exceptions (st.rerun / st.stop) are BaseExceptions; the
    work done before them was already validated, so it is committed."""
    s = Session(get_engine(), expire_on_commit=False)
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    except BaseException:
        s.commit()
        raise
    finally:
        s.close()


AUDIT_TRIGGERS = {
    "sqlite": [
        "CREATE TRIGGER IF NOT EXISTS audit_no_upd BEFORE UPDATE ON audit_logs "
        "BEGIN SELECT RAISE(ABORT,'audit_logs is append-only'); END;",
        "CREATE TRIGGER IF NOT EXISTS audit_no_del BEFORE DELETE ON audit_logs "
        "BEGIN SELECT RAISE(ABORT,'audit_logs is append-only'); END;"],
    "postgresql": [
        "CREATE OR REPLACE FUNCTION audit_immutable() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'audit_logs is append-only'; END; $$ LANGUAGE plpgsql;",
        "DROP TRIGGER IF EXISTS audit_no_change ON audit_logs;",
        "CREATE TRIGGER audit_no_change BEFORE UPDATE OR DELETE ON audit_logs "
        "FOR EACH ROW EXECUTE FUNCTION audit_immutable();"],
}


@st.cache_resource(show_spinner=False)
def init_db():
    eng = get_engine()
    Base.metadata.create_all(eng)  # additive only; never drops tables
    with eng.begin() as conn:
        for stmt in AUDIT_TRIGGERS.get(eng.dialect.name, []):
            conn.execute(text(stmt))
    return True


def health_check():
    try:
        with get_engine().connect() as c:
            c.execute(text("SELECT 1"))
        return True, f"ok [{get_engine().dialect.name}]"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def get_setting(key, default=""):
    with S() as s:
        row = s.get(Setting, key)
        return row.value if row else default


def set_setting(key, value):
    with S() as s:
        row = s.get(Setting, key)
        if row:
            row.value = value
        else:
            s.add(Setting(key=key, value=value))


def get_list(name):
    raw = get_setting("list:" + name, "")
    try:
        data = json.loads(raw) if raw else None
    except ValueError:
        data = None
    return data or DEFAULT_LISTS[name]


def next_ref(s, prefix):
    key = f"{prefix}-{date.today().year}"
    row = s.execute(select(Sequence).where(Sequence.key == key).with_for_update()).scalar_one_or_none()
    if row is None:
        row = Sequence(key=key, value=0)
        s.add(row)
        s.flush()
    row.value += 1
    s.flush()
    return f"{key}-{row.value:04d}"


# =============================================================================
# 5. SECURITY: PASSWORDS, PERMISSIONS, SCOPE, AUDIT
# =============================================================================
def hash_pw(pw):
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"


def check_pw(pw, stored):
    try:
        _, salt, h = stored.split("$")
        calc = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:  # noqa: BLE001
        return False


def pw_problems(pw):
    errs = []
    if len(pw) < MIN_PW:
        errs.append(L(f"كلمة المرور أقل من {MIN_PW} أحرف", f"Password must be at least {MIN_PW} characters"))
    if not re.search(r"[A-Za-z\u0600-\u06FF]", pw) or not re.search(r"\d", pw):
        errs.append(L("يجب أن تحتوي على حروف وأرقام", "Password must contain letters and digits"))
    return errs


MODULES = ["dashboard", "reviews", "documents", "validations", "capa", "tasks", "kpis", "checklists",
           "org", "reports", "audit", "notifications", "users", "settings", "portal"]
ACT = {"r": "read", "c": "create", "u": "update", "d": "delete", "a": "approve", "x": "export", "k": "close"}
_VIEW = {"dashboard": "r", "reviews": "r", "documents": "r", "validations": "r", "capa": "r", "tasks": "r",
         "kpis": "r", "checklists": "r", "org": "r", "reports": "r", "notifications": "ru", "portal": "r"}
PERMS_RAW = {
    "system_admin": {m: "rcudaxk" for m in MODULES},
    "qa_manager": {**{m: "rcudaxk" for m in MODULES}, "users": "r", "settings": "r", "audit": "rx"},
    "qa_reviewer": {**_VIEW, "reviews": "rcux", "documents": "rcux", "validations": "rcux",
                    "capa": "rcuxa", "tasks": "rcu", "kpis": "rx", "reports": "rx"},
    "department_manager": {**_VIEW, "capa": "ru", "tasks": "rcu"},
    "process_owner": {**_VIEW, "documents": "rcu", "capa": "ru", "tasks": "rcu"},
    "viewer": dict(_VIEW),
}
PERMS = {r: {m: {ACT[c] for c in v} for m, v in mods.items()} for r, mods in PERMS_RAW.items()}
GLOBAL_ROLES = {"system_admin", "qa_manager", "qa_reviewer"}
ROLES = list(PERMS_RAW)


@dataclass
class CU:
    id: int
    email: str
    name: str
    role: str
    employee_id: Optional[int]
    dept_ids: list

    @property
    def is_global(self):
        return self.role in GLOBAL_ROLES


def can(user, module, action):
    return bool(user) and action in PERMS.get(user.role, {}).get(module, set())


def require(user, module, action):
    if not can(user, module, action):
        raise PermissionError(L("ليست لديك صلاحية لتنفيذ هذا الإجراء", "You are not permitted to do this"))


def scope_clause(user, M):
    """Row-level (department) restriction applied to every query."""
    if user.is_global:
        return None
    ids = user.dept_ids or [-1]
    if M is Task:
        emp = select(Employee.id).where(Employee.department_id.in_(ids))
        return or_(Task.assignee_id.in_(emp), Task.created_by_id == user.id)
    if M is Document:
        base = Document.department_id.in_(ids)
        return base & (Document.status == "compliant") if user.role == "viewer" else base
    if M in (Checklist, KPI):
        return or_(M.department_id.is_(None), M.department_id.in_(ids))
    if M is Department:
        return Department.id.in_(ids)
    if hasattr(M, "department_id"):
        return M.department_id.in_(ids)
    return None


def fetch(s, user, M, *where):
    q = select(M)
    if hasattr(M, "archived"):
        q = q.where(M.archived.is_(False))
    sc = scope_clause(user, M)
    if sc is not None:
        q = q.where(sc)
    for w in where:
        q = q.where(w)
    return list(s.scalars(q))


def fetch_one(s, user, M, rid):
    rows = fetch(s, user, M, M.id == rid)
    return rows[0] if rows else None


def audit(s, user, action, etype, eid=None, ref="", old=None, new=None, event_name=""):
    dump = lambda v: json.dumps(v, default=str, ensure_ascii=False) if v is not None else ""
    s.add(AuditLog(user_id=user.id if user else None, user_email=user.email if user else "",
                   action=action, entity_type=etype, entity_id=eid, record_ref=str(ref or ""),
                   old_values=dump(old), new_values=dump(new), workflow_event=event_name))


def snapshot(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns
            if c.name not in ("content", "password_hash", "totp_secret")}


def log_status(s, user, etype, obj, old, new, note=""):
    s.add(StatusHistory(entity_type=etype, entity_id=obj.id, from_status=old or "", to_status=new,
                        note=note, user_id=user.id))
    audit(s, user, "status_change", etype, obj.id, getattr(obj, "reference", "") or getattr(obj, "doc_code", ""),
          {"status": old}, {"status": new, "note": note}, f"{old}->{new}")


# =============================================================================
# 6. AUTHENTICATION
# =============================================================================
def create_user(s, email, name, pw, role, employee_id=None):
    s.add(User(email=email.strip().lower(), full_name=name.strip(), password_hash=hash_pw(pw),
               role=role, employee_id=employee_id))


def load_user(uid):
    with S() as s:
        u = s.get(User, uid)
        if not u or not u.is_active or u.archived:
            return None
        depts = set()
        if u.employee_id:
            e = s.get(Employee, u.employee_id)
            if e and e.department_id:
                depts.add(e.department_id)
        depts |= set(s.scalars(select(UserDept.department_id).where(UserDept.user_id == u.id)))
        return CU(u.id, u.email, u.full_name, u.role, u.employee_id, sorted(depts))


def session_user():
    uid = st.session_state.get("uid")
    if not uid:
        return None
    last = st.session_state.get("last_seen")
    if last and datetime.utcnow() - last > timedelta(minutes=SESSION_MINUTES):
        logout()
        return None
    st.session_state["last_seen"] = datetime.utcnow()
    u = load_user(uid)
    if u is None:
        logout()
    return u


def logout():
    for k in ("uid", "pre_uid", "last_seen"):
        st.session_state.pop(k, None)


def login_brand(title, sub=""):
    logo = get_logo("company")
    st.markdown(f'<div class="login-brand"><img src="{logo}"><div class="t">{esc(title)}</div>'
                f'<div class="s">{esc(sub)}</div></div>', unsafe_allow_html=True)


def needs_setup():
    with S() as s:
        return s.scalar(select(func.count(User.id))) == 0


def render_setup():
    em, pw = str(secret("BOOTSTRAP_ADMIN_EMAIL", "")).strip().lower(), str(secret("BOOTSTRAP_ADMIN_PASSWORD", ""))
    if em and pw and not pw_problems(pw):
        with S() as s:
            create_user(s, em, "System Administrator", pw, "system_admin")
        st.rerun()
    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        login_brand(L("الإعداد الأولي", "First-run setup"),
                    L("أنشئ حساب مدير النظام الأول", "Create the first administrator account"))
        with st.form("setup"):
            name = st.text_input(L("الاسم", "Full name"))
            email = st.text_input(L("البريد الإلكتروني", "Email"))
            p1 = st.text_input(L("كلمة المرور", "Password"), type="password")
            p2 = st.text_input(L("تأكيد كلمة المرور", "Confirm password"), type="password")
            ok = st.form_submit_button(L("إنشاء", "Create"), type="primary")
        if ok:
            errs = pw_problems(p1)
            if not name.strip() or "@" not in email:
                errs.append(L("الاسم والبريد الصحيح مطلوبان", "Name and a valid email are required"))
            if p1 != p2:
                errs.append(L("كلمتا المرور غير متطابقتين", "Passwords do not match"))
            if errs:
                for e in errs:
                    st.error(e)
            else:
                with S() as s:
                    create_user(s, email, name, p1, "system_admin")
                    s.flush()
                st.rerun()


def render_login():
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        if st.session_state.get("pre_uid"):
            login_brand(L("التحقق الثنائي", "Two-factor verification"),
                        L("أدخل الرمز من تطبيق المصادقة", "Enter the code from your authenticator app"))
            with st.form("totp"):
                code = st.text_input(L("الرمز", "Code"), max_chars=6)
                go = st.form_submit_button(L("تحقق", "Verify"), type="primary")
            if go:
                with S() as s:
                    u = s.get(User, st.session_state["pre_uid"])
                    ok = bool(pyotp and u and u.totp_secret and pyotp.TOTP(u.totp_secret).verify(code.strip(), valid_window=1))
                if ok:
                    st.session_state["uid"] = st.session_state.pop("pre_uid")
                    st.session_state["last_seen"] = datetime.utcnow()
                    st.rerun()
                else:
                    st.error(L("الرمز غير صحيح", "Invalid code"))
            if st.button(L("رجوع", "Back")):
                logout()
                st.rerun()
            return
        login_brand(L("نظام إدارة الجودة - ليناركو", "Linrco Quality Assurance ERP"),
                    L("سجّل الدخول بالبريد الإلكتروني", "Sign in with your email"))
        with st.form("login"):
            email = st.text_input(L("البريد الإلكتروني", "Email"))
            pw = st.text_input(L("كلمة المرور", "Password"), type="password")
            go = st.form_submit_button(L("تسجيل الدخول", "Sign in"), type="primary")
        if go:
            msg = L("بيانات الدخول غير صحيحة", "Invalid credentials")
            with S() as s:
                u = s.scalar(select(User).where(User.email == email.strip().lower()))
                if u and u.locked_until and u.locked_until > now():
                    st.error(L("الحساب مقفل مؤقتاً، حاول لاحقاً", "Account temporarily locked, try later"))
                elif u and u.is_active and not u.archived and check_pw(pw, u.password_hash):
                    u.failed_logins, u.locked_until, u.last_login_at = 0, None, now()
                    audit(s, None, "login", "user", u.id, u.email)
                    if u.totp_enabled and pyotp:
                        st.session_state["pre_uid"] = u.id
                    else:
                        st.session_state["uid"] = u.id
                        st.session_state["last_seen"] = datetime.utcnow()
                    st.rerun()
                else:
                    if u:
                        u.failed_logins += 1
                        if u.failed_logins >= MAX_FAILED:
                            u.locked_until = now() + timedelta(minutes=LOCK_MINUTES)
                            u.failed_logins = 0
                        audit(s, None, "login_failed", "user", u.id, u.email)
                    st.error(msg)


# =============================================================================
# 7. UTILITIES: FILES, URLS, EMAIL, NOTIFICATIONS, SAFE FORMULAS
# =============================================================================
def safe_name(name):
    return re.sub(r"[^\w.\- ]", "_", name or "file")[:120]


def save_upload(s, user, up, etype, eid):
    ext = os.path.splitext(up.name)[1].lower()
    data = up.getvalue()
    if ext not in ALLOWED_EXT:
        raise ValueError(L("نوع الملف غير مسموح", "File type not allowed"))
    if len(data) > MAX_UPLOAD:
        raise ValueError(L("حجم الملف أكبر من المسموح", "File exceeds the size limit"))
    sigs = SIGNATURES.get(ext)
    if sigs and not any(data.startswith(g) for g in sigs):
        raise ValueError(L("محتوى الملف لا يطابق امتداده", "File content does not match its extension"))
    att = Attachment(entity_type=etype, entity_id=eid, original_name=safe_name(up.name),
                     stored_name=uuid.uuid4().hex + ext, size_bytes=len(data),
                     sha256=hashlib.sha256(data).hexdigest(), content=data, uploaded_by_id=user.id)
    s.add(att)
    s.flush()
    audit(s, user, "upload", etype, eid, att.original_name, new={"sha256": att.sha256, "size": att.size_bytes})
    return att


def attachments_panel(s, user, module, etype, obj, key):
    st.markdown(f"**{L('المرفقات', 'Attachments')}**")
    atts = list(s.scalars(select(Attachment).where(Attachment.entity_type == etype,
                                                   Attachment.entity_id == obj.id,
                                                   Attachment.archived.is_(False))))
    if not atts:
        st.caption(L("لا توجد مرفقات", "No attachments"))
    for a in atts:
        c1, c2, c3 = st.columns([5, 2, 1])
        c1.write(f"📎 {a.original_name} · {a.size_bytes // 1024} KB · {a.uploaded_at:%Y-%m-%d}")
        c2.download_button(L("تحميل", "Download"), a.content, file_name=a.original_name,
                           key=f"{key}_dl_{a.id}")
        if can(user, module, "delete") and c3.button("🗑", key=f"{key}_rm_{a.id}"):
            a.archived = True
            audit(s, user, "archive", "attachment", a.id, a.original_name)
            st.rerun()
    if can(user, module, "update") or can(user, module, "create"):
        up = st.file_uploader(L("إرفاق ملف", "Attach a file"), key=f"{key}_up_{obj.id}",
                              type=[e.strip(".") for e in sorted(ALLOWED_EXT)])
        if up is not None and st.button(L("حفظ المرفق", "Save attachment"), key=f"{key}_upb_{obj.id}"):
            try:
                save_upload(s, user, up, etype, obj.id)
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))


def send_email(to, subject, body):
    host = str(secret("SMTP_HOST", ""))
    if not host or not to:
        return False
    try:
        msg = EmailMessage()
        msg["Subject"], msg["To"] = subject, to
        msg["From"] = str(secret("SMTP_FROM", secret("SMTP_USER", "")))
        msg.set_content(body)
        with smtplib.SMTP(host, int(secret("SMTP_PORT", 587) or 587), timeout=10) as srv:
            srv.starttls()
            if secret("SMTP_USER", ""):
                srv.login(str(secret("SMTP_USER")), str(secret("SMTP_PASSWORD", "")))
            srv.send_message(msg)
        return True
    except Exception:  # noqa: BLE001
        return False


def notify_user(s, user_id, category, title, body, etype, eid, key):
    dk = f"{key}:u{user_id}"
    if s.scalar(select(func.count(Notification.id)).where(Notification.dedupe_key == dk)):
        return
    s.add(Notification(user_id=user_id, category=category, title=title, body=body,
                       entity_type=etype, entity_id=eid, dedupe_key=dk))
    s.flush()
    u = s.get(User, user_id)
    if u:
        send_email(u.email, title, body)


def notify_employee(s, emp_id, category, title, body, etype, eid, key):
    if not emp_id:
        return
    for uid in s.scalars(select(User.id).where(User.employee_id == emp_id, User.is_active.is_(True))):
        notify_user(s, uid, category, title, body, etype, eid, key)


def notify_roles(s, roles, category, title, body, etype, eid, key):
    for uid in s.scalars(select(User.id).where(User.role.in_(roles), User.is_active.is_(True))):
        notify_user(s, uid, category, title, body, etype, eid, key)


def scan_notifications():
    """Deadline / expiry / approval scans. Dedupe keys prevent repeated notifications."""
    today = date.today()
    with S() as s:
        for d in s.scalars(select(Document).where(Document.archived.is_(False), Document.status == "compliant",
                                                  Document.expiration_date.isnot(None),
                                                  Document.expiration_date < today)):
            d.status = "expired"
            s.add(StatusHistory(entity_type="documents", entity_id=d.id, from_status="compliant",
                                to_status="expired", note="auto: expiration date passed"))
        for t in s.scalars(select(Task).where(Task.archived.is_(False), Task.status.notin_(["done", "cancelled"]),
                                              Task.due_date.isnot(None), Task.due_date <= today + timedelta(days=3))):
            late = t.due_date < today
            notify_employee(s, t.assignee_id, "overdue" if late else "deadline",
                            f"{'متأخرة' if late else 'قريبة'}: {t.title}", f"{t.reference} - {t.due_date}",
                            "tasks", t.id, f"task:{t.id}:{'late' if late else 'soon'}:{t.due_date}")
        for c in s.scalars(select(Capa).where(Capa.archived.is_(False), Capa.status.notin_(["closed", "rejected"]),
                                              Capa.target_date.isnot(None), Capa.target_date < today)):
            notify_employee(s, c.action_owner_id, "overdue", f"CAPA متأخر: {c.title}", c.reference,
                            "capa", c.id, f"capa:{c.id}:late:{c.target_date}")
            if (today - c.target_date).days > 7 and c.escalation_level < 1:
                c.escalation_level = 1
                notify_roles(s, ["qa_manager"], "escalation", f"تصعيد: {c.reference}", c.title, "capa", c.id,
                             f"capa:{c.id}:esc")
        for d in s.scalars(select(Document).where(Document.archived.is_(False), Document.status != "obsolete")):
            for field, cat in (("expiration_date", "expiry"), ("review_date", "review")):
                dt = getattr(d, field)
                if dt and dt <= today + timedelta(days=30):
                    notify_employee(s, d.owner_id, cat, f"{d.doc_code}: {field} {dt}", d.title, "documents", d.id,
                                    f"doc:{d.id}:{field}:{dt}")
            if d.status == "pending_approval":
                notify_roles(s, ["qa_manager"], "approval", f"بانتظار الموافقة: {d.doc_code}", d.title,
                             "documents", d.id, f"doc:{d.id}:pa:{d.current_version_no}")
        for v in s.scalars(select(ProcessValidation).where(ProcessValidation.archived.is_(False),
                                                           ProcessValidation.decision == "not_validated")):
            notify_roles(s, ["qa_manager"], "validation", f"تحقق فاشل: {v.reference}", "", "validations", v.id,
                         f"val:{v.id}:failed")
        for r in s.scalars(select(Review).where(Review.archived.is_(False), Review.status == "awaiting_approval")):
            notify_roles(s, ["qa_manager"], "approval", f"مراجعة بانتظار الاعتماد: {r.reference}", r.title,
                         "reviews", r.id, f"rev:{r.id}:pa")


class _FormulaError(ValueError):
    pass


_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}


def formula_vars(expr):
    tree = ast.parse(expr, mode="eval")
    return sorted({n.id for n in ast.walk(tree) if isinstance(n, ast.Name)})


def safe_eval(expr, variables):
    """Restricted arithmetic evaluator (+ - * / parentheses, numbers, variables).
    Never uses eval()/exec()."""
    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
            return float(n.value)
        if isinstance(n, ast.Name):
            if n.id in variables:
                return float(variables[n.id])
            raise _FormulaError(f"unknown variable {n.id}")
        if isinstance(n, ast.BinOp) and type(n.op) in _OPS:
            a, b = ev(n.left), ev(n.right)
            if isinstance(n.op, ast.Div) and b == 0:
                raise _FormulaError("division by zero")
            return _OPS[type(n.op)](a, b)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd)):
            v = ev(n.operand)
            return -v if isinstance(n.op, ast.USub) else v
        raise _FormulaError("unsupported expression")
    try:
        return ev(ast.parse(expr, mode="eval"))
    except SyntaxError as exc:
        raise _FormulaError("invalid formula") from exc


def safe_url(url):
    url = (url or "").strip()
    return url if url.startswith(("http://", "https://")) else ""


_REPORT_RE = re.compile(r"(?:lookerstudio|datastudio)\.google\.com/(?:u/\d+/)?reporting/([0-9a-zA-Z-]+)(?:/page/([0-9a-zA-Z_-]+))?")


@st.cache_data(ttl=3600, show_spinner=False)
def resolve_short_url(url):
    try:
        return requests.get(url, allow_redirects=True, timeout=6, headers={"User-Agent": "Mozilla/5.0"}).url
    except Exception:  # noqa: BLE001
        return url


def to_embed_url(url):
    url = safe_url(url)
    if not url or "/embed/reporting/" in url:
        return url
    orig = url
    if requests and "/s/" in url and ("lookerstudio.google.com" in url or "datastudio.google.com" in url):
        url = resolve_short_url(url)
    m = _REPORT_RE.search(url)
    if m:
        e = f"https://lookerstudio.google.com/embed/reporting/{m.group(1)}"
        return e + (f"/page/{m.group(2)}" if m.group(2) else "")
    return orig


def get_logo(which):
    raw = get_setting(f"logo_{which}", "")
    if raw:
        return "data:image/png;base64," + raw
    return DEFAULT_COMPANY_LOGO if which == "company" else DEFAULT_QA_LOGO


# =============================================================================
# 8. SCORING AND WORKFLOW RULES (pure functions - unit tested below)
# =============================================================================
def parse_choices(text_):
    out = []
    for line in (text_ or "").splitlines():
        line = line.strip()
        if not line:
            continue
        label, _, pts = line.partition(":")
        try:
            frac = max(0.0, min(1.0, float(pts))) if pts.strip() else None
        except ValueError:
            frac = None
        out.append((label.strip(), frac))
    return [(lbl, (1.0 if frac is None and i == 0 else (frac if frac is not None else 0.0)))
            for i, (lbl, frac) in enumerate(out)]


def item_fraction(qtype, answer, choices="", max_score=1.0):
    """Return fraction (0..1) of credit for an answer, or None if unanswered."""
    if answer is None or str(answer).strip() == "":
        return None
    a = str(answer).strip().lower()
    if qtype == "yes_no":
        return 1.0 if a == "yes" else 0.0
    if qtype == "pass_fail":
        return 1.0 if a == "pass" else 0.0
    if qtype == "multiple_choice":
        return dict((c.lower(), f) for c, f in parse_choices(choices)).get(a, 0.0)
    if qtype == "numeric_score":
        try:
            return max(0.0, min(1.0, float(a) / (max_score or 1.0)))
        except ValueError:
            return None
    return 1.0  # text / date / evidence_required: answered counts as satisfied


def compute_score(items, answers):
    """items: ChecklistItem list; answers: {item_id: fraction or None}.
    Unanswered scored items contribute ZERO (never compliant). Returns (pct|None, missing_mandatory)."""
    total = sum(i.weight for i in items if i.is_scored)
    got = sum(i.weight * (answers.get(i.id) or 0.0) for i in items if i.is_scored)
    missing = [i for i in items if i.is_mandatory and answers.get(i.id) is None]
    return (round(got / total * 100, 1) if total > 0 else None), missing


REVIEW_FLOW = {
    "draft": ["scheduled", "in_progress", "cancelled"], "scheduled": ["in_progress", "cancelled"],
    "in_progress": ["under_review", "cancelled"],
    "under_review": ["passed", "failed", "requires_modification", "requires_process_validation", "in_progress"],
    "passed": ["awaiting_approval"], "failed": ["awaiting_approval", "in_progress"],
    "requires_modification": ["in_progress", "awaiting_approval"],
    "requires_process_validation": ["in_progress", "awaiting_approval"],
    "awaiting_approval": ["closed", "under_review"], "closed": [], "cancelled": [],
}
DOC_FLOW = {
    "pending_review": ["pending_approval", "requires_modification", "obsolete"],
    "requires_modification": ["pending_review", "obsolete"],
    "pending_approval": ["compliant", "requires_modification"],
    "compliant": ["pending_review", "requires_process_validation", "obsolete"],
    "expired": ["pending_review", "obsolete"],
    "requires_process_validation": ["pending_review", "compliant", "obsolete"], "obsolete": [],
}
CAPA_FLOW = {
    "open": ["assigned", "rejected"], "assigned": ["in_progress", "rejected"],
    "in_progress": ["awaiting_evidence", "rejected"],
    "awaiting_evidence": ["awaiting_qa_verification", "in_progress"],
    "awaiting_qa_verification": ["effectiveness_review", "in_progress", "rejected"],
    "effectiveness_review": ["closed", "in_progress"], "closed": [], "rejected": [],
}
REVIEW_DONE = ["passed", "failed", "closed"]
PRIORITIES = ["low", "medium", "high", "critical"]


def kpi_status(actual, target, higher=True, warn=0.9):
    if target in (None, 0) or actual is None:
        return "off_target"
    ratio = (actual / target) if higher else (target / actual if actual else 2.0)
    return "on_target" if ratio >= 1 else "warning" if ratio >= (warn or 0.9) else "off_target"


def period_bounds(freq, year, idx):
    if freq == "annual":
        return date(year, 1, 1), date(year, 12, 31)
    if freq == "quarterly":
        m = (idx - 1) * 3 + 1
        start = date(year, m, 1)
        end = (date(year + (m + 3 > 12), (m + 3 - 1) % 12 + 1, 1)) - timedelta(days=1)
        return start, end
    start = date(year, idx, 1)
    nxt = date(year + (idx == 12), idx % 12 + 1, 1)
    return start, nxt - timedelta(days=1)


# =============================================================================
# 9. UI: CSS, NAVIGATION HELPERS, GENERIC COMPONENTS
# =============================================================================
def inject_css():
    rtl = lang() == "ar"
    dark = st.session_state.get("theme") == "dark"
    v = ("--bg:#14161B;--surface:#1D2128;--ink:#ECEEF2;--muted:#9AA3B2;--line:#2C323C;" if dark else
         "--bg:#F4F5F7;--surface:#FFFFFF;--ink:#1D2433;--muted:#667085;--line:#E3E6EB;")
    st.markdown(f"""<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap');
:root{{--brand:#8A1C2B;--brand-deep:#5C0F1B;{v}}}
#MainMenu,footer,[data-testid="stToolbar"],[data-testid="stDecoration"]{{display:none!important}}
header[data-testid="stHeader"]{{background:transparent}}
.stApp{{background:var(--bg);color:var(--ink);direction:{'rtl' if rtl else 'ltr'}}}
.stApp,.stApp :is(p,h1,h2,h3,h4,label,input,textarea,button,li,a,td,th){{font-family:'IBM Plex Sans Arabic',Tahoma,sans-serif!important}}
.stApp :is(p,h1,h2,h3,h4,label,li){{text-align:{'right' if rtl else 'left'}}}
[data-testid="stAppViewContainer"],[data-testid="stMain"],[data-testid="stSidebar"]{{direction:{'rtl' if rtl else 'ltr'}}}
.block-container{{max-width:1320px;padding:1rem 1.5rem 4rem}}
[data-testid="stSidebar"]{{background:var(--surface);border-{'left' if rtl else 'right'}:1px solid var(--line)}}
[data-testid="stSidebar"] .stButton>button{{width:100%;justify-content:flex-start;border:none;background:transparent;color:var(--ink);font-weight:500}}
[data-testid="stSidebar"] .stButton>button[kind="primary"]{{background:var(--brand);color:#fff}}
.sb-logo{{background:#fff;border:1px solid var(--line);border-radius:10px;padding:.5rem;margin-bottom:.5rem;text-align:center}}
.sb-logo img{{max-width:100%;max-height:56px;object-fit:contain}}
.grp{{font-size:.75rem;color:var(--muted);margin:.9rem .3rem .2rem;font-weight:700}}
.topbar{{background:var(--brand-deep);color:#fff;border-radius:12px;padding:.6rem 1rem;margin-bottom:.8rem;display:flex;justify-content:space-between;align-items:center}}
.crumbs{{color:var(--muted);font-size:.85rem;margin:.2rem 0 .6rem}}
.card{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:.9rem 1.1rem;margin-bottom:.6rem}}
.card .v{{font-size:1.7rem;font-weight:700;color:var(--brand)}} .card .l{{color:var(--muted);font-size:.85rem}}
.badge{{display:inline-block;border-radius:999px;padding:.05rem .7rem;font-size:.8rem;font-weight:600;border:1px solid var(--line)}}
.b-good{{background:#DDF3E4;color:#146C2E}} .b-bad{{background:#FBE0E0;color:#A11A1A}}
.b-warn{{background:#FFF1D6;color:#8A5A00}} .b-neutral{{background:#ECEEF2;color:#4B5565}}
.login-brand{{text-align:center;margin:2rem 0 1rem}} .login-brand img{{max-height:70px;margin-bottom:.8rem}}
.login-brand .t{{font-size:1.4rem;font-weight:700}} .login-brand .s{{color:var(--muted)}}
.news{{background:var(--surface);border:1px solid var(--line);border-radius:12px;overflow:hidden;margin-bottom:.6rem}}
.news img{{width:100%;height:160px;object-fit:cover}} .news .b{{padding:.8rem 1rem}}
.btn-link{{display:inline-block;padding:.4rem 1rem;border-radius:8px;background:var(--brand);color:#fff!important;text-decoration:none!important;font-weight:600}}
.stButton>button[kind="primary"],.stFormSubmitButton>button{{background:var(--brand);border-color:var(--brand);color:#fff}}
.stTabs [aria-selected="true"]{{color:var(--brand)}} .stTabs [data-baseweb="tab-highlight"]{{background:var(--brand)}}
iframe{{border:1px solid var(--line)!important;border-radius:12px;background:#fff}}
@media(max-width:768px){{.block-container{{padding:.6rem}}}}
</style>""", unsafe_allow_html=True)
    st.session_state["_css_sig"] = (lang(), st.session_state.get("theme"))


def card(label, value, sub=""):
    st.markdown(f'<div class="card"><div class="l">{esc(str(label))}</div><div class="v">{esc(str(value))}</div>'
                f'<div class="l">{esc(str(sub))}</div></div>', unsafe_allow_html=True)


def goto(page, key=None, rid=None):
    st.session_state["page"] = page
    if key is not None:
        st.session_state[f"{key}_view"] = rid


def F(name, ar, en, typ="text", req=False, opts=None, fk=None, default=None):
    return dict(name=name, ar=ar, en=en, type=typ, req=req, opts=opts, fk=fk, default=default)


def widget(f, cur, key, disabled, s):
    lbl = L(f["ar"], f["en"]) + (" *" if f["req"] else "")
    k, t = f"{key}_{f['name']}", f["type"]
    if cur is None and f["default"] is not None:
        cur = f["default"]
    if t == "text":
        return st.text_input(lbl, value=cur or "", key=k, disabled=disabled).strip()
    if t == "area":
        return st.text_area(lbl, value=cur or "", key=k, disabled=disabled).strip()
    if t == "int":
        v = st.text_input(lbl, value="" if cur is None else str(cur), key=k, disabled=disabled).strip()
        return int(v) if re.fullmatch(r"-?\d+", v) else (None if not v else "ERR")
    if t == "float":
        v = st.text_input(lbl, value="" if cur is None else str(cur), key=k, disabled=disabled).strip()
        try:
            return float(v) if v else None
        except ValueError:
            return "ERR"
    if t == "bool":
        return st.checkbox(lbl, value=bool(cur), key=k, disabled=disabled)
    if t == "date":
        return st.date_input(lbl, value=cur, key=k, disabled=disabled, format="YYYY-MM-DD")
    if t == "select":
        options = ([""] if not f["req"] else []) + list(f["opts"])
        idx = options.index(cur) if cur in options else 0
        return st.selectbox(lbl, options, index=idx, format_func=lab, key=k, disabled=disabled) or None
    if t == "fk":
        M, attr = f["fk"]
        q = select(M.id, getattr(M, attr)).order_by(getattr(M, attr))
        if hasattr(M, "archived"):
            q = q.where(M.archived.is_(False))
        rows = s.execute(q).all()
        names = {i: str(n) for i, n in rows}
        ids = [None] + [i for i, _ in rows]
        idx = ids.index(cur) if cur in ids else 0
        return st.selectbox(lbl, ids, index=idx, format_func=lambda i: "—" if i is None else names.get(i, str(i)),
                            key=k, disabled=disabled)
    return None


def data_table(df, key, search_cols, page_size=PAGE_SIZE):
    """Searchable / sortable / paginated table; returns the selected row's _id or None."""
    if df.empty:
        st.info(L("لا توجد سجلات.", "No records found."))
        return None
    c1, c2, c3 = st.columns([3, 2, 1])
    q = c1.text_input(L("بحث", "Search"), key=f"{key}_q", placeholder=L("اكتب للبحث...", "Type to search..."))
    if q:
        mask = df[search_cols].astype(str).apply(lambda c: c.str.contains(q, case=False, na=False, regex=False)).any(axis=1)
        df = df[mask]
    cols = [c for c in df.columns if c != "_id"]
    sort_by = c2.selectbox(L("ترتيب حسب", "Sort by"), cols, key=f"{key}_sort")
    asc = c3.toggle(L("تصاعدي", "Asc"), value=False, key=f"{key}_asc")
    df = df.sort_values(sort_by, ascending=asc, na_position="last", key=lambda c: c.astype(str))
    pages = max(1, math.ceil(len(df) / page_size))
    page = st.number_input(L("الصفحة", "Page"), 1, pages, 1, key=f"{key}_pg") if pages > 1 else 1
    view = df.iloc[(page - 1) * page_size: page * page_size]
    st.caption(L(f"{len(df)} سجل", f"{len(df)} records"))
    ev = st.dataframe(view, hide_index=True, column_order=cols, use_container_width=True,
                      on_select="rerun", selection_mode="single-row", key=f"{key}_tbl{st.session_state.get(key + '_n', 0)}")
    sel = ev.selection.rows if ev is not None and hasattr(ev, "selection") else []
    return int(view.iloc[sel[0]]["_id"]) if sel else None


def df_download(df, name, user, module):
    if not can(user, module, "export"):
        return
    c1, c2 = st.columns(2)
    c1.download_button("CSV", df.to_csv(index=False).encode("utf-8-sig"), f"{name}.csv", "text/csv", key=f"csv_{name}")
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    c2.download_button("Excel", buf.getvalue(), f"{name}.xlsx", key=f"xls_{name}")


# =============================================================================
# 10. GENERIC CRUD ENGINE
# =============================================================================
@dataclass
class Cfg:
    key: str
    module: str
    model: type
    title: tuple
    fields: Callable
    cols: list                       # (ar, en, attr, kind)
    ref_field: str = "reference"
    ref_prefix: Optional[str] = None
    validate: Optional[Callable] = None
    extra: Optional[Callable] = None
    on_save: Optional[Callable] = None
    overdue: Optional[tuple] = None  # (date_attr, terminal statuses)
    status_attr: Optional[str] = None
    name_attr: str = "title"
    soft_delete: bool = True


def _lookup(s, cache, M, attr):
    k = (M, attr)
    if k not in cache:
        cache[k] = {i: n for i, n in s.execute(select(M.id, getattr(M, attr))).all()}
    return cache[k]


def build_df(s, user, cfg):
    objs = fetch(s, user, cfg.model)
    cache, rows = {}, []
    for o in objs:
        r = {"_id": o.id}
        for ar, en, attr, kind in cfg.cols:
            v = getattr(o, attr, None)
            if kind == "status":
                v = lab(v)
            elif isinstance(kind, tuple):
                v = _lookup(s, cache, *kind).get(v, "") if v is not None else ""
            elif kind == "bool":
                v = "✓" if v else "—"
            elif isinstance(v, float):
                v = round(v, 1)
            r[L(ar, en)] = v
        if cfg.overdue:
            dt, term = cfg.overdue
            d_ = getattr(o, dt, None)
            r["⚠"] = "⚠" if d_ and d_ < date.today() and getattr(o, cfg.status_attr or "status", "") not in term else ""
        rows.append(r)
    return pd.DataFrame(rows)


def validate_common(cfg, fields, values, user):
    errs = []
    for f in fields:
        v = values.get(f["name"])
        lbl = L(f["ar"], f["en"])
        if v == "ERR":
            errs.append(L(f"قيمة غير صالحة: {lbl}", f"Invalid value: {lbl}"))
        elif f["req"] and (v is None or v == ""):
            errs.append(L(f"الحقل مطلوب: {lbl}", f"Required field: {lbl}"))
    dep = values.get("department_id")
    if dep and not user.is_global and dep not in user.dept_ids:
        errs.append(L("لا يمكنك التعامل مع هذا القسم", "You cannot work with this department"))
    return errs


def save_record(cfg, user, rid, values):
    fields = cfg.fields()
    errs = validate_common(cfg, fields, values, user)
    try:
        with S() as s:
            if cfg.validate:
                errs += cfg.validate(s, values, rid)
            if errs:
                return errs, None
            if rid:
                require(user, cfg.module, "update")
                obj = fetch_one(s, user, cfg.model, rid)
                if obj is None:
                    return [L("السجل غير موجود أو لا تملك صلاحية الوصول", "Record not found or access denied")], None
                old = snapshot(obj)
                for k, v in values.items():
                    setattr(obj, k, v)
                if hasattr(obj, "updated_by_id"):
                    obj.updated_by_id = user.id
                s.flush()
                new = snapshot(obj)
                diff = {k: [old[k], new[k]] for k in new if old.get(k) != new[k]}
                audit(s, user, "update", cfg.key, obj.id, getattr(obj, cfg.ref_field, ""), old={k: v[0] for k, v in diff.items()},
                      new={k: v[1] for k, v in diff.items()})
                is_new = False
            else:
                require(user, cfg.module, "create")
                obj = cfg.model(**values)
                if cfg.ref_prefix:
                    setattr(obj, cfg.ref_field, next_ref(s, cfg.ref_prefix))
                if hasattr(obj, "created_by_id"):
                    obj.created_by_id = user.id
                s.add(obj)
                s.flush()
                audit(s, user, "create", cfg.key, obj.id, getattr(obj, cfg.ref_field, ""), new=snapshot(obj))
                is_new = True
            if cfg.on_save:
                cfg.on_save(s, user, obj, is_new)
            s.flush()
            return [], obj.id
    except IntegrityError:
        return [L("قيمة مكررة أو مرتبطة بسجلات أخرى (تحقق من الأكواد الفريدة)",
                  "Duplicate value or constraint violation (check unique codes)")], None
    except PermissionError as exc:
        return [str(exc)], None


def history_tab(s, user, cfg, obj):
    hist = list(s.scalars(select(StatusHistory).where(StatusHistory.entity_type == cfg.key,
                                                      StatusHistory.entity_id == obj.id).order_by(StatusHistory.id.desc())))
    if hist:
        names = _lookup(s, {}, User, "full_name")
        st.dataframe(pd.DataFrame([{L("التاريخ", "When"): h.created_at.strftime("%Y-%m-%d %H:%M"),
                                    L("من", "From"): lab(h.from_status), L("إلى", "To"): lab(h.to_status),
                                    L("المستخدم", "User"): names.get(h.user_id, ""), L("ملاحظة", "Note"): h.note}
                                   for h in hist]), hide_index=True, use_container_width=True)
    else:
        st.caption(L("لا يوجد سجل حالات", "No status history"))
    if can(user, "audit", "read"):
        logs = list(s.scalars(select(AuditLog).where(AuditLog.entity_type == cfg.key, AuditLog.entity_id == obj.id)
                              .order_by(AuditLog.id.desc()).limit(50)))
        if logs:
            st.markdown(f"**{L('سجل التدقيق', 'Audit trail')}**")
            st.dataframe(pd.DataFrame([{"time": a.created_at.strftime("%Y-%m-%d %H:%M"), "user": a.user_email,
                                        "action": a.action, "old": a.old_values[:120], "new": a.new_values[:120]}
                                       for a in logs]), hide_index=True, use_container_width=True)


def comments_panel(s, user, module, etype, obj, key):
    st.markdown(f"**{L('التعليقات', 'Comments')}**")
    names = _lookup(s, {}, User, "full_name")
    for c in s.scalars(select(Comment).where(Comment.entity_type == etype, Comment.entity_id == obj.id).order_by(Comment.id)):
        st.markdown(f"> {esc(c.body)}  \n<small>{esc(names.get(c.user_id, ''))} · {c.created_at:%Y-%m-%d %H:%M}</small>",
                    unsafe_allow_html=True)
    if can(user, module, "update"):
        body = st.text_input(L("تعليق جديد", "New comment"), key=f"{key}_cm_{obj.id}")
        if st.button(L("إضافة تعليق", "Add comment"), key=f"{key}_cmb_{obj.id}") and body.strip():
            s.add(Comment(entity_type=etype, entity_id=obj.id, user_id=user.id, body=body.strip()))
            audit(s, user, "comment", etype, obj.id, getattr(obj, "reference", ""))
            st.rerun()


def workflow_panel(s, user, cfg, obj, flow, guard, key):
    cur = obj.status
    st.markdown(f"{L('الحالة الحالية', 'Current status')}: {badge(cur)}", unsafe_allow_html=True)
    nxt = flow.get(cur, [])
    if not nxt:
        st.info(L("لا توجد انتقالات متاحة من هذه الحالة.", "No further transitions from this status."))
        return
    c1, c2 = st.columns([1, 2])
    to = c1.selectbox(L("الانتقال إلى", "Move to"), nxt, format_func=lab, key=f"{key}_to_{obj.id}_{cur}")
    note = c2.text_input(L("ملاحظة / سبب", "Note / reason"), key=f"{key}_note_{obj.id}_{cur}")
    if st.button(L("تنفيذ الانتقال", "Apply transition"), type="primary", key=f"{key}_apply_{obj.id}_{cur}"):
        errs = guard(s, user, obj, to, note.strip())
        if errs:
            for e in errs:
                st.error(e)
            return
        log_status(s, user, cfg.key, obj, cur, to, note.strip())
        obj.status = to
        s.flush()
        st.success(L("تم تنفيذ الانتقال", "Transition applied"))
        st.rerun()


def crud_page(cfg, user):
    view_key, n_key = f"{cfg.key}_view", f"{cfg.key}_n"
    view = st.session_state.get(view_key)
    title = L(*cfg.title)
    if view is None:
        c1, c2 = st.columns([4, 1])
        c1.subheader(title)
        if can(user, cfg.module, "create") and c2.button(L("➕ جديد", "➕ New"), key=f"{cfg.key}_newbtn", type="primary"):
            st.session_state[view_key] = "new"
            st.rerun()
        with S() as s:
            df = build_df(s, user, cfg)
        pick = data_table(df, cfg.key, [c for c in df.columns if c not in ("_id",)] if not df.empty else [])
        if not df.empty:
            df_download(df.drop(columns=["_id"]), cfg.key, user, cfg.module)
        if pick:
            st.session_state[view_key] = pick
            st.rerun()
        return
    if st.button(L("← رجوع للقائمة", "← Back to list"), key=f"{cfg.key}_back"):
        st.session_state[view_key] = None
        st.session_state[n_key] = st.session_state.get(n_key, 0) + 1
        st.rerun()
    rid = None if view == "new" else int(view)
    with S() as s:
        obj = None
        if rid:
            obj = fetch_one(s, user, cfg.model, rid)
            if obj is None:
                st.error(L("السجل غير موجود أو لا تملك صلاحية الوصول", "Record not found or access denied"))
                return
            ref = getattr(obj, cfg.ref_field, "")
            st.session_state["crumb_record"] = str(ref)
            head = f"### {esc(str(ref))} — {esc(str(getattr(obj, cfg.name_attr, '') or ''))}"
            if hasattr(obj, "status"):
                head += f" &nbsp; {badge(obj.status)}"
            st.markdown(head, unsafe_allow_html=True)
        else:
            st.session_state["crumb_record"] = L("جديد", "New")
            st.markdown(f"### {L('سجل جديد', 'New record')}: {title}")
        tabs = st.tabs([L("التفاصيل", "Details"), L("سير العمل والعلاقات", "Workflow & related"), L("السجل", "History")]
                       if rid else [L("التفاصيل", "Details")])
        with tabs[0]:
            editable = can(user, cfg.module, "update" if rid else "create")
            fields = cfg.fields()
            with st.form(f"{cfg.key}_form_{rid or 'new'}"):
                cols = st.columns(2)
                values = {}
                for i, f in enumerate(fields):
                    with cols[i % 2] if f["type"] not in ("area",) else st.container():
                        values[f["name"]] = widget(f, getattr(obj, f["name"], None) if obj else None,
                                                   f"{cfg.key}_{rid or 'new'}", not editable, s)
                submitted = st.form_submit_button(L("حفظ", "Save"), type="primary", disabled=not editable)
            if submitted:
                errs, new_id = save_record(cfg, user, rid, values)
                if errs:
                    for e in errs:
                        st.error(e)
                else:
                    st.success(L("تم الحفظ بنجاح", "Saved successfully"))
                    st.session_state[view_key] = new_id
                    st.rerun()
            if rid and can(user, cfg.module, "delete") and cfg.soft_delete:
                with st.expander(L("منطقة الخطر", "Danger zone")):
                    ok = st.checkbox(L("أؤكد أرشفة هذا السجل", "I confirm archiving this record"), key=f"{cfg.key}_cf_{rid}")
                    if st.button(L("🗑 أرشفة السجل", "🗑 Archive record"), key=f"{cfg.key}_del_{rid}", disabled=not ok):
                        obj.archived = True
                        audit(s, user, "archive", cfg.key, rid, getattr(obj, cfg.ref_field, ""))
                        st.session_state[view_key] = None
                        st.session_state[n_key] = st.session_state.get(n_key, 0) + 1
                        st.rerun()
        if rid:
            with tabs[1]:
                if cfg.extra:
                    cfg.extra(s, user, obj)
                comments_panel(s, user, cfg.module, cfg.key, obj, cfg.key)
            with tabs[2]:
                history_tab(s, user, cfg, obj)


# =============================================================================
# 11. MODULE CONFIGURATIONS AND WORKFLOW GUARDS
# =============================================================================
D_FK = (Department, "name")
E_FK = (Employee, "full_name")
P_FK = (Process, "name")


def dept_fields():
    return [F("code", "الكود", "Code", req=True), F("name", "الاسم", "Name", req=True),
            F("name_ar", "الاسم بالعربية", "Arabic name"), F("description", "الوصف", "Description", "area"),
            F("active", "نشط", "Active", "bool", default=True)]


def emp_fields():
    return [F("employee_no", "الرقم الوظيفي", "Employee No.", req=True), F("full_name", "الاسم", "Full name", req=True),
            F("email", "البريد", "Email"), F("department_id", "القسم", "Department", "fk", fk=D_FK),
            F("job_title", "المسمى الوظيفي", "Job title", "select", opts=get_list("job_titles")),
            F("is_reviewer", "مراجع جودة", "QA reviewer", "bool"), F("is_owner", "مالك عملية", "Process owner", "bool"),
            F("is_manager", "مدير قسم", "Department manager", "bool"),
            F("responsibilities", "المسؤوليات", "Responsibilities", "area"),
            F("active", "نشط", "Active", "bool", default=True)]


def proc_fields():
    return [F("name", "اسم العملية", "Process name", req=True),
            F("department_id", "القسم", "Department", "fk", req=True, fk=D_FK),
            F("owner_id", "مالك العملية", "Owner", "fk", fk=E_FK),
            F("responsible_role", "الدور المسؤول", "Responsible role"),
            F("sla_hours", "SLA (ساعات)", "SLA (hours)", "float"),
            F("validation_interval_days", "دورة التحقق (أيام)", "Validation interval (days)", "int"),
            F("description", "الوصف", "Description", "area"), F("active", "نشطة", "Active", "bool", default=True)]


def v_nonneg(values, *names):
    out = []
    for n in names:
        v = values.get(n)
        if isinstance(v, (int, float)) and v < 0:
            out.append(L("القيمة لا يمكن أن تكون سالبة", "Value cannot be negative"))
    return out


def v_proc(s, values, rid):
    return v_nonneg(values, "sla_hours", "validation_interval_days")


def v_dates(a, b, ar, en):
    return lambda values: ([L(ar, en)] if values.get(a) and values.get(b) and values[b] < values[a] else [])


# ---- Reviews -----------------------------------------------------------------
def review_fields():
    return [F("title", "عنوان المراجعة", "Title", req=True), F("department_id", "القسم", "Department", "fk", req=True, fk=D_FK),
            F("process_id", "العملية", "Process", "fk", fk=P_FK), F("responsible_id", "الموظف المسؤول", "Responsible", "fk", fk=E_FK),
            F("reviewer_id", "المراجع", "Reviewer", "fk", fk=E_FK),
            F("review_type", "نوع المراجعة", "Review type", "select", req=True, opts=get_list("review_types")),
            F("priority", "الأولوية", "Priority", "select", req=True, opts=PRIORITIES, default="medium"),
            F("review_date", "تاريخ المراجعة", "Review date", "date"), F("due_date", "تاريخ الاستحقاق", "Due date", "date"),
            F("checklist_id", "قائمة الفحص", "Checklist", "fk", fk=(Checklist, "title")),
            F("document_id", "المستند المرجعي", "Related document", "fk", fk=(Document, "title")),
            F("comments", "تعليقات", "Comments", "area"), F("observations", "ملاحظات", "Observations", "area")]


def v_review(s, values, rid):
    errs = v_dates("review_date", "due_date", "تاريخ الاستحقاق قبل تاريخ المراجعة", "Due date is before review date")(values)
    if rid:
        r = s.get(Review, rid)
        if r and r.checklist_id != values.get("checklist_id") and s.scalar(
                select(func.count(ReviewAnswer.id)).where(ReviewAnswer.review_id == rid)):
            errs.append(L("لا يمكن تغيير قائمة الفحص بعد تسجيل إجابات", "Cannot change checklist after answers exist"))
    return errs


def review_state(s, r):
    items = list(s.scalars(select(ChecklistItem).where(ChecklistItem.checklist_id == r.checklist_id).order_by(ChecklistItem.sequence))) if r.checklist_id else []
    ans = {a.item_id: a for a in s.scalars(select(ReviewAnswer).where(ReviewAnswer.review_id == r.id))}
    score, missing = compute_score(items, {i: a.fraction for i, a in ans.items()})
    return items, ans, score, missing


def review_guard(s, user, r, to, note):
    errs = []
    deny = L("ليست لديك صلاحية لهذا الانتقال", "You are not permitted to make this transition")
    if to == "closed":
        if not can(user, "reviews", "close"):
            errs.append(deny)
        if r.reviewer_id and user.employee_id == r.reviewer_id and user.role != "system_admin":
            errs.append(L("لا يمكن للمراجع اعتماد مراجعته بنفسه", "A reviewer cannot approve their own review"))
        if not note:
            errs.append(L("ملاحظة الإغلاق مطلوبة", "A closing note is required"))
    elif not can(user, "reviews", "update"):
        errs.append(deny)
    if to == "in_progress" and not r.reviewer_id:
        errs.append(L("يجب تعيين مراجع أولاً", "Assign a reviewer first"))
    if to in ("under_review", "passed", "failed"):
        if not r.checklist_id:
            errs.append(L("يجب ربط قائمة فحص", "A checklist must be linked"))
        else:
            _, _, score, missing = review_state(s, r)
            if missing:
                errs.append(L(f"{len(missing)} بنود إلزامية بلا إجابة", f"{len(missing)} mandatory items unanswered"))
            if to == "passed":
                thr = s.get(Checklist, r.checklist_id).pass_threshold
                if score is None or score < thr:
                    errs.append(L(f"الدرجة {score} أقل من حد النجاح {thr}", f"Score {score} is below pass threshold {thr}"))
    if to in ("failed", "requires_modification", "requires_process_validation", "cancelled") and not note:
        errs.append(L("السبب مطلوب", "A reason is required"))
    if not errs and r.checklist_id and to in ("under_review", "passed", "failed"):
        r.compliance_score = review_state(s, r)[2]
    if not errs and to in REVIEW_DONE:
        r.completed_at, r.final_outcome = now(), to
    if not errs:
        r.updated_by_id = user.id
    return errs


def review_extra(s, user, r):
    cfg = CFGS["reviews"]
    workflow_panel(s, user, cfg, r, REVIEW_FLOW, review_guard, "rv")
    st.divider()
    items, ans, score, missing = review_state(s, r)
    st.markdown(f"**{L('قائمة الفحص', 'Checklist')}** — {L('الدرجة', 'Score')}: "
                f"{'—' if score is None else str(score) + '%'}")
    if not r.checklist_id:
        st.info(L("اربط قائمة فحص من تبويب التفاصيل.", "Link a checklist from the Details tab."))
    else:
        editable = can(user, "reviews", "update") and r.status in ("in_progress", "under_review")
        if not editable:
            st.caption(L("الإجابات قابلة للتعديل أثناء حالة «قيد التنفيذ» أو «قيد المراجعة».",
                         "Answers are editable while the review is In Progress or Under Review."))
        with st.form(f"ans_form_{r.id}"):
            new = {}
            for it in items:
                a = ans.get(it.id)
                cur = a.answer if a else None
                k = f"ans_{r.id}_{it.id}"
                lbl = f"{it.sequence}. {it.question}" + (" *" if it.is_mandatory else "")
                st.markdown(f"**{esc(lbl)}**" + (f"  \n<small>{esc(it.criteria)}</small>" if it.criteria else ""), unsafe_allow_html=True)
                t = it.question_type
                if t in ("yes_no", "pass_fail"):
                    opts = ["", "yes", "no"] if t == "yes_no" else ["", "pass", "fail"]
                    v = st.selectbox("answer", opts, index=opts.index(cur) if cur in opts else 0, key=k, disabled=not editable,
                                     format_func=lambda x: "—" if x == "" else x, label_visibility="collapsed")
                elif t == "multiple_choice":
                    opts = [""] + [c for c, _ in parse_choices(it.choices)]
                    v = st.selectbox("answer", opts, index=opts.index(cur) if cur in opts else 0, key=k, disabled=not editable,
                                     format_func=lambda x: "—" if x == "" else x, label_visibility="collapsed")
                elif t == "numeric_score":
                    v = st.text_input(f"0 – {it.max_score}", value=cur or "", key=k, disabled=not editable)
                elif t == "date":
                    try:
                        dv = date.fromisoformat(cur) if cur else None
                    except ValueError:
                        dv = None
                    d_ = st.date_input("answer", value=dv, key=k, disabled=not editable, label_visibility="collapsed")
                    v = d_.isoformat() if d_ else ""
                else:
                    v = st.text_area("answer", value=cur or "", key=k, disabled=not editable, label_visibility="collapsed")
                cm = st.text_input(L("تعليق / دليل" + (" (مطلوب)" if it.evidence_required else ""),
                                     "Comment / evidence" + (" (required)" if it.evidence_required else "")),
                                   value=a.comment if a else "", key=k + "_c", disabled=not editable)
                new[it.id] = (v, cm.strip())
            save = st.form_submit_button(L("حفظ الإجابات", "Save answers"), type="primary", disabled=not editable)
        if save:
            errs = []
            for it in items:
                v, cm = new[it.id]
                if it.question_type == "numeric_score" and v:
                    try:
                        if not 0 <= float(v) <= it.max_score:
                            errs.append(f"#{it.sequence}: " + L(f"القيمة بين 0 و {it.max_score}", f"value must be 0–{it.max_score}"))
                    except ValueError:
                        errs.append(f"#{it.sequence}: " + L("رقم غير صالح", "invalid number"))
                if it.evidence_required and v not in ("", None) and not cm:
                    errs.append(f"#{it.sequence}: " + L("الدليل مطلوب", "evidence required"))
            if errs:
                for e in errs:
                    st.error(e)
            else:
                for it in items:
                    v, cm = new[it.id]
                    a = ans.get(it.id)
                    if a is None:
                        a = ReviewAnswer(review_id=r.id, item_id=it.id)
                        s.add(a)
                    a.answer, a.comment = (v or None), cm
                    a.fraction = item_fraction(it.question_type, v, it.choices, it.max_score)
                    a.answered_by_id, a.answered_at = user.id, now()
                audit(s, user, "answers_saved", "reviews", r.id, r.reference)
                st.success(L("تم حفظ الإجابات", "Answers saved"))
                st.rerun()
    st.divider()
    attachments_panel(s, user, "reviews", "reviews", r, "rv")
    st.divider()
    ncs = list(s.scalars(select(Capa).where(Capa.review_id == r.id, Capa.archived.is_(False))))
    st.markdown(f"**{L('حالات عدم المطابقة المرتبطة', 'Linked nonconformities')}**")
    for c in ncs:
        st.button(f"{c.reference} · {c.title}", key=f"rv_nc_{c.id}", on_click=goto, args=("capa", "capa", c.id))
    if can(user, "capa", "create") and st.button(L("➕ تسجيل عدم مطابقة من هذه المراجعة", "➕ Raise nonconformity from this review"),
                                                  key=f"rv_newnc_{r.id}"):
        c = Capa(reference=next_ref(s, "NC"), title=f"NC - {r.title}"[:300], review_id=r.id, process_id=r.process_id,
                 department_id=r.department_id, action_owner_id=r.responsible_id, severity="medium")
        s.add(c)
        s.flush()
        audit(s, user, "create", "capa", c.id, c.reference, new={"from_review": r.reference})
        goto("capa", "capa", c.id)
        st.rerun()
    if can(user, "tasks", "create") and st.button(L("➕ مهمة متابعة", "➕ Follow-up task"), key=f"rv_newtask_{r.id}"):
        t = Task(reference=next_ref(s, "TK"), title=f"متابعة: {r.title}"[:300], review_id=r.id, assignee_id=r.responsible_id,
                 created_by_id=user.id)
        s.add(t)
        s.flush()
        goto("tasks", "tasks", t.id)
        st.rerun()


def review_on_save(s, user, r, is_new):
    if is_new:
        r.status = "draft"
    notify_employee(s, r.reviewer_id, "assignment", f"تم إسناد مراجعة: {r.title}", r.reference, "reviews", r.id,
                    f"rev:{r.id}:assign:{r.reviewer_id}")
    notify_employee(s, r.responsible_id, "assignment", f"مراجعة تخص عملك: {r.title}", r.reference, "reviews", r.id,
                    f"rev:{r.id}:resp:{r.responsible_id}")


# ---- Documents -----------------------------------------------------------------
def doc_fields():
    return [F("doc_code", "كود المستند", "Document code", req=True), F("title", "العنوان", "Title", req=True),
            F("category", "النوع", "Category", "select", req=True, opts=get_list("doc_categories")),
            F("classification", "التصنيف", "Classification", "select", req=True, opts=get_list("classifications"), default="internal"),
            F("department_id", "القسم", "Department", "fk", req=True, fk=D_FK), F("process_id", "العملية", "Process", "fk", fk=P_FK),
            F("owner_id", "مالك المستند", "Document owner", "fk", fk=E_FK),
            F("process_owner_id", "مالك العملية", "Process owner", "fk", fk=E_FK),
            F("effective_date", "تاريخ السريان", "Effective date", "date"), F("review_date", "تاريخ المراجعة", "Review date", "date"),
            F("expiration_date", "تاريخ الانتهاء", "Expiration date", "date"),
            F("review_interval_days", "دورة المراجعة (أيام)", "Review interval (days)", "int"),
            F("external_link", "رابط المستند", "Document link"), F("description", "الوصف", "Description", "area")]


def v_doc(s, values, rid):
    errs = v_nonneg(values, "review_interval_days")
    errs += v_dates("effective_date", "expiration_date", "الانتهاء قبل السريان", "Expiration before effective date")(values)
    if values.get("external_link") and not safe_url(values["external_link"]):
        errs.append(L("الرابط يجب أن يبدأ بـ http(s)", "Link must start with http(s)"))
    return errs


def doc_on_save(s, user, d, is_new):
    if is_new:
        d.status, d.current_version_no = "pending_review", "1.0"
        s.add(DocVersion(document_id=d.id, version_no="1.0", change_description="Initial version", author_id=user.id))


def doc_guard(s, user, d, to, note):
    errs = []
    deny = L("ليست لديك صلاحية لهذا الانتقال", "You are not permitted to make this transition")
    if to == "compliant":
        if not can(user, "documents", "approve"):
            errs.append(deny)
        v = s.scalar(select(DocVersion).where(DocVersion.document_id == d.id, DocVersion.version_no == d.current_version_no))
        if v and v.author_id == user.id and user.role != "system_admin":
            errs.append(L("لا يمكنك اعتماد نسخة كتبتها بنفسك", "You cannot approve a version you authored"))
        if not errs and v:
            v.approved_by_id, v.approved_at = user.id, now()
            d.effective_date = d.effective_date or date.today()
            if d.review_interval_days:
                d.review_date = date.today() + timedelta(days=d.review_interval_days)
    elif to in ("pending_approval", "pending_review", "requires_process_validation") and not can(user, "documents", "update"):
        errs.append(deny)
    elif to == "obsolete" and not can(user, "documents", "close"):
        errs.append(deny)
    if to in ("requires_modification", "obsolete") and not note:
        errs.append(L("السبب مطلوب", "A reason is required"))
    return errs


def doc_extra(s, user, d):
    cfg = CFGS["documents"]
    new_flag = d.updated_at and d.updated_at > now() - timedelta(days=7)
    if new_flag:
        st.caption("🆕 " + L("تم تحديثه خلال آخر 7 أيام", "Updated within the last 7 days"))
    if d.expiration_date and d.expiration_date < date.today():
        st.warning(L("انتهت صلاحية المستند", "Document has expired"))
    workflow_panel(s, user, cfg, d, DOC_FLOW, doc_guard, "dc")
    if d.external_link and safe_url(d.external_link):
        st.markdown(f'<a class="btn-link" href="{esc(d.external_link, quote=True)}" target="_blank" rel="noopener">{L("فتح الرابط", "Open link")}</a>',
                    unsafe_allow_html=True)
    st.divider()
    st.markdown(f"**{L('سجل الإصدارات', 'Version history')}**")
    names = _lookup(s, {}, User, "full_name")
    vs = list(s.scalars(select(DocVersion).where(DocVersion.document_id == d.id).order_by(DocVersion.id.desc())))
    st.dataframe(pd.DataFrame([{L("الإصدار", "Version"): v.version_no, L("التغيير", "Change"): v.change_description,
                                L("الكاتب", "Author"): names.get(v.author_id, ""), L("التاريخ", "Date"): v.created_at.strftime("%Y-%m-%d"),
                                L("اعتمد بواسطة", "Approved by"): names.get(v.approved_by_id, "")} for v in vs]),
                 hide_index=True, use_container_width=True)
    if can(user, "documents", "update"):
        with st.form(f"dv_{d.id}"):
            vn = st.text_input(L("رقم الإصدار الجديد", "New version number"))
            ch = st.text_area(L("وصف التغيير", "Change description"))
            up = st.file_uploader(L("ملف الإصدار (اختياري)", "Version file (optional)"), key=f"dv_up_{d.id}")
            go = st.form_submit_button(L("إنشاء إصدار جديد", "Create new version"))
        if go:
            if not vn.strip() or not ch.strip():
                st.error(L("رقم الإصدار والوصف مطلوبان", "Version number and description are required"))
            elif any(v.version_no == vn.strip() for v in vs):
                st.error(L("رقم الإصدار موجود", "Version number already exists"))
            else:
                try:
                    att = save_upload(s, user, up, "documents", d.id) if up else None
                    s.add(DocVersion(document_id=d.id, version_no=vn.strip(), change_description=ch.strip(),
                                     author_id=user.id, attachment_id=att.id if att else None))
                    old = d.status
                    d.current_version_no = vn.strip()
                    if old != "pending_review":
                        d.status = "pending_review"
                        log_status(s, user, "documents", d, old, "pending_review", f"new version {vn.strip()}")
                    audit(s, user, "new_version", "documents", d.id, d.doc_code, new={"version": vn.strip()})
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
    st.divider()
    attachments_panel(s, user, "documents", "documents", d, "dc")
    for r in s.scalars(select(Review).where(Review.document_id == d.id, Review.archived.is_(False))):
        st.button(f"🔗 {r.reference} · {r.title}", key=f"dc_rv_{r.id}", on_click=goto, args=("reviews", "reviews", r.id))


# ---- Process validation -----------------------------------------------------
def val_fields():
    return [F("process_id", "العملية", "Process", "fk", req=True, fk=P_FK),
            F("department_id", "القسم", "Department", "fk", req=True, fk=D_FK),
            F("owner_id", "مالك العملية", "Process owner", "fk", fk=E_FK), F("reviewer_id", "المراجع", "Reviewer", "fk", fk=E_FK),
            F("responsible_role", "الدور المسؤول", "Responsible role"),
            F("document_id", "SOP / السياسة", "SOP / policy", "fk", fk=(Document, "title")),
            F("checklist_id", "قائمة التحقق", "Checklist", "fk", fk=(Checklist, "title")),
            F("criteria", "معايير التحقق", "Validation criteria", "area"), F("expected_result", "النتيجة المتوقعة", "Expected result", "area"),
            F("actual_result", "النتيجة الفعلية", "Actual result", "area"), F("deviations", "الانحرافات", "Deviations", "area"),
            F("reviewer_comments", "تعليقات المراجع", "Reviewer comments", "area"),
            F("risk_level", "مستوى المخاطر", "Risk level", "select", req=True, opts=PRIORITIES, default="low"),
            F("score", "الدرجة (0-100)", "Score (0-100)", "float"), F("validation_date", "تاريخ التحقق", "Validation date", "date"),
            F("next_validation_date", "تاريخ التحقق القادم", "Next validation", "date"),
            F("decision", "القرار", "Decision", "select", req=True, opts=["pending", "validated", "validated_with_deviations", "not_validated"], default="pending")]


def v_val(s, values, rid):
    errs = []
    sc, dec = values.get("score"), values.get("decision")
    if isinstance(sc, float) and not 0 <= sc <= 100:
        errs.append(L("الدرجة بين 0 و 100", "Score must be between 0 and 100"))
    p = s.get(Process, values.get("process_id")) if values.get("process_id") else None
    if p and values.get("department_id") and p.department_id != values["department_id"]:
        errs.append(L("العملية تتبع قسماً آخر", "The process belongs to another department"))
    if dec != "pending":
        if not values.get("validation_date"):
            errs.append(L("تاريخ التحقق مطلوب للقرار", "Validation date is required for a decision"))
        if not isinstance(sc, float):
            errs.append(L("الدرجة مطلوبة للقرار", "A score is required for a decision"))
    if dec == "validated" and (values.get("deviations") or (isinstance(sc, float) and sc < 80)):
        errs.append(L("لا يمكن «تم التحقق» مع انحرافات أو درجة أقل من 80", "Cannot be 'Validated' with deviations or a score below 80"))
    if dec in ("validated_with_deviations", "not_validated") and not values.get("deviations"):
        errs.append(L("وصف الانحرافات مطلوب", "Deviations must be described"))
    errs += v_dates("validation_date", "next_validation_date", "التحقق القادم قبل الحالي", "Next validation precedes current")(values)
    return errs


def val_on_save(s, user, v, is_new):
    p = s.get(Process, v.process_id)
    if v.validation_date and not v.next_validation_date and p and p.validation_interval_days:
        v.next_validation_date = v.validation_date + timedelta(days=p.validation_interval_days)


def val_extra(s, user, v):
    p = s.get(Process, v.process_id)
    st.markdown(f"**{L('سجل التحقق للعملية', 'Validation history for this process')}**: {p.name if p else ''}")
    hist = list(s.scalars(select(ProcessValidation).where(ProcessValidation.process_id == v.process_id,
                                                          ProcessValidation.archived.is_(False)).order_by(ProcessValidation.id.desc())))
    st.dataframe(pd.DataFrame([{L("المرجع", "Reference"): h.reference, L("التاريخ", "Date"): h.validation_date,
                                L("الدرجة", "Score"): h.score, L("القرار", "Decision"): lab(h.decision)} for h in hist]),
                 hide_index=True, use_container_width=True)
    linked = list(s.scalars(select(Capa).where(Capa.validation_id == v.id, Capa.archived.is_(False))))
    for c in linked:
        st.button(f"{c.reference} · {c.title}", key=f"vl_c_{c.id}", on_click=goto, args=("capa", "capa", c.id))
    if v.decision in ("not_validated", "validated_with_deviations") and not linked and can(user, "capa", "create"):
        if st.button(L("➕ فتح إجراء تصحيحي", "➕ Open corrective action"), key=f"vl_nc_{v.id}"):
            c = Capa(reference=next_ref(s, "NC"), title=f"NC - {v.reference}", validation_id=v.id, process_id=v.process_id,
                     department_id=v.department_id, description=v.deviations, severity=v.risk_level,
                     action_owner_id=v.owner_id)
            s.add(c)
            s.flush()
            audit(s, user, "create", "capa", c.id, c.reference, new={"from_validation": v.reference})
            goto("capa", "capa", c.id)
            st.rerun()
    attachments_panel(s, user, "validations", "validations", v, "vl")


# ---- CAPA ------------------------------------------------------------------------
def capa_fields():
    return [F("title", "العنوان", "Title", req=True), F("department_id", "القسم", "Department", "fk", req=True, fk=D_FK),
            F("review_id", "المراجعة", "Review", "fk", fk=(Review, "reference")), F("process_id", "العملية", "Process", "fk", fk=P_FK),
            F("validation_id", "التحقق", "Validation", "fk", fk=(ProcessValidation, "reference")),
            F("severity", "الخطورة", "Severity", "select", req=True, opts=PRIORITIES, default="medium"),
            F("root_cause_category", "تصنيف السبب الجذري", "Root-cause category", "select", opts=get_list("root_causes")),
            F("action_owner_id", "مسؤول الإجراء", "Action owner", "fk", fk=E_FK), F("target_date", "التاريخ المستهدف", "Target date", "date"),
            F("description", "الوصف", "Description", "area"), F("root_cause", "السبب الجذري", "Root cause", "area"),
            F("impact", "الأثر", "Impact", "area"), F("risk_assessment", "تقييم المخاطر", "Risk assessment", "area"),
            F("immediate_correction", "التصحيح الفوري", "Immediate correction", "area"),
            F("corrective_action", "الإجراء التصحيحي", "Corrective action", "area"),
            F("preventive_action", "الإجراء الوقائي", "Preventive action", "area"),
            F("implementation_evidence", "دليل التنفيذ", "Implementation evidence", "area"),
            F("verification_notes", "ملاحظات التحقق", "Verification notes", "area"),
            F("effectiveness_result", "نتيجة الفعالية", "Effectiveness result", "select", opts=["effective", "ineffective"]),
            F("effectiveness_notes", "ملاحظات الفعالية", "Effectiveness notes", "area")]


def capa_guard(s, user, c, to, note):
    errs = []
    deny = L("ليست لديك صلاحية لهذا الانتقال", "You are not permitted to make this transition")
    if not can(user, "capa", "update"):
        errs.append(deny)
    n_att = s.scalar(select(func.count(Attachment.id)).where(Attachment.entity_type == "capa", Attachment.entity_id == c.id,
                                                             Attachment.archived.is_(False)))
    if to == "assigned" and (not c.action_owner_id or not c.target_date):
        errs.append(L("المسؤول والتاريخ المستهدف مطلوبان", "Action owner and target date are required"))
    if to == "in_progress" and c.status == "assigned" and not (c.corrective_action or "").strip():
        errs.append(L("الإجراء التصحيحي مطلوب", "Corrective action is required"))
    if to == "awaiting_qa_verification" and not ((c.implementation_evidence or "").strip() or n_att):
        errs.append(L("دليل التنفيذ مطلوب (نص أو مرفق)", "Implementation evidence (text or attachment) is required"))
    if to == "effectiveness_review":
        if not can(user, "capa", "approve"):
            errs.append(deny)
        if not (c.verification_notes or "").strip():
            errs.append(L("ملاحظات التحقق مطلوبة", "Verification notes are required"))
        if not errs:
            c.verified_by_id, c.verified_at = user.id, now()
    if to == "closed":
        if not can(user, "capa", "close"):
            errs.append(deny)
        if not c.verified_by_id:
            errs.append(L("لم يتم تحقق الجودة بعد", "QA verification has not been completed"))
        if c.effectiveness_result != "effective":
            errs.append(L("يجب أن تكون نتيجة الفعالية «فعّال»", "Effectiveness result must be 'Effective'"))
        if not note:
            errs.append(L("ملاحظة الإغلاق مطلوبة", "A closing note is required"))
        if not errs:
            c.qa_approved_by_id, c.qa_approved_at, c.closure_date = user.id, now(), date.today()
    if to == "rejected":
        if not can(user, "capa", "approve"):
            errs.append(deny)
        if not note:
            errs.append(L("سبب الرفض مطلوب", "Rejection reason is required"))
        elif not errs:
            c.rejection_reason = note
    return errs


def capa_extra(s, user, c):
    workflow_panel(s, user, CFGS["capa"], c, CAPA_FLOW, capa_guard, "cp")
    if c.target_date and c.target_date < date.today() and c.status not in ("closed", "rejected"):
        st.error(L(f"⚠ متأخر {(date.today() - c.target_date).days} يوم", f"⚠ Overdue by {(date.today() - c.target_date).days} days"))
    st.divider()
    attachments_panel(s, user, "capa", "capa", c, "cp")
    for lbl, M, rid, pg in ((L("المراجعة", "Review"), Review, c.review_id, "reviews"),
                            (L("التحقق", "Validation"), ProcessValidation, c.validation_id, "validations")):
        if rid:
            o = s.get(M, rid)
            st.button(f"🔗 {lbl}: {o.reference}", key=f"cp_l_{pg}_{rid}", on_click=goto, args=(pg, pg, rid))
    if can(user, "tasks", "create") and st.button(L("➕ مهمة مرتبطة", "➕ Linked task"), key=f"cp_task_{c.id}"):
        t = Task(reference=next_ref(s, "TK"), title=f"CAPA: {c.title}"[:300], capa_id=c.id, assignee_id=c.action_owner_id,
                 due_date=c.target_date, created_by_id=user.id)
        s.add(t)
        s.flush()
        goto("tasks", "tasks", t.id)
        st.rerun()


def capa_on_save(s, user, c, is_new):
    if is_new:
        c.status = "open"
    if c.action_owner_id:
        notify_employee(s, c.action_owner_id, "assignment", f"إجراء تصحيحي: {c.title}", c.reference, "capa", c.id,
                        f"capa:{c.id}:owner:{c.action_owner_id}")


# ---- Tasks -----------------------------------------------------------------------
def task_fields():
    return [F("title", "العنوان", "Title", req=True), F("assignee_id", "المسؤول", "Assignee", "fk", fk=E_FK),
            F("priority", "الأولوية", "Priority", "select", req=True, opts=PRIORITIES, default="medium"),
            F("status", "الحالة", "Status", "select", req=True, opts=["todo", "in_progress", "blocked", "done", "cancelled"], default="todo"),
            F("start_date", "تاريخ البدء", "Start date", "date"), F("due_date", "تاريخ الاستحقاق", "Due date", "date"),
            F("reminder_date", "تاريخ التذكير", "Reminder date", "date"), F("percent_complete", "نسبة الإنجاز", "Completion %", "int", default=0),
            F("review_id", "المراجعة", "Review", "fk", fk=(Review, "reference")), F("document_id", "المستند", "Document", "fk", fk=(Document, "title")),
            F("capa_id", "عدم المطابقة", "Nonconformity", "fk", fk=(Capa, "reference")),
            F("description", "الوصف", "Description", "area")]


def v_task(s, values, rid):
    errs = v_dates("start_date", "due_date", "الاستحقاق قبل البدء", "Due date precedes start date")(values)
    pc = values.get("percent_complete")
    if isinstance(pc, int) and not 0 <= pc <= 100:
        errs.append(L("النسبة بين 0 و 100", "Percent must be 0–100"))
    return errs


def task_on_save(s, user, t, is_new):
    if t.status == "done":
        t.percent_complete, t.completed_at = 100, t.completed_at or now()
    elif t.completed_at:
        t.completed_at = None
    notify_employee(s, t.assignee_id, "assignment", f"مهمة جديدة: {t.title}", t.reference, "tasks", t.id,
                    f"task:{t.id}:assign:{t.assignee_id}")


def task_extra(s, user, t):
    for lbl, M, rid, pg in ((L("المراجعة", "Review"), Review, t.review_id, "reviews"), (L("المستند", "Document"), Document, t.document_id, "documents"),
                            ("CAPA", Capa, t.capa_id, "capa")):
        if rid:
            o = s.get(M, rid)
            st.button(f"🔗 {lbl}: {getattr(o, 'reference', None) or o.doc_code}", key=f"tk_l_{pg}_{rid}", on_click=goto, args=(pg, pg, rid))


def move_task(tid, status, user_id):
    user = load_user(user_id)
    try:
        require(user, "tasks", "update")
        with S() as s:
            t = fetch_one(s, user, Task, tid)
            if t:
                old = t.status
                t.status = status
                task_on_save(s, user, t, False)
                log_status(s, user, "tasks", t, old, status)
    except PermissionError:
        st.session_state["flash_error"] = True


def tasks_page(user):
    mode = st.radio("view", ["list", "kanban", "calendar"], horizontal=True, key="tasks_mode", label_visibility="collapsed",
                    format_func=lambda m: {"list": L("قائمة", "List"), "kanban": L("كانبان", "Kanban"), "calendar": L("تقويم", "Calendar")}[m])
    if st.session_state.pop("flash_error", None):
        st.error(L("ليست لديك صلاحية", "Not permitted"))
    if mode == "list":
        crud_page(CFGS["tasks"], user)
        return
    with S() as s:
        tasks = fetch(s, user, Task)
        emp = _lookup(s, {}, Employee, "full_name")
        if mode == "kanban":
            cols = st.columns(4)
            flow = ["todo", "in_progress", "blocked", "done"]
            for i, stt in enumerate(flow):
                with cols[i]:
                    st.markdown(f"**{lab(stt)}** ({sum(1 for t in tasks if t.status == stt)})")
                    for t in [t for t in tasks if t.status == stt][:30]:
                        late = t.due_date and t.due_date < date.today() and stt != "done"
                        st.markdown(f'<div class="card"><b>{esc(t.title)}</b><br><small>{esc(emp.get(t.assignee_id, ""))} · '
                                    f'{t.due_date or ""} {"⚠" if late else ""}</small></div>', unsafe_allow_html=True)
                        b1, b2, b3 = st.columns(3)
                        if i > 0:
                            b1.button("◀", key=f"kb_l_{t.id}", on_click=move_task, args=(t.id, flow[i - 1], user.id))
                        if i < 3:
                            b2.button("▶", key=f"kb_r_{t.id}", on_click=move_task, args=(t.id, flow[i + 1], user.id))
                        b3.button("↗", key=f"kb_o_{t.id}", on_click=goto, args=("tasks", "tasks", t.id))
        else:
            rows = [{L("التاريخ", "Date"): t.due_date, L("المهمة", "Task"): t.title, L("المسؤول", "Assignee"): emp.get(t.assignee_id, ""),
                     L("الحالة", "Status"): lab(t.status), "⚠": "⚠" if t.due_date and t.due_date < date.today() and t.status not in ("done", "cancelled") else ""}
                    for t in tasks if t.due_date]
            if rows:
                st.dataframe(pd.DataFrame(rows).sort_values(L("التاريخ", "Date")), hide_index=True, use_container_width=True)
            else:
                st.info(L("لا توجد مهام بتواريخ", "No dated tasks"))


# ---- KPIs --------------------------------------------------------------------
def kpi_fields():
    return [F("code", "الكود", "Code", req=True), F("name", "اسم المؤشر", "KPI name", req=True),
            F("department_id", "القسم", "Department", "fk", fk=D_FK), F("process_id", "العملية", "Process", "fk", fk=P_FK),
            F("owner_id", "المالك", "Owner", "fk", fk=E_FK), F("unit", "الوحدة", "Unit", req=True, default="%"),
            F("target", "المستهدف", "Target", "float", req=True),
            F("higher_is_better", "الأعلى أفضل", "Higher is better", "bool", default=True),
            F("warning_threshold", "حد التحذير (0-1 من المستهدف)", "Warning threshold (0–1 of target)", "float", default=0.9),
            F("frequency", "التكرار", "Frequency", "select", req=True, opts=["monthly", "quarterly", "annual"], default="monthly"),
            F("calculation_method", "معادلة الحساب (مثال: passed / total * 100)", "Formula (e.g. passed / total * 100)"),
            F("description", "الوصف", "Description", "area"), F("notes", "ملاحظات", "Notes", "area"),
            F("active", "نشط", "Active", "bool", default=True)]


def v_kpi(s, values, rid):
    errs = []
    t = values.get("target")
    if isinstance(t, float) and t <= 0:
        errs.append(L("المستهدف يجب أن يكون أكبر من صفر", "Target must be greater than zero"))
    w = values.get("warning_threshold")
    if isinstance(w, float) and not 0 < w <= 1:
        errs.append(L("حد التحذير بين 0 و 1", "Warning threshold must be between 0 and 1"))
    f = values.get("calculation_method")
    if f:
        try:
            safe_eval(f, {n: 1.0 for n in formula_vars(f)})
        except (_FormulaError, SyntaxError):
            errs.append(L("المعادلة غير صالحة (+ - * / وأقواس فقط)", "Invalid formula (only + - * / and parentheses)"))
    return errs


def kpi_extra(s, user, k):
    vals = list(s.scalars(select(KPIValue).where(KPIValue.kpi_id == k.id).order_by(KPIValue.period_start)))
    if vals:
        df = pd.DataFrame([{"period": v.period_start.strftime("%Y-%m"), "actual": v.actual, "target": k.target} for v in vals]).set_index("period")
        st.line_chart(df)
        last = vals[-1]
        st.markdown(f"{L('آخر حالة', 'Latest status')}: {badge(kpi_status(last.actual, k.target, k.higher_is_better, k.warning_threshold))}",
                    unsafe_allow_html=True)
        st.dataframe(pd.DataFrame([{L("الفترة", "Period"): f"{v.period_start} → {v.period_end}", L("الفعلي", "Actual"): round(v.actual, 2),
                                    L("الإنجاز %", "Achievement %"): round((v.actual / k.target if k.higher_is_better else k.target / v.actual if v.actual else 0) * 100, 1),
                                    L("الحالة", "Status"): lab(kpi_status(v.actual, k.target, k.higher_is_better, k.warning_threshold)),
                                    L("ملاحظات", "Notes"): v.notes} for v in reversed(vals)]), hide_index=True, use_container_width=True)
    else:
        st.info(L("لا توجد قيم مسجلة بعد.", "No values recorded yet."))
    if not can(user, "kpis", "update"):
        return
    st.markdown(f"**{L('تسجيل قيمة', 'Record a value')}**")
    c1, c2 = st.columns(2)
    year = c1.number_input(L("السنة", "Year"), 2000, 2100, date.today().year, key=f"kv_y_{k.id}")
    idx = 1
    if k.frequency == "monthly":
        idx = c2.number_input(L("الشهر", "Month"), 1, 12, date.today().month, key=f"kv_m_{k.id}")
    elif k.frequency == "quarterly":
        idx = c2.number_input(L("الربع", "Quarter"), 1, 4, (date.today().month - 1) // 3 + 1, key=f"kv_q_{k.id}")
    with st.form(f"kv_form_{k.id}"):
        inputs = {}
        if k.calculation_method:
            for n in formula_vars(k.calculation_method):
                inputs[n] = st.text_input(n, key=f"kv_in_{k.id}_{n}")
            actual_txt = ""
        else:
            actual_txt = st.text_input(L("القيمة الفعلية", "Actual value"), key=f"kv_a_{k.id}")
        notes = st.text_input(L("ملاحظات", "Notes"), key=f"kv_n_{k.id}")
        go = st.form_submit_button(L("حفظ القيمة", "Save value"), type="primary")
    if go:
        try:
            if k.calculation_method:
                actual = safe_eval(k.calculation_method, {n: float(v) for n, v in inputs.items()})
            else:
                actual = float(actual_txt)
            if not math.isfinite(actual) or actual < 0 or (k.unit == "%" and actual > 100):
                raise ValueError
        except (ValueError, _FormulaError):
            st.error(L("قيمة غير صالحة (رقم ≥ 0، وللنسبة ≤ 100)", "Invalid value (number ≥ 0; ≤ 100 for %)"))
            return
        ps, pe = period_bounds(k.frequency, int(year), int(idx))
        ex = next((v for v in vals if v.period_start == ps), None)
        if ex:
            ex.actual, ex.notes, ex.recorded_by_id = actual, notes, user.id
        else:
            s.add(KPIValue(kpi_id=k.id, period_start=ps, period_end=pe, actual=actual, notes=notes, recorded_by_id=user.id))
        audit(s, user, "kpi_value", "kpis", k.id, k.code, new={"period": str(ps), "actual": actual})
        st.rerun()


# ---- Checklists --------------------------------------------------------------------
def chk_fields():
    return [F("code", "الكود", "Code", req=True), F("title", "العنوان", "Title", req=True),
            F("department_id", "القسم", "Department", "fk", fk=D_FK), F("process_id", "العملية", "Process", "fk", fk=P_FK),
            F("pass_threshold", "حد النجاح %", "Pass threshold %", "float", req=True, default=80.0),
            F("active", "نشطة", "Active", "bool", default=True), F("description", "الوصف", "Description", "area")]


def v_chk(s, values, rid):
    t = values.get("pass_threshold")
    return [L("حد النجاح بين 0 و 100", "Threshold must be 0–100")] if isinstance(t, float) and not 0 <= t <= 100 else []


_ITEM_COLS = ("sequence", "question", "criteria", "question_type", "choices", "is_mandatory", "evidence_required", "weight", "max_score", "is_scored")
_QTYPES = ["yes_no", "pass_fail", "multiple_choice", "numeric_score", "text", "date", "evidence_required"]


def chk_extra(s, user, c):
    st.caption(f"{L('الإصدار', 'Version')}: {c.version}")
    used = s.scalar(select(func.count(ReviewAnswer.id)).join(ChecklistItem, ReviewAnswer.item_id == ChecklistItem.id)
                    .where(ChecklistItem.checklist_id == c.id))
    can_edit = can(user, "checklists", "update") and not used
    if used:
        st.info(L("هذه القائمة مستخدمة في مراجعات؛ أنشئ إصداراً جديداً للتعديل.", "This checklist is used in reviews; create a new version to change it."))
    df = pd.DataFrame([{k: getattr(i, k) for k in _ITEM_COLS} for i in c.items])
    if df.empty:
        df = pd.DataFrame({"sequence": pd.Series(dtype="int"), "question": pd.Series(dtype="str"), "criteria": pd.Series(dtype="str"),
                           "question_type": pd.Series(dtype="str"), "choices": pd.Series(dtype="str"),
                           "is_mandatory": pd.Series(dtype="bool"), "evidence_required": pd.Series(dtype="bool"),
                           "weight": pd.Series(dtype="float"), "max_score": pd.Series(dtype="float"), "is_scored": pd.Series(dtype="bool")})
    st.caption(L("الاختيار المتعدد: سطر لكل خيار، ويمكن إضافة نقاط هكذا «جيد:1» أو «مقبول:0.5».",
                 "Multiple choice: one option per line, optionally with credit like 'Good:1' or 'Fair:0.5'."))
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True, disabled=not can_edit, key=f"chk_ed_{c.id}",
                            column_config={"question_type": st.column_config.SelectboxColumn(options=_QTYPES)})
    if can_edit and st.button(L("حفظ البنود", "Save items"), type="primary", key=f"chk_save_{c.id}"):
        errs, rows = [], []
        for n, r in edited.iterrows():
            q = str(r.get("question") or "").strip()
            if not q or q == "nan":
                continue
            qt = r.get("question_type") if isinstance(r.get("question_type"), str) else "yes_no"
            if qt not in _QTYPES:
                errs.append(f"#{n + 1}: invalid type")
            if qt == "multiple_choice" and len(parse_choices(r.get("choices"))) < 2:
                errs.append(f"#{n + 1}: " + L("خياران على الأقل", "at least two choices"))
            w = float(r.get("weight") if pd.notna(r.get("weight")) else 1.0)
            ms = float(r.get("max_score") if pd.notna(r.get("max_score")) else 1.0)
            if w <= 0 or ms <= 0:
                errs.append(f"#{n + 1}: " + L("الوزن والدرجة العظمى > 0", "weight and max score must be > 0"))
            seq = int(r.get("sequence")) if pd.notna(r.get("sequence")) else (n + 1) * 10
            crit = r.get("criteria") if isinstance(r.get("criteria"), str) else ""
            chs = r.get("choices") if isinstance(r.get("choices"), str) else ""
            flag = lambda name, dflt: bool(r.get(name)) if pd.notna(r.get(name)) else dflt  # noqa: E731
            rows.append(ChecklistItem(sequence=seq, question=q, criteria=crit, question_type=qt, choices=chs,
                                      is_mandatory=flag("is_mandatory", True), evidence_required=flag("evidence_required", False),
                                      weight=w, max_score=ms, is_scored=flag("is_scored", True)))
        if errs:
            for e in errs:
                st.error(e)
        else:
            c.items.clear()
            s.flush()
            c.items.extend(rows)
            audit(s, user, "items_saved", "checklists", c.id, c.code, new={"count": len(rows)})
            st.success(L("تم حفظ البنود", "Items saved"))
            st.rerun()
    if can(user, "checklists", "create"):
        c1, c2 = st.columns(2)
        if c1.button(L("نسخ كقالب جديد", "Duplicate as new template"), key=f"chk_dup_{c.id}"):
            n = Checklist(code=f"{c.code}-COPY-{uuid.uuid4().hex[:4].upper()}", version=1, title=f"{c.title} (copy)", description=c.description,
                          department_id=c.department_id, process_id=c.process_id, pass_threshold=c.pass_threshold)
            n.items = [ChecklistItem(**{k: getattr(i, k) for k in _ITEM_COLS}) for i in c.items]
            s.add(n)
            s.flush()
            audit(s, user, "duplicate", "checklists", n.id, n.code)
            goto("checklists", "checklists", n.id)
            st.rerun()
        if c2.button(L("إنشاء إصدار جديد", "Create new version"), key=f"chk_ver_{c.id}"):
            top = s.scalar(select(func.max(Checklist.version)).where(Checklist.code == c.code)) or 1
            n = Checklist(code=c.code, version=top + 1, title=c.title, description=c.description, department_id=c.department_id,
                          process_id=c.process_id, pass_threshold=c.pass_threshold)
            n.items = [ChecklistItem(**{k: getattr(i, k) for k in _ITEM_COLS}) for i in c.items]
            s.add(n)
            c.active = False
            s.flush()
            audit(s, user, "new_version", "checklists", n.id, n.code, new={"version": n.version})
            goto("checklists", "checklists", n.id)
            st.rerun()


# ---- Employees profile / portal projects / news -----------------------------------
def emp_extra(s, user, e):
    c = lambda M, *w: s.scalar(select(func.count(M.id)).where(*w))  # noqa: E731
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        card(L("مهام مفتوحة", "Open tasks"), c(Task, Task.assignee_id == e.id, Task.status.notin_(["done", "cancelled"]), Task.archived.is_(False)))
    with k2:
        card(L("مراجعات كمراجع", "Reviews as reviewer"), c(Review, Review.reviewer_id == e.id, Review.archived.is_(False)))
    with k3:
        card(L("مراجعات تخصه", "Reviews as responsible"), c(Review, Review.responsible_id == e.id, Review.archived.is_(False)))
    with k4:
        card(L("إجراءات CAPA مفتوحة", "Open CAPAs"), c(Capa, Capa.action_owner_id == e.id, Capa.status.notin_(["closed", "rejected"]), Capa.archived.is_(False)))
    done = c(Task, Task.assignee_id == e.id, Task.status == "done")
    tot = c(Task, Task.assignee_id == e.id, Task.status != "cancelled")
    st.caption(L(f"معدل إنجاز المهام: {round(done / tot * 100) if tot else 0}%", f"Task completion rate: {round(done / tot * 100) if tot else 0}%"))


def proj_fields():
    return [F("name", "اسم المشروع", "Project name", req=True), F("title", "العنوان", "Title"), F("category", "التصنيف", "Category", default="عام"),
            F("url", "رابط الداشبورد", "Dashboard URL", req=True), F("embed_url", "رابط التضمين (اختياري)", "Embed URL (optional)"),
            F("description", "الوصف", "Description", "area")]


def v_proj(s, values, rid):
    errs = []
    for n in ("url", "embed_url"):
        if values.get(n) and not safe_url(values[n]):
            errs.append(L("الرابط يجب أن يبدأ بـ http(s)", "URL must start with http(s)"))
    return errs


def proj_extra(s, user, p):
    url, embed = safe_url(p.url), safe_url(p.embed_url) or to_embed_url(p.url)
    if url:
        st.markdown(f'<a class="btn-link" href="{esc(url, quote=True)}" target="_blank" rel="noopener">{L("فتح في تبويب جديد", "Open in new tab")}</a>',
                    unsafe_allow_html=True)
    attachments_panel(s, user, "portal", "portal_project", p, "pj")
    if embed:
        st.components.v1.iframe(embed, height=780, scrolling=True)
        st.caption(L("لو لم يظهر التقرير فعّل Embed من Looker Studio أو افتحه في تبويب جديد.",
                     "If the report does not appear, enable embedding in Looker Studio or open it in a new tab."))


def news_fields():
    return [F("title", "العنوان", "Title", req=True), F("image_url", "رابط الصورة", "Image URL"), F("content", "النص", "Content", "area", req=True)]


CFGS = {
    "departments": Cfg("departments", "org", Department, ("الأقسام", "Departments"), dept_fields,
                       [("الكود", "Code", "code", None), ("الاسم", "Name", "name", None), ("نشط", "Active", "active", "bool")],
                       ref_field="code", name_attr="name"),
    "employees": Cfg("employees", "org", Employee, ("الموظفون", "Employees"), emp_fields,
                     [("الرقم", "No.", "employee_no", None), ("الاسم", "Name", "full_name", None), ("القسم", "Department", "department_id", (Department, "name")),
                      ("المسمى", "Job title", "job_title", None), ("نشط", "Active", "active", "bool")],
                     ref_field="employee_no", name_attr="full_name", extra=emp_extra),
    "processes": Cfg("processes", "org", Process, ("العمليات", "Processes"), proc_fields,
                     [("المرجع", "Ref", "reference", None), ("العملية", "Process", "name", None), ("القسم", "Department", "department_id", (Department, "name")),
                      ("المالك", "Owner", "owner_id", (Employee, "full_name")), ("SLA", "SLA h", "sla_hours", None)],
                     ref_prefix="PR", name_attr="name", validate=v_proc),
    "reviews": Cfg("reviews", "reviews", Review, ("مراجعات الجودة", "QA Reviews"), review_fields,
                   [("المرجع", "Ref", "reference", None), ("العنوان", "Title", "title", None), ("القسم", "Department", "department_id", (Department, "name")),
                    ("المراجع", "Reviewer", "reviewer_id", (Employee, "full_name")), ("الحالة", "Status", "status", "status"),
                    ("الأولوية", "Priority", "priority", "status"), ("الاستحقاق", "Due", "due_date", None), ("الدرجة", "Score", "compliance_score", None)],
                   ref_prefix="QR", validate=v_review, extra=review_extra, on_save=review_on_save,
                   overdue=("due_date", ["passed", "failed", "closed", "cancelled"])),
    "documents": Cfg("documents", "documents", Document, ("مراقبة المستندات", "Document Control"), doc_fields,
                     [("الكود", "Code", "doc_code", None), ("العنوان", "Title", "title", None), ("النوع", "Category", "category", None),
                      ("القسم", "Department", "department_id", (Department, "name")), ("الإصدار", "Version", "current_version_no", None),
                      ("الحالة", "Status", "status", "status"), ("المراجعة", "Review", "review_date", None), ("الانتهاء", "Expires", "expiration_date", None)],
                     ref_field="doc_code", validate=v_doc, extra=doc_extra, on_save=doc_on_save),
    "validations": Cfg("validations", "validations", ProcessValidation, ("التحقق من العمليات", "Process Validation"), val_fields,
                       [("المرجع", "Ref", "reference", None), ("العملية", "Process", "process_id", (Process, "name")),
                        ("القسم", "Department", "department_id", (Department, "name")), ("القرار", "Decision", "decision", "status"),
                        ("المخاطر", "Risk", "risk_level", "status"), ("الدرجة", "Score", "score", None), ("التالي", "Next", "next_validation_date", None)],
                       ref_prefix="PV", name_attr="reference", validate=v_val, extra=val_extra, on_save=val_on_save),
    "capa": Cfg("capa", "capa", Capa, ("عدم المطابقة والإجراءات التصحيحية", "Nonconformities & CAPA"), capa_fields,
                [("المرجع", "Ref", "reference", None), ("العنوان", "Title", "title", None), ("القسم", "Department", "department_id", (Department, "name")),
                 ("الخطورة", "Severity", "severity", "status"), ("المسؤول", "Owner", "action_owner_id", (Employee, "full_name")),
                 ("الحالة", "Status", "status", "status"), ("المستهدف", "Target", "target_date", None)],
                ref_prefix="NC", extra=capa_extra, on_save=capa_on_save, overdue=("target_date", ["closed", "rejected"])),
    "tasks": Cfg("tasks", "tasks", Task, ("المهام والمتابعات", "Tasks & Follow-ups"), task_fields,
                 [("المرجع", "Ref", "reference", None), ("المهمة", "Task", "title", None), ("المسؤول", "Assignee", "assignee_id", (Employee, "full_name")),
                  ("الأولوية", "Priority", "priority", "status"), ("الحالة", "Status", "status", "status"), ("الاستحقاق", "Due", "due_date", None),
                  ("%", "%", "percent_complete", None)],
                 ref_prefix="TK", validate=v_task, extra=task_extra, on_save=task_on_save, overdue=("due_date", ["done", "cancelled"])),
    "kpis": Cfg("kpis", "kpis", KPI, ("مؤشرات الأداء", "KPI Management"), kpi_fields,
                [("الكود", "Code", "code", None), ("المؤشر", "KPI", "name", None), ("القسم", "Department", "department_id", (Department, "name")),
                 ("المستهدف", "Target", "target", None), ("الوحدة", "Unit", "unit", None), ("التكرار", "Frequency", "frequency", "status")],
                ref_field="code", name_attr="name", validate=v_kpi, extra=kpi_extra),
    "checklists": Cfg("checklists", "checklists", Checklist, ("قوائم الفحص والقوالب", "Checklists & Templates"), chk_fields,
                      [("الكود", "Code", "code", None), ("الإصدار", "Ver", "version", None), ("العنوان", "Title", "title", None),
                       ("القسم", "Department", "department_id", (Department, "name")), ("حد النجاح", "Threshold", "pass_threshold", None),
                       ("نشطة", "Active", "active", "bool")], ref_field="code", validate=v_chk, extra=chk_extra),
    "portal_projects": Cfg("portal_projects", "portal", PortalProject, ("المشاريع والتقارير", "Projects & Reports"), proj_fields,
                           [("الاسم", "Name", "name", None), ("التصنيف", "Category", "category", None), ("العنوان", "Title", "title", None)],
                           ref_field="name", name_attr="title", validate=v_proj, extra=proj_extra),
    "news": Cfg("news", "portal", News, ("الأخبار", "News"), news_fields,
                [("العنوان", "Title", "title", None)], ref_field="title", name_attr="title"),
}


# =============================================================================
# 12. DASHBOARD, REPORTS, KNOWLEDGE CENTER, NOTIFICATIONS, AUDIT, ADMIN
# =============================================================================
def show_bar(df, group_col, value_col, agg="mean"):
    if df.empty:
        st.caption(L("لا بيانات", "No data"))
    else:
        st.bar_chart(getattr(df.groupby(group_col)[value_col], agg)())


def dashboard_page(user):
    st.subheader(L("لوحة المؤشرات التنفيذية", "Executive Dashboard"))
    with S() as s:
        depts = {d.id: d.name for d in fetch(s, user, Department)}
        c1, c2, c3 = st.columns(3)
        rng = c1.date_input(L("الفترة", "Date range"), (date.today() - timedelta(days=365), date.today()), key="dash_rng")
        dsel = c2.multiselect(L("الأقسام", "Departments"), list(depts), format_func=lambda i: depts[i], key="dash_dept")
        ssel = c3.multiselect(L("الحالات", "Statuses"), list(REVIEW_FLOW), format_func=lab, key="dash_stat")
        start, end = (rng[0], rng[1]) if isinstance(rng, (list, tuple)) and len(rng) == 2 else (date.min, date.max)
        revs = [r for r in fetch(s, user, Review) if start <= (r.review_date or r.created_at.date()) <= end
                and (not dsel or r.department_id in dsel) and (not ssel or r.status in ssel)]
        docs = [d for d in fetch(s, user, Document) if not dsel or d.department_id in dsel]
        capas = [c for c in fetch(s, user, Capa) if not dsel or c.department_id in dsel]
        tasks = fetch(s, user, Task)
        procs = [p for p in fetch(s, user, Process) if not dsel or p.department_id in dsel]
        vals = fetch(s, user, ProcessValidation)
        kpis = fetch(s, user, KPI)
        emp = _lookup(s, {}, Employee, "full_name")
        today = date.today()
        pending_st = {"draft", "scheduled", "in_progress", "under_review", "awaiting_approval"}
        scored = [r.compliance_score for r in revs if r.status in REVIEW_DONE and r.compliance_score is not None]
        times = [(r.completed_at - r.created_at).days for r in revs if r.completed_at]
        validated_ids = {v.process_id for v in vals if v.decision in ("validated", "validated_with_deviations")
                         and (not v.next_validation_date or v.next_validation_date >= today)}
        overdue_tasks = [t for t in tasks if t.due_date and t.due_date < today and t.status not in ("done", "cancelled")]
        metrics = [
            (L("إجمالي المراجعات", "Total QA records"), len(revs)),
            (L("قيد الانتظار", "Pending reviews"), sum(r.status in pending_st for r in revs)),
            (L("مكتملة", "Completed reviews"), sum(r.status in ("passed", "closed") for r in revs)),
            (L("تحقق فاشل", "Failed validations"), sum(v.decision == "not_validated" for v in vals)),
            (L("مستندات تتطلب تعديل", "Docs requiring modification"), sum(d.status == "requires_modification" for d in docs)),
            (L("عمليات بانتظار التحقق", "Processes awaiting validation"), sum(p.id not in validated_ids and p.active for p in procs)),
            (L("نسبة الامتثال", "Compliance %"), f"{round(sum(scored) / len(scored), 1)}%" if scored else "—"),
            (L("متوسط زمن الإنجاز (يوم)", "Avg completion (days)"), round(sum(times) / len(times), 1) if times else "—"),
            (L("إجراءات تصحيحية مفتوحة", "Open corrective actions"), sum(c.status not in ("closed", "rejected") for c in capas)),
            (L("مهام متأخرة", "Overdue tasks"), len(overdue_tasks)),
        ]
        for i in range(0, len(metrics), 5):
            for col, (lbl, v) in zip(st.columns(5), metrics[i:i + 5]):
                with col:
                    card(lbl, v)
        st.caption(L("الامتثال = متوسط درجات المراجعات المكتملة (ناجحة/راسبة/مغلقة)؛ البنود بلا إجابة تُحسب صفراً.",
                     "Compliance = mean score of completed reviews (passed/failed/closed); unanswered items count as zero."))
        a, b = st.columns(2)
        with a:
            st.markdown(f"**{L('أداء الأقسام (متوسط الدرجة)', 'Department performance (avg score)')}**")
            dd = pd.DataFrame([{"dept": depts.get(r.department_id, "?"), "score": r.compliance_score} for r in revs
                               if r.compliance_score is not None])
            show_bar(dd, "dept", "score")
        with b:
            st.markdown(f"**{L('الامتثال حسب العملية', 'Process-level compliance')}**")
            pn = {p.id: p.name for p in procs}
            pp = pd.DataFrame([{"process": pn.get(r.process_id, "—"), "score": r.compliance_score} for r in revs
                               if r.compliance_score is not None and r.process_id])
            show_bar(pp, "process", "score")
        a, b = st.columns(2)
        with a:
            st.markdown(f"**{L('الاتجاه الشهري', 'Monthly trend')}**")
            mt = pd.DataFrame([{"month": (r.review_date or r.created_at.date()).strftime("%Y-%m"), "reviews": 1, "score": r.compliance_score} for r in revs])
            if mt.empty:
                st.caption(L("لا بيانات", "No data"))
            else:
                st.line_chart(mt.groupby("month").agg(reviews=("reviews", "sum"), avg_score=("score", "mean")))
        with b:
            st.markdown(f"**{L('تحقيق مؤشرات الأداء', 'KPI achievement')}**")
            rows = []
            for k in kpis:
                last = s.scalar(select(KPIValue).where(KPIValue.kpi_id == k.id).order_by(KPIValue.period_start.desc()).limit(1))
                if last:
                    rows.append({"KPI": k.name, L("الإنجاز %", "Achievement %"): round((last.actual / k.target if k.higher_is_better else (k.target / last.actual if last.actual else 0)) * 100, 1)})
            if rows:
                st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            else:
                st.caption(L("لا توجد قيم مؤشرات", "No KPI values"))
        a, b = st.columns(2)
        with a:
            st.markdown(f"**{L('عبء عمل المراجعين', 'Reviewer workload')}**")
            wl = pd.DataFrame([{"reviewer": emp.get(r.reviewer_id, "—"), "open": 1} for r in revs if r.status in pending_st])
            show_bar(wl, "reviewer", "open", "sum")
        with b:
            st.markdown(f"**{L('المواعيد القادمة (14 يوماً)', 'Upcoming deadlines (14 days)')}**")
            horizon = today + timedelta(days=14)
            up = [{L("النوع", "Type"): "Task", L("العنصر", "Item"): t.title, L("التاريخ", "Date"): t.due_date} for t in tasks if t.due_date and today <= t.due_date <= horizon and t.status not in ("done", "cancelled")]
            up += [{L("النوع", "Type"): "Review", L("العنصر", "Item"): r.title, L("التاريخ", "Date"): r.due_date} for r in revs if r.due_date and today <= r.due_date <= horizon and r.status in pending_st]
            up += [{L("النوع", "Type"): "CAPA", L("العنصر", "Item"): c.title, L("التاريخ", "Date"): c.target_date} for c in capas if c.target_date and today <= c.target_date <= horizon and c.status not in ("closed", "rejected")]
            up += [{L("النوع", "Type"): "Document", L("العنصر", "Item"): d.title, L("التاريخ", "Date"): d.review_date} for d in docs if d.review_date and today <= d.review_date <= horizon]
            if up:
                st.dataframe(pd.DataFrame(up).sort_values(L("التاريخ", "Date")), hide_index=True, use_container_width=True)
            else:
                st.caption(L("لا مواعيد قريبة", "No upcoming deadlines"))
        if can(user, "audit", "read"):
            st.markdown(f"**{L('آخر الأنشطة', 'Recent activities')}**")
            logs = s.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(10))
            st.dataframe(pd.DataFrame([{"time": a_.created_at.strftime("%Y-%m-%d %H:%M"), "user": a_.user_email, "action": a_.action,
                                        "entity": a_.entity_type, "ref": a_.record_ref} for a_ in logs]), hide_index=True, use_container_width=True)


def reports_page(user):
    st.subheader(L("التقارير والتحليلات", "Reports & Analytics"))
    names = {"reviews": L("ملخص المراجعات", "QA review summary"), "dept": L("امتثال الأقسام", "Department compliance"),
             "validation": L("نتائج التحقق من العمليات", "Process validation results"), "docs": L("امتثال المستندات", "Documentation compliance"),
             "nc_trend": L("اتجاه عدم المطابقة", "Nonconformity trends"), "capa_aging": L("أعمار الإجراءات التصحيحية", "Corrective action aging"),
             "kpi": L("تحقيق المؤشرات", "KPI achievement"), "reviewer": L("إنتاجية المراجعين", "Reviewer productivity"),
             "overdue": L("الأعمال المتأخرة", "Overdue work"), "quarter": L("مقارنة ربع سنوية", "Quarterly comparison")}
    c1, c2 = st.columns([2, 2])
    rep = c1.selectbox(L("التقرير", "Report"), list(names), format_func=lambda k: names[k])
    rng = c2.date_input(L("الفترة", "Date range"), (date.today() - timedelta(days=365), date.today()), key="rp_rng")
    start, end = (rng[0], rng[1]) if isinstance(rng, (list, tuple)) and len(rng) == 2 else (date.min, date.max)
    inr = lambda d_: d_ is not None and start <= (d_.date() if isinstance(d_, datetime) else d_) <= end  # noqa: E731
    today = date.today()
    with S() as s:
        dn, en, pn = _lookup(s, {}, Department, "name"), _lookup(s, {}, Employee, "full_name"), _lookup(s, {}, Process, "name")
        df = pd.DataFrame()
        if rep in ("reviews", "dept", "reviewer", "quarter"):
            revs = [r for r in fetch(s, user, Review) if inr(r.review_date or r.created_at)]
            base = pd.DataFrame([{"reference": r.reference, "title": r.title, "department": dn.get(r.department_id, ""), "reviewer": en.get(r.reviewer_id, ""),
                                  "status": lab(r.status), "score": r.compliance_score, "date": r.review_date or r.created_at.date(),
                                  "completed": r.status in REVIEW_DONE} for r in revs])
            if rep == "reviews":
                df = base
            elif not base.empty and rep == "dept":
                df = base.groupby("department").agg(reviews=("reference", "count"), avg_score=("score", "mean"), completed=("completed", "sum")).reset_index()
            elif not base.empty and rep == "reviewer":
                df = base.groupby("reviewer").agg(assigned=("reference", "count"), completed=("completed", "sum"), avg_score=("score", "mean")).reset_index()
            elif not base.empty:
                base["quarter"] = pd.to_datetime(base["date"]).dt.to_period("Q").astype(str)
                df = base.groupby("quarter").agg(reviews=("reference", "count"), avg_score=("score", "mean")).reset_index()
        elif rep == "validation":
            df = pd.DataFrame([{"reference": v.reference, "process": pn.get(v.process_id, ""), "department": dn.get(v.department_id, ""),
                                "date": v.validation_date, "score": v.score, "decision": lab(v.decision), "risk": lab(v.risk_level)}
                               for v in fetch(s, user, ProcessValidation) if not v.validation_date or inr(v.validation_date)])
        elif rep == "docs":
            df = pd.DataFrame([{"code": d.doc_code, "title": d.title, "department": dn.get(d.department_id, ""), "status": lab(d.status),
                                "version": d.current_version_no, "review_date": d.review_date, "expiration": d.expiration_date,
                                "review_overdue": bool(d.review_date and d.review_date < today)} for d in fetch(s, user, Document)])
        elif rep in ("nc_trend", "capa_aging"):
            cs = [c for c in fetch(s, user, Capa) if inr(c.created_at)]
            if rep == "nc_trend":
                b = pd.DataFrame([{"month": c.created_at.strftime("%Y-%m"), "severity": lab(c.severity), "count": 1, "root_cause": c.root_cause_category or "—"} for c in cs])
                df = b.pivot_table(index="month", columns="severity", values="count", aggfunc="sum", fill_value=0).reset_index() if not b.empty else b
                if not b.empty:
                    st.markdown(f"**{L('الأسباب الجذرية المتكررة', 'Recurring root causes')}**")
                    st.bar_chart(b.groupby("root_cause")["count"].sum())
            else:
                df = pd.DataFrame([{"reference": c.reference, "title": c.title, "owner": en.get(c.action_owner_id, ""), "status": lab(c.status),
                                    "age_days": (today - c.created_at.date()).days, "overdue_days": max(0, (today - c.target_date).days) if c.target_date and c.status not in ("closed", "rejected") else 0}
                                   for c in cs if c.status not in ("closed", "rejected")])
        elif rep == "kpi":
            rows = []
            for k in fetch(s, user, KPI):
                for v in s.scalars(select(KPIValue).where(KPIValue.kpi_id == k.id)):
                    if inr(v.period_start):
                        rows.append({"kpi": k.name, "period": v.period_start, "target": k.target, "actual": v.actual,
                                     "status": lab(kpi_status(v.actual, k.target, k.higher_is_better, k.warning_threshold))})
            df = pd.DataFrame(rows)
        elif rep == "overdue":
            rows = [{"type": "Task", "ref": t.reference, "title": t.title, "owner": en.get(t.assignee_id, ""), "due": t.due_date, "days_late": (today - t.due_date).days}
                    for t in fetch(s, user, Task) if t.due_date and t.due_date < today and t.status not in ("done", "cancelled")]
            rows += [{"type": "Review", "ref": r.reference, "title": r.title, "owner": en.get(r.reviewer_id, ""), "due": r.due_date, "days_late": (today - r.due_date).days}
                     for r in fetch(s, user, Review) if r.due_date and r.due_date < today and r.status not in ("passed", "failed", "closed", "cancelled")]
            rows += [{"type": "CAPA", "ref": c.reference, "title": c.title, "owner": en.get(c.action_owner_id, ""), "due": c.target_date, "days_late": (today - c.target_date).days}
                     for c in fetch(s, user, Capa) if c.target_date and c.target_date < today and c.status not in ("closed", "rejected")]
            df = pd.DataFrame(rows)
    if df.empty:
        st.info(L("لا توجد بيانات ضمن الفترة المختارة.", "No data for the selected period."))
        return
    st.dataframe(df, hide_index=True, use_container_width=True)
    num = [c for c in df.columns if df[c].dtype.kind in "fi" and c not in ("age_days",)]
    if rep in ("dept", "reviewer", "quarter") and num:
        st.bar_chart(df.set_index(df.columns[0])[num])
    if can(user, "reports", "export"):
        df_download(df, f"report_{rep}", user, "reports")
    else:
        st.caption(L("التصدير غير متاح لدورك", "Export is not available for your role"))


def knowledge_page(user):
    st.markdown(f"**{L('مركز المعرفة (المستندات المعتمدة)', 'Knowledge Center (approved documents)')}**")
    with S() as s:
        docs = fetch(s, user, Document, Document.status == "compliant")
        dn = _lookup(s, {}, Department, "name")
        cats = sorted({d.category for d in docs})
        c1, c2 = st.columns([2, 1])
        q = c1.text_input(L("بحث", "Search"), key="kc_q").strip().lower()
        all_lbl = L("الكل", "All")
        cat = c2.selectbox(L("النوع", "Category"), [all_lbl] + cats, key="kc_cat")
        shown = [d for d in docs if (cat == all_lbl or d.category == cat) and (not q or q in f"{d.title} {d.description} {d.doc_code}".lower())]
        if not shown:
            st.info(L("لا توجد مستندات معتمدة مطابقة.", "No matching approved documents."))
        for d in shown:
            c1, c2 = st.columns([5, 1])
            c1.markdown(f"**{esc(d.title)}** · {esc(d.doc_code)} · v{esc(d.current_version_no)} · {esc(dn.get(d.department_id, ''))}")
            c2.button(L("فتح", "Open"), key=f"kc_{d.id}", on_click=goto, args=("documents", "documents", d.id))


def portal_page(user):
    st.subheader(L("الإعلانات ومركز المعرفة والتقارير", "Announcements, Knowledge & Reports"))
    t1, t2, t3, t4 = st.tabs([L("الأخبار", "News"), L("الداشبوردات", "Dashboards"), L("مركز المعرفة", "Knowledge Center"), L("إدارة", "Manage")])
    with t1:
        with S() as s:
            news = fetch(s, user, News)
            if not news:
                st.info(L("لا توجد أخبار.", "No news yet."))
            for start in range(0, len(news), 3):
                for col, n in zip(st.columns(3), news[start:start + 3]):
                    img = safe_url(n.image_url) or DEFAULT_NEWS_IMAGE
                    col.markdown(f'<div class="news"><img src="{esc(img, quote=True)}"><div class="b"><b>{esc(n.title)}</b><br>{esc(n.content)}</div></div>', unsafe_allow_html=True)
    with t2:
        with S() as s:
            projs = fetch(s, user, PortalProject)
            if not projs:
                st.info(L("لا توجد مشاريع.", "No projects yet."))
            else:
                cats = sorted({p.category or "عام" for p in projs})
                all_lbl = L("الكل", "All")
                c1, c2 = st.columns([2, 1])
                q = c1.text_input(L("بحث", "Search"), key="pj_q").strip().lower()
                cat = c2.selectbox(L("التصنيف", "Category"), [all_lbl] + cats, key="pj_cat")
                opts = [p for p in projs if (cat == all_lbl or p.category == cat) and (not q or q in f"{p.name} {p.title} {p.description}".lower())]
                if not opts:
                    st.info(L("لا نتائج", "No results"))
                else:
                    pick = st.selectbox(L("اختر المشروع", "Select project"), opts, format_func=lambda p: p.name, key="pj_pick")
                    st.markdown(f"### {esc(pick.title or pick.name)}")
                    st.write(pick.description)
                    proj_extra(s, user, pick)
    with t3:
        knowledge_page(user)
    with t4:
        if not can(user, "portal", "create"):
            st.info(L("للإدارة فقط", "Managers only"))
        else:
            which = st.radio("manage", ["portal_projects", "news"], format_func=lambda k: L(*CFGS[k].title), horizontal=True,
                             key="pt_which", label_visibility="collapsed")
            crud_page(CFGS[which], user)


def notifications_page(user):
    st.subheader(L("مركز الإشعارات", "Notification Center"))
    c1, c2 = st.columns([1, 1])
    if c1.button(L("تحديث الإشعارات", "Refresh notifications")):
        scan_notifications()
        st.rerun()
    with S() as s:
        items = list(s.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.id.desc()).limit(200)))
        if c2.button(L("تعليم الكل كمقروء", "Mark all read")):
            for n in items:
                n.is_read = True
            st.rerun()
        if not items:
            st.info(L("لا توجد إشعارات.", "No notifications."))
        for n in items:
            a, b, c = st.columns([6, 1, 1])
            a.markdown(f"{'🔵 ' if not n.is_read else ''}**{esc(n.title)}**  \n<small>{n.created_at:%Y-%m-%d %H:%M} · {esc(n.category)} · {esc(n.body)}</small>", unsafe_allow_html=True)
            if n.entity_type in CFGS and n.entity_id:
                b.button(L("فتح", "Open"), key=f"nt_o_{n.id}", on_click=goto, args=(n.entity_type, n.entity_type, n.entity_id))
            if not n.is_read and c.button("✓", key=f"nt_r_{n.id}"):
                n.is_read = True
                st.rerun()


def audit_page(user):
    st.subheader(L("سجل التدقيق (للقراءة فقط)", "Audit Trail (read-only)"))
    with S() as s:
        c1, c2, c3 = st.columns(3)
        ent = c1.text_input(L("نوع الكيان", "Entity type"), key="au_e").strip()
        usr = c2.text_input(L("المستخدم", "User"), key="au_u").strip().lower()
        act = c3.text_input(L("الإجراء", "Action"), key="au_a").strip()
        q = select(AuditLog).order_by(AuditLog.id.desc()).limit(1000)
        if ent:
            q = q.where(AuditLog.entity_type == ent)
        if usr:
            q = q.where(AuditLog.user_email.contains(usr))
        if act:
            q = q.where(AuditLog.action == act)
        df = pd.DataFrame([{"_id": a.id, "time": a.created_at.strftime("%Y-%m-%d %H:%M:%S"), "user": a.user_email, "action": a.action,
                            "entity": a.entity_type, "ref": a.record_ref, "event": a.workflow_event, "old": a.old_values[:200], "new": a.new_values[:200]}
                           for a in s.scalars(q)])
    data_table(df, "audit", ["user", "action", "entity", "ref"], 25)
    if not df.empty:
        df_download(df.drop(columns=["_id"]), "audit_log", user, "audit")


def profile_page(user):
    st.subheader(L("الملف الشخصي والأمان", "Profile & Security"))
    with S() as s:
        u = s.get(User, user.id)
        st.write(f"**{esc(u.full_name)}** · {esc(u.email)} · {lab(u.role)}")
        st.markdown(f"**{L('تغيير كلمة المرور', 'Change password')}**")
        with st.form("chpw"):
            old = st.text_input(L("الحالية", "Current"), type="password")
            n1 = st.text_input(L("الجديدة", "New"), type="password")
            n2 = st.text_input(L("تأكيد", "Confirm"), type="password")
            go = st.form_submit_button(L("تغيير", "Change"), type="primary")
        if go:
            errs = pw_problems(n1)
            if not check_pw(old, u.password_hash):
                errs.append(L("كلمة المرور الحالية خاطئة", "Current password is wrong"))
            if n1 != n2:
                errs.append(L("غير متطابقتين", "Passwords do not match"))
            if errs:
                for e in errs:
                    st.error(e)
            else:
                u.password_hash = hash_pw(n1)
                audit(s, user, "password_change", "user", u.id, u.email)
                st.success(L("تم التغيير", "Password changed"))
        st.divider()
        st.markdown(f"**{L('التحقق الثنائي (TOTP)', 'Two-factor authentication (TOTP)')}**")
        if not pyotp:
            st.info(L("ثبّت pyotp لتفعيل التحقق الثنائي.", "Install pyotp to enable 2FA."))
        elif u.totp_enabled:
            st.success(L("مفعّل", "Enabled"))
            pw = st.text_input(L("كلمة المرور لإلغاء التفعيل", "Password to disable"), type="password", key="tf_dis")
            if st.button(L("إلغاء التفعيل", "Disable 2FA")):
                if check_pw(pw, u.password_hash):
                    u.totp_enabled, u.totp_secret = False, None
                    audit(s, user, "2fa_disabled", "user", u.id, u.email)
                    st.rerun()
                else:
                    st.error(L("كلمة المرور خاطئة", "Wrong password"))
        else:
            if not u.totp_secret:
                u.totp_secret = pyotp.random_base32()
                s.flush()
            uri = pyotp.TOTP(u.totp_secret).provisioning_uri(name=u.email, issuer_name="Linrco QA ERP")
            if qrcode:
                buf = io.BytesIO()
                qrcode.make(uri).save(buf)
                st.image(buf.getvalue(), width=200)
            st.code(u.totp_secret, language="text")
            code = st.text_input(L("الرمز للتأكيد", "Code to confirm"), max_chars=6, key="tf_code")
            if st.button(L("تفعيل", "Enable 2FA"), type="primary"):
                if pyotp.TOTP(u.totp_secret).verify(code.strip(), valid_window=1):
                    u.totp_enabled = True
                    audit(s, user, "2fa_enabled", "user", u.id, u.email)
                    st.rerun()
                else:
                    st.error(L("الرمز غير صحيح", "Invalid code"))


def users_page(user):
    st.subheader(L("الموظفون وإدارة الصلاحيات", "Employee & Access Management"))
    if not can(user, "users", "read"):
        st.error(L("غير مصرح", "Not permitted"))
        return
    with S() as s:
        users = list(s.scalars(select(User).where(User.archived.is_(False)).order_by(User.id)))
        emp = {e.id: e.full_name for e in s.scalars(select(Employee).where(Employee.archived.is_(False)))}
        dn = _lookup(s, {}, Department, "name")
        st.dataframe(pd.DataFrame([{"email": u.email, L("الاسم", "Name"): u.full_name, L("الدور", "Role"): lab(u.role),
                                    L("نشط", "Active"): "✓" if u.is_active else "—", L("2FA", "2FA"): "✓" if u.totp_enabled else "—",
                                    L("آخر دخول", "Last login"): u.last_login_at} for u in users]), hide_index=True, use_container_width=True)
        if not can(user, "users", "update"):
            return
        st.markdown(f"**{L('تعديل مستخدم', 'Edit user')}**")
        sel = st.selectbox(L("المستخدم", "User"), users, format_func=lambda u: u.email, key="us_sel")
        c1, c2, c3 = st.columns(3)
        role = c1.selectbox(L("الدور", "Role"), ROLES, index=ROLES.index(sel.role), format_func=lab, key=f"us_role_{sel.id}")
        active = c2.checkbox(L("نشط", "Active"), value=sel.is_active, key=f"us_act_{sel.id}")
        emp_ids = [None] + list(emp)
        eid = c3.selectbox(L("الموظف المرتبط", "Linked employee"), emp_ids, index=emp_ids.index(sel.employee_id) if sel.employee_id in emp_ids else 0,
                           format_func=lambda i: "—" if i is None else emp[i], key=f"us_emp_{sel.id}")
        cur_d = list(s.scalars(select(UserDept.department_id).where(UserDept.user_id == sel.id)))
        dsel = st.multiselect(L("أقسام إضافية يمكنه الوصول إليها", "Additional accessible departments"), list(dn),
                              default=[d for d in cur_d if d in dn], format_func=lambda i: dn[i], key=f"us_dp_{sel.id}")
        npw = st.text_input(L("كلمة مرور جديدة (اختياري)", "New password (optional)"), type="password", key=f"us_pw_{sel.id}")
        if st.button(L("حفظ المستخدم", "Save user"), type="primary", key=f"us_save_{sel.id}"):
            errs = pw_problems(npw) if npw else []
            if sel.id == user.id and (not active or (role != "system_admin" and sel.role == "system_admin")):
                errs.append(L("لا يمكنك إلغاء تفعيل أو خفض صلاحية حسابك", "You cannot deactivate or demote your own account"))
            if errs:
                for e in errs:
                    st.error(e)
            else:
                old = {"role": sel.role, "active": sel.is_active}
                sel.role, sel.is_active, sel.employee_id = role, active, eid
                if npw:
                    sel.password_hash = hash_pw(npw)
                s.query(UserDept).filter(UserDept.user_id == sel.id).delete()
                for d in dsel:
                    s.add(UserDept(user_id=sel.id, department_id=d))
                audit(s, user, "user_update", "user", sel.id, sel.email, old, {"role": role, "active": active, "pw_reset": bool(npw)})
                st.success(L("تم الحفظ", "Saved"))
                st.rerun()
        st.divider()
        st.markdown(f"**{L('مستخدم جديد', 'New user')}**")
        with st.form("us_new", clear_on_submit=True):
            a, b = st.columns(2)
            email, name = a.text_input("Email"), b.text_input(L("الاسم", "Name"))
            pw, rl = a.text_input(L("كلمة المرور", "Password"), type="password"), b.selectbox(L("الدور", "Role"), ROLES, format_func=lab)
            go = st.form_submit_button(L("إنشاء", "Create"), type="primary")
        if go:
            errs = pw_problems(pw)
            if "@" not in email or not name.strip():
                errs.append(L("بريد واسم صحيحان مطلوبان", "Valid email and name required"))
            if errs:
                for e in errs:
                    st.error(e)
            else:
                try:
                    create_user(s, email, name, pw, rl)
                    s.flush()
                    audit(s, user, "user_create", "user", None, email.strip().lower(), new={"role": rl})
                    st.success(L("تم الإنشاء", "Created"))
                except IntegrityError:
                    s.rollback()
                    st.error(L("البريد مستخدم", "Email already in use"))


# ---- Demo data (clearly labelled, fictional, removable) -------------------------
def seed_demo(user):
    if get_setting("demo_seeded") == "1":
        return False
    with S() as s:
        names = [("REC", "Recruitment"), ("SRC", "Sourcing"), ("ROP", "Recruitment Operations"), ("HRG", "HR & GOSI"), ("TRI", "Travel & Insurance")]
        deps = {}
        for code, n in names:
            d = Department(code=f"DEMO-{code}", name=f"[DEMO] {n}", is_demo=True)
            s.add(d)
            deps[code] = d
        s.flush()
        emps = []
        for i, (code, d) in enumerate(deps.items()):
            e = Employee(employee_no=f"DEMO-E{i + 1:03d}", full_name=f"[DEMO] Employee {i + 1}", department_id=d.id, job_title="Specialist",
                         is_owner=True, is_demo=True)
            s.add(e)
            emps.append(e)
        rev = Employee(employee_no="DEMO-E100", full_name="[DEMO] QA Reviewer", job_title="QA Reviewer", is_reviewer=True, is_demo=True)
        s.add(rev)
        s.flush()
        procs = []
        for e, (code, d) in zip(emps, deps.items()):
            p = Process(reference=next_ref(s, "PR"), name=f"[DEMO] {d.name} main process", department_id=d.id, owner_id=e.id, sla_hours=48,
                        validation_interval_days=180, is_demo=True)
            s.add(p)
            procs.append(p)
        s.flush()
        ck = Checklist(code="DEMO-CHK", title="[DEMO] Process adherence checklist", department_id=deps["REC"].id, is_demo=True)
        ck.items = [ChecklistItem(sequence=10, question="Is the approved SOP available to staff?", question_type="yes_no"),
                    ChecklistItem(sequence=20, question="Were records completed correctly?", question_type="pass_fail"),
                    ChecklistItem(sequence=30, question="Accuracy score", question_type="numeric_score", max_score=10),
                    ChecklistItem(sequence=40, question="Evidence reference", question_type="evidence_required", evidence_required=True, is_scored=False)]
        s.add(ck)
        s.flush()
        for i, p in enumerate(procs[:3]):
            d = Document(doc_code=f"DEMO-SOP-{i + 1:02d}", title=f"[DEMO] SOP {i + 1}", department_id=p.department_id, process_id=p.id,
                         owner_id=p.owner_id, status="compliant" if i == 0 else "pending_review", effective_date=date.today() - timedelta(days=30),
                         review_date=date.today() + timedelta(days=20 + i * 40), is_demo=True)
            s.add(d)
            s.flush()
            s.add(DocVersion(document_id=d.id, version_no="1.0", change_description="Demo initial version"))
        s.add(Review(reference=next_ref(s, "QR"), title="[DEMO] Recruitment process review", department_id=deps["REC"].id, process_id=procs[0].id,
                     responsible_id=emps[0].id, reviewer_id=rev.id, checklist_id=ck.id, status="in_progress", review_date=date.today(),
                     due_date=date.today() + timedelta(days=7), is_demo=True))
        s.add(Capa(reference=next_ref(s, "NC"), title="[DEMO] Missing candidate document", department_id=deps["ROP"].id, process_id=procs[2].id,
                   action_owner_id=emps[2].id, target_date=date.today() + timedelta(days=14), is_demo=True))
        s.add(Task(reference=next_ref(s, "TK"), title="[DEMO] Update SOP", assignee_id=emps[0].id, due_date=date.today() + timedelta(days=5), is_demo=True))
        k = KPI(code="DEMO-KPI-1", name="[DEMO] Process compliance %", department_id=deps["REC"].id, target=90, unit="%", is_demo=True)
        s.add(k)
        s.flush()
        for m in range(3):
            ps, pe = period_bounds("monthly", date.today().year, max(1, date.today().month - 2 + m))
            s.add(KPIValue(kpi_id=k.id, period_start=ps, period_end=pe, actual=82 + m * 4))
        audit(s, user, "seed_demo", "system", None, "demo")
    set_setting("demo_seeded", "1")
    return True


def remove_demo(user):
    try:
        with S() as s:
            demo = lambda M: [o.id for o in s.scalars(select(M).where(M.is_demo.is_(True)))]  # noqa: E731
            rv = demo(Review)
            if rv:
                s.query(ReviewAnswer).filter(ReviewAnswer.review_id.in_(rv)).delete(synchronize_session=False)
            for M in (Task, Capa, ProcessValidation, Review):
                s.query(M).filter(M.is_demo.is_(True)).delete(synchronize_session=False)
            dd = demo(Document)
            if dd:
                s.query(DocVersion).filter(DocVersion.document_id.in_(dd)).delete(synchronize_session=False)
            s.query(Document).filter(Document.is_demo.is_(True)).delete(synchronize_session=False)
            kd = demo(KPI)
            if kd:
                s.query(KPIValue).filter(KPIValue.kpi_id.in_(kd)).delete(synchronize_session=False)
            s.query(KPI).filter(KPI.is_demo.is_(True)).delete(synchronize_session=False)
            cd = demo(Checklist)
            if cd:
                s.query(ChecklistItem).filter(ChecklistItem.checklist_id.in_(cd)).delete(synchronize_session=False)
            for M in (Checklist, Process, Employee, Department):
                s.query(M).filter(M.is_demo.is_(True)).delete(synchronize_session=False)
            audit(s, user, "remove_demo", "system", None, "demo")
        set_setting("demo_seeded", "")
        return True, ""
    except IntegrityError:
        return False, L("سجلات حقيقية مرتبطة ببيانات العرض؛ فك الارتباط أولاً.", "Real records reference demo data; unlink them first.")


def seed_defaults():
    """Original portal defaults (real Linrco dashboards) - inserted once, never demo-flagged."""
    if get_setting("defaults_seeded") == "1":
        return
    with S() as s:
        if not s.scalar(select(func.count(PortalProject.id))):
            s.add(PortalProject(name="مؤشرات أداء قسم الـ QA", title="📊 QA Dashboard تحليل الأداء قسم الجودة", category="مؤشرات الأداء",
                                description="تحتوي هذه الداشبورد على تحليلات شاملة للنشاطات اليومية والشهرية، بالإضافة إلى مقارنة الأداء ومؤشرات الأداء الرئيسية (KPIs).",
                                url="https://datastudio.google.com/s/pZkBFbgR5as"))
            s.add(PortalProject(name="مشروع الـ TPV", title="📈 TPV Dashboard", category="المشاريع",
                                description="تستعرض الداشبورد تفاصيل مشروع TPV ونتيجتها وتفاصيل الأنشطة المستخدمة يومياً من قسم الجودة ونسب الربحية لمختلف القطاعات.",
                                url="https://datastudio.google.com/s/lzMLkPXvy28"))
        if not s.scalar(select(func.count(News.id))):
            s.add(News(title="📢 إطلاق نظام إدارة الجودة الجديد", content="تم تحديث كافة تقارير ومؤشرات الأداء الخاصة بقسم الجودة لرفع كفاءة ومتابعة العمليات التشغيلية اليومية.",
                       image_url=DEFAULT_NEWS_IMAGE))
    set_setting("defaults_seeded", "1")


def settings_page(user):
    st.subheader(L("إدارة النظام", "System Administration"))
    if not can(user, "settings", "read"):
        st.error(L("غير مصرح", "Not permitted"))
        return
    edit = can(user, "settings", "update")
    t1, t2, t3, t4 = st.tabs([L("القوائم المرجعية", "Reference lists"), L("الشعارات", "Logos"), L("بيانات العرض", "Demo data"), L("نسخ احتياطي", "Backup")])
    with t1:
        labels = {"review_types": L("أنواع المراجعات", "Review types"), "doc_categories": L("أنواع المستندات", "Document types"),
                  "classifications": L("تصنيفات السرية", "Classifications"), "root_causes": L("تصنيفات الأسباب الجذرية", "Root-cause categories"),
                  "job_titles": L("المسميات الوظيفية", "Job titles")}
        for name, lbl in labels.items():
            txt = st.text_area(lbl + L(" (سطر لكل عنصر)", " (one per line)"), value="\n".join(get_list(name)), key=f"ls_{name}", disabled=not edit)
            if edit and st.button(L("حفظ", "Save") + f" · {lbl}", key=f"ls_b_{name}"):
                items = [x.strip() for x in txt.splitlines() if x.strip()]
                if not items:
                    st.error(L("القائمة لا يمكن أن تكون فارغة", "List cannot be empty"))
                else:
                    set_setting("list:" + name, json.dumps(items, ensure_ascii=False))
                    with S() as s:
                        audit(s, user, "setting_update", "settings", None, name, new=items)
                    st.success(L("تم الحفظ", "Saved"))
    with t2:
        for which, lbl in (("company", L("شعار الشركة", "Company logo")), ("qa", L("شعار الجودة", "QA logo"))):
            st.image(get_logo(which), width=160)
            up = st.file_uploader(lbl, type=["png", "jpg", "jpeg"], key=f"lg_{which}", disabled=not edit)
            if up is not None and st.button(L("حفظ", "Save") + f" · {lbl}", key=f"lg_b_{which}"):
                data = up.getvalue()
                if len(data) > 1_000_000 or not (data.startswith(b"\x89PNG") or data.startswith(b"\xff\xd8\xff")):
                    st.error(L("صورة PNG/JPG بحجم أقل من 1MB", "PNG/JPG image under 1 MB required"))
                else:
                    set_setting(f"logo_{which}", base64.b64encode(data).decode())
                    st.rerun()
    with t3:
        st.caption(L("بيانات تجريبية وهمية موسومة [DEMO] ويمكن حذفها.", "Fictional records labelled [DEMO]; removable."))
        c1, c2 = st.columns(2)
        if c1.button(L("إضافة بيانات العرض", "Add demo data"), disabled=not edit or get_setting("demo_seeded") == "1"):
            if seed_demo(user):
                st.success(L("تمت الإضافة", "Added"))
            st.rerun()
        if c2.button(L("حذف بيانات العرض", "Remove demo data"), disabled=not edit):
            ok, msg = remove_demo(user)
            if ok:
                st.success(L("تم الحذف", "Removed"))
            else:
                st.error(msg)
    with t4:
        st.caption(L("نسخة احتياطية كاملة من الجداول (بدون كلمات المرور).", "Full table export (password hashes excluded)."))
        if can(user, "settings", "export"):
            if st.button(L("تجهيز النسخة الاحتياطية", "Prepare backup")):
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine="openpyxl") as xw:
                    for tbl in Base.metadata.sorted_tables:
                        if tbl.name == "attachments":
                            cols = [c for c in tbl.c if c.name != "content"]
                        elif tbl.name == "users":
                            cols = [c for c in tbl.c if c.name not in ("password_hash", "totp_secret")]
                        else:
                            cols = list(tbl.c)
                        with get_engine().connect() as conn:
                            pd.DataFrame(conn.execute(select(*cols)).mappings().all()).to_excel(xw, sheet_name=tbl.name[:31], index=False)
                st.session_state["backup"] = buf.getvalue()
                with S() as s:
                    audit(s, user, "backup", "system", None, "excel")
            if st.session_state.get("backup"):
                st.download_button(L("تحميل النسخة", "Download backup"), st.session_state["backup"], "qa_erp_backup.xlsx")
        ok, detail = health_check()
        (st.success if ok else st.error)(f"DB: {detail}")
        if db_url().startswith("sqlite"):
            st.warning(L("قاعدة SQLite محلية: غير دائمة على Streamlit Cloud. اضبط DATABASE_URL لقاعدة PostgreSQL.",
                         "Local SQLite: NOT persistent on Streamlit Cloud. Set DATABASE_URL to PostgreSQL."))


def org_page(user):
    st.subheader(L("الأقسام والموظفون والعمليات", "Departments, Employees & Processes"))
    which = st.radio("org", ["departments", "employees", "processes"], format_func=lambda k: L(*CFGS[k].title), horizontal=True,
                     key="org_which", label_visibility="collapsed")
    crud_page(CFGS[which], user)


# =============================================================================
# 13. NAVIGATION SHELL
# =============================================================================
def _crud(key):
    return lambda user: crud_page(CFGS[key], user)


PAGES = [
    ("dashboard", "g_home", "🏠", "الرئيسية", "Home", "dashboard", dashboard_page),
    ("reviews", "g_qa", "✅", "مراجعات الجودة", "QA Reviews", "reviews", _crud("reviews")),
    ("checklists", "g_qa", "📋", "قوائم الفحص", "Checklists", "checklists", _crud("checklists")),
    ("validations", "g_qa", "🧪", "التحقق من العمليات", "Process Validation", "validations", _crud("validations")),
    ("documents", "g_qa", "📚", "مراقبة المستندات", "Document Control", "documents", _crud("documents")),
    ("capa", "g_qa", "🛠", "عدم المطابقة CAPA", "Nonconformities / CAPA", "capa", _crud("capa")),
    ("tasks", "g_work", "🗂", "المهام والمتابعات", "Tasks", "tasks", tasks_page),
    ("kpis", "g_work", "📈", "مؤشرات الأداء", "KPIs", "kpis", _crud("kpis")),
    ("org", "g_org", "🏢", "الأقسام والموظفون والعمليات", "Org & Processes", "org", org_page),
    ("portal", "g_know", "📰", "الأخبار والتقارير والمعرفة", "News, Reports & Knowledge", "portal", portal_page),
    ("reports", "g_rep", "📊", "التقارير والتحليلات", "Reports", "reports", reports_page),
    ("audit", "g_rep", "🔍", "سجل التدقيق", "Audit Trail", "audit", audit_page),
    ("notifications", "g_rep", "🔔", "الإشعارات", "Notifications", "notifications", notifications_page),
    ("users", "g_admin", "👥", "المستخدمون والصلاحيات", "Users & Access", "users", users_page),
    ("settings", "g_admin", "⚙️", "إدارة النظام", "System Admin", "settings", settings_page),
    ("profile", "g_admin", "👤", "ملفي والأمان", "My Profile", "dashboard", profile_page),
]
GROUPS = {"g_home": ("الرئيسية", "Home"), "g_qa": ("إدارة الجودة", "Quality"), "g_work": ("العمل والأداء", "Work & Performance"),
          "g_org": ("المؤسسة", "Organization"), "g_know": ("المعرفة", "Knowledge"), "g_rep": ("التقارير والنظام", "Reports & System"),
          "g_admin": ("الإدارة", "Administration")}


def render_sidebar(user):
    with st.sidebar:
        st.markdown(f'<div class="sb-logo"><img src="{get_logo("company")}"></div><div class="sb-logo"><img src="{get_logo("qa")}"></div>', unsafe_allow_html=True)
        st.markdown(f"**{esc(user.name)}**  \n<small>{lab(user.role)}</small>", unsafe_allow_html=True)
        last = None
        for key, grp, icon, ar, en, module, _ in PAGES:
            if not can(user, module, "read"):
                continue
            if grp != last:
                st.markdown(f'<div class="grp">{esc(L(*GROUPS[grp]))}</div>', unsafe_allow_html=True)
                last = grp
            badge_txt = ""
            if key == "notifications":
                with S() as s:
                    n = s.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.is_read.is_(False)))
                badge_txt = f" ({n})" if n else ""
            st.button(f"{icon} {L(ar, en)}{badge_txt}", key=f"nav_{key}", on_click=goto, args=(key,),
                      type="primary" if st.session_state["page"] == key else "secondary")
        st.divider()
        c1, c2 = st.columns(2)
        chosen = c1.selectbox("lang", ["ar", "en"], index=0 if lang() == "ar" else 1,
                              format_func=lambda x: "العربية" if x == "ar" else "English", label_visibility="collapsed", key="lang_pick")
        st.session_state["lang"] = chosen
        dark = c2.toggle("🌙", value=st.session_state.get("theme") == "dark")
        st.session_state["theme"] = "dark" if dark else "light"
        if st.button(L("تسجيل الخروج", "Sign out"), key="logout"):
            logout()
            st.rerun()


def global_search(user, q):
    like = f"%{q}%"
    out = []
    with S() as s:
        for key, M, fields in (("reviews", Review, (Review.title, Review.reference)), ("documents", Document, (Document.title, Document.doc_code)),
                               ("capa", Capa, (Capa.title, Capa.reference)), ("tasks", Task, (Task.title, Task.reference)),
                               ("validations", ProcessValidation, (ProcessValidation.reference,))):
            if not can(user, CFGS[key].module, "read"):
                continue
            for o in fetch(s, user, M, or_(*[f.ilike(like) for f in fields]))[:5]:
                out.append((key, o.id, f"{getattr(o, CFGS[key].ref_field, '')} · {getattr(o, 'title', '') or ''}"))
    return out


def render_topbar(user):
    st.markdown(f'<div class="topbar"><b>{esc(L("نظام جودة ليناركو", "Linrco QA ERP"))}</b><span>{esc(user.name)} · {esc(lab(user.role))}</span></div>', unsafe_allow_html=True)
    c1, c2 = st.columns([4, 1])
    q = c1.text_input("search", placeholder=L("🔎 بحث شامل (مراجعات، مستندات، CAPA، مهام)...", "🔎 Global search (reviews, documents, CAPA, tasks)..."),
                      key="gsearch", label_visibility="collapsed").strip()
    with c2.popover(L("⚡ إجراءات سريعة", "⚡ Quick actions")):
        for key, ar, en in (("reviews", "مراجعة جديدة", "New review"), ("documents", "مستند جديد", "New document"),
                            ("capa", "عدم مطابقة جديدة", "New nonconformity"), ("tasks", "مهمة جديدة", "New task")):
            if can(user, CFGS[key].module, "create"):
                st.button(f"➕ {L(ar, en)}", key=f"qa_{key}", on_click=goto, args=(key, key, "new"))
    if len(q) >= 2:
        res = global_search(user, q)
        if not res:
            st.caption(L("لا نتائج", "No results"))
        for key, rid, label in res:
            st.button(f"{L(*CFGS[key].title)} → {label}", key=f"gs_{key}_{rid}", on_click=goto, args=(key, key, rid))


def render_breadcrumbs(page_tuple):
    parts = [L("الرئيسية", "Home")]
    if page_tuple[0] != "dashboard":
        parts += [L(*GROUPS[page_tuple[1]]), L(page_tuple[3], page_tuple[4])]
        rec = st.session_state.get("crumb_record")
        open_ = any(st.session_state.get(f"{k}_view") not in (None, "") for k in CFGS if CFGS[k].module == page_tuple[5])
        if rec and open_:
            parts.append(str(rec))
    st.markdown(f'<div class="crumbs">{" / ".join(esc(p) for p in parts)}</div>', unsafe_allow_html=True)


def main():
    init_db()
    seed_defaults()
    st.session_state.setdefault("lang", "ar")
    st.session_state.setdefault("theme", "light")
    st.session_state.setdefault("page", "dashboard")
    inject_css()
    if st.query_params.get("health") == "1":
        ok, d = health_check()
        (st.success if ok else st.error)(f"database: {d}")
        st.stop()
    if needs_setup():
        render_setup()
        st.stop()
    user = session_user()
    if user is None:
        render_login()
        st.stop()
    # Periodic scans (at most once per hour per browser session)
    if datetime.utcnow() - st.session_state.get("last_scan", datetime.min) > timedelta(hours=1):
        try:
            scan_notifications()
        except Exception:  # noqa: BLE001  (a scan failure must never block the UI)
            pass
        st.session_state["last_scan"] = datetime.utcnow()
    render_sidebar(user)
    if st.session_state.get("_css_sig") != (lang(), st.session_state.get("theme")):
        inject_css()  # language or theme changed in the sidebar during this run
    render_topbar(user)
    page = next((p for p in PAGES if p[0] == st.session_state["page"]), PAGES[0])
    if not can(user, page[5], "read"):
        st.error(L("ليست لديك صلاحية للوصول لهذه الصفحة", "You do not have access to this page"))
        st.stop()
    render_breadcrumbs(page)
    try:
        page[6](user)
    except PermissionError as exc:
        st.error(str(exc))
    except Exception as exc:  # noqa: BLE001
        st.error(L("حدث خطأ غير متوقع", "An unexpected error occurred"))
        if os.environ.get("QA_ERP_DEBUG"):
            st.exception(exc)


# =============================================================================
# 14. AUTOMATED TESTS  -  run with:  pytest app.py
#     (pure-logic tests; DB-level tests can be added with DATABASE_URL=sqlite://)
# =============================================================================
class _I:
    def __init__(self, id, weight=1.0, scored=True, mandatory=True):
        self.id, self.weight, self.is_scored, self.is_mandatory = id, weight, scored, mandatory


def test_password_hash_roundtrip():
    h = hash_pw("S3cure-passw0rd")
    assert h.startswith("scrypt$") and check_pw("S3cure-passw0rd", h) and not check_pw("wrong", h)


def test_permissions_least_privilege():
    viewer = CU(1, "v@x", "V", "viewer", None, [])
    mgr = CU(2, "m@x", "M", "qa_manager", None, [])
    assert not can(viewer, "reviews", "create") and can(viewer, "reviews", "read")
    assert can(mgr, "reviews", "close") and not can(mgr, "users", "update")
    try:
        require(viewer, "capa", "update")
        assert False
    except PermissionError:
        pass


def test_scoring_unanswered_is_not_compliant():
    items = [_I(1), _I(2), _I(3, mandatory=False)]
    score, missing = compute_score(items, {1: 1.0, 2: None, 3: None})
    assert round(score, 1) == 33.3 and [i.id for i in missing] == [2]


def test_item_fractions():
    assert item_fraction("yes_no", "yes") == 1.0 and item_fraction("yes_no", "no") == 0.0
    assert item_fraction("numeric_score", "5", max_score=10) == 0.5 and item_fraction("pass_fail", "") is None
    assert item_fraction("multiple_choice", "Fair", "Good:1\nFair:0.5") == 0.5


def test_workflow_flows_are_closed_and_valid():
    for flow in (REVIEW_FLOW, DOC_FLOW, CAPA_FLOW):
        for src, targets in flow.items():
            assert all(t in flow or t in LABELS for t in targets)
    assert CAPA_FLOW["open"] == ["assigned", "rejected"] and "closed" not in CAPA_FLOW["in_progress"]


def test_safe_formula():
    assert safe_eval("passed / total * 100", {"passed": 9, "total": 10}) == 90.0
    for bad in ("__import__('os').system('x')", "1 + (lambda: 1)()", "a ** 2"):
        try:
            safe_eval(bad, {"a": 2})
            assert False, bad
        except (_FormulaError, SyntaxError):
            pass


def test_kpi_status_and_periods():
    assert kpi_status(95, 90) == "on_target" and kpi_status(85, 90) == "warning" and kpi_status(50, 90) == "off_target"
    assert period_bounds("quarterly", 2026, 4) == (date(2026, 10, 1), date(2026, 12, 31))
    assert period_bounds("monthly", 2026, 2) == (date(2026, 2, 1), date(2026, 2, 28))


def test_embed_url_and_safe_url():
    assert safe_url("javascript:alert(1)") == "" and safe_url("https://a.b") == "https://a.b"
    assert to_embed_url("https://lookerstudio.google.com/reporting/abc-123/page/p1") == "https://lookerstudio.google.com/embed/reporting/abc-123/page/p1"


if __name__ == "__main__":
    main()
