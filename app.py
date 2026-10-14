import streamlit as st
from PIL import Image, ImageEnhance
import io
import requests
import pyotp
import qrcode

# إعدادات صفحة الويب
st.set_page_config(page_title="لوحة تحكم قسم الجودة - ليناركو", page_icon="📊", layout="wide")

# تخصيص وتكبير الخطوط، قلب الاتجاه إلى RTL، ونقل الشريط الجانبي لليمين
st.markdown("""
    <style>
    header {visibility: hidden !important;}
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    
    html, body, [class*="css"] {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Cairo', Tahoma, sans-serif !important;
        font-size: 20px !important;
    }
    
    h1, h2, h3, h4, h5, h6 {
        text-align: right !important;
        color: #8B0000;
        direction: rtl !important;
    }
    h1 { font-size: 38px !important; }
    h2 { font-size: 30px !important; color: #333333; }
    h3 { font-size: 24px !important; }

    [data-testid="stSidebar"] {
        right: 0px !important;
        left: auto !important;
        direction: rtl !important;
        text-align: right !important;
    }
    
    .main .block-container {
        direction: rtl !important;
        text-align: right !important;
    }

    .project-card {
        background-color: #f9f9f9;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        text-align: right !important;
        direction: rtl !important;
    }
    
    .stSelectbox, .stTextInput, .stTextArea, .stFileUploader {
        text-align: right !important;
        direction: rtl !important;
    }

    .rtl-right {
        direction: rtl !important;
        text-align: right !important;
        display: block !important;
    }
    </style>
""", unsafe_allow_html=True)

# دالة ذكية لمعالجة وتحسين الصور
def enhance_image_ai_style(image_file):
    img = Image.open(image_file)
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    
    enhancer = ImageEnhance.Sharpness(img)
    img = enhancer.enhance(1.3)
    
    color_enhancer = ImageEnhance.Color(img)
    img = color_enhancer.enhance(1.1)
    
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    return buffered.getvalue()

# 1. الداشبوردات والمشاريع الافتراضية
DEFAULT_DASHBOARDS = {
    "مؤشرات أداء قسم الـ QA": {
        "title": "📊 QA Dashboard تحليل الأداء قسم الجودة",
        "description": "تحتوي هذه الداشبورد على تحليلات شاملة للنشاطات اليومية والشهرية، بالإضافة إلى مقارنة الأداء ومؤشرات الأداء الرئيسية (KPIs).",
        "url": "https://datastudio.google.com/s/pZkBFbgR5as",
        "files": []
    },
    "مشروع الـ TPV": {
        "title": "📈 TPV Dashboard",
        "description": "تستعرض الداشبورد تفاصيل مشروع TPV و نتيجتها و تفاصيل الانشطه المستخدمه اليوميه من قسم الجوده و نسب الربحيه لمختلف القطاعات.",
        "url": "https://datastudio.google.com/s/lzMLkPXvy28",
        "files": []
    }
}

# 2. أخبار قسم الجودة
DEFAULT_NEWS = [
    {
        "title": "📢 إطلاق نظام إدارة الجودة الجديد للعام الحالي",
        "content": "تم تحديث كافة تقارير ومؤشرات الأداء الخاصة بقسم الجودة لرفع كفاءة ومتابعة العمليات التشغيلية اليومية.",
        "image": "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=800&auto=format&fit=crop&q=60"
    },
    {
        "title": "🚀 ورشة عمل لتقييم الأداء والإنتاجية",
        "content": "تابعوا تفاصيل الأنشطة اليومية عبر داشبورد TPV المحدثة وراجعات التقارير الدورية المرفقة.",
        "image": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=800&auto=format&fit=crop&q=60"
    }
]

# 3. حسابات المستخدمين مع الصلاحيات
if "users_db" not in st.session_state:
    st.session_state.users_db = {
        "admin": {"password": "123", "name": "مدير النظام", "role": "admin"},
        "manager.qa@fnrco.com.sa": {"password": "M123", "name": "مدير القسم", "role": "manager"},
        "hossam.saeed@fnrco.com.sa": {"password": "HS123", "name": "حسام سعيد", "role": "user"},
        "abdelrahman.lashine@fnrco.com.sa": {"password": "AL123", "name": "عبد الرحمن لاشين", "role": "user"},
        "yassmen.khaled@fnrco.com.sa": {"password": "HS123", "name": "ياسمين خالد", "role": "user"},
        "kenzy.hisham@fnrco.com.sa": {"password": "KH123", "name": "كنزي هشام", "role": "user"},
        "lamia.adel@fnrco.com.sa": {"password": "LA123", "name": "لمياء عادل", "role": "user"},
        "nancy.safwat@fnrco.com.sa": {"password": "NS123", "name": "نانسي صفوت", "role": "user"},
        "abdallah.zaukzouk@fnrco.com.sa": {"password": "AZ123", "name": "عبد الله زقزوق", "role": "user"}
    }

# 4. إدارة حالة التطبيق (Session State)
if "dashboards" not in st.session_state:
    st.session_state.dashboards = DEFAULT_DASHBOARDS

if "news_list" not in st.session_state:
    st.session_state.news_list = DEFAULT_NEWS

if "company_logo" not in st.session_state:
    st.session_state.company_logo = "https://raw.githubusercontent.com/ahmedgouda2727/QA-Dashboard-APP/main/Linrco-Egypt.PNG"

if "qa_logo" not in st.session_state:
    st.session_state.qa_logo = "https://raw.githubusercontent.com/ahmedgouda2727/QA-Dashboard-APP/main/QA.png"

# تثبيت مفتاح سري ثابت لعدم تغيره عند إعادة تشغيل السيرفر
if "totp_secret" not in st.session_state:
    st.session_state.totp_secret = "JBSWY3DPEHPK3PXP"

# قائمة الأجهزة الموثوقة الديناميكية
if "trusted_devices" not in st.session_state:
    st.session_state.trusted_devices = [{"name": "موبايل الشركة الرئيسي (مدير النظام)", "user": "admin"}]

if "device_trusted" not in st.session_state:
    st.session_state.device_trusted = False

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "two_fa_passed" not in st.session_state:
    st.session_state.two_fa_passed = False

if "username" not in st.session_state:
    st.session_state.username = ""

if "show_admin_settings" not in st.session_state:
    st.session_state.show_admin_settings = False

# 5. شاشة تسجيل الدخول
if not st.session_state.logged_in:
    st.title("🔐 تسجيل الدخول إلى نظام الداشبوردات - ليناركو")
    st.write("الرجاء إدخال البريد الإلكتروني / اسم المستخدم وكلمة المرور.")
    
    with st.form("login_form"):
        username_input = st.text_input("اسم المستخدم / البريد الإلكتروني")
        password_input = st.text_input("كلمة المرور", type="password")
        submit_button = st.form_submit_button("دخول")
        
        if submit_button:
            clean_username = username_input.strip().lower()
            users = st.session_state.users_db
            if clean_username in users and users[clean_username]["password"] == password_input:
                st.session_state.logged_in = True
                st.session_state.username = clean_username
                
                if users[clean_username]["role"] == "admin":
                    st.session_state.two_fa_passed = True
                
                st.success("تم تسجيل الدخول بنجاح!")
                st.rerun()
            else:
                st.error("اسم المستخدم أو كلمة المرور غير صحيحة.")

# 6. شاشة التحقق الثنائي للمستخدمين الآخرين
elif st.session_state.logged_in and not st.session_state.device_trusted and not st.session_state.two_fa_passed:
    st.title("🛡️ التحقق الثنائي الأمني (Google Authenticator)")
    st.write("هذا الجهاز غير موثوق. يرجى إدخال رمز التحقق المكون من 6 أرقام من تطبيق Google Authenticator:")
    
    with st.form("2fa_form"):
        totp_code = st.text_input("رمز التحقق (6 أرقام):", max_chars=6)
        device_name_input = st.text_input("اسم جهازك أو المتصفح (مثال: لاب توب أحمد / موبايل سامسونج):", value="جهاز موثوق جديد")
        trust_this_device = st.checkbox("وثق هذا الجهاز (عدم طلب الرمز مرة أخرى على هذا المتصفح)")
        verify_btn = st.form_submit_button("تحقق ودخول")
        
        if verify_btn:
            totp = pyotp.TOTP(st.session_state.totp_secret)
            # valid_window=2 لقبول الفارق الزمني بين الهاتف والسيرفر
            if totp.verify(totp_code, valid_window=2):
                st.session_state.two_fa_passed = True
                if trust_this_device:
                    st.session_state.device_trusted = True
                    device_entry = {"name": f"{device_name_input} ({st.session_state.username})", "user": st.session_state.username}
                    if device_entry not in st.session_state.trusted_devices:
                        st.session_state.trusted_devices.append(device_entry)
                
                st.success("تم التحقق بنجاح!")
                st.rerun()
            else:
                st.error("رمز التحقق غير صحيح أو انتهت صلاحيته. يرجى الانتظار لحين ظهور الرمز الجديد على تطبيق الهاتف والمحاولة مجدداً.")

# 7. الشاشة الرئيسية بعد اجتياز الأمان
else:
    current_user_key = st.session_state.username
    user_info = st.session_state.users_db[current_user_key]
    user_role = user_info["role"]
    is_admin = (user_role == "admin")
    is_manager = (user_role == "manager")
    
    # الشريط الجانبي (Sidebar)
    with st.sidebar:
        st.image(st.session_state.company_logo, use_column_width=True)
        if is_admin:
            with st.expander("✏️ تغيير شعار الشركة"):
                c_logo_up = st.file_uploader("رفع شعار ليناركو جديد:", type=["png", "jpg", "jpeg"], key="sb_c_logo")
                if c_logo_up is not None and st.button("حفظ شعار الشركة الجديد"):
                    st.session_state.company_logo = enhance_image_ai_style(c_logo_up)
                    st.success("تم التحديث!")
                    st.rerun()
                    
        st.write("---")
        st.image(st.session_state.qa_logo, use_column_width=True)
        if is_admin:
            with st.expander("✏️ تغيير شعار قسم الجودة"):
                qa_logo_up = st.file_uploader("رفع شعار الجودة جديد:", type=["png", "jpg", "jpeg"], key="sb_qa_logo")
                if qa_logo_up is not None and st.button("حفظ شعار الجودة الجديد"):
                    st.session_state.qa_logo = enhance_image_ai_style(qa_logo_up)
                    st.success("تم التحديث!")
                    st.rerun()
                    
        st.write("---")
        st.write(f"مرحباً بك، **{user_info['name']}** 👋")
        
        role_display = "مدير النظام (Admin)" if is_admin else ("مدير القسم (Manager)" if is_manager else "موظف (User)")
        st.caption(f"الصلاحية: {role_display}")
        st.write("---")
        
        if is_admin:
            if st.button("⚙️ إعدادات التحقق والنظام (Admin)"):
                st.session_state.show_admin_settings = not st.session_state.show_admin_settings
                st.rerun()
            st.write("---")
        
        if st.button("تسجيل الخروج"):
            st.session_state.logged_in = False
            st.session_state.two_fa_passed = False
            st.session_state.show_admin_settings = False
            st.session_state.username = ""
            st.rerun()

    # صفحة إعدادات الآدمن المنفصلة
    if is_admin and st.session_state.show_admin_settings:
        st.title("⚙️ لوحة إعدادات النظام والأمان المركزية")
        st.write("هذه اللوحة مخصصة للآدمن فقط لإدارة إعدادات الأجهزة، المصادقة الثنائية، وصلاحيات المستخدمين.")
        
        if st.button("⬅️ العودة للرئيسية"):
            st.session_state.show_admin_settings = False
            st.rerun()
            
        st.markdown("---")
        
        tab_sec1, tab_sec2 = st.tabs(["📱 إعدادات الأمان والتحقق الثنائي", "👥 لوحة تحكم المستخدمين والصلاحيات"])
        
        with tab_sec1:
            st.subheader("خطوات تسجيل موبايل الشركة في Google Authenticator:")
            st.markdown("""
            1. حمل تطبيق **Google Authenticator** على هاتفك.
            2. افتح التطبيق واضغط على زر الإضافة **(+)** ثم اختر **مسح رمز الاستجابة السريعة (Scan a QR code)**.
            3. امسح كود الـ QR الموجود بالأسفل مرة واحدة فقط، وسيبقى متوافقاً دائماً.
            """)
            
            totp_uri = pyotp.totp.TOTP(st.session_state.totp_secret).provisioning_uri(
                name="Linrco-QA-Admin",
                issuer_name="Linrco Quality Assurance"
            )
            
            img_qr = qrcode.make(totp_uri)
            buf = io.BytesIO()
            img_qr.save(buf)
            st.image(buf.getvalue(), width=230)
            
            st.code(st.session_state.totp_secret, language="text")
            
            st.markdown("---")
            st.subheader("📱 إدارة الأجهزة المقترنة (Trusted Devices)")
            st.write("هنا تظهر الأجهزة التي تمت الموافقة عليها وثقتها بنجاح أثناء تسجيل الدخول:")
            
            if st.session_state.trusted_devices:
                for d_idx, dev_item in enumerate(st.session_state.trusted_devices):
                    col_d1, col_d2 = st.columns([4, 1])
                    with col_d1:
                        st.write(f"🔹 **{dev_item['name']}** (المستخدم: {dev_item['user']})")
                    with col_d2:
                        if st.button("إزالة الجهاز", key=f"del_dev_{d_idx}"):
                            st.session_state.trusted_devices.pop(d_idx)
                            st.success("تم إزالة الجهاز من قائمة الثقة بنجاح!")
                            st.rerun()
            else:
                st.info("لا توجد أجهزة موثوقة مسجلة حالياً.")

        with tab_sec2:
            st.subheader("👥 إدارة المستخدمين والصلاحيات")
            
            users_list = []
            for uname, udata in st.session_state.users_db.items():
                role_ar = "أدمن (Admin)" if udata["role"] == "admin" else ("مدير (Manager)" if udata["role"] == "manager" else "موظف (User)")
                users_list.append({"المستخدم / الإيميل": uname, "الاسم": udata["name"], "الصلاحية": role_ar})
            
            st.table(users_list)
            
            st.markdown("### ➕ إضافة مستخدم جديد")
            with st.form("add_user_form"):
                new_email = st.text_input("البريد الإلكتروني / اسم المستخدم الجديد:")
                new_pass = st.text_input("كلمة المرور:", type="password")
                new_name = st.text_input("اسم المستخدم:")
                new_role_choice = st.selectbox("تحديد الصلاحية:", ["موظف", "مدير", "أدمن"])
                add_user_btn = st.form_submit_button("إضافة المستخدم للنظام")
                
                if add_user_btn:
                    if new_email and new_pass and new_name:
                        role_map = {"أدمن": "admin", "مدير": "manager", "موظف": "user"}
                        clean_new_email = new_email.strip().lower()
                        st.session_state.users_db[clean_new_email] = {
                            "password": new_pass,
                            "name": new_name,
                            "role": role_map[new_role_choice]
                        }
                        st.success(f"تم إضافة المستخدم {new_name} بنجاح!")
                        st.rerun()
                    else:
                        st.warning("يرجى ملء جميع الحقول المطلوبة.")
            
            st.markdown("### 🗑️ مسح مستخدم")
            del_user_target = st.selectbox("اختر المستخدم للحذف:", [u for u in st.session_state.users_db.keys() if u != "admin"])
            if st.button("حذف المستخدم المختار"):
                if del_user_target in st.session_state.users_db:
                    del st.session_state.users_db[del_user_target]
                    st.success("تم حذف المستخدم بنجاح!")
                    st.rerun()

    # الواجهة الرئيسية (Main Portal)
    else:
        if is_admin or is_manager:
            with st.expander("⚙️ لوحة تحكم المشاريع والملفات والأخبار"):
                tab1, tab2, tab3 = st.tabs([
                    "تعديل مشروع وإرفاق ملفات", 
                    "إضافة مشروع جديد", 
                    "إضافة خبر جديد (سلايدر)"
                ])
                
                with tab1:
                    edit_key = st.selectbox("اختر المشروع للتعديل:", list(st.session_state.dashboards.keys()), key="edit_select")
                    if edit_key:
                        current_dash = st.session_state.dashboards[edit_key]
                        new_title = st.text_input("العنوان:", value=current_dash["title"], key="edit_title")
                        new_desc = st.text_area("الوصف والشرح:", value=current_dash["description"], key="edit_desc")
                        new_url = st.text_input("الرابط (URL):", value=current_dash["url"], key="edit_url")
                        
                        st.write("📎 **إرفاق مستند أو ملف:**")
                        uploaded_file = st.file_uploader("اختر الملف للرفع:", type=["docx", "xlsx", "pdf", "vsdx", "pbix", "accdb", "msg", "txt"], key=f"up_{edit_key}")
                        
                        if st.button("حفظ التعديلات ورفع الملف"):
                            files_list = current_dash.get("files", [])
                            if uploaded_file is not None:
                                files_list.append({"name": uploaded_file.name, "data": uploaded_file.getvalue()})
                            
                            st.session_state.dashboards[edit_key] = {
                                "title": new_title,
                                "description": new_desc,
                                "url": new_url,
                                "files": files_list
                            }
                            st.success("تم حفظ التعديلات وتحديث الملفات بنجاح!")
                            st.rerun()
                
                with tab2:
                    add_name = st.text_input("اسم المشروع القصير (في القائمة):", key="add_name")
                    add_title = st.text_input("العنوان الرئيسي:", key="add_title")
                    add_desc = st.text_area("الوصف والشرح التفصيلي:", key="add_desc")
                    add_url = st.text_input("رابط الداشبورد أو المشروع:", key="add_url")
                    
                    if st.button("إضافة المشروع"):
                        if add_name and add_url:
                            st.session_state.dashboards[add_name] = {
                                "title": add_title,
                                "description": add_desc,
                                "url": add_url,
                                "files": []
                            }
                            st.success("تمت إضافة المشروع الجديد بنجاح!")
                            st.rerun()
                        else:
                            st.warning("يرجى إدخال اسم المشروع والرابط على الأقل.")

                with tab3:
                    news_title = st.text_input("عنوان الخبر أو التحديث:", key="news_t")
                    news_content = st.text_area("محتوى الخبر وتفاصيله:", key="news_c")
                    
                    st.write("🖼️ **صورة الخبر:**")
                    news_img_file = st.file_uploader("اختر صورة الخبر:", type=["png", "jpg", "jpeg"], key="news_img_upload")
                    
                    if st.button("نشر الخبر في السلايدر"):
                        if news_title and news_content:
                            img_path = "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=800&auto=format&fit=crop&q=60"
                            if news_img_file is not None:
                                img_path = enhance_image_ai_style(news_img_file)
                                
                            st.session_state.news_list.append({
                                "title": news_title,
                                "content": news_content,
                                "image": img_path
                            })
                            st.success("تم نشر الخبر بنجاح!")
                            st.rerun()
                        else:
                            st.warning("يرجى إدخال عنوان ومحتوى الخبر.")

        # الواجهة الرئيسية (Main Portal)
        st.title("📊 البوابة المركزية لتقارير ومشاريع ضمان الجودة")
        st.markdown(f'<p class="rtl-right">مرحباً بك في منصة متابعة المشاريع والتقارير التحليلية لشركة ليناركو ({user_info["name"]}).</p>', unsafe_allow_html=True)
        
        st.markdown("---")
        st.subheader("📰 آخر الأخبار والتحديثات الإدارية")
        
        if st.session_state.news_list:
            cols = st.columns(len(st.session_state.news_list) if len(st.session_state.news_list) <= 2 else 2)
            for idx, news in enumerate(st.session_state.news_list):
                with cols[idx % len(cols)]:
                    with st.container(border=True):
                        if news.get("image"):
                            st.image(news["image"], use_column_width=True)
                        st.markdown(f"#### {news['title']}")
                        st.write(news['content'])
                        
                        if is_admin or is_manager:
                            with st.expander(f"⚙️ تغيير صورة الخبر ({idx+1})"):
                                changed_img = st.file_uploader("اختر صورة جديدة:", type=["png", "jpg", "jpeg"], key=f"news_ch_{idx}")
                                if changed_img is not None:
                                    if st.button(f"حفظ الصورة الجديدة للخبر {idx+1}", key=f"btn_ch_{idx}"):
                                        st.session_state.news_list[idx]["image"] = enhance_image_ai_style(changed_img)
                                        st.success("تم تحديث صورة الخبر بنجاح!")
                                        st.rerun()

        st.markdown("---")
        st.subheader("📁 استعراض المشاريع والتقارير المتاحة")
        
        for proj_name, proj_data in st.session_state.dashboards.items():
            with st.container():
                st.markdown(f"""
                    <div class="project-card">
                        <h3>📌 {proj_name}</h3>
                        <p><b>العنوان:</b> {proj_data['title']}</p>
                        <p><b>نبذة:</b> {proj_data['description']}</p>
                    </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        selected_key = st.selectbox("🎯 اختر المشروع المطلوب عرضه بالأسفل:", list(st.session_state.dashboards.keys()))
        
        if selected_key:
            dash_data = st.session_state.dashboards[selected_key]
            
            st.markdown("---")
            st.header(dash_data["title"])
            
            st.info(f"📝 **الشرح والتفاصيل:**\n\n{dash_data['description']}")
            
            if dash_data.get("files"):
                st.markdown("### 📥 الملفات والمستندات المرفقة بالمشروع:")
                for file_item in dash_data["files"]:
                    st.download_button(
                        label=f"📥 تحميل الملف المرفق: {file_item['name']}",
                        data=file_item["data"],
                        file_name=file_item["name"],
                        mime="application/octet-stream"
                    )
            else:
                st.markdown('<p class="rtl-right" style="color: gray; font-size: 16px;">لا توجد ملفات مرفقة حالياً لهذا المشروع.</p>', unsafe_allow_html=Test)
            
            st.markdown(f'<p class="rtl-right">🔗 <b>رابط مباشر:</b> <a href="{dash_data["url"]}" target="_blank">اضغط هنا لفتح المشروع في تبويب جديد</a></p>', unsafe_allow_html=True)
            
            st.markdown("---")
            
            st.components.v1.iframe(dash_data["url"], width=1200, height=800, scrolling=True)
