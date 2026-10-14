import streamlit as st

# إعدادات صفحة الويب
st.set_page_config(page_title="لوحة تحكم الداشبورد", page_icon="📊", layout="wide")

# تخصيص وتكبير الخطوط وإخفاء شريط أدوات Streamlit العلوي بالكامل
st.markdown("""
    <style>
    /* إخفاء شريط أدوات Streamlit العلوي (Toolbar) وأزرار المشاركة والتعديل */
    header {visibility: hidden !important;}
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    
    /* تكبير الخط العام في الصفحة */
    html, body, [class*="css"] {
        font-size: 28px !important;
    }
    /* تكبير خط العناوين */
    h1 { font-size: 42px !important; }
    h2 { font-size: 36px !important; }
    h3 { font-size: 32px !important; }
    
    /* تكبير خط التسميات والحقول */
    .stSelectbox label, .stTextInput label, .stPassword label, .stTextArea label {
        font-size: 20px !important;
        font-weight: bold !important;
        color: #1f77b4;
    }
    </style>
""", unsafe_allow_html=True)

# 1. الداشبوردات المتاحة افتراضياً للجميع مع التفاصيل والعناوين
DEFAULT_DASHBOARDS = {
    "مؤشرات أداء قسم الـ QA": {
        "title": "📊 QA داشبورد تحليل الأداء قسم الجودة",
        "description": "تحتوي هذه الداشبورد على تحليلات شاملة للنشاطات اليومية والشهرية، بالإضافة إلى مقارنة الأداء ومؤشرات الأداء الرئيسية (KPIs).",
        "url": "https://datastudio.google.com/s/pZkBFbgR5as"
    },
    "مشروع الـ TPV": {
        "title": "📈 TPV داشبورد مشروع الـ",
        "description": "تستعرض الداشبورد تفاصيل مشروع TPV و نتيجتها و تفاصيل الانشطه المستخدمه اليوميه من قسم الجوده و نسب الربحيه لمختلف القطاعات.",
        "url": "https://datastudio.google.com/s/lzMLkPXvy28"
    }
}

# 2. قاموس حسابات المستخدمين وكلمات المرور
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

# 3. إدارة حالة التطبيق والبيانات في Session State
if "dashboards" not in st.session_state:
    st.session_state.dashboards = DEFAULT_DASHBOARDS

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

# 4. شاشة تسجيل الدخول
if not st.session_state.logged_in:
    st.title("🔐 تسجيل الدخول إلى نظام الداشبوردات")
    st.write("الرجاء إدخال البريد الإلكتروني / اسم المستخدم وكلمة المرور.")
    
    with st.form("login_form"):
        username_input = st.text_input("اسم المستخدم / البريد الإلكتروني")
        password_input = st.text_input("كلمة المرور", type="password")
        submit_button = st.form_submit_button("دخول")
        
        if submit_button:
            clean_username = username_input.strip().lower()
            if clean_username in USERS and USERS[clean_username]["password"] == password_input:
                st.session_state.logged_in = True
                st.session_state.username = clean_username
                st.success("تم تسجيل الدخول بنجاح!")
                st.rerun()
            else:
                st.error("اسم المستخدم أو كلمة المرور غير صحيحة.")

# 5. الشاشة الرئيسية بعد تسجيل الدخول
else:
    current_user_key = st.session_state.username
    user_info = USERS[current_user_key]
    is_admin = user_info["role"] == "admin"
    
    # الشريط الجانبي (Sidebar)
    with st.sidebar:
        st.write(f"مرحباً بك، **{user_info['name']}** 👋")
        st.caption(f"نوع الحساب: {'مدير النظام (Admin)' if is_admin else 'مستخدم (User)'}")
        st.write("---")
        
        if st.button("تسجيل الخروج"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()

    # قسم خاص بالآدمن فقط للتعديل والإضافة
    if is_admin:
        with st.expander("⚙️ لوحة تحكم المدير (تعديل / إضافة داشبوردات)"):
            tab1, tab2 = st.tabs(["تعديل داشبورد حالية", "إضافة داشبورد جديدة"])
            
            # تعديل داشبورد
            with tab1:
                edit_key = st.selectbox("اختر الداشبورد للتعديل:", list(st.session_state.dashboards.keys()), key="edit_select")
                if edit_key:
                    current_dash = st.session_state.dashboards[edit_key]
                    new_title = st.text_input("العنوان:", value=current_dash["title"], key="edit_title")
                    new_desc = st.text_area("الوصف والشرح:", value=current_dash["description"], key="edit_desc")
                    new_url = st.text_input("الرابط (URL):", value=current_dash["url"], key="edit_url")
                    
                    if st.button("حفظ التعديلات"):
                        st.session_state.dashboards[edit_key] = {
                            "title": new_title,
                            "description": new_desc,
                            "url": new_url
                        }
                        st.success("تم حفظ التعديلات بنجاح!")
                        st.rerun()
            
            # إضافة داشبورد جديدة
            with tab2:
                add_name = st.text_input("اسم الداشبورد القصير (في القائمة):", key="add_name")
                add_title = st.text_input("العنوان الرئيسي:", key="add_title")
                add_desc = st.text_area("الوصف والشرح التفصيلي:", key="add_desc")
                add_url = st.text_input("رابط Looker Studio:", key="add_url")
                
                if st.button("إضافة الداشبورد"):
                    if add_name and add_url:
                        st.session_state.dashboards[add_name] = {
                            "title": add_title,
                            "description": add_desc,
                            "url": add_url
                        }
                        st.success("تمت إضافة الداشبورد الجديدة بنجاح!")
                        st.rerun()
                    else:
                        st.warning("يرجى إدخال اسم الداشبورد والرابط على الأقل.")

    # المحتوى الرئيسي المتاح لجميع المستخدمين
    st.title("📊 لوحة تقارير Looker Studio")
    st.write("اختر الداشبورد المطلوبة من القائمة لعرض التفاصيل والمعاينة:")
    
    # القائمة المنسدلة لاختيار الداشبورد
    selected_key = st.selectbox("اختر الداشبورد:", list(st.session_state.dashboards.keys()))
    
    if selected_key:
        dash_data = st.session_state.dashboards[selected_key]
        
        st.markdown("---")
        # عرض العنوان
        st.header(dash_data["title"])
        
        # عرض الشرح التفصيلي
        st.info(f"📝 **الشرح والتفاصيل:**\n\n{dash_data['description']}")
        
        # رابط الفتح في صفحة جديدة
        st.markdown(f"🔗 **رابط مباشر:** [اضغط هنا لفتح الداشبورد في تبويب جديد]({dash_data['url']})")
        
        st.markdown("---")
        
        # عرض الداشبورد المدمجة داخل الصفحة
        st.components.v1.iframe(dash_data["url"], width=1200, height=800, scrolling=True)
