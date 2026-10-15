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
    initial_sidebar_state="expanded",
)

# ──────────────────────────────────────────────────────────────
# التنسيق (CSS) النظيف الآمن
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
}

/* إخفاء عناصر ستريمليت غير الضرورية */
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {
    display: none !important;
}
header[data-testid="stHeader"] { background: transparent; }

/* الاتجاه والخط العام */
html, body, [class*="css"], .stApp {
    font-family: 'IBM Plex Sans Arabic', Tahoma, sans-serif !important;
    direction: rtl !important;
    text-align: right !important;
    background: var(--bg);
}

/* تنسيق الهيرو بكروت الإحصائيات */
.hero {
    background: var(--brand-deep);
    color: #fff;
    border-radius: 12px;
    padding: 1.8rem 2rem;
    margin-bottom: 1.5rem;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 1.5rem;
    flex-wrap: wrap;
}
.hero-title { font-size: 1.8rem; font-weight: 700; margin-bottom: .4rem; color: #fff; }
.hero-sub { color: #EBD3D8; font-size: 0.95rem; line-height: 1.6; }
.hero-stats { display: flex; gap: 1rem; }
.hero-stat {
    padding: 0 1.2rem;
    border-right: 1px solid rgba(255,255,255,.28);
    text-align: center;
}
.hero-stat:last-child { border-right: none; }
.hero-stat b { display: block; font-size: 1.6rem; line-height: 1.15; }
.hero-stat span { font-size: .85rem; color: #EBD3D8; }

.section-title {
    font-size: 1.2rem;
    font-weight: 700;
    color: var(--ink);
    margin: 1.5rem 0 1rem;
    border-right: 4px solid var(--brand);
    padding-right: 8px;
}

/* كروت الأخبار */
.news-card {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 10px;
    overflow: hidden;
    margin-bottom: 1rem;
}
.news-card img { width: 100%; height: 160px; object-fit: cover; display: block; }
.news-body { padding: 1rem; }
.news-body .nt { font-size: 1rem; font-weight: 700; margin-bottom: .3rem; color: var(--ink); }
.news-body .nc { color: var(--muted); font-size: .9rem; line-height: 1.6; }

/* عرض مشروع/تقرير */
.viewer-head {
    background: var(--surface);
    border: 1px solid var(--line);
    border-radius: 10px;
    padding: 1.25rem;
    margin: 1rem 0;
}
.btn-link {
    display: inline-block;
    padding: .4rem 1rem;
    border-radius: 6px;
    background: var(--brand);
    color: #fff !important;
    font-weight: 600;
    text-decoration: none !important;
}

iframe { border: 1px solid var(--line) !important; border-radius: 10px; background: #fff; }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

# ──────────────────────────────────────────────────────────────
# دوال مساعدة
# ──────────────────────────────────────────────────────────────
esc = html.escape

def enhance_image(image_file):
    img = Image.open(image_file)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img = ImageEnhance.Sharpness(img).enhance(1.3)
    img = ImageEnhance.Color(img).enhance(1.1)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def safe_url(url):
    url = (url or "").strip()
    return url if url.startswith(("http://", "https://")) else ""

@st.cache_data(ttl=3600, show_spinner=False)
def resolve_short_url(url):
    try:
        r = requests.get(url, allow_redirects=True, timeout=6, headers={"User-Agent": "Mozilla/5.0"})
        return r.url
    except Exception:
        return url

_REPORT_RE = re.compile(
    r"(?:lookerstudio|datastudio)\.google\.com/(?:u/\d+/)?reporting/([0-9a-zA-Z-]+)(?:/page/([0-9a-zA-Z_-]+))?"
)

def to_embed_url(url):
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
        "description": "تحتوي هذه الداشبورد على تحليلات شاملة للنشاطات اليومية والشهرية ومؤشرات الأداء الرئيسية (KPIs).",
        "url": "https://datastudio.google.com/s/pZkBFbgR5as",
        "embed_url": "",
        "category": "مؤشرات الأداء",
        "files": [],
    },
    "مشروع الـ TPV": {
        "title": "📈 TPV Dashboard",
        "description": "تستعرض تفاصيل مشروع TPV ونتائجه والأنشطة اليومية لقسم الجودة.",
        "url": "https://datastudio.google.com/s/lzMLkPXvy28",
        "embed_url": "",
        "category": "المشاريع",
        "files": [],
    },
}

DEFAULT_NEWS = [
    {
        "title": "📢 إطلاق نظام إدارة الجودة الجديد",
        "content": "تم تحديث كافة تقارير ومؤشرات الأداء الخاصة بقسم الجودة لرفع كفاءة العمليات التشغيلية.",
        "image": "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=800&auto=format&fit=crop&q=60",
    },
    {
        "title": "🚀 ورشة عمل لتقييم الأداء",
        "content": "تابعوا تفاصيل الأنشطة اليومية عبر داشبورد TPV المحدثة ومراجعات التقارير.",
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

for _key, _default in {
    "logged_in": False,
    "two_fa_passed": False,
    "device_trusted": False,
    "username": "",
    "show_admin_settings": False,
}.items():
    st.session_state.setdefault(_key, _default)

def logout():
    st.session_state.logged_in = False
    st.session_state.two_fa_passed = False
    st.session_state.show_admin_settings = False
    st.session_state.username = ""
    st.rerun()

# ──────────────────────────────────────────────────────────────
# الواجهات والشاشات
# ──────────────────────────────────────────────────────────────
def render_login():
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.image(store['company_logo'], use_container_width=True)
        st.subheader("تسجيل الدخول - بوابة الجودة")
        with st.form("login_form"):
            username_input = st.text_input("اسم المستخدم / البريد")
            password_input = st.text_input("كلمة المرور", type="password")
            submitted = st.form_submit_button("تسجيل الدخول", use_container_width=True)

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
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.subheader("التحقق الثنائي")
        st.caption("أدخل الرمز المكون من 6 أرقام من تطبيق Google Authenticator")
        with st.form("2fa_form"):
            totp_code = st.text_input("رمز التحقق", max_chars=6)
            device_name = st.text_input("اسم الجهاز", value="جهاز جديد")
            trust = st.checkbox("وثّق هذا الجهاز")
            verify = st.form_submit_button("تحقق ودخول", use_container_width=True)

        if verify:
            totp = pyotp.TOTP(store["totp_secret"])
            if totp.verify(totp_code, valid_window=2):
                st.session_state.two_fa_passed = True
                if trust:
                    st.session_state.device_trusted = True
                    entry = {"name": f"{device_name} ({st.session_state.username})", "user": st.session_state.username}
                    if entry not in store["trusted_devices"]:
                        store["trusted_devices"].append(entry)
                st.rerun()
            else:
                st.error("الرمز غير صحيح.")

        if st.button("رجوع لتسجيل الدخول", use_container_width=True):
            logout()

def render_sidebar(user_info, is_admin):
    with st.sidebar:
        st.title("بوابة الجودة")
        st.caption("شركة ليناركو")
        st.divider()

        if store["company_logo"]:
            st.image(store["company_logo"], use_container_width=True)
        if store["qa_logo"]:
            st.image(store["qa_logo"], use_container_width=True)

        if is_admin:
            with st.expander("تغيير الشعار"):
                up = st.file_uploader("شعار الشركة", type=["png", "jpg", "jpeg"], key="sb_c_logo")
                if up is not None and st.button("حفظ الشعار", key="save_c_logo", use_container_width=True):
                    store["company_logo"] = enhance_image(up)
                    st.rerun()

        st.divider()
        st.write(f"👤 **{esc(user_info['name'])}**")
        st.caption(f"الصلاحية: {ROLE_LABELS[user_info['role']]}")
        st.divider()

        if st.button("🏠 الرئيسية", key="sidebar_home", use_container_width=True):
            st.session_state.show_admin_settings = False
            st.rerun()

        if is_admin:
            label = "↩ العودة للرئيسية" if st.session_state.show_admin_settings else "⚙️ إعدادات النظام"
            if st.button(label, key="toggle_admin", use_container_width=True):
                st.session_state.show_admin_settings = not st.session_state.show_admin_settings
                st.rerun()

        if st.button("🚪 تسجيل الخروج", key="logout_btn", use_container_width=True):
            logout()

def render_admin_settings(current_user):
    st.title("إعدادات النظام والأمان")
    tab_sec, tab_users = st.tabs(["الأمان والتحقق الثنائي", "المستخدمون والصلاحيات"])

    with tab_sec:
        section_title("ربط تطبيق Google Authenticator")
        uri = pyotp.totp.TOTP(store["totp_secret"]).provisioning_uri(
            name="Linrco-QA-Admin", issuer_name="Linrco Quality Assurance"
        )
        buf = io.BytesIO()
        qrcode.make(uri).save(buf)
        st.image(buf.getvalue(), width=200)
        st.code(store["totp_secret"], language="text")

        section_title("الأجهزة الموثوقة")
        devices = store["trusted_devices"]
        if devices:
            for i, dev in enumerate(devices):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.write(f"• **{dev['name']}** ({dev['user']})")
                with c2:
                    if st.button("إزالة", key=f"del_dev_{i}"):
                        devices.pop(i)
                        st.rerun()

    with tab_users:
        section_title("المستخدمون")
        st.table([
            {"المستخدم": uname, "الاسم": udata["name"], "الصلاحية": ROLE_LABELS[udata["role"]]}
            for uname, udata in store["users"].items()
        ])

        section_title("إضافة مستخدم")
        with st.form("add_user_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                new_email = st.text_input("اسم المستخدم / البريد")
                new_name = st.text_input("الاسم")
            with c2:
                new_pass = st.text_input("كلمة المرور", type="password")
                new_role = st.selectbox("الصلاحية", list(ROLE_FROM_AR.keys()))
            if st.form_submit_button("إضافة", use_container_width=True):
                if new_email and new_pass and new_name:
                    store["users"][new_email.strip().lower()] = {
                        "password": new_pass, "name": new_name, "role": ROLE_FROM_AR[new_role]
                    }
                    st.success(f"تمت إضافة {new_name}")
                    st.rerun()

def render_manage_panel():
    dashboards = store["dashboards"]
    with st.expander("🛠️ لوحة إدارة المشاريع والأخبار"):
        tab1, tab2, tab3 = st.tabs(["تعديل مشروع", "إضافة مشروع", "إضافة خبر"])

        with tab1:
            edit_key = st.selectbox("اختر المشروع", list(dashboards.keys()), key="edit_select")
            if edit_key:
                cur = dashboards[edit_key]
                new_title = st.text_input("العنوان", value=cur["title"], key=f"edit_title_{edit_key}")
                new_desc = st.text_area("الوصف", value=cur["description"], key=f"edit_desc_{edit_key}")
                new_url = st.text_input("الرابط", value=cur["url"], key=f"edit_url_{edit_key}")
                uploaded = st.file_uploader("إرفاق ملف", key=f"up_{edit_key}")
                if st.button("حفظ التعديلات", key=f"save_{edit_key}"):
                    files = cur.get("files", [])
                    if uploaded is not None:
                        files.append({"name": uploaded.name, "data": uploaded.getvalue()})
                    dashboards[edit_key].update({"title": new_title, "description": new_desc, "url": new_url, "files": files})
                    st.rerun()

        with tab2:
            add_name = st.text_input("اسم المشروع القصير", key="add_name")
            add_title = st.text_input("العنوان الكامل", key="add_title")
            add_desc = st.text_area("الوصف", key="add_desc")
            add_url = st.text_input("رابط التقرير", key="add_url")
            if st.button("إضافة المشروع", key="add_p_btn"):
                if add_name and add_url:
                    dashboards[add_name] = {"title": add_title, "description": add_desc, "url": add_url, "embed_url": "", "category": "عام", "files": []}
                    st.rerun()

        with tab3:
            news_title = st.text_input("عنوان الخبر", key="news_t")
            news_content = st.text_area("تفاصيل الخبر", key="news_c")
            news_img = st.file_uploader("صورة الخبر", key="news_img_upload")
            if st.button("نشر الخبر", key="pub_n_btn"):
                if news_title and news_content:
                    store["news"].append({
                        "title": news_title, "content": news_content,
                        "image": enhance_image(news_img) if news_img is not None else DEFAULT_NEWS_IMAGE
                    })
                    st.rerun()

def render_news(can_manage):
    news = store["news"]
    if not news:
        return
    section_title("آخر الأخبار والتحديثات")
    cols = st.columns(min(len(news), 3))
    for idx, item in enumerate(news):
        with cols[idx % len(cols)]:
            st.markdown(f"""
            <div class="news-card">
                <img src="{item['image']}">
                <div class="news-body">
                    <div class="nt">{esc(item['title'])}</div>
                    <div class="nc">{esc(item['content'])}</div>
                </div>
            </div>
            """, unsafe_allow_html=True)

def render_projects(can_manage):
    dashboards = store["dashboards"]
    if not dashboards:
        st.info("لا توجد مشاريع.")
        return

    section_title("المشاريع والتقارير")
    selected = st.selectbox("اختر المشروع لمراجعته", list(dashboards.keys()), key="project_select")

    data = dashboards[selected]
    url = safe_url(data["url"])
    embed_url = safe_url(data.get("embed_url", "")) or to_embed_url(data["url"])

    st.markdown(f"""
    <div class="viewer-head">
        <h3>{esc(data['title'])}</h3>
        <p>{esc(data['description'])}</p>
        <a class="btn-link" href="{esc(url)}" target="_blank">فتح في تبويب جديد 🔗</a>
    </div>
    """, unsafe_allow_html=True)

    if data.get("files"):
        with st.expander("الملفات المرفقة"):
            for j, f in enumerate(data["files"]):
                st.download_button(f"تحميل {f['name']}", f["data"], file_name=f["name"], key=f"dl_{selected}_{j}")

    if embed_url:
        st.components.v1.iframe(embed_url, height=750, scrolling=True)

def render_portal(user_info, can_manage):
    dashboards = store["dashboards"]
    files_total = sum(len(d.get("files", [])) for d in dashboards.values())

    st.markdown(f"""
    <div class="hero">
        <div>
            <div class="hero-title">بوابة تقارير ومشاريع الجودة</div>
            <div class="hero-sub">مرحباً {esc(user_info['name'])}، تجد هنا جميع تقارير ومؤشرات أداء قسم الجودة.</div>
        </div>
        <div class="hero-stats">
            <div class="hero-stat"><b>{len(dashboards)}</b><span>مشاريع</span></div>
            <div class="hero-stat"><b>{len(store['news'])}</b><span>أخبار</span></div>
            <div class="hero-stat"><b>{files_total}</b><span>ملفات</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

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
    if current_user not in store["users"]:
        logout()

    user_info = store["users"][current_user]
    is_admin = user_info["role"] == "admin"
    can_manage = user_info["role"] in ("admin", "manager")

    render_sidebar(user_info, is_admin)

    if is_admin and st.session_state.show_admin_settings:
        render_admin_settings(current_user)
    else:
        render_portal(user_info, can_manage)
