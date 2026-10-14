import streamlit as st
from PIL import Image, ImageEnhance
import io
import pyotp

# إعدادات صفحة الويب
st.set_page_config(page_title="لوحة تحكم قسم الجودة - ليناركو", page_icon="📊", layout="wide")

# تخصيص وتكبير الخطوط، قلب الاتجاه إلى RTL، ونقل الشريط الجانبي لليمين
st.markdown("""
    <style>
    /* إخفاء شريط أدوات Streamlit العلوي (Toolbar) */
    header {visibility: hidden !important;}
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    
    /* جعل الاتجاه من اليمين لليسار لكافة عناصر الصفحة والنصوص العربية */
    html, body, [class*="css"] {
        direction: rtl !important;
        text-align: right !important;
        font-family: 'Cairo', Tahoma, sans-serif !important;
        font-size: 20px !important;
    }
    
    /* تكبير خط العناوين وتثبيت محاذاتها لليمين */
    h1, h2, h3, h4, h5, h6 {
        text-align: right !important;
        color: #8B0000;
        direction: rtl !important;
    }
    h1 { font-size: 38px !important; }
    h2 { font-size: 30px !important; color: #333333; }
    h3 { font-size: 24px !important; }

    /* نقل الشريط الجانبي (Sidebar) إلى اليمين وعكس اتجاهه */
    [data-testid="stSidebar"] {
        right: 0px !important;
        left: auto !important;
        direction: rtl !important;
        text-align: right !important;
    }
    
    /* تعديل مكان محتوى الصفحة الرئيسية ليترك مساحة للشريط الجانبي الأيمن */
    .main .block-container {
        direction: rtl !important;
        text-align: right !important;
    }

    /* تنسيق كاردات المشاريع والأخبار */
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
    
    /* ضبط محاذاة الحقول والتسميات */
    .stSelectbox, .stTextInput, .stTextArea, .stFileUploader {
        text-align: right !important;
        direction: rtl !important;
    }

    /* فئة خاصة للمحاذاة الصريحة من اليمين للشمال */
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

# المفتاح السري الموحد لتطبيق Google Authenticator (يمكن للآدمن تغييره من اللوحة)
if "totp_secret" not in st.session_state:
    st.session_state.totp_secret = "JBSWY3DPEHPK3PXP" # مفتاح سري افتراضي

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

# 2. أخبار قسم الجودة (Slider / Recent News)
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

# 3. قاموس حسابات المستخدمين وكلمات المرور
USERS = {
    "admin": {"password": "123", "name": "مدير النظام", "role": "admin"},
    "hossam.saeed@fnrco.com.sa": {"password": "HS123", "name": "حسام سعيد", "role": "user"},
    "abdelrahman.lashine@fnrco.com.sa": {"password": "AL123", "name": "عبد الرحمن لاشين", "role": "user"},
    "yassmen.khaled@fnrco.com.sa": {"password": "HS123", "name": "ياسمين خالد", "role": "user"},
    "kenzy.hisham@fnrco.com.sa": {"password": "KH123", "name": "كنزي هشام", "role": "user"},
    "lamia.adel@fnrco.com.sa": {"password": "LA123", "name": "لمياء عادل", "role": "user"},
    "nancy.safwat@fnrco.com.sa": {"password": "NS123", "name": "نانسي صفوت", "role": "user"},
    "abdallah.zaukzouk@fnrco.com.sa": {"password": "AZ123", "name": "عبد الله زقزوق", "role": "user"}
}

# رمز الشبكة الداخلية للشركة (Network PIN)
COMPANY_NETWORK_PIN = "Linrco2026"

# 4. إدارة حالة التطبيق (Session State)
if "dashboards" not in st.session_state:
    st.session_state.dashboards = DEFAULT_DASHBOARDS

if "news_list" not in st.session_state:
    st.session_state.news_list = DEFAULT_NEWS

if "company_logo" not in st.session_state:
    st.session_state.company_logo = "https://raw.githubusercontent.com/ahmedgouda2727/QA-Dashboard-APP/main/Linrco-Egypt.PNG"

if "qa_logo" not in st.session_state:
    st.session_state.qa_logo = "https://raw.githubusercontent.com/ahmedgouda2727/QA-Dashboard-APP/main/QA.png"

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

# الاحتفاظ بالأجهزة الموثوقة (Trusted Devices) في الـ Session
if "trusted_devices" not in st.session_state:
    st.session_state.trusted_devices = set()

# 5. شاشة تسجيل الدخول المدمجة بالرمز السري ومصادقة Google Authenticator
if not st.session_state.logged_in:
    st.title("🔐 تسجيل الدخول إلى نظام الداشبوردات - ليناركو")
    st.write("الرجاء إدخال بيانات الحساب ورمز أمان المقر.")
    
    with st.form("login_form"):
        username_input = st.text_input("اسم المستخدم / البريد الإلكتروني")
        password_input = st.text_input("كلمة المرور", type="password")
        network_pin_input = st.text_input("🔑 رمز أمان شبكة الشركة (Network PIN)", type="password")
        
        # معرف افتراضي للجهاز الحالي
        device_id = f"{username_input.strip().lower()}_trusted_device"
        is_device_trusted = device_id in st.session_state.trusted_devices
        
        # حقل رمز Google Authenticator (يطلب فقط إذا لم يكن الجهاز موثوقاً)
        if not is_device_trusted:
            otp_input = st.text_input("📲 رمز المصادقة (Google Authenticator App)", help="أدخل الرمز المكون من 6 أرقام والموجود على موبايل الشركة")
            remember_device = st.checkbox("طلب التوثيق والوثوق بهذا الجهاز (Trust this device) لتخطي رمز الأمان لاحقاً")
        else:
            st.info("🟢 هذا الجهاز موثوق ومسجل بالفعل (Trusted Device).")
            otp_input = None
            remember_device = False

        submit_button = st.form_submit_button("دخول للنظام")
        
        if submit_button:
            clean_username = username_input.strip().lower()
            
            # التحقق من اسم المستخدم وكلمة المرور ورمز المقر
            if clean_username in USERS and USERS[clean_username]["password"] == password_input:
                if network_pin_input != COMPANY_NETWORK_PIN:
                    st.error("❌ رمز أمان شبكة الشركة (Network PIN) غير صحيح.")
                else:
                    # التحقق من رمز Google Authenticator إذا كان الجهاز غير موثوق
                    if not is_device_trusted:
                        totp = pyotp.TOTP(st.session_state.totp_secret)
                        if not otp_input or not totp.verify(otp_input):
                            st.error("❌ رمز المصادقة (Google Authenticator Code) غير صحيح أو منتهي الصلاحية.")
                        else:
                            if remember_device:
                                st.session_state.trusted_devices.add(device_id)
                            st.session_state.logged_in = True
                            st.session_state.username = clean_username
                            st.success("تم تسجيل الدخول وتوثيق الجهاز بنجاح!")
                            st.rerun()
                    else:
                        st.session_state.logged_in = True
                        st.session_state.username = clean_username
                        st.success("تم تسجيل الدخول بنجاح!")
                        st.rerun()
            else:
                st.error("اسم المستخدم أو كلمة المرور غير صحيحة.")

# 6. الشاشة الرئيسية بعد تسجيل الدخول
else:
    current_user_key = st.session_state.username
    user_info = USERS[current_user_key]
    is_admin = user_info["role"] == "admin"
    
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
        st.caption(f"نوع الحساب: {'مدير النظام (Admin)' if is_admin else 'مستخدم (User)'}")
        st.write("---")
        
        if st.button("تسجيل الخروج"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()

    # لوحة تحكم المدير (تتضمن قسم الـ Google Authenticator للآدمن فقط)
    if is_admin:
        with st.expander("⚙️ لوحة تحكم المدير (إدارة المشاريع، الملفات، الأخبار، وإعدادات الـ 2FA)"):
            tab1, tab2, tab3, tab4 = st.tabs([
                "تعديل مشروع وإرفاق ملفات", 
                "إضافة مشروع جديد", 
                "إضافة خبر جديد (سلايدر)",
                "📲 إعدادات Google Authenticator (خاص للآدمن فقط)"
            ])
            
            with tab1:
                edit_key = st.selectbox("اختر المشروع للتعديل:", list(st.session_state.dashboards.keys()), key="edit_select")
                if edit_key:
                    current_dash = st.session_state.dashboards[edit_key]
                    new_title = st.text_input("العنوان:", value=current_dash["title"], key="edit_title")
                    new_desc = st.text_area("الوصف والشرح:", value=current_dash["description"], key="edit_desc")
                    new_url = st.text_input("الرابط (URL):", value=current_dash["url"], key="edit_url")
                    
                    st.write("📎 **إرفاق مستند أو ملف (Word, Excel, PDF, Power BI, Visio, Access, Outlook):**")
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
                
                st.write("🖼️ **صورة الخبر (معالجة ذكية للحواف والجودة):**")
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
                        st.success("تم نشر الخبر بنجاح مع ضبط الحدود والجودة بالذكاء الاصطناعي!")
                        st.rerun()
                    else:
                        st.warning("يرجى إدخال عنوان ومحتوى الخبر.")

            # 🔒 القسم الخاص بالآدمن لإعداد وربط Google Authenticator
            with tab4:
                st.write("### 🔑 إدارة رمز المصادقة الثنائية (Google Authenticator)")
                st.write("امسح هذا المفتاح برمجياً في تطبيق Google Authenticator على موبايل الشركة فقط:")
                
                totp = pyotp.TOTP(st.session_state.totp_secret)
                provisioning_uri = totp.provisioning_uri(name="QA_Linrco_Admin", issuer_name="Linrco")
                
                st.code(f"المفتاح السري (Secret Key): {st.session_state.totp_secret}")
                st.info("💡 يمكنك إضافة هذا المفتاح السري يدوياً في تطبيق Google Authenticator بفتح التطبيق واختيار 'Enter a setup key'.")
                
                # إمكانية للآدمن لتوليد مفتاح سري جديد في حال رغب في ذلك
                if st.button("توليد مفتاح سري جديد للـ 2FA"):
                    st.session_state.totp_secret = pyotp.random_base32()
                    st.success("تم إعادة تعيين المفتاح السري! يرجى إعادة ربطه بموبايل الشركة.")
                    st.rerun()

    # الواجهة الرئيسية (Main Portal)
    st.title("📊 البوابة المركزية لتقارير ومشاريع ضمان الجودة")
    
    st.markdown('<p class="rtl-right">مرحباً بك في منصة متابعة المشاريع والتقارير التحليلية لشركة ليناركو.</p>', unsafe_allow_html=True)
    
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
                    
                    if is_admin:
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
            st.markdown('<p class="rtl-right" style="color: gray; font-size: 16px;">لا توجد ملفات مرفقة حالياً لهذا المشروع.</p>', unsafe_allow_html=True)
        
        st.markdown(f'<p class="rtl-right">🔗 <b>رابط مباشر:</b> <a href="{dash_data["url"]}" target="_blank">اضغط هنا لفتح المشروع في تبويب جديد</a></p>', unsafe_allow_html=True)
        
        st.markdown("---")
        
        st.components.v1.iframe(dash_data["url"], width=1200, height=800, scrolling=True)
