import base64
import copy
import hashlib
import hmac
import html
import io
import json
import os
import re
import secrets
import time
from datetime import datetime
from pathlib import Path

import pyotp
import qrcode
import requests
import streamlit as st
from PIL import Image, ImageEnhance

# ──────────────────────────────────────────────────────────────
# إعدادات الصفحة / Page config
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="بوابة الجودة | Quality Portal",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────────────────────
# الترجمة / Translations
# ──────────────────────────────────────────────────────────────
TR = {
    "ar": {
        "language": "اللغة",
        "company_name": "ليناركو",
        "qa_name": "قسم الجودة",
        # الدخول
        "login_title": "نظام الداشبوردات - قسم الجودة",
        "login_sub": "سجّل الدخول باسم المستخدم أو البريد الإلكتروني",
        "username_label": "اسم المستخدم / البريد الإلكتروني",
        "password": "كلمة المرور",
        "sign_in": "تسجيل الدخول",
        "login_error": "اسم المستخدم أو كلمة المرور غير صحيحة.",
        # التحقق الثنائي
        "tfa_title": "التحقق الثنائي",
        "tfa_sub": "أدخل الرمز المكوّن من 6 أرقام من تطبيق Google Authenticator",
        "tfa_code": "رمز التحقق",
        "device_name": "اسم الجهاز أو المتصفح",
        "device_default": "جهاز موثوق جديد",
        "trust_device": "تذكّر هذا الجهاز لمدة 3 أشهر (لا تطلب الرمز مرة أخرى)",
        "verify": "تحقق ودخول",
        "tfa_error": "الرمز غير صحيح أو انتهت صلاحيته. انتظر ظهور الرمز الجديد وحاول مرة أخرى.",
        "back_login": "رجوع لتسجيل الدخول",
        # اللوحة الجانبية
        "welcome": "أهلاً بك، {name}",
        "menu": "القائمة",
        "home": "🏠 الرئيسية",
        "admin_settings": "⚙️ إعدادات النظام والأمان",
        "change_logos": "🖼️ تغيير الشعارات",
        "new_company_logo": "شعار ليناركو الجديد",
        "save_company_logo": "حفظ شعار الشركة",
        "new_qa_logo": "شعار قسم الجودة الجديد",
        "save_qa_logo": "حفظ شعار الجودة",
        "logout": "🚪 تسجيل الخروج",
        "role_admin": "مدير النظام",
        "role_manager": "مدير القسم",
        "role_user": "موظف",
        # إعدادات الأدمن
        "settings_title": "إعدادات النظام والأمان",
        "settings_caption": "هذه الصفحة للأدمن فقط: إدارة المصادقة الثنائية والأجهزة الموثوقة والمستخدمين.",
        "tab_security": "الأمان والتحقق الثنائي",
        "tab_users": "المستخدمون والصلاحيات",
        "link_phone_title": "ربط موبايل الشركة بتطبيق Google Authenticator",
        "link_steps": """
1. حمّل تطبيق **Google Authenticator** على هاتفك.
2. اضغط **(+)** ثم اختر **Scan a QR code**.
3. امسح الكود التالي مرة واحدة فقط، وسيبقى صالحاً دائماً.
""",
        "devices_title": "الأجهزة الموثوقة",
        "user_word": "المستخدم",
        "remove_device": "إزالة الجهاز",
        "no_devices": "لا توجد أجهزة موثوقة مسجلة حالياً.",
        "dev_trusted_on": "تاريخ التوثيق",
        "dev_expires": "ينتهي في",
        "dev_last_used": "آخر استخدام",
        "remove_all_devices": "إزالة كل الأجهزة الموثوقة",
        "current_users": "المستخدمون الحاليون",
        "col_user": "المستخدم / الإيميل",
        "col_name": "الاسم",
        "col_role": "الصلاحية",
        "add_user": "إضافة مستخدم جديد",
        "f_email": "البريد الإلكتروني / اسم المستخدم",
        "f_name": "الاسم",
        "f_pass": "كلمة المرور",
        "f_role": "الصلاحية",
        "add_user_btn": "إضافة المستخدم",
        "user_added": "تمت إضافة {name}.",
        "fill_all": "يرجى ملء جميع الحقول.",
        "delete_user": "حذف مستخدم",
        "choose_user": "اختر المستخدم",
        "delete_selected": "حذف المستخدم المختار",
        # لوحة الإدارة
        "manage_panel": "لوحة إدارة المشاريع والملفات والأخبار",
        "tab_edit": "تعديل مشروع وإرفاق ملفات",
        "tab_add_project": "إضافة مشروع",
        "tab_add_news": "إضافة خبر",
        "project": "المشروع",
        "f_title": "العنوان",
        "f_title_en": "العنوان بالإنجليزية (اختياري)",
        "f_desc": "الوصف",
        "f_desc_en": "الوصف بالإنجليزية (اختياري)",
        "f_url": "الرابط (URL)",
        "f_embed": "رابط التضمين Embed URL (اختياري)",
        "embed_help": "لو تركته فارغاً سيحاول النظام تحويل الرابط العادي تلقائياً.",
        "f_category": "التصنيف",
        "attach_doc": "إرفاق مستند",
        "save_changes": "حفظ التعديلات",
        "add_name": "اسم المشروع (يظهر في القائمة)",
        "add_name_en": "اسم المشروع بالإنجليزية (اختياري)",
        "add_main_title": "العنوان الرئيسي",
        "add_dash_url": "رابط الداشبورد",
        "add_project_btn": "إضافة المشروع",
        "need_name_url": "أدخل اسم المشروع والرابط على الأقل.",
        "news_title": "عنوان الخبر",
        "news_title_en": "عنوان الخبر بالإنجليزية (اختياري)",
        "news_text": "نص الخبر",
        "news_text_en": "نص الخبر بالإنجليزية (اختياري)",
        "news_image": "صورة الخبر",
        "publish_news": "نشر الخبر",
        "need_news": "أدخل عنوان الخبر ونصه.",
        # الأخبار والمشاريع
        "latest_news": "آخر الأخبار والتحديثات",
        "manage_news": "إدارة الخبر",
        "new_image": "صورة جديدة",
        "save_image": "حفظ الصورة",
        "delete_news": "حذف الخبر",
        "projects_title": "المشاريع والتقارير",
        "no_projects": "لا توجد مشاريع حالياً.",
        "search": "بحث",
        "search_ph": "اكتب جزءاً من اسم المشروع أو وصفه...",
        "all": "الكل",
        "results_count": "عدد النتائج: {n} من {total}",
        "no_match": "لا توجد مشاريع مطابقة. غيّر كلمة البحث أو التصنيف.",
        "choose_project": "اختر المشروع",
        "open_new_tab": "فتح في تبويب جديد",
        "attached_files": "الملفات المرفقة ({n})",
        "download": "تحميل {name}",
        "iframe_hint": "لو التقرير لم يظهر هنا، افتحه من زر «فتح في تبويب جديد».",
        "trouble": "التقرير لا يظهر؟ خطوات الحل",
        "trouble_md": """
1. في Looker Studio: **File ← Embed report ← Enable embedding**، ثم انسخ **Embed URL** والصقه في خانة «رابط التضمين» في لوحة الإدارة.
2. الروابط القصيرة `/s/...` لا تعمل داخل iframe، ويجب أن يكون الرابط على شكل `/embed/reporting/...`.
3. تأكد من مشاركة التقرير (Share) مع المستخدمين أو المؤسسة، أو «Anyone with the link».
4. إذا كان التقرير خاصاً بحسابات Google، يجب أن يكون المستخدم مسجّلاً الدخول بحساب Google في نفس المتصفح، وأن لا يمنع المتصفح الكوكيز الخارجية.

الرابط المستخدم حالياً للعرض:
""",
        "invalid_url": "رابط المشروع غير صالح. يجب أن يبدأ بـ http:// أو https://",
        # الواجهة الرئيسية
        "hero_title": "بوابة تقارير ومشاريع الجودة",
        "hero_sub": "مرحباً {name}، هنا تجد تقارير قسم الجودة في ليناركو ومؤشرات الأداء ومستندات المشاريع.",
        "stat_projects": "مشاريع",
        "stat_news": "أخبار",
        "stat_files": "ملفات مرفقة",
        "general": "عام",
        "saved_github": "تم حفظ الشعار بشكل دائم ✅",
        "saved_temp": "تم حفظ الشعار على السيرفر فقط، وقد يُمسح عند إعادة تشغيل التطبيق. فعّل الحفظ الدائم (GitHub) من الأسرار.",
        "saved_failed": "تعذّر الحفظ الدائم على GitHub، راجع GITHUB_TOKEN و GITHUB_REPO. الشعار محفوظ مؤقتاً فقط.",
        "storage_on": "✅ الحفظ الدائم على GitHub مفعّل",
        "storage_off": "⚠️ الحفظ على السيرفر فقط (قد يُمسح عند إعادة التشغيل)",
    },
    "en": {
        "language": "Language",
        "company_name": "Linrco",
        "qa_name": "Quality Department",
        # Login
        "login_title": "Dashboards System – Quality Department",
        "login_sub": "Sign in with your username or email",
        "username_label": "Username / Email",
        "password": "Password",
        "sign_in": "Sign in",
        "login_error": "Incorrect username or password.",
        # 2FA
        "tfa_title": "Two-Factor Authentication",
        "tfa_sub": "Enter the 6-digit code from the Google Authenticator app",
        "tfa_code": "Verification code",
        "device_name": "Device or browser name",
        "device_default": "New trusted device",
        "trust_device": "Remember this device for 3 months (don't ask for the code again)",
        "verify": "Verify and sign in",
        "tfa_error": "The code is incorrect or has expired. Wait for the new code and try again.",
        "back_login": "Back to sign in",
        # Side panel
        "welcome": "Welcome, {name}",
        "menu": "Menu",
        "home": "🏠 Home",
        "admin_settings": "⚙️ System & Security Settings",
        "change_logos": "🖼️ Change logos",
        "new_company_logo": "New Linrco logo",
        "save_company_logo": "Save company logo",
        "new_qa_logo": "New Quality Dept. logo",
        "save_qa_logo": "Save quality logo",
        "logout": "🚪 Sign out",
        "role_admin": "System Admin",
        "role_manager": "Department Manager",
        "role_user": "Employee",
        # Admin settings
        "settings_title": "System & Security Settings",
        "settings_caption": "Admin only: manage two-factor authentication, trusted devices and users.",
        "tab_security": "Security & Two-Factor",
        "tab_users": "Users & Permissions",
        "link_phone_title": "Link the company phone to Google Authenticator",
        "link_steps": """
1. Install the **Google Authenticator** app on your phone.
2. Tap **(+)** then choose **Scan a QR code**.
3. Scan the code below once only; it stays valid permanently.
""",
        "devices_title": "Trusted devices",
        "user_word": "User",
        "remove_device": "Remove device",
        "no_devices": "No trusted devices are registered yet.",
        "dev_trusted_on": "Trusted on",
        "dev_expires": "Expires",
        "dev_last_used": "Last used",
        "remove_all_devices": "Remove all trusted devices",
        "current_users": "Current users",
        "col_user": "User / Email",
        "col_name": "Name",
        "col_role": "Role",
        "add_user": "Add a new user",
        "f_email": "Email / Username",
        "f_name": "Name",
        "f_pass": "Password",
        "f_role": "Role",
        "add_user_btn": "Add user",
        "user_added": "{name} was added.",
        "fill_all": "Please fill in all fields.",
        "delete_user": "Delete a user",
        "choose_user": "Select a user",
        "delete_selected": "Delete selected user",
        # Management panel
        "manage_panel": "Projects, files and news management",
        "tab_edit": "Edit project & attach files",
        "tab_add_project": "Add project",
        "tab_add_news": "Add news",
        "project": "Project",
        "f_title": "Title",
        "f_title_en": "English title (optional)",
        "f_desc": "Description",
        "f_desc_en": "English description (optional)",
        "f_url": "Link (URL)",
        "f_embed": "Embed URL (optional)",
        "embed_help": "If left empty, the system will try to convert the regular link automatically.",
        "f_category": "Category",
        "attach_doc": "Attach a document",
        "save_changes": "Save changes",
        "add_name": "Project name (shown in the list)",
        "add_name_en": "English project name (optional)",
        "add_main_title": "Main title",
        "add_dash_url": "Dashboard link",
        "add_project_btn": "Add project",
        "need_name_url": "Enter at least the project name and link.",
        "news_title": "News title",
        "news_title_en": "English news title (optional)",
        "news_text": "News text",
        "news_text_en": "English news text (optional)",
        "news_image": "News image",
        "publish_news": "Publish news",
        "need_news": "Enter the news title and text.",
        # News & projects
        "latest_news": "Latest news & updates",
        "manage_news": "Manage news item",
        "new_image": "New image",
        "save_image": "Save image",
        "delete_news": "Delete news item",
        "projects_title": "Projects & Reports",
        "no_projects": "There are no projects yet.",
        "search": "Search",
        "search_ph": "Type part of a project name or description...",
        "all": "All",
        "results_count": "Results: {n} of {total}",
        "no_match": "No matching projects. Change the search text or category.",
        "choose_project": "Select a project",
        "open_new_tab": "Open in a new tab",
        "attached_files": "Attached files ({n})",
        "download": "Download {name}",
        "iframe_hint": "If the report doesn't appear here, open it with the \"Open in a new tab\" button.",
        "trouble": "Report not showing? Troubleshooting steps",
        "trouble_md": """
1. In Looker Studio: **File → Embed report → Enable embedding**, then copy the **Embed URL** and paste it into the "Embed URL" field in the management panel.
2. Short links `/s/...` don't work inside an iframe; the link must look like `/embed/reporting/...`.
3. Make sure the report is shared (Share) with users or the organization, or "Anyone with the link".
4. If the report is restricted to Google accounts, the user must be signed in to Google in the same browser, and the browser must not block third-party cookies.

The link currently used for display:
""",
        "invalid_url": "The project link is invalid. It must start with http:// or https://",
        # Main page
        "hero_title": "Quality Reports & Projects Portal",
        "hero_sub": "Hello {name}, here you will find the Quality department's reports, performance indicators and project documents at Linrco.",
        "stat_projects": "Projects",
        "stat_news": "News",
        "stat_files": "Attached files",
        "general": "General",
        "saved_github": "Logo saved permanently ✅",
        "saved_temp": "Logo saved on the server only and may be lost when the app restarts. Enable permanent storage (GitHub) via secrets.",
        "saved_failed": "Permanent save to GitHub failed; check GITHUB_TOKEN and GITHUB_REPO. The logo is saved temporarily only.",
        "storage_on": "✅ Permanent GitHub storage is enabled",
        "storage_off": "⚠️ Server-only storage (may be lost on restart)",
    },
}

# اللغة الحالية (تُحفظ في الجلسة وفي رابط الصفحة ?lang=)
if "lang" not in st.session_state:
    _q = st.query_params.get("lang", "ar")
    st.session_state.lang = _q if _q in ("ar", "en") else "ar"


def cur_lang():
    return st.session_state.get("lang", "ar")


def t(key, **kw):
    s = TR[cur_lang()].get(key) or TR["ar"].get(key, key)
    return s.format(**kw) if kw else s


def loc(item, field):
    """يرجع النص المناسب للغة الحالية (field_en للإنجليزية لو موجود، وإلا النص الأصلي)."""
    if cur_lang() == "en":
        v = item.get(f"{field}_en")
        if v:
            return v
    return item.get(field, "")


def role_label(role):
    return t(f"role_{role}")


# تصنيفات معروفة (القيمة المخزّنة بالعربي، والعرض حسب اللغة)
CAT_EN = {"مؤشرات الأداء": "KPIs", "المشاريع": "Projects", "عام": "General"}
CAT_FROM_EN = {v: k for k, v in CAT_EN.items()}


def cat_label(cat):
    cat = cat or "عام"
    return CAT_EN.get(cat, cat) if cur_lang() == "en" else cat


def norm_cat(text):
    text = (text or "").strip()
    return CAT_FROM_EN.get(text, text) or "عام"


def _set_lang(key):
    st.session_state.lang = st.session_state[key]
    st.query_params["lang"] = st.session_state.lang


def language_selector(key):
    st.radio(
        t("language"),
        ["ar", "en"],
        index=0 if cur_lang() == "ar" else 1,
        format_func=lambda c: "العربية" if c == "ar" else "English",
        horizontal=True,
        key=key,
        on_change=_set_lang,
        args=(key,),
        label_visibility="collapsed",
    )


# ──────────────────────────────────────────────────────────────
# التنسيق (CSS) - يتغير الاتجاه والخط حسب اللغة
# ──────────────────────────────────────────────────────────────
CSS_TEMPLATE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --brand: #8A1C2B;
    --brand-deep: #5C0F1B;
    --ink: #1D2433;
    --muted: #667085;
    --bg: #F4F5F7;
    --surface: #FFFFFF;
    --line: #E3E6EB;
    --link: #1F6F8B;
}

/* إخفاء عناصر ستريمليت الافتراضية */
#MainMenu, footer,
[data-testid="stDecoration"],
[data-testid="stToolbarActions"],
[data-testid="stMainMenu"],
[data-testid="stAppDeployButton"],
[data-testid="stStatusWidget"],
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent; }

/* الاتجاه (RTL للعربي / LTR للإنجليزي) والخط */
.stApp { background: var(--bg); color: var(--ink); }
[data-testid="stMain"],
[data-baseweb="popover"],
[data-baseweb="menu"],
[data-testid="stPopoverBody"] { direction: __DIR__; }

.stApp,
.stApp :is(p, h1, h2, h3, h4, h5, h6, label, input, textarea, button, li, a, td, th, caption, summary) {
    font-family: __FONT__ !important;
}
.stApp :is(p, h1, h2, h3, h4, h5, h6, label, li) { text-align: __ALIGN__; }
[data-testid="stCode"], .stApp code { direction: ltr; text-align: left; }

.block-container {
    max-width: 1400px;
    padding: 2.5rem 2rem 4rem;
}
h1, h2, h3 { color: var(--ink); font-weight: 700; }

/* اللوحة الجانبية (يمين في العربي، شمال في الإنجليزي) */
[data-testid="stColumn"]:has(.side-marker) {
    position: sticky; top: 3.5rem; align-self: flex-start;
}
[data-testid="stColumn"]:has(.side-marker) > [data-testid="stVerticalBlock"] {
    background: var(--surface); border: 1px solid var(--line);
    border-radius: 14px; padding: 1rem;
}
[data-testid="stColumn"]:has(.side-marker) .stButton > button,
[data-testid="stColumn"]:has(.side-marker) [data-testid="stPopover"],
[data-testid="stColumn"]:has(.side-marker) [data-testid="stPopover"] > button { width: 100%; }
[data-testid="stColumn"]:has(.side-marker) [data-testid="stPopover"] > button {
    border-radius: 8px; font-weight: 600; justify-content: center;
}
.side-marker { display: none; }

.sb-logo {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: .75rem;
    margin-bottom: .6rem;
    text-align: center;
}
.sb-logo img { max-width: 100%; max-height: 64px; object-fit: contain; }
.logo-fallback { font-weight: 700; color: var(--brand); padding: .5rem 0; font-size: 1.05rem; }
.sb-label { font-size: .8rem; font-weight: 600; color: var(--muted); margin: 1rem .25rem .5rem; }
.sb-sep { height: 1px; background: var(--line); margin: 1rem 0; }
.user-chip {
    display: flex; align-items: center; gap: .75rem;
    padding: .75rem; background: var(--bg); border-radius: 10px;
    margin: .9rem 0 .25rem;
}
.avatar {
    width: 40px; height: 40px; border-radius: 50%;
    background: var(--brand); color: #fff; font-weight: 700;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.user-chip .name { font-weight: 600; line-height: 1.3; }
.user-chip .role { font-size: .82rem; color: var(--muted); }

/* شاشة الدخول */
.login-brand { text-align: center; margin: 1.5rem 0 1.25rem; }
.login-brand img { max-height: 72px; margin-bottom: 1rem; }
.login-brand .t { font-size: 1.5rem; font-weight: 700; color: var(--ink); }
.login-brand .s { color: var(--muted); margin-top: .25rem; }

/* الواجهة الرئيسية */
.hero {
    background: var(--brand-deep); color: #fff;
    border-radius: 14px; padding: 2rem 2.25rem; margin-bottom: 1.5rem;
    display: flex; justify-content: space-between; align-items: flex-end;
    gap: 1.5rem; flex-wrap: wrap;
}
.hero-title { font-size: 1.9rem; font-weight: 700; line-height: 1.4; margin-bottom: .4rem; }
.hero-sub { color: #EBD3D8; font-size: 1rem; line-height: 1.8; max-width: 48ch; }
.hero-stats { display: flex; }
.hero-stat { padding: 0 1.4rem; border-inline-start: 1px solid rgba(255,255,255,.28); }
.hero-stat:first-child { border-inline-start: none; }
.hero-stat b { display: block; font-size: 1.7rem; line-height: 1.15; }
.hero-stat span { font-size: .85rem; color: #EBD3D8; }

.section-title {
    display: flex; align-items: center; gap: .6rem;
    font-size: 1.2rem; font-weight: 700; color: var(--ink);
    margin: 2rem 0 1rem;
}
.section-title::before {
    content: ""; width: 4px; height: 1.15em;
    background: var(--brand); border-radius: 2px;
}

/* الأخبار */
.news-card {
    background: var(--surface); border: 1px solid var(--line);
    border-radius: 12px; overflow: hidden; margin-bottom: .6rem;
}
.news-card img { width: 100%; height: 180px; object-fit: cover; display: block; }
.news-body { padding: 1rem 1.15rem 1.25rem; }
.news-body .nt { font-size: 1.05rem; font-weight: 700; line-height: 1.6; margin-bottom: .4rem; }
.news-body .nc { color: var(--muted); font-size: .95rem; line-height: 1.9; }

/* المشاريع */
.badge {
    display: inline-block; background: var(--bg); border: 1px solid var(--line);
    border-radius: 999px; padding: .1rem .75rem; font-size: .82rem;
    color: var(--muted); margin-bottom: .7rem;
}

/* عرض التقرير */
.viewer-head {
    background: var(--surface); border: 1px solid var(--line);
    border-radius: 12px; padding: 1.25rem 1.5rem; margin: 1rem 0;
}
.viewer-head .vt { font-size: 1.4rem; font-weight: 700; margin-bottom: .5rem; }
.viewer-head .vd { color: var(--muted); line-height: 1.9; margin-bottom: 1rem; }
.btn-link {
    display: inline-block; padding: .45rem 1.1rem; border-radius: 8px;
    background: var(--brand); color: #fff !important; font-weight: 600;
    text-decoration: none !important;
}
.btn-link:hover { background: var(--brand-deep); }
iframe { border: 1px solid var(--line) !important; border-radius: 12px; background: #fff; }

/* عناصر الإدخال والأزرار */
[data-testid="stForm"] {
    background: var(--surface); border: 1px solid var(--line);
    border-radius: 12px; padding: 1.5rem;
}
[data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="select"] > div { border-radius: 8px; }

[data-testid="stExpander"] details {
    background: var(--surface); border: 1px solid var(--line); border-radius: 12px;
}

.stButton > button,
.stDownloadButton > button,
.stFormSubmitButton > button {
    border-radius: 8px; font-weight: 600; padding: .45rem 1.1rem;
    border: 1px solid var(--line); background: var(--surface); color: var(--ink);
    transition: border-color .15s, color .15s, background .15s;
}
.stButton > button:hover,
.stDownloadButton > button:hover {
    border-color: var(--brand); color: var(--brand);
}
.stButton button *, .stDownloadButton button *, .stFormSubmitButton button * { color: inherit; }

.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"],
.stFormSubmitButton > button {
    background: var(--brand); border-color: var(--brand); color: #fff;
}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover,
.stFormSubmitButton > button:hover {
    background: var(--brand-deep); border-color: var(--brand-deep); color: #fff;
}

.stTabs [data-baseweb="tab-list"] { gap: .25rem; border-bottom: 1px solid var(--line); }
.stTabs [data-baseweb="tab"] { font-weight: 600; }
.stTabs [aria-selected="true"] { color: var(--brand); }
.stTabs [data-baseweb="tab-highlight"] { background: var(--brand); }

/* الجوال */
@media (max-width: 768px) {
    .block-container { padding: 1rem; }
    .hero { padding: 1.25rem; }
    .hero-title { font-size: 1.5rem; }
    .hero-stat { padding: 0 .9rem; }
}
</style>
"""


def build_css():
    rtl = cur_lang() == "ar"
    return (
        CSS_TEMPLATE.replace("__DIR__", "rtl" if rtl else "ltr")
        .replace("__ALIGN__", "right" if rtl else "left")
        .replace(
            "__FONT__",
            "'IBM Plex Sans Arabic', Tahoma, sans-serif"
            if rtl
            else "'Inter', 'Segoe UI', Arial, sans-serif",
        )
    )


st.markdown(build_css(), unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# دوال مساعدة
# ──────────────────────────────────────────────────────────────
esc = html.escape


def enhance_image(image_file):
    """تحسين الصورة (حدة وألوان) وإرجاعها كـ bytes بصيغة PNG."""
    img = Image.open(image_file)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img = ImageEnhance.Sharpness(img).enhance(1.3)
    img = ImageEnhance.Color(img).enhance(1.1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def sniff_mime(b):
    head = bytes(b[:12])
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"GIF8"):
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def img_src(img):
    """يحوّل رابط أو bytes إلى قيمة صالحة لوسم <img>."""
    if isinstance(img, (bytes, bytearray)):
        return f"data:{sniff_mime(img)};base64," + base64.b64encode(img).decode()
    return esc(str(img), quote=True)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_data_uri(url):
    """يحمّل الصورة من الرابط على السيرفر ويرجعها كـ data URI (أو None لو فشل)."""
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
        if r.ok and ctype.startswith("image/"):
            return f"data:{ctype};base64," + base64.b64encode(r.content).decode()
    except Exception:
        pass
    return None


def logo_html(src, alt):
    """وسم صورة للشعار، ولو تعذّر تحميلها يظهر اسم الشعار كنص."""
    if isinstance(src, (bytes, bytearray)):
        return f'<img src="{img_src(src)}" alt="{esc(alt)}">'
    uri = fetch_data_uri(str(src)) if src else None
    if uri:
        return f'<img src="{uri}" alt="{esc(alt)}">'
    return f'<div class="logo-fallback">{esc(alt)}</div>'


def safe_url(url):
    url = (url or "").strip()
    return url if url.startswith(("http://", "https://")) else ""


@st.cache_data(ttl=3600, show_spinner=False)
def resolve_short_url(url):
    """يتتبع التحويلات للرابط القصير ويرجع الرابط النهائي."""
    try:
        r = requests.get(url, allow_redirects=True, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
        return r.url
    except Exception:
        return url


_REPORT_RE = re.compile(
    r"(?:lookerstudio|datastudio)\.google\.com/(?:u/\d+/)?reporting/([0-9a-zA-Z-]+)(?:/page/([0-9a-zA-Z_-]+))?"
)


def to_embed_url(url):
    """يحوّل رابط تقرير Looker Studio (عادي أو قصير) إلى رابط التضمين الصالح للـ iframe."""
    url = safe_url(url)
    if not url or "/embed/reporting/" in url:
        return url
    original = url
    if "/s/" in url and ("lookerstudio.google.com" in url or "datastudio.google.com" in url):
        url = resolve_short_url(url)
    m = _REPORT_RE.search(url)
    if m:
        embed = f"https://lookerstudio.google.com/embed/reporting/{m.group(1)}"
        if m.group(2):
            embed += f"/page/{m.group(2)}"
        return embed
    return original


def section_title(text):
    st.markdown(f'<div class="section-title">{esc(text)}</div>', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
# البيانات الافتراضية
# ──────────────────────────────────────────────────────────────
DEFAULT_NEWS_IMAGE = "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=800&auto=format&fit=crop&q=60"

DEFAULT_DASHBOARDS = {
    "مؤشرات أداء قسم الـ QA": {
        "name_en": "QA Department Performance Indicators",
        "title": "📊 QA Dashboard تحليل الأداء قسم الجودة",
        "title_en": "📊 QA Dashboard – Quality Department Performance Analysis",
        "description": "تحتوي هذه الداشبورد على تحليلات شاملة للنشاطات اليومية والشهرية، بالإضافة إلى مقارنة الأداء ومؤشرات الأداء الرئيسية (KPIs).",
        "description_en": "This dashboard contains comprehensive analyses of daily and monthly activities, along with performance comparisons and key performance indicators (KPIs).",
        "url": "https://datastudio.google.com/s/pZkBFbgR5as",
        "embed_url": "",
        "category": "مؤشرات الأداء",
        "files": [],
    },
    "مشروع الـ TPV": {
        "name_en": "TPV Project",
        "title": "📈 TPV Dashboard",
        "title_en": "📈 TPV Dashboard",
        "description": "تستعرض الداشبورد تفاصيل مشروع TPV ونتيجتها وتفاصيل الأنشطة المستخدمة يومياً من قسم الجودة ونسب الربحية لمختلف القطاعات.",
        "description_en": "The dashboard presents the TPV project details and results, the activities used daily by the Quality department, and profitability rates across the different sectors.",
        "url": "https://datastudio.google.com/s/lzMLkPXvy28",
        "embed_url": "",
        "category": "المشاريع",
        "files": [],
    },
}

DEFAULT_NEWS = [
    {
        "title": "📢 إطلاق نظام إدارة الجودة الجديد للعام الحالي",
        "title_en": "📢 Launching the new quality management system for this year",
        "content": "تم تحديث كافة تقارير ومؤشرات الأداء الخاصة بقسم الجودة لرفع كفاءة ومتابعة العمليات التشغيلية اليومية.",
        "content_en": "All reports and performance indicators of the Quality department have been updated to improve the efficiency of following up daily operations.",
        "image": "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=800&auto=format&fit=crop&q=60",
    },
    {
        "title": "🚀 ورشة عمل لتقييم الأداء والإنتاجية",
        "title_en": "🚀 Performance and productivity evaluation workshop",
        "content": "تابعوا تفاصيل الأنشطة اليومية عبر داشبورد TPV المحدثة ومراجعات التقارير الدورية المرفقة.",
        "content_en": "Follow the daily activity details through the updated TPV dashboard and the attached periodic report reviews.",
        "image": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800&auto=format&fit=crop&q=60",
    },
]

DEFAULT_USERS = {
    "admin": {"password": "123", "name": "مدير النظام", "name_en": "System Admin", "role": "admin"},
    "manager.qa@fnrco.com.sa": {"password": "M123", "name": "مدير القسم", "name_en": "Department Manager", "role": "manager"},
    "hossam.saeed@fnrco.com.sa": {"password": "HS123", "name": "حسام سعيد", "name_en": "Hossam Saeed", "role": "user"},
    "abdelrahman.lashine@fnrco.com.sa": {"password": "AL123", "name": "عبد الرحمن لاشين", "name_en": "Abdelrahman Lashine", "role": "user"},
    "yassmen.khaled@fnrco.com.sa": {"password": "HS123", "name": "ياسمين خالد", "name_en": "Yassmen Khaled", "role": "user"},
    "kenzy.hisham@fnrco.com.sa": {"password": "KH123", "name": "كنزي هشام", "name_en": "Kenzy Hisham", "role": "user"},
    "lamia.adel@fnrco.com.sa": {"password": "LA123", "name": "لمياء عادل", "name_en": "Lamia Adel", "role": "user"},
    "nancy.safwat@fnrco.com.sa": {"password": "NS123", "name": "نانسي صفوت", "name_en": "Nancy Safwat", "role": "user"},
    "abdallah.zaukzouk@fnrco.com.sa": {"password": "AZ123", "name": "عبد الله زقزوق", "name_en": "Abdallah Zaukzouk", "role": "user"},
}


# ──────────────────────────────────────────────────────────────
# التخزين الدائم (الشعارات والأجهزة الموثوقة)
#  1) قرص السيرفر (مجلد app_data)
#  2) اختياري: فرع على GitHub (من خلال st.secrets) ليبقى الحفظ دائماً حتى بعد إعادة تشغيل التطبيق
#     GITHUB_TOKEN = "..."   GITHUB_REPO = "owner/repo"   GITHUB_BRANCH = "app-data"
# ──────────────────────────────────────────────────────────────
APP_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.environ.get("APP_DATA_DIR", str(APP_DIR / "app_data")))
TRUST_DAYS = 90


def _gh_conf():
    try:
        token = st.secrets.get("GITHUB_TOKEN")
        repo = st.secrets.get("GITHUB_REPO")
        branch = st.secrets.get("GITHUB_BRANCH", "app-data")
    except Exception:
        return None
    return (token, repo, branch) if token and repo else None


def _gh_headers(token, raw=False):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _gh_read(name):
    conf = _gh_conf()
    if not conf:
        return None
    token, repo, branch = conf
    try:
        r = requests.get(
            f"https://api.github.com/repos/{repo}/contents/{name}",
            params={"ref": branch},
            headers=_gh_headers(token, raw=True),
            timeout=15,
        )
        return r.content if r.status_code == 200 else None
    except Exception:
        return None


def _gh_ensure_branch(token, repo, branch):
    base = f"https://api.github.com/repos/{repo}"
    h = _gh_headers(token)
    if requests.get(f"{base}/git/ref/heads/{branch}", headers=h, timeout=15).status_code == 200:
        return True
    default = requests.get(base, headers=h, timeout=15).json().get("default_branch", "main")
    sha = requests.get(f"{base}/git/ref/heads/{default}", headers=h, timeout=15).json()["object"]["sha"]
    r = requests.post(
        f"{base}/git/refs", headers=h, json={"ref": f"refs/heads/{branch}", "sha": sha}, timeout=15
    )
    return r.status_code in (200, 201)


def _gh_write(name, data):
    conf = _gh_conf()
    if not conf:
        return False
    token, repo, branch = conf
    try:
        if not _gh_ensure_branch(token, repo, branch):
            return False
        url = f"https://api.github.com/repos/{repo}/contents/{name}"
        h = _gh_headers(token)
        payload = {
            "message": f"update {name}",
            "content": base64.b64encode(data).decode(),
            "branch": branch,
        }
        cur = requests.get(url, params={"ref": branch}, headers=h, timeout=15)
        if cur.status_code == 200:
            payload["sha"] = cur.json()["sha"]
        r = requests.put(url, headers=h, json=payload, timeout=30)
        return r.status_code in (200, 201)
    except Exception:
        return False


def persist_write(name, data, remote=True):
    """يحفظ الملف على القرص (+ GitHub لو مفعّل). يرجع: github | github_failed | disk | memory."""
    on_disk = False
    try:
        path = DATA_DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        on_disk = True
    except Exception:
        pass
    if remote and _gh_conf():
        return "github" if _gh_write(name, data) else "github_failed"
    return "disk" if on_disk else "memory"


def persist_read(name):
    try:
        path = DATA_DIR / name
        if path.exists():
            return path.read_bytes()
    except Exception:
        pass
    data = _gh_read(name)
    if data:
        persist_write(name, data, remote=False)  # كاش محلي
    return data


def bundled_file(*names):
    """ملف موجود داخل مجلد التطبيق (مثلاً الشعار الذي رفعته في الريبو)."""
    for n in names:
        try:
            p = APP_DIR / n
            if p.exists():
                return p.read_bytes()
        except Exception:
            pass
    return None


def load_devices():
    try:
        raw = persist_read("trusted_devices.json")
        data = json.loads(raw.decode("utf-8")) if raw else []
        now = time.time()
        return [d for d in data if d.get("expires_at", 0) > now and d.get("token_hash")]
    except Exception:
        return []


def save_devices(devices, sync=True):
    persist_write(
        "trusted_devices.json",
        json.dumps(devices, ensure_ascii=False).encode("utf-8"),
        remote=sync,
    )


def save_logo(kind, uploaded_file):
    """يحفظ الشعار المرفوع بشكل دائم ويجهّز رسالة النتيجة."""
    data = enhance_image(uploaded_file)
    store[kind] = data
    st.session_state.flash = persist_write(f"logos/{kind}.png", data)


@st.cache_resource
def get_store():
    """مخزن مشترك بين كل الجلسات (المستخدمون، المشاريع، الأخبار، الشعارات...).
    ملاحظة: يبقى في الذاكرة فقط، ويُعاد ضبطه عند إعادة تشغيل التطبيق."""
    return {
        "users": copy.deepcopy(DEFAULT_USERS),
        "dashboards": copy.deepcopy(DEFAULT_DASHBOARDS),
        "news": copy.deepcopy(DEFAULT_NEWS),
        "company_logo": persist_read("logos/company_logo.png")
        or bundled_file("Linrco-Egypt.PNG", "Linrco-Egypt.png")
        or "https://raw.githubusercontent.com/ahmedgouda2727/QA-Dashboard-APP/main/Linrco-Egypt.PNG",
        "qa_logo": persist_read("logos/qa_logo.png")
        or bundled_file("QA.png", "QA.PNG")
        or "https://raw.githubusercontent.com/ahmedgouda2727/QA-Dashboard-APP/main/QA.png",
        "totp_secret": "JBSWY3DPEHPK3PXP",
        "trusted_devices": load_devices(),
    }


store = get_store()


# ── الأجهزة الموثوقة (كوكي في المتصفح + سجل في السيرفر يستطيع الأدمن حذفه) ──
def cookie_name(username):
    return "qa_td_" + hashlib.sha256(username.encode()).hexdigest()[:12]


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def purge_expired():
    devs = store["trusted_devices"]
    now = time.time()
    keep = [d for d in devs if d.get("expires_at", 0) > now]
    if len(keep) != len(devs):
        devs[:] = keep
        save_devices(devs)


def is_device_trusted(username):
    """هل هذا المتصفح موثوق لهذا المستخدم (ولم تنتهِ مدة الـ 3 شهور)؟"""
    if username in st.session_state.trusted_users:
        return True
    try:
        token = st.context.cookies.get(cookie_name(username))
    except Exception:
        token = None
    if not token:
        return False
    purge_expired()
    h = hash_token(token)
    for d in store["trusted_devices"]:
        if d["user"] == username and hmac.compare_digest(d["token_hash"], h):
            d["last_used"] = time.time()
            save_devices(store["trusted_devices"], sync=False)
            return True
    return False


def trust_device(username, device_name):
    """يسجّل الجهاز كموثوق لمدة 3 شهور، ويجهّز الكوكي ليُكتب في المتصفح."""
    token = secrets.token_urlsafe(32)
    now = time.time()
    store["trusted_devices"].append(
        {
            "id": secrets.token_hex(6),
            "name": device_name,
            "user": username,
            "token_hash": hash_token(token),
            "created_at": now,
            "expires_at": now + TRUST_DAYS * 86400,
            "last_used": now,
        }
    )
    save_devices(store["trusted_devices"])
    st.session_state.trusted_users.add(username)
    st.session_state.pending_cookie = (cookie_name(username), token)


def remove_device(device_id):
    devs = store["trusted_devices"]
    devs[:] = [d for d in devs if d["id"] != device_id]
    save_devices(devs)


def remove_user_devices(username):
    devs = store["trusted_devices"]
    devs[:] = [d for d in devs if d["user"] != username]
    save_devices(devs)


def flush_pending_cookie():
    """يكتب كوكي الجهاز الموثوق في المتصفح (مرة واحدة بعد التحقق الناجح)."""
    pending = st.session_state.pop("pending_cookie", None)
    if not pending:
        return
    name, value = pending
    max_age = TRUST_DAYS * 86400
    st.components.v1.html(
        f"""<script>
        (function () {{
            var p = window.parent;
            var secure = p.location.protocol === 'https:' ? '; Secure' : '';
            p.document.cookie = "{name}={value}; max-age={max_age}; path=/; SameSite=Lax" + secure;
        }})();
        </script>""",
        height=0,
    )


def guess_device():
    """اسم افتراضي للجهاز من نوع المتصفح والنظام."""
    try:
        ua = st.context.headers.get("User-Agent", "")
    except Exception:
        ua = ""
    browser = next(
        (n for k, n in [("Edg/", "Edge"), ("OPR/", "Opera"), ("Firefox", "Firefox"), ("Chrome", "Chrome"), ("Safari", "Safari")] if k in ua),
        "Browser",
    )
    os_name = next(
        (n for k, n in [("Windows", "Windows"), ("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"), ("Mac OS", "macOS"), ("Linux", "Linux")] if k in ua),
        "",
    )
    return f"{browser} / {os_name}" if os_name else browser


def fmt_date(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else "—"


def project_name(key):
    d = store["dashboards"].get(key, {})
    return d.get("name_en") if cur_lang() == "en" and d.get("name_en") else key


# حالة الجلسة الخاصة بكل متصفح
for _key, _default in {
    "logged_in": False,
    "two_fa_passed": False,
    "trusted_users": set(),
    "username": "",
    "show_admin_settings": False,
    "selected_project": None,
}.items():
    st.session_state.setdefault(_key, _default)


def logout():
    st.session_state.logged_in = False
    st.session_state.two_fa_passed = False
    st.session_state.show_admin_settings = False
    st.session_state.username = ""
    st.rerun()


# ──────────────────────────────────────────────────────────────
# الشاشات
# ──────────────────────────────────────────────────────────────
def login_brand(title, subtitle):
    st.markdown(
        f"""
        <div class="login-brand">
            {logo_html(store['company_logo'], t('company_name'))}
            <div class="t">{esc(title)}</div>
            <div class="s">{esc(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_login():
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        language_selector("lang_login")
        login_brand(t("login_title"), t("login_sub"))
        with st.form("login_form"):
            username_input = st.text_input(t("username_label"))
            password_input = st.text_input(t("password"), type="password")
            submitted = st.form_submit_button(t("sign_in"), type="primary")

        if submitted:
            clean = username_input.strip().lower()
            users = store["users"]
            if clean in users and users[clean]["password"] == password_input:
                st.session_state.logged_in = True
                st.session_state.username = clean
                if users[clean]["role"] == "admin" or is_device_trusted(clean):
                    st.session_state.two_fa_passed = True
                st.rerun()
            else:
                st.error(t("login_error"))


def render_2fa():
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        language_selector("lang_2fa")
        login_brand(t("tfa_title"), t("tfa_sub"))
        with st.form("2fa_form"):
            totp_code = st.text_input(t("tfa_code"), max_chars=6)
            device_name = st.text_input(t("device_name"), value=guess_device())
            trust = st.checkbox(t("trust_device"), value=True)
            verify = st.form_submit_button(t("verify"), type="primary")

        if verify:
            totp = pyotp.TOTP(store["totp_secret"])
            if totp.verify(totp_code, valid_window=2):
                st.session_state.two_fa_passed = True
                if trust:
                    trust_device(st.session_state.username, device_name.strip() or guess_device())
                st.rerun()
            else:
                st.error(t("tfa_error"))

        if st.button(t("back_login")):
            logout()


def render_side_panel(user_info, is_admin):
    """لوحة جانبية: يمين في العربي وشمال في الإنجليزي.
    للجميع: لوجو الشركة + لوجو القسم + أهلاً بك واسم المستخدم + اختيار اللغة + تسجيل الخروج.
    للأدمن فقط: الإعدادات وتغيير الشعارات."""
    st.markdown('<span class="side-marker"></span>', unsafe_allow_html=True)

    st.markdown(
        f'<div class="sb-logo">{logo_html(store["company_logo"], t("company_name"))}</div>'
        f'<div class="sb-logo">{logo_html(store["qa_logo"], t("qa_name"))}</div>',
        unsafe_allow_html=True,
    )

    name = loc(user_info, "name")
    st.markdown(
        f"""
        <div class="user-chip">
            <div class="avatar">{esc(name[:1])}</div>
            <div>
                <div class="name">{esc(t('welcome', name=name))}</div>
                <div class="role">{esc(role_label(user_info['role']))}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── اختيار اللغة (للجميع) ──
    st.markdown(f'<div class="sb-label">{esc(t("language"))}</div>', unsafe_allow_html=True)
    language_selector("lang_panel")

    # ── أدوات الأدمن فقط ──
    if is_admin:
        on_settings = st.session_state.show_admin_settings
        st.markdown(f'<div class="sb-label">{esc(t("menu"))}</div>', unsafe_allow_html=True)

        if st.button(
            t("home"),
            key="nav_home",
            type="secondary" if on_settings else "primary",
        ):
            st.session_state.show_admin_settings = False
            st.rerun()

        if st.button(
            t("admin_settings"),
            key="nav_admin",
            type="primary" if on_settings else "secondary",
        ):
            st.session_state.show_admin_settings = True
            st.rerun()

        with st.popover(t("change_logos")):
            up_c = st.file_uploader(
                t("new_company_logo"), type=["png", "jpg", "jpeg"], key="hd_c_logo"
            )
            if up_c is not None and st.button(t("save_company_logo"), key="save_c_logo"):
                save_logo("company_logo", up_c)
                st.rerun()

            st.markdown('<div class="sb-sep"></div>', unsafe_allow_html=True)

            up_q = st.file_uploader(
                t("new_qa_logo"), type=["png", "jpg", "jpeg"], key="hd_qa_logo"
            )
            if up_q is not None and st.button(t("save_qa_logo"), key="save_qa_logo"):
                save_logo("qa_logo", up_q)
                st.rerun()

            st.caption(t("storage_on") if _gh_conf() else t("storage_off"))

    st.markdown('<div class="sb-sep"></div>', unsafe_allow_html=True)
    if st.button(t("logout"), key="logout_btn"):
        logout()


def render_admin_settings(current_user):
    st.title(t("settings_title"))
    st.caption(t("settings_caption"))

    tab_sec, tab_users = st.tabs([t("tab_security"), t("tab_users")])

    with tab_sec:
        section_title(t("link_phone_title"))
        st.markdown(t("link_steps"))
        uri = pyotp.totp.TOTP(store["totp_secret"]).provisioning_uri(
            name="Linrco-QA-Admin", issuer_name="Linrco Quality Assurance"
        )
        buf = io.BytesIO()
        qrcode.make(uri).save(buf)
        st.image(buf.getvalue(), width=230)
        st.code(store["totp_secret"], language="text")

        section_title(t("devices_title"))
        purge_expired()
        devices = store["trusted_devices"]
        if devices:
            for dev in list(devices):
                uname = dev["user"]
                shown = loc(store["users"].get(uname, {}), "name") or uname
                c1, c2 = st.columns([4, 1], vertical_alignment="center")
                with c1:
                    st.markdown(
                        f"**{dev['name']}**  \n"
                        f"{t('user_word')}: {shown} ({uname}) · "
                        f"{t('dev_trusted_on')}: {fmt_date(dev.get('created_at'))} · "
                        f"{t('dev_expires')}: {fmt_date(dev.get('expires_at'))} · "
                        f"{t('dev_last_used')}: {fmt_date(dev.get('last_used'))}"
                    )
                with c2:
                    if st.button(t("remove_device"), key=f"del_dev_{dev['id']}"):
                        remove_device(dev["id"])
                        st.rerun()
            if st.button(t("remove_all_devices"), key="del_all_devs"):
                devices.clear()
                save_devices(devices)
                st.rerun()
        else:
            st.info(t("no_devices"))

    with tab_users:
        section_title(t("current_users"))
        st.table(
            [
                {
                    t("col_user"): uname,
                    t("col_name"): loc(udata, "name"),
                    t("col_role"): role_label(udata["role"]),
                }
                for uname, udata in store["users"].items()
            ]
        )

        section_title(t("add_user"))
        with st.form("add_user_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                new_email = st.text_input(t("f_email"))
                new_name = st.text_input(t("f_name"))
            with c2:
                new_pass = st.text_input(t("f_pass"), type="password")
                new_role = st.selectbox(
                    t("f_role"), ["admin", "manager", "user"], format_func=role_label
                )
            add_user = st.form_submit_button(t("add_user_btn"), type="primary")

        if add_user:
            if new_email and new_pass and new_name:
                store["users"][new_email.strip().lower()] = {
                    "password": new_pass,
                    "name": new_name,
                    "role": new_role,
                }
                st.success(t("user_added", name=new_name))
                st.rerun()
            else:
                st.warning(t("fill_all"))

        section_title(t("delete_user"))
        deletable = [u for u in store["users"] if u not in ("admin", current_user)]
        target = st.selectbox(
            t("choose_user"),
            deletable,
            format_func=lambda u: f"{loc(store['users'][u], 'name')} ({u})" if u in store["users"] else u,
        )
        if st.button(t("delete_selected")) and target in store["users"]:
            del store["users"][target]
            remove_user_devices(target)
            st.session_state.trusted_users.discard(target)
            st.rerun()


def render_manage_panel():
    """لوحة إدارة المشاريع والأخبار (للأدمن والمدير)."""
    dashboards = store["dashboards"]

    with st.expander(t("manage_panel")):
        tab1, tab2, tab3 = st.tabs([t("tab_edit"), t("tab_add_project"), t("tab_add_news")])

        with tab1:
            edit_key = st.selectbox(
                t("project"), list(dashboards.keys()), format_func=project_name, key="edit_select"
            )
            if edit_key:
                cur = dashboards[edit_key]
                new_title = st.text_input(t("f_title"), value=cur["title"], key=f"edit_title_{edit_key}")
                new_title_en = st.text_input(
                    t("f_title_en"), value=cur.get("title_en", ""), key=f"edit_title_en_{edit_key}"
                )
                new_desc = st.text_area(t("f_desc"), value=cur["description"], key=f"edit_desc_{edit_key}")
                new_desc_en = st.text_area(
                    t("f_desc_en"), value=cur.get("description_en", ""), key=f"edit_desc_en_{edit_key}"
                )
                new_url = st.text_input(t("f_url"), value=cur["url"], key=f"edit_url_{edit_key}")
                new_embed = st.text_input(
                    t("f_embed"),
                    value=cur.get("embed_url", ""),
                    key=f"edit_embed_{edit_key}",
                    help=t("embed_help"),
                )
                new_cat = st.text_input(
                    t("f_category"),
                    value=cat_label(cur.get("category", "عام")),
                    key=f"edit_cat_{edit_key}",
                )
                uploaded = st.file_uploader(
                    t("attach_doc"),
                    type=["docx", "xlsx", "pdf", "vsdx", "pbix", "accdb", "msg", "txt"],
                    key=f"up_{edit_key}",
                )
                if st.button(t("save_changes"), type="primary", key=f"save_{edit_key}"):
                    files = cur.get("files", [])
                    if uploaded is not None:
                        files.append({"name": uploaded.name, "data": uploaded.getvalue()})
                    dashboards[edit_key] = {
                        **cur,
                        "title": new_title,
                        "title_en": new_title_en.strip(),
                        "description": new_desc,
                        "description_en": new_desc_en.strip(),
                        "url": new_url,
                        "embed_url": new_embed.strip(),
                        "category": norm_cat(new_cat),
                        "files": files,
                    }
                    st.rerun()

        with tab2:
            add_name = st.text_input(t("add_name"), key="add_name")
            add_name_en = st.text_input(t("add_name_en"), key="add_name_en")
            add_title = st.text_input(t("add_main_title"), key="add_title")
            add_title_en = st.text_input(t("f_title_en"), key="add_title_en")
            add_desc = st.text_area(t("f_desc"), key="add_desc")
            add_desc_en = st.text_area(t("f_desc_en"), key="add_desc_en")
            add_url = st.text_input(t("add_dash_url"), key="add_url")
            add_embed = st.text_input(t("f_embed"), key="add_embed")
            add_cat = st.text_input(t("f_category"), value=cat_label("عام"), key="add_cat")
            if st.button(t("add_project_btn"), type="primary", key="add_project_btn"):
                if add_name and add_url:
                    dashboards[add_name] = {
                        "name_en": add_name_en.strip(),
                        "title": add_title,
                        "title_en": add_title_en.strip(),
                        "description": add_desc,
                        "description_en": add_desc_en.strip(),
                        "url": add_url,
                        "embed_url": add_embed.strip(),
                        "category": norm_cat(add_cat),
                        "files": [],
                    }
                    st.rerun()
                else:
                    st.warning(t("need_name_url"))

        with tab3:
            news_title = st.text_input(t("news_title"), key="news_t")
            news_title_en = st.text_input(t("news_title_en"), key="news_t_en")
            news_content = st.text_area(t("news_text"), key="news_c")
            news_content_en = st.text_area(t("news_text_en"), key="news_c_en")
            news_img = st.file_uploader(t("news_image"), type=["png", "jpg", "jpeg"], key="news_img_upload")
            if st.button(t("publish_news"), type="primary", key="publish_news_btn"):
                if news_title and news_content:
                    store["news"].append(
                        {
                            "title": news_title,
                            "title_en": news_title_en.strip(),
                            "content": news_content,
                            "content_en": news_content_en.strip(),
                            "image": enhance_image(news_img) if news_img is not None else DEFAULT_NEWS_IMAGE,
                        }
                    )
                    st.rerun()
                else:
                    st.warning(t("need_news"))


def render_news(can_manage):
    news = store["news"]
    if not news:
        return
    section_title(t("latest_news"))

    per_row = 3 if len(news) >= 3 else len(news)
    for start in range(0, len(news), per_row):
        cols = st.columns(per_row)
        for offset, item in enumerate(news[start:start + per_row]):
            idx = start + offset
            with cols[offset]:
                image_html = f'<img src="{img_src(item["image"])}" alt="">' if item.get("image") else ""
                st.markdown(
                    f"""
                    <div class="news-card">
                        {image_html}
                        <div class="news-body">
                            <div class="nt">{esc(loc(item, 'title'))}</div>
                            <div class="nc">{esc(loc(item, 'content'))}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if can_manage:
                    with st.expander(t("manage_news")):
                        new_img = st.file_uploader(
                            t("new_image"), type=["png", "jpg", "jpeg"], key=f"news_ch_{idx}"
                        )
                        if new_img is not None and st.button(t("save_image"), key=f"btn_ch_{idx}"):
                            news[idx]["image"] = enhance_image(new_img)
                            st.rerun()
                        if st.button(t("delete_news"), key=f"btn_del_news_{idx}"):
                            news.pop(idx)
                            st.rerun()


def render_projects(can_manage):
    dashboards = store["dashboards"]
    if not dashboards:
        st.info(t("no_projects"))
        return

    section_title(t("projects_title"))

    # ── الفلاتر: بحث نصي + تصنيف ──
    categories = sorted({(d.get("category") or "عام") for d in dashboards.values()})
    f1, f2 = st.columns([2, 1])
    with f1:
        query = st.text_input(
            t("search"),
            placeholder=t("search_ph"),
            key="project_query",
        ).strip().lower()
    with f2:
        category = st.selectbox(
            t("f_category"),
            ["__all__"] + categories,
            format_func=lambda c: t("all") if c == "__all__" else cat_label(c),
            key="project_category",
        )

    def matches(name, d):
        if category != "__all__" and (d.get("category") or "عام") != category:
            return False
        if not query:
            return True
        haystack = " ".join(
            [
                name,
                d.get("name_en", ""),
                d.get("title", ""),
                d.get("title_en", ""),
                d.get("description", ""),
                d.get("description_en", ""),
            ]
        ).lower()
        return query in haystack

    options = [name for name, d in dashboards.items() if matches(name, d)]
    st.caption(t("results_count", n=len(options), total=len(dashboards)))

    if not options:
        st.info(t("no_match"))
        return

    # لو المشروع المختار خرج من نتائج الفلتر نرجع لأول نتيجة
    if st.session_state.get("project_select") not in options:
        st.session_state["project_select"] = options[0]
    selected = st.selectbox(
        t("choose_project"), options, format_func=project_name, key="project_select"
    )

    # ── عارض التقرير ──
    data = dashboards[selected]
    url = safe_url(data["url"])
    embed_url = safe_url(data.get("embed_url", "")) or to_embed_url(data["url"])
    link_html = (
        f'<a class="btn-link" href="{esc(url, quote=True)}" target="_blank" rel="noopener">{esc(t("open_new_tab"))}</a>'
        if url
        else ""
    )
    files = data.get("files", [])
    st.markdown(
        f"""
        <div class="viewer-head">
            <span class="badge">{esc(cat_label(data.get('category')))}</span>
            <div class="vt">{esc(loc(data, 'title'))}</div>
            <div class="vd">{esc(loc(data, 'description'))}</div>
            {link_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    if files:
        with st.expander(t("attached_files", n=len(files))):
            for j, f in enumerate(files):
                st.download_button(
                    label=t("download", name=f["name"]),
                    data=f["data"],
                    file_name=f["name"],
                    mime="application/octet-stream",
                    key=f"dl_{selected}_{j}",
                )

    if embed_url:
        st.components.v1.iframe(embed_url, height=820, scrolling=True)
        st.caption(t("iframe_hint"))
        if can_manage:
            with st.expander(t("trouble")):
                st.markdown(t("trouble_md"))
                st.code(embed_url, language="text")
    else:
        st.warning(t("invalid_url"))


def render_portal(user_info, can_manage):
    dashboards = store["dashboards"]
    files_total = sum(len(d.get("files", [])) for d in dashboards.values())

    st.markdown(
        f"""
        <div class="hero">
            <div>
                <div class="hero-title">{esc(t('hero_title'))}</div>
                <div class="hero-sub">{esc(t('hero_sub', name=loc(user_info, 'name')))}</div>
            </div>
            <div class="hero-stats">
                <div class="hero-stat"><b>{len(dashboards)}</b><span>{esc(t('stat_projects'))}</span></div>
                <div class="hero-stat"><b>{len(store['news'])}</b><span>{esc(t('stat_news'))}</span></div>
                <div class="hero-stat"><b>{files_total}</b><span>{esc(t('stat_files'))}</span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if can_manage:
        render_manage_panel()

    render_news(can_manage)
    render_projects(can_manage)


# ──────────────────────────────────────────────────────────────
# التوجيه الرئيسي
# ──────────────────────────────────────────────────────────────
if not st.session_state.logged_in:
    render_login()

elif not st.session_state.two_fa_passed:
    render_2fa()

else:
    current_user = st.session_state.username
    if current_user not in store["users"]:  # تم حذف المستخدم أثناء الجلسة
        logout()

    user_info = store["users"][current_user]
    is_admin = user_info["role"] == "admin"
    can_manage = user_info["role"] in ("admin", "manager")

    flush_pending_cookie()

    _flash = st.session_state.pop("flash", None)
    if _flash:
        _msg = {"github": "saved_github", "github_failed": "saved_failed"}.get(_flash, "saved_temp")
        st.toast(t(_msg), icon="✅" if _flash == "github" else "⚠️")

    # العمود الأول هو اللوحة الجانبية: يظهر يمين الصفحة في العربي (RTL) وشمالها في الإنجليزي (LTR)
    side_col, main_col = st.columns([1, 3.6], gap="large")

    with side_col:
        render_side_panel(user_info, is_admin)

    with main_col:
        if is_admin and st.session_state.show_admin_settings:
            render_admin_settings(current_user)
        else:
            render_portal(user_info, can_manage)
