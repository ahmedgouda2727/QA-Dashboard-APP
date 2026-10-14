import streamlit as st

# إعدادات صفحة الويب
st.set_page_config(page_title="لوحة تحكم قسم الجودة - ليناركو", page_icon="📊", layout="wide")

# تخصيص وتكبير الخطوط وإخفاء شريط أدوات Streamlit العلوي بالكامل
st.markdown("""
    <style>
    /* إخفاء شريط أدوات Streamlit العلوي (Toolbar) وأزرار المشاركة والتعديل */
    header {visibility: hidden !important;}
    #MainMenu {visibility: hidden !important;}
    footer {visibility: hidden !important;}
    
    /* تكبير الخط العام في الصفحة */
    html, body, [class*="css"] {
        font-size: 20px !important;
    }
    /* تكبير خط العناوين */
    h1 { font-size: 38px !important; color: #8B0000; }
    h2 { font-size: 30px !important; color: #333333; }
    h3 { font-size: 24px !important; }
    
    /* تنسيق كاردات المشاريع والأخبار */
    .project-card {
        background-color: #f9f9f9;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
    }
    </style>
""", unsafe_allow_html=True)

# 1. الداشبوردات والمشاريع الافتراضية مع إمكانية إرفاق ملفات
DEFAULT_DASHBOARDS = {
    "مؤشرات أداء قسم الـ QA": {
        "title": "📊 QA Dashboard تحليل الأداء قسم الجودة",
        "description": "تحتوي هذه الداشبورد على تحليلات شاملة للنشاطات اليومية والشهرية، بالإضافة إلى مقارنة الأداء ومؤشرات الأداء الرئيسية (KPIs).",
        "url": "https://datastudio.google.com/s/pZkBFbgR5as",
        "files": [] # قائمة الملفات المرفقة للمشروع
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

# 4. إدارة حالة التطبيق (Session State)
if "dashboards" not in st.session_state:
    st.session_state.dashboards = DEFAULT_DASHBOARDS

if "news_list" not in st.session_state:
    st.session_state.news_list = DEFAULT_NEWS

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "username" not in st.session_state:
    st.session_state.username = ""

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
            if clean_username in USERS and USERS[clean_username]["password"] == password_input:
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
    
    # الشريط الجانبي (Sidebar) مع شعارات الشركة والقسم
    with st.sidebar:
        # عرض شعار الشركة وشعار القسم (استبدل الروابط أو استخدم الصور المحلية المرفوعة)
        st.image("https://images.unsplash.com/photo-1599305445671-ac291c95aaa9?w=300&auto=format&fit=crop&q=60", width=220)
        st.markdown("### 🏢 **شركة ليناركو (Linrco)**")
        st.markdown("### 🛡️ **قسم ضمان الجودة (QA)**")
        st.write("---")
        st.write(f"مرحباً بك، **{user_info['name']}** 👋")
        st.caption(f"نوع الحساب: {'مدير النظام (Admin)' if is_admin else 'مستخدم (User)'}")
        st.write("---")
        
        if st.button("تسجيل الخروج"):
            st.session_state.logged_in = False
            st.session_state.username = ""
            st.rerun()

    # لوحة تحكم المدير (تعديل / إضافة مشاريع، ملفات، وأخبار)
    if is_admin:
        with st.expander("⚙️ لوحة تحكم المدير (إدارة المشاريع، الملفات، والأخبار)"):
            tab1, tab2, tab3 = st.tabs(["تعديل مشروع حالي وإرفاق ملفات", "إضافة مشروع جديد", "إضافة خبر جديد للإعلان"])
            
            # تعديل مشروع وإرفاق ملفات
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
                            # حفظ الملف في القائمة المرتبطة بالمشروع
                            files_list.append({"name": uploaded_file.name, "data": uploaded_file.getvalue()})
                        
                        st.session_state.dashboards[edit_key] = {
                            "title": new_title,
                            "description": new_desc,
                            "url": new_url,
                            "files": files_list
                        }
                        st.success("تم حفظ التعديلات وتحديث الملفات بنجاح!")
                        st.rerun()
            
            # إضافة مشروع جديد
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

            # إضافة خبر جديد (Slider News)
            with tab3:
                news_title = st.text_input("عنوان الخبر أو التحديث:", key="news_t")
                news_content = st.text_area("محتوى الخبر وتفاصيله:", key="news_c")
                news_img = st.text_input("رابط صورة توضيحية للخبر (اختياري):", key="news_i")
                
                if st.button("نشر الخبر في السلايدر"):
                    if news_title and news_content:
                        st.session_state.news_list.append({
                            "title": news_title,
                            "content": news_content,
                            "image": news_img if news_img else "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=800&auto=format&fit=crop&q=60"
                        })
                        st.success("تم نشر الخبر بنجاح!")
                        st.rerun()
                    else:
                        st.warning("يرجى إدخال عنوان ومحتوى الخبر.")

    # الواجهة الرئيسية (Main Portal)
    st.title("📊 البوابة المركزية لتقارير ومشاريع ضمان الجودة")
    st.write("مرحباً بك في منصة متابعة المشاريع والتقارير التحليلية لشركة ليناركو.")
    
    # قسم سلايدر الأخبار والتحديثات (Recent News Slider)
    st.markdown("---")
    st.subheader("📰 آخر الأخبار والتحديثات الإدارية")
    
    if st.session_state.news_list:
        # عرض الأخبار بشكل منظم وتفاعلي
        cols = st.columns(len(st.session_state.news_list) if len(st.session_state.news_list) <= 2 else 2)
        for idx, news in enumerate(st.session_state.news_list):
            with cols[idx % len(cols)]:
                with st.container(border=True):
                    if news.get("image"):
                        st.image(news["image"], use_column_width=True)
                    st.markdown(f"#### {news['title']}")
                    st.write(news['content'])

    st.markdown("---")
    st.subheader("📁 استعراض المشاريع والتقارير المتاحة")
    
    # عرض بطاقات ملخصة للمشاريع كعرض مبسط ومنظم
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
    # القائمة المنسدلة لاختيار المشروع المراد عرضه بالتفصيل والتحميل
    selected_key = st.selectbox("🎯 اختر المشروع المطلوب عرضه بالأسفل:", list(st.session_state.dashboards.keys()))
    
    if selected_key:
        dash_data = st.session_state.dashboards[selected_key]
        
        st.markdown("---")
        st.header(dash_data["title"])
        
        # عرض الشرح التفصيلي
        st.info(f"📝 **الشرح والتفاصيل:**\n\n{dash_data['description']}")
        
        # قسم الملفات المرفقة (للتحميل والاستعراض)
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
            st.caption("لا توجد ملفات مرفقة حالياً لهذا المشروع.")
        
        # رابط الفتح في تبويب جديد
        st.markdown(f"🔗 **رابط مباشر:** [اضغط هنا لفتح المشروع في تبويب جديد]({dash_data['url']})")
        
        st.markdown("---")
        
        # عرض المشروع المدمج داخل الصفحة
        st.components.v1.iframe(dash_data["url"], width=1200, height=800, scrolling=True)
