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
    initial_sidebar_state="expanded"
)

# ──────────────────────────────────────────────────────────────
# تنسيق CSS نظيف وآمن (RTL)
# ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap');

/* تطبيق الخط العربي والاتجاه على التطبيق بالكامل */
html, body, [class*="css"], .stApp {
    font-family: 'Cairo', sans-serif !important;
    direction: rtl !important;
    text-align: right !important;
}

/* إخفاء الهيدر والفوتر الافتراضي */
#MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden !important; }
header { visibility: hidden !important; }

/* إجبار الصفحة والمحتوى والشريط الجانبي على الاتجاه الصحيح */
.main .block-container, [data-testid="stSidebar"] {
    direction: rtl !important;
    text-align: right !important;
}

/* كروت الأخبار والمشاريع */
.news-card {
    background-color: #ffffff;
    border: 1px solid #e0e0e0;
    border-radius: 10px;
    padding: 15px;
    margin-bottom: 15px;
    box-shadow: 0 2px 5px rgba(0,0,0,0.05);
}
.news-card img {
    width: 100%;
    height: 180px;
    object-fit: cover;
    border-radius: 8px;
}

/* تحسين شكل الهيرو والبطاقات */
.hero-box {
    background-color: #8A1C2B;
    color: white;
    padding: 25px;
    border-radius: 12px;
    margin-bottom: 25px;
}
.hero-box h1 {
    color: white !important;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)


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

def img_src(img):
    if isinstance(img, (bytes, bytearray)):
        return "data:image/png;base64," + base64.b64encode(img).decode()
    return esc(str(img), quote=True)

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


# ──────────────────────────────────────────────────────────────
# البيانات الافتراضية والذاكرة
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
# الشاشات
# ──────────────────────────────────────────────────────────────
def render_login():
    st.title("🔐 تسجيل الدخول إلى بوابة الجودة")
    st.write("الرجاء إدخال اسم المستخدم وكلمة المرور للدخول إلى النظام.")
    
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
    st.title("🛡️ التحقق الثنائي الأمني")
    st.write("أدخل الرمز المكون من 6 أرقام من تطبيق Google Authenticator:")
    
    with st.form("2fa_form"):
        totp_code = st.text_input("رمز التحقق", max_chars=6)
        device_name = st.text_input("اسم الجهاز أو المتصفح", value="جهاز موثوق جديد")
        trust = st.checkbox("وثّق هذا الجهاز (عدم طلب الرمز مجدداً)")
        verify = st.form_submit_button("تحقق ودخول", type="primary")

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
                st.error("رمز التحقق غير صحيح أو انتهت صلاحيته.")

    if st.button("رجوع لتسجيل الدخول"):
        logout()

def render_sidebar(user_info, is_admin):
    with st.sidebar:
        st.image(store["company_logo"], use_column_width=True)
        if is_admin:
            with st.expander("✏️ تغيير شعار الشركة"):
                up = st.file_uploader("شعار ليناركو الجديد", type=["png", "jpg", "jpeg"], key="sb_c_logo")
                if up is not None and st.button("حفظ الشعار", key="save_c_logo"):
                    store["company_logo"] = enhance_image(up)
                    st.rerun()

        st.markdown("---")
        st.image(store["qa_logo"], use_column_width=True)
        if is_admin:
            with st.expander("✏️ تغيير شعار قسم الجودة"):
                up = st.file_uploader("شعار الجودة الجديد", type=["png", "jpg", "jpeg"], key="sb_qa_logo")
                if up is not None and st.button("حفظ الشعار", key="save_qa_logo"):
                    store["qa_logo"] = enhance_image(up)
                    st.rerun()

        st.markdown("---")
        st.write(f"مرحباً بك، **{user_info['name']}** 👋")
        st.caption(f"الصلاحية: {ROLE_LABELS[user_info['role']]}")
        st.markdown("---")

        if is_admin:
            label = "🏠 العودة للرئيسية" if st.session_state.show_admin_settings else "⚙️ إعدادات النظام والأمان"
            if st.button(label, key="toggle_admin"):
                st.session_state.show_admin_settings = not st.session_state.show_admin_settings
                st.rerun()
            st.markdown("---")

        if st.button("🚪 تسجيل الخروج", key="logout_btn"):
            logout()

def render_admin_settings(current_user):
    st.title("⚙️ لوحة إعدادات النظام والأمان")
    st.caption("مخصصة لمدير النظام فقط لإدارة المصادقة والأجهزة والمستخدمين.")

    tab_sec, tab_users = st.tabs(["🔒 الأمان والتحقق الثنائي", "👥 المستخدمون والصلاحيات"])

    with tab_sec:
        st.subheader("📱 ربط Google Authenticator")
        st.write("امسح الكود التالي عبر التطبيق لربط الهواتف بالنظام:")
        
        uri = pyotp.totp.TOTP(store["totp_secret"]).provisioning_uri(
            name="Linrco-QA-Admin", issuer_name="Linrco Quality Assurance"
        )
        buf = io.BytesIO()
        qrcode.make(uri).save(buf)
        st.image(buf.getvalue(), width=220)
        st.code(store["totp_secret"], language="text")

        st.markdown("---")
        st.subheader("💻 الأجهزة الموثوقة")
        devices = store["trusted_devices"]
        if devices:
            for i, dev in enumerate(devices):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.write(f"🔹 **{dev['name']}** (المستخدم: {dev['user']})")
                with c2:
                    if st.button("حذف", key=f"del_dev_{i}"):
                        devices.pop(i)
                        st.rerun()
        else:
            st.info("لا توجد أجهزة موثوقة حالياً.")

    with tab_users:
        st.subheader("👥 إدارة المستخدمين")
        st.table([
            {"المستخدم / الإيميل": uname, "الاسم": udata["name"], "الصلاحية": ROLE_LABELS[udata["role"]]}
            for uname, udata in store["users"].items()
        ])

        st.markdown("---")
        st.subheader("➕ إضافة مستخدم جديد")
        with st.form("add_user_form", clear_on_submit=True):
            new_email = st.text_input("البريد الإلكتروني / اسم المستخدم")
            new_name = st.text_input("الاسم")
            new_pass = st.text_input("كلمة المرور", type="password")
            new_role = st.selectbox("الصلاحية", list(ROLE_FROM_AR.keys()))
            add_user = st.form_submit_button("إضافة المستخدم", type="primary")

        if add_user:
            if new_email and new_pass and new_name:
                store["users"][new_email.strip().lower()] = {
                    "password": new_pass, "name": new_name, "role": ROLE_FROM_AR[new_role]
                }
                st.success(f"تمت إضافة {new_name} بنجاح!")
                st.rerun()

def render_manage_panel():
    dashboards = store["dashboards"]

    with st.expander("🛠️ لوحة إدارة المشاريع والملفات والأخبار"):
        tab1, tab2, tab3 = st.tabs(["تعديل مشروع وإرفاق ملفات", "إضافة مشروع جديد", "إضافة خبر جديد"])

        with tab1:
            edit_key = st.selectbox("اختر المشروع:", list(dashboards.keys()), key="edit_select")
            if edit_key:
                cur = dashboards[edit_key]
                new_title = st.text_input("العنوان", value=cur["title"], key=f"edit_title_{edit_key}")
                new_desc = st.text_area("الوصف", value=cur["description"], key=f"edit_desc_{edit_key}")
                new_url = st.text_input("الرابط (URL)", value=cur["url"], key=f"edit_url_{edit_key}")
                uploaded = st.file_uploader("إرفاق مستند", type=["docx", "xlsx", "pdf", "vsdx", "pbix", "accdb", "msg", "txt"], key=f"up_{edit_key}")
                
                if st.button("حفظ التعديلات", type="primary", key=f"save_{edit_key}"):
                    files = cur.get("files", [])
                    if uploaded is not None:
                        files.append({"name": uploaded.name, "data": uploaded.getvalue()})
                    dashboards[edit_key] = {
                        "title": new_title, "description": new_desc, "url": new_url,
                        "embed_url": "", "category": "عام", "files": files
                    }
                    st.success("تم الحفظ!")
                    st.rerun()

        with tab2:
            add_name = st.text_input("اسم المشروع القصير", key="add_name")
            add_title = st.text_input("العنوان الرئيسي", key="add_title")
            add_desc = st.text_area("الوصف والشرح", key="add_desc")
            add_url = st.text_input("رابط الداشبورد", key="add_url")
            if st.button("إضافة المشروع", type="primary", key="add_project_btn"):
                if add_name and add_url:
                    dashboards[add_name] = {
                        "title": add_title, "description": add_desc, "url": add_url,
                        "embed_url": "", "category": "عام", "files": []
                    }
                    st.success("تمت الإضافة!")
                    st.rerun()

        with tab3:
            news_title = st.text_input("عنوان الخبر", key="news_t")
            news_content = st.text_area("تفاصيل الخبر", key="news_c")
            news_img = st.file_uploader("صورة الخبر", type=["png", "jpg", "jpeg"], key="news_img_upload")
            if st.button("نشر الخبر", type="primary", key="publish_news_btn"):
                if news_title and news_content:
                    store["news"].append({
                        "title": news_title, "content": news_content,
                        "image": enhance_image(news_img) if news_img is not None else DEFAULT_NEWS_IMAGE
                    })
                    st.success("تم النشر!")
                    st.rerun()

def render_portal(user_info, can_manage):
    st.markdown(f"""
    <div class="hero-box">
        <h1>📊 بوابة تقارير ومشاريع الجودة</h1>
        <p>مرحباً بك <b>{esc(user_info['name'])}</b>، يمكنك هنا متابعة تقارير قسم الجودة ومؤشرات الأداء لشركة ليناركو.</p>
    </div>
    """, unsafe_allow_html=True)

    if can_manage:
        render_manage_panel()

    # قسم الأخبار
    st.subheader("📰 آخر الأخبار والتحديثات")
    news = store["news"]
    if news:
        cols = st.columns(len(news) if len(news) <= 2 else 2)
        for idx, item in enumerate(news):
            with cols[idx % len(cols)]:
                with st.container():
                    st.markdown(f"""
                    <div class="news-card">
                        <img src="{img_src(item['image'])}">
                        <h3>{esc(item['title'])}</h3>
                        <p>{esc(item['content'])}</p>
                    </div>
                    """, unsafe_allow_html=True)

    st.markdown("---")
    
    # قسم المشاريع
    st.subheader("📁 المشاريع والتقارير المتاحة")
    dashboards = store["dashboards"]
    selected = st.selectbox("🎯 اختر المشروع المطلوبة معاينته بالأسفل:", list(dashboards.keys()))

    if selected:
        data = dashboards[selected]
        embed_url = to_embed_url(data["url"])
        
        st.markdown(f"### {data['title']}")
        st.info(data['description'])
        
        if data.get("files"):
            st.write("📎 **الملفات المرفقة:**")
            for j, f in enumerate(data["files"]):
                st.download_button(label=f"📥 تحميل {f['name']}", data=f["data"], file_name=f["name"], key=f"dl_{selected}_{j}")

        st.markdown(f"[🔗 اضغط هنا لفتح الداشبورد في تبويب جديد]({data['url']})")
        st.markdown("---")
        st.components.v1.iframe(embed_url, height=800, scrolling=True)


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
