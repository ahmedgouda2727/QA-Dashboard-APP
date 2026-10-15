import base64
import copy
import html
import io
import re

import pyotp
import qrcode
import requests
import streamlit as st
from PIL import Image, ImageEnhance

# ──────────────────────────────────────────────────────────────
# إعدادات الصفحة
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="بوابة الجودة - ليناركو",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ──────────────────────────────────────────────────────────────
# التنسيق (CSS)
# ──────────────────────────────────────────────────────────────
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Arabic:wght@400;500;600;700&display=swap');

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

/* إخفاء عناصر ستريمليت الافتراضية (مع الإبقاء على زر الشريط الجانبي) */
#MainMenu, footer,
[data-testid="stDecoration"],
[data-testid="stToolbarActions"],
[data-testid="stMainMenu"],
[data-testid="stAppDeployButton"],
[data-testid="stStatusWidget"] { display: none !important; }
header[data-testid="stHeader"] { background: transparent; }

/* لا نستخدم الشريط الجانبي: كل شيء في الهيدر العلوي */
[data-testid="stSidebar"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stExpandSidebarButton"] { display: none !important; }

/* (قديم) */
[data-testid="stToolbar"],
[data-testid="stExpandSidebarButton"],
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapseButton"] {
    visibility: visible !important;
    opacity: 1 !important;
}

/* الاتجاه والخط
   مهم: الحاوية الخارجية تبقى LTR حتى لا يتداخل الشريط الجانبي مع المحتوى،
   والاتجاه RTL يُطبَّق على المحتوى نفسه وعلى محتوى الشريط الجانبي. */
.stApp {
    background: var(--bg);
    color: var(--ink);
}
[data-testid="stAppViewContainer"] { direction: ltr; }
[data-testid="stMain"],
[data-testid="stSidebarContent"] { direction: rtl; }

.stApp,
.stApp :is(p, h1, h2, h3, h4, h5, h6, label, input, textarea, button, li, a, td, th, caption, summary) {
    font-family: 'IBM Plex Sans Arabic', Tahoma, sans-serif !important;
}
.stApp :is(p, h1, h2, h3, h4, h5, h6, label, li) { text-align: right; }
[data-testid="stCode"], .stApp code { direction: ltr; text-align: left; }

.block-container {
    max-width: 1400px;
    padding: 2.5rem 2rem 4rem;
}
h1, h2, h3 { color: var(--ink); font-weight: 700; }

/* الشريط الجانبي */
[data-testid="stSidebar"] {
    background: var(--surface);
    border-right: 1px solid var(--line);
}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding: 1rem .9rem; }
[data-testid="stSidebar"] .stButton { margin-bottom: .35rem; }
[data-testid="stSidebar"] .stButton > button { width: 100%; justify-content: center; }
[data-testid="stSidebar"] [data-testid="stExpander"] summary { text-align: right; }
[data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] { flex-wrap: wrap; gap: .5rem; }

.sb-logo {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: .75rem;
    margin-bottom: .6rem;
    text-align: center;
}
.sb-logo img { max-width: 100%; max-height: 64px; object-fit: contain; }
.logo-fallback {
    font-weight: 700; color: var(--brand); padding: .5rem 0; font-size: 1.05rem;
}
.sb-label {
    font-size: .8rem; font-weight: 600; color: var(--muted);
    margin: 1rem .25rem .5rem;
}
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
.login-brand { text-align: center; margin: 2.5rem 0 1.25rem; }
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

/* اللوحة الجانبية اليمنى */
[data-testid="stColumn"]:has(.side-marker) {
    position: sticky; top: 3.5rem; align-self: flex-start;
}
[data-testid="stColumn"]:has(.side-marker) > [data-testid="stVerticalBlock"] {
    background: var(--surface); border: 1px solid var(--line);
    border-radius: 14px; padding: 1rem;
}
[data-testid="stColumn"]:has(.side-marker) .stButton > button,
[data-testid="stColumn"]:has(.side-marker) [data-testid="stPopover"] > button,
[data-testid="stColumn"]:has(.side-marker) [data-testid="stPopover"] { width: 100%; }
[data-testid="stColumn"]:has(.side-marker) [data-testid="stPopover"] > button {
    border-radius: 8px; font-weight: 600; justify-content: center;
}
.side-marker { display: none; }

/* الجوال */
@media (max-width: 768px) {
    .block-container { padding: 1rem; }
    .hero { padding: 1.25rem; }
    .hero-title { font-size: 1.5rem; }
    .hero-stat { padding: 0 .9rem; }
}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


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


def img_src(img):
    """يحوّل رابط أو bytes إلى قيمة صالحة لوسم <img>."""
    if isinstance(img, (bytes, bytearray)):
        return "data:image/png;base64," + base64.b64encode(img).decode()
    return esc(str(img), quote=True)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_data_uri(url):
    """يحمّل الصورة من الرابط على السيرفر ويرجعها كـ data URI (أو None لو فشل التحميل).
    هذا يتجنب مشكلة الصور المكسورة عند حظر المتصفح للرابط الخارجي."""
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        ctype = r.headers.get("content-type", "").split(";")[0].strip().lower()
        if r.ok and ctype.startswith("image/"):
            return f"data:{ctype};base64," + base64.b64encode(r.content).decode()
    except Exception:
        pass
    return None


def logo_html(src, alt):
    """وسم صورة للشعار، ولو تعذّر تحميلها يظهر اسم الشعار كنص بدل الأيقونة المكسورة."""
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
        "title": "📊 QA Dashboard تحليل الأداء قسم الجودة",
        "description": "تحتوي هذه الداشبورد على تحليلات شاملة للنشاطات اليومية والشهرية، بالإضافة إلى مقارنة الأداء ومؤشرات الأداء الرئيسية (KPIs).",
        "url": "https://datastudio.google.com/s/pZkBFbgR5as",
        "embed_url": "",
        "category": "مؤشرات الأداء",
        "files": [],
    },
    "مشروع الـ TPV": {
        "title": "📈 TPV Dashboard",
        "description": "تستعرض الداشبورد تفاصيل مشروع TPV ونتيجتها وتفاصيل الأنشطة المستخدمة يومياً من قسم الجودة ونسب الربحية لمختلف القطاعات.",
        "url": "https://datastudio.google.com/s/lzMLkPXvy28",
        "embed_url": "",
        "category": "المشاريع",
        "files": [],
    },
}

DEFAULT_NEWS = [
    {
        "title": "📢 إطلاق نظام إدارة الجودة الجديد للعام الحالي",
        "content": "تم تحديث كافة تقارير ومؤشرات الأداء الخاصة بقسم الجودة لرفع كفاءة ومتابعة العمليات التشغيلية اليومية.",
        "image": "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=800&auto=format&fit=crop&q=60",
    },
    {
        "title": "🚀 ورشة عمل لتقييم الأداء والإنتاجية",
        "content": "تابعوا تفاصيل الأنشطة اليومية عبر داشبورد TPV المحدثة ومراجعات التقارير الدورية المرفقة.",
        "image": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800&auto=format&fit=crop&q=60",
    },
]

DEFAULT_USERS = {
    "admin": {"password": "123", "name": "مدير النظام", "role": "admin"},
    "manager.qa@fnrco.com.sa": {"password": "M123", "name": "مدير القسم", "role": "manager"},
    "hossam.saeed@fnrco.com.sa": {"password": "HS123", "name": "حسام سعيد", "role": "user"},
    "abdelrahman.lashine@fnrco.com.sa": {"password": "AL123", "name": "عبد الرحمن لاشين", "role": "user"},
    "yassmen.khaled@fnrco.com.sa": {"password": "HS123", "name": "ياسمين خالد", "role": "user"},
    "kenzy.hisham@fnrco.com.sa": {"password": "KH123", "name": "كنزي هشام", "role": "user"},
    "lamia.adel@fnrco.com.sa": {"password": "LA123", "name": "لمياء عادل", "role": "user"},
    "nancy.safwat@fnrco.com.sa": {"password": "NS123", "name": "نانسي صفوت", "role": "user"},
    "abdallah.zaukzouk@fnrco.com.sa": {"password": "AZ123", "name": "عبد الله زقزوق", "role": "user"},
}

ROLE_LABELS = {"admin": "مدير النظام", "manager": "مدير القسم", "user": "موظف"}
ROLE_FROM_AR = {"أدمن": "admin", "مدير": "manager", "موظف": "user"}


@st.cache_resource
def get_store():
    """مخزن مشترك بين كل الجلسات (المستخدمون، المشاريع، الأخبار، الشعارات...).
    ملاحظة: يبقى في الذاكرة فقط، ويُعاد ضبطه عند إعادة تشغيل التطبيق."""
    return {
        "users": copy.deepcopy(DEFAULT_USERS),
        "dashboards": copy.deepcopy(DEFAULT_DASHBOARDS),
        "news": copy.deepcopy(DEFAULT_NEWS),
        "company_logo": "https://raw.githubusercontent.com/ahmedgouda2727/QA-Dashboard-APP/main/Linrco-Egypt.PNG",
        "qa_logo": "https://raw.githubusercontent.com/ahmedgouda2727/QA-Dashboard-APP/main/QA.png",
        "totp_secret": "JBSWY3DPEHPK3PXP",
        "trusted_devices": [{"name": "موبايل الشركة الرئيسي (مدير النظام)", "user": "admin"}],
    }


store = get_store()

# حالة الجلسة الخاصة بكل متصفح
for _key, _default in {
    "logged_in": False,
    "two_fa_passed": False,
    "device_trusted": False,
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
            {logo_html(store['company_logo'], 'ليناركو')}
            <div class="t">{esc(title)}</div>
            <div class="s">{esc(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_login():
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        login_brand("نظام الداشبوردات - قسم الجودة", "سجّل الدخول باسم المستخدم أو البريد الإلكتروني")
        with st.form("login_form"):
            username_input = st.text_input("اسم المستخدم / البريد الإلكتروني")
            password_input = st.text_input("كلمة المرور", type="password")
            submitted = st.form_submit_button("تسجيل الدخول", type="primary")

        if submitted:
            clean = username_input.strip().lower()
            users = store["users"]
            if clean in users and users[clean]["password"] == password_input:
                st.session_state.logged_in = True
                st.session_state.username = clean
                if users[clean]["role"] == "admin":
                    st.session_state.two_fa_passed = True
                st.rerun()
            else:
                st.error("اسم المستخدم أو كلمة المرور غير صحيحة.")


def render_2fa():
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        login_brand("التحقق الثنائي", "أدخل الرمز المكوّن من 6 أرقام من تطبيق Google Authenticator")
        with st.form("2fa_form"):
            totp_code = st.text_input("رمز التحقق", max_chars=6)
            device_name = st.text_input("اسم الجهاز أو المتصفح", value="جهاز موثوق جديد")
            trust = st.checkbox("وثّق هذا الجهاز (لا تطلب الرمز مرة أخرى)")
            verify = st.form_submit_button("تحقق ودخول", type="primary")

        if verify:
            totp = pyotp.TOTP(store["totp_secret"])
            if totp.verify(totp_code, valid_window=2):
                st.session_state.two_fa_passed = True
                if trust:
                    st.session_state.device_trusted = True
                    entry = {
                        "name": f"{device_name} ({st.session_state.username})",
                        "user": st.session_state.username,
                    }
                    if entry not in store["trusted_devices"]:
                        store["trusted_devices"].append(entry)
                st.rerun()
            else:
                st.error("الرمز غير صحيح أو انتهت صلاحيته. انتظر ظهور الرمز الجديد وحاول مرة أخرى.")

        if st.button("رجوع لتسجيل الدخول"):
            logout()


def render_side_panel(user_info, is_admin):
    """لوحة جانبية على اليمين (بدل st.sidebar الذي كان يختفي):
    لوجو الشركة + لوجو القسم + أهلاً بك واسم المستخدم + تسجيل الخروج.
    أدوات الأدمن (الإعدادات وتغيير الشعارات) تظهر للأدمن فقط."""
    st.markdown('<span class="side-marker"></span>', unsafe_allow_html=True)

    st.markdown(
        f'<div class="sb-logo">{logo_html(store["company_logo"], "ليناركو")}</div>'
        f'<div class="sb-logo">{logo_html(store["qa_logo"], "قسم الجودة")}</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="user-chip">
            <div class="avatar">{esc(user_info["name"][:1])}</div>
            <div>
                <div class="name">أهلاً بك، {esc(user_info["name"])}</div>
                <div class="role">{ROLE_LABELS[user_info["role"]]}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── أدوات الأدمن فقط ──
    if is_admin:
        on_settings = st.session_state.show_admin_settings
        st.markdown('<div class="sb-label">القائمة</div>', unsafe_allow_html=True)

        if st.button(
            "🏠 الرئيسية",
            key="nav_home",
            type="secondary" if on_settings else "primary",
        ):
            st.session_state.show_admin_settings = False
            st.rerun()

        if st.button(
            "⚙️ إعدادات النظام والأمان",
            key="nav_admin",
            type="primary" if on_settings else "secondary",
        ):
            st.session_state.show_admin_settings = True
            st.rerun()

        with st.popover("🖼️ تغيير الشعارات"):
            up_c = st.file_uploader(
                "شعار ليناركو الجديد", type=["png", "jpg", "jpeg"], key="hd_c_logo"
            )
            if up_c is not None and st.button("حفظ شعار الشركة", key="save_c_logo"):
                store["company_logo"] = enhance_image(up_c)
                st.rerun()

            st.markdown('<div class="sb-sep"></div>', unsafe_allow_html=True)

            up_q = st.file_uploader(
                "شعار قسم الجودة الجديد", type=["png", "jpg", "jpeg"], key="hd_qa_logo"
            )
            if up_q is not None and st.button("حفظ شعار الجودة", key="save_qa_logo"):
                store["qa_logo"] = enhance_image(up_q)
                st.rerun()

    st.markdown('<div class="sb-sep"></div>', unsafe_allow_html=True)
    if st.button("🚪 تسجيل الخروج", key="logout_btn"):
        logout()


def render_admin_settings(current_user):
    st.title("إعدادات النظام والأمان")
    st.caption("هذه الصفحة للأدمن فقط: إدارة المصادقة الثنائية والأجهزة الموثوقة والمستخدمين.")

    tab_sec, tab_users = st.tabs(["الأمان والتحقق الثنائي", "المستخدمون والصلاحيات"])

    with tab_sec:
        section_title("ربط موبايل الشركة بتطبيق Google Authenticator")
        st.markdown(
            """
            1. حمّل تطبيق **Google Authenticator** على هاتفك.
            2. اضغط **(+)** ثم اختر **Scan a QR code**.
            3. امسح الكود التالي مرة واحدة فقط، وسيبقى صالحاً دائماً.
            """
        )
        uri = pyotp.totp.TOTP(store["totp_secret"]).provisioning_uri(
            name="Linrco-QA-Admin", issuer_name="Linrco Quality Assurance"
        )
        buf = io.BytesIO()
        qrcode.make(uri).save(buf)
        st.image(buf.getvalue(), width=230)
        st.code(store["totp_secret"], language="text")

        section_title("الأجهزة الموثوقة")
        devices = store["trusted_devices"]
        if devices:
            for i, dev in enumerate(devices):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.write(f"**{dev['name']}**  ·  المستخدم: {dev['user']}")
                with c2:
                    if st.button("إزالة الجهاز", key=f"del_dev_{i}"):
                        devices.pop(i)
                        st.rerun()
        else:
            st.info("لا توجد أجهزة موثوقة مسجلة حالياً.")

    with tab_users:
        section_title("المستخدمون الحاليون")
        st.table(
            [
                {
                    "المستخدم / الإيميل": uname,
                    "الاسم": udata["name"],
                    "الصلاحية": ROLE_LABELS[udata["role"]],
                }
                for uname, udata in store["users"].items()
            ]
        )

        section_title("إضافة مستخدم جديد")
        with st.form("add_user_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                new_email = st.text_input("البريد الإلكتروني / اسم المستخدم")
                new_name = st.text_input("الاسم")
            with c2:
                new_pass = st.text_input("كلمة المرور", type="password")
                new_role = st.selectbox("الصلاحية", list(ROLE_FROM_AR.keys()))
            add_user = st.form_submit_button("إضافة المستخدم", type="primary")

        if add_user:
            if new_email and new_pass and new_name:
                store["users"][new_email.strip().lower()] = {
                    "password": new_pass,
                    "name": new_name,
                    "role": ROLE_FROM_AR[new_role],
                }
                st.success(f"تمت إضافة {new_name}.")
                st.rerun()
            else:
                st.warning("يرجى ملء جميع الحقول.")

        section_title("حذف مستخدم")
        deletable = [u for u in store["users"] if u not in ("admin", current_user)]
        target = st.selectbox("اختر المستخدم", deletable)
        if st.button("حذف المستخدم المختار") and target in store["users"]:
            del store["users"][target]
            st.rerun()


def render_manage_panel():
    """لوحة إدارة المشاريع والأخبار (للأدمن والمدير)."""
    dashboards = store["dashboards"]

    with st.expander("لوحة إدارة المشاريع والملفات والأخبار"):
        tab1, tab2, tab3 = st.tabs(["تعديل مشروع وإرفاق ملفات", "إضافة مشروع", "إضافة خبر"])

        with tab1:
            edit_key = st.selectbox("المشروع", list(dashboards.keys()), key="edit_select")
            if edit_key:
                cur = dashboards[edit_key]
                new_title = st.text_input("العنوان", value=cur["title"], key=f"edit_title_{edit_key}")
                new_desc = st.text_area("الوصف", value=cur["description"], key=f"edit_desc_{edit_key}")
                new_url = st.text_input("الرابط (URL)", value=cur["url"], key=f"edit_url_{edit_key}")
                new_embed = st.text_input(
                    "رابط التضمين Embed URL (اختياري)",
                    value=cur.get("embed_url", ""),
                    key=f"edit_embed_{edit_key}",
                    help="لو تركته فارغاً سيحاول النظام تحويل الرابط العادي تلقائياً.",
                )
                new_cat = st.text_input(
                    "التصنيف", value=cur.get("category", "عام"), key=f"edit_cat_{edit_key}"
                )
                uploaded = st.file_uploader(
                    "إرفاق مستند",
                    type=["docx", "xlsx", "pdf", "vsdx", "pbix", "accdb", "msg", "txt"],
                    key=f"up_{edit_key}",
                )
                if st.button("حفظ التعديلات", type="primary", key=f"save_{edit_key}"):
                    files = cur.get("files", [])
                    if uploaded is not None:
                        files.append({"name": uploaded.name, "data": uploaded.getvalue()})
                    dashboards[edit_key] = {
                        "title": new_title,
                        "description": new_desc,
                        "url": new_url,
                        "embed_url": new_embed.strip(),
                        "category": new_cat.strip() or "عام",
                        "files": files,
                    }
                    st.rerun()

        with tab2:
            add_name = st.text_input("اسم المشروع (يظهر في القائمة)", key="add_name")
            add_title = st.text_input("العنوان الرئيسي", key="add_title")
            add_desc = st.text_area("الوصف", key="add_desc")
            add_url = st.text_input("رابط الداشبورد", key="add_url")
            add_embed = st.text_input("رابط التضمين Embed URL (اختياري)", key="add_embed")
            add_cat = st.text_input("التصنيف", value="عام", key="add_cat")
            if st.button("إضافة المشروع", type="primary", key="add_project_btn"):
                if add_name and add_url:
                    dashboards[add_name] = {
                        "title": add_title,
                        "description": add_desc,
                        "url": add_url,
                        "embed_url": add_embed.strip(),
                        "category": add_cat.strip() or "عام",
                        "files": [],
                    }
                    st.rerun()
                else:
                    st.warning("أدخل اسم المشروع والرابط على الأقل.")

        with tab3:
            news_title = st.text_input("عنوان الخبر", key="news_t")
            news_content = st.text_area("نص الخبر", key="news_c")
            news_img = st.file_uploader("صورة الخبر", type=["png", "jpg", "jpeg"], key="news_img_upload")
            if st.button("نشر الخبر", type="primary", key="publish_news_btn"):
                if news_title and news_content:
                    store["news"].append(
                        {
                            "title": news_title,
                            "content": news_content,
                            "image": enhance_image(news_img) if news_img is not None else DEFAULT_NEWS_IMAGE,
                        }
                    )
                    st.rerun()
                else:
                    st.warning("أدخل عنوان الخبر ونصه.")


def render_news(can_manage):
    news = store["news"]
    if not news:
        return
    section_title("آخر الأخبار والتحديثات")

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
                            <div class="nt">{esc(item['title'])}</div>
                            <div class="nc">{esc(item['content'])}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                if can_manage:
                    with st.expander("إدارة الخبر"):
                        new_img = st.file_uploader(
                            "صورة جديدة", type=["png", "jpg", "jpeg"], key=f"news_ch_{idx}"
                        )
                        if new_img is not None and st.button("حفظ الصورة", key=f"btn_ch_{idx}"):
                            news[idx]["image"] = enhance_image(new_img)
                            st.rerun()
                        if st.button("حذف الخبر", key=f"btn_del_news_{idx}"):
                            news.pop(idx)
                            st.rerun()


def render_projects(can_manage):
    dashboards = store["dashboards"]
    if not dashboards:
        st.info("لا توجد مشاريع حالياً.")
        return

    section_title("المشاريع والتقارير")

    # ── الفلاتر: بحث نصي + تصنيف ──
    categories = sorted({(d.get("category") or "عام") for d in dashboards.values()})
    f1, f2 = st.columns([2, 1])
    with f1:
        query = st.text_input(
            "بحث",
            placeholder="اكتب جزءاً من اسم المشروع أو وصفه...",
            key="project_query",
        ).strip().lower()
    with f2:
        category = st.selectbox("التصنيف", ["الكل"] + categories, key="project_category")

    def matches(name, d):
        if category != "الكل" and (d.get("category") or "عام") != category:
            return False
        if not query:
            return True
        haystack = f"{name} {d.get('title', '')} {d.get('description', '')}".lower()
        return query in haystack

    options = [name for name, d in dashboards.items() if matches(name, d)]
    st.caption(f"عدد النتائج: {len(options)} من {len(dashboards)}")

    if not options:
        st.info("لا توجد مشاريع مطابقة. غيّر كلمة البحث أو التصنيف.")
        return

    # لو المشروع المختار خرج من نتائج الفلتر نرجع لأول نتيجة
    if st.session_state.get("project_select") not in options:
        st.session_state["project_select"] = options[0]
    selected = st.selectbox("اختر المشروع", options, key="project_select")

    # ── عارض التقرير ──
    data = dashboards[selected]
    url = safe_url(data["url"])
    embed_url = safe_url(data.get("embed_url", "")) or to_embed_url(data["url"])
    link_html = (
        f'<a class="btn-link" href="{esc(url, quote=True)}" target="_blank" rel="noopener">فتح في تبويب جديد</a>'
        if url
        else ""
    )
    files_n = len(data.get("files", []))
    st.markdown(
        f"""
        <div class="viewer-head">
            <span class="badge">{esc(data.get('category') or 'عام')}</span>
            <div class="vt">{esc(data['title'])}</div>
            <div class="vd">{esc(data['description'])}</div>
            {link_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    files = data.get("files", [])
    if files:
        with st.expander(f"الملفات المرفقة ({files_n})"):
            for j, f in enumerate(files):
                st.download_button(
                    label=f"تحميل {f['name']}",
                    data=f["data"],
                    file_name=f["name"],
                    mime="application/octet-stream",
                    key=f"dl_{selected}_{j}",
                )

    if embed_url:
        st.components.v1.iframe(embed_url, height=820, scrolling=True)
        st.caption("لو التقرير لم يظهر هنا، افتحه من زر «فتح في تبويب جديد».")
        if can_manage:
            with st.expander("التقرير لا يظهر؟ خطوات الحل"):
                st.markdown(
                    """
                    1. في Looker Studio: **File ← Embed report ← Enable embedding**، ثم انسخ **Embed URL** والصقه في خانة «رابط التضمين» في لوحة الإدارة.
                    2. الروابط القصيرة `/s/...` لا تعمل داخل iframe، ويجب أن يكون الرابط على شكل `/embed/reporting/...`.
                    3. تأكد من مشاركة التقرير (Share) مع المستخدمين أو المؤسسة، أو «Anyone with the link».
                    4. إذا كان التقرير خاصاً بحسابات Google، يجب أن يكون المستخدم مسجّلاً الدخول بحساب Google في نفس المتصفح، وأن لا يمنع المتصفح الكوكيز الخارجية.

                    الرابط المستخدم حالياً للعرض:
                    """
                )
                st.code(embed_url, language="text")
    else:
        st.warning("رابط المشروع غير صالح. يجب أن يبدأ بـ http:// أو https://")


def render_portal(user_info, can_manage):
    dashboards = store["dashboards"]
    files_total = sum(len(d.get("files", [])) for d in dashboards.values())

    st.markdown(
        f"""
        <div class="hero">
            <div>
                <div class="hero-title">بوابة تقارير ومشاريع الجودة</div>
                <div class="hero-sub">مرحباً {esc(user_info['name'])}، هنا تجد تقارير قسم الجودة في ليناركو ومؤشرات الأداء ومستندات المشاريع.</div>
            </div>
            <div class="hero-stats">
                <div class="hero-stat"><b>{len(dashboards)}</b><span>مشاريع</span></div>
                <div class="hero-stat"><b>{len(store['news'])}</b><span>أخبار</span></div>
                <div class="hero-stat"><b>{files_total}</b><span>ملفات مرفقة</span></div>
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

elif not st.session_state.device_trusted and not st.session_state.two_fa_passed:
    render_2fa()

else:
    current_user = st.session_state.username
    if current_user not in store["users"]:  # تم حذف المستخدم أثناء الجلسة
        logout()

    user_info = store["users"][current_user]
    is_admin = user_info["role"] == "admin"
    can_manage = user_info["role"] in ("admin", "manager")

    side_col, main_col = st.columns([1, 3.6], gap="large")

    with side_col:
        render_side_panel(user_info, is_admin)

    with main_col:
        if is_admin and st.session_state.show_admin_settings:
            render_admin_settings(current_user)
        else:
            render_portal(user_info, can_manage)
