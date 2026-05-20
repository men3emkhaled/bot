import logging
import sqlite3
import asyncio
import datetime
import textwrap
import os
import threading
from dotenv import load_dotenv

load_dotenv()
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    PicklePersistence,
)

# ─── الإعدادات ───────────────────────────────
BOT_TOKEN  = os.getenv("BOT_TOKEN")
ADMIN_ID   = int(os.getenv("ADMIN_ID",   "5481609181"))
ADMIN_ID_2 = int(os.getenv("ADMIN_ID_2", "1049124970"))
ADMINS     = [ADMIN_ID, ADMIN_ID_2]  # قائمة جميع الآدمنز لتوجيه الطلبات
CHANNEL_ID = os.getenv("CHANNEL_ID", "@AlBalashon_Channel")

# ─── مسارات قواعد البيانات وحفظ الحالة ────────
DATA_DIR = os.getenv("DATA_DIR", ".")
if DATA_DIR != "." and not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "albalashon.db")
PERSISTENCE_PATH = os.path.join(DATA_DIR, "albalashon_state.pickle")

# تم استبدال المتغيرات العامة باستخدام context.bot_data لحفظ الحالة

# ─── مراحل المحادثة ──────────────────────────
WAITING_FOR_REQUEST_DETAILS = 1

# ─── نصوص ثابتة (يمكنك تعديلها لاحقاً) ────────
DOCTORS_TEXT = textwrap.dedent("""\
    🩺 *دليل الأطباء والعيادات بالبلاشون:*

    يرجى اختيار التخصص المطلوب من الأزرار بالأسفل لعرض كافة التفاصيل والمواعيد.

    ----------------------------------------
    🚨 *[ملاحظة هامة]:*
    • 👨‍⚕️ د/ عبد الله نبيل الشوبكي (طوارئ 24 ساعة)
      📞 هاتفياً: 01130396842 | 💬 واتساب: 01069431963
    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

DENTISTRY_TEXT = textwrap.dedent("""\
    🦷 *[طب وجراحة الفم والأسنان]*
    ----------------------------------------

    • 👨‍⚕️ د/ محمود حسن (جراحة وتجميل الأسنان)
      📍 العنوان: البلاشون - أمام الجامع الكبير.
      📅 المواعيد: من السبت إلى الخميس (من 5:00 مساءً إلى 10:00 مساءً).
      📞 للتواصل: 0552800010 - 01002992125

    • 👨‍⚕️ د/ سيد مصطفى درويش (الفم والأسنان)
      📅 المواعيد: الأحد، الثلاثاء، والخميس (من 1:00 ظهراً إلى 9:00 مساءً).
      📞 رقم الموبايل: 01091339445

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

PHYSIO_NUTRITION_TEXT = textwrap.dedent("""\
    🦾 *[العلاج الطبيعي والتغذية]*
    ----------------------------------------

    • 👨‍⚕️ د/ أحمد صقر (أخصائي العلاج الطبيعي، التغذية العلاجية، والحجامة الطبية)
      📍 العنوان: البلاشون - مركز بلبيس.
      📞 رقم التواصل: 01064348233

    • 👨‍⚕️ د/ أحمد سامي عزام (العلاج الطبيعي، الجلسات المنزلية، والحجامة)
      📝 التخصص: حالات الجراحة، الكسور، الجلطات، والمسنين.
      📞 أرقام التواصل: 01050915289 - 01113997889

    • 👨‍⚕️ د/ يوسف محمد محمد (أخصائي العلاج الطبيعي - Physiotherapy)
      📞 أرقام التواصل: 01004567506 - 01016233543

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

INTERNAL_CARDIO_CHEST_TEXT = textwrap.dedent("""\
    🫁 *[الباطنة والقلب والصدر]*
    ----------------------------------------

    • 👨‍⚕️ د/ فاروق دياب (الباطنة والجهاز الهضمي)
      📅 المواعيد: من السبت للخميس (من 6:00 مساءً لـ 10:00 مساءً).
      📞 للتواصل: 0552801193

    • 👨‍⚕️ د/ محمد حسني (القلب والباطنة والصدر)
      📞 للتواصل: 01067682611

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

OBSTETRICS_GYNECOLOGY_TEXT = textwrap.dedent("""\
    🤰 *[أمراض النساء والتوليد]*
    ----------------------------------------

    • 👩‍⚕️ د/ سهام هجرس (أخصائية النساء والتوليد)
      📍 العنوان: أعلى صيدلية الدكتور شكري محمد - بجوار مجوهرات حامد محروس.
      📅 المواعيد: يومياً بدءاً من الساعة 5:00 مساءً.

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

ENT_TEXT = textwrap.dedent("""\
    👂 *[الأنف والأذن والحنجرة]*
    ----------------------------------------

    • 👨‍⚕️ د/ أحمد مصطفى خطاب (استشاري الأنف والأذن والحنجرة وتجميل الأنف)
      📍 العنوان: الطريق الرئيسي - أعلى صيدلية خطاب.
      📅 المواعيد: 
      - السبت، الإثنين، والأربعاء (من 5:00 إلى 9:00 مساءً).
      - الأحد، الثلاثاء، والخميس (من 3:00 إلى 5:00 مساءً).
      📞 للتواصل: 01022007977

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

NEURO_SURGERY_TEXT = textwrap.dedent("""\
    🧠 *[مخ وأعصاب وجراحة عامة]*
    ----------------------------------------

    • 👨‍⚕️ د/ أحمد صلاح (المخ والأعصاب)
      📍 العنوان: أعلى صيدلية دكتور شكري.
      📅 المواعيد: من الإثنين للخميس (من 4:00 عصراً لـ 8:00 مساءً).

    • 👨‍⚕️ د/ إسلام جمال هندي (الجراحة العامة)
      📅 المواعيد: كل يوم عدا الإثنين (من 5:00 مساءً لـ 10:00 مساءً).

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

UROLOGY_DERMA_TEXT = textwrap.dedent("""\
    🩸 *[المسالك البولية والجلدية]*
    ----------------------------------------

    • 👨‍⚕️ د/ أسامة الجندي (مسالك بولية)
      📅 المواعيد: يومياً عدا الجمعة (من 5:00 مساءً لـ 11:00 مساءً).

    • 👨‍⚕️ د/ عبد الرحمن (الجلدية)
      📍 العنوان: عمارة الأطباء.

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

XRAY_LABS_TEXT = textwrap.dedent("""\
    • 🔬 معمل: رسالة (للطب والتحاليل الطبية)
      💼 الإدارة: دكتور غنيمي عزام
      🎓 المؤهلات: بكالوريوس علوم - جامعة الزقازيق | دبلومة التحاليل الطبية - جامعة بنها | رئيس قسم التحاليل الطبية بالشركة العربية للأدوية
      📍 العنوان: البلاشون - بجانب المسجد الكبير
      📞 للتواصل: 01020408604 (هاتف وواتساب) | 01124373151 (هاتف)
    🔬 *[مراكز الأشعة والتحاليل]*
    ----------------------------------------

    • 🏢 مركز أ.د/ محمد عبد الخالق باشا للأشعة التشخيصية
      📍 العنوان: البلاشون - بجوار بنزينة رمضان عبد الكريم.
      📅 المواعيد:
      - يومياً: من 2:30 ظهراً إلى 10:30 مساءً.
      - الجمعة: من 3:00 عصراً إلى 10:00 مساءً.
      📞 أرقام التواصل: 0552801774 - 01025071770 - 01289740450

    • 🔬 معمل الدكتور: محمد الخولي (للتحاليل الطبية)
      📞 للتواصل: 01001095354
    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\\_services\\\_bot""")
PEDIATRICS_TEXT = textwrap.dedent("""\
    👶 *[طب الأطفال وحديثي الولادة]*
    ----------------------------------------

    • 🩺 الدكتورة: إيمان السيد عفيفي
      💼 التخصص: استشاري طب الأطفال وحديثي الولادة
      📍 العنوان: قرية البلاشون - منزل أ / السيد عفيفي (رحمه الله)
      📞 للتواصل: 01028447728

    ✨ *خدمات العيادة:*
    - فحص شامل حديثي الولادة
    - صفراء حديثي الولادة
    - نزلات البرد وحساسية الصدر
    - النزلات المعوية
    - اضطرابات النمو والضعف العام وقصر القامة
    - التبول اللاإرادي
    - الأمراض الجلدية في الأطفال
    - ضعف المناعة
    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")
ALFATH_CLINICS_TEXT = textwrap.dedent("""\
    🏛️ *عيادات الفتح التخصصية*
    ----------------------------------------

    🦷 *[قسم طب وجراحة الفم والأسنان]:*

    • 👨‍⚕️ د/ علي الشاهد (أخصائي طب وجراحة الفم والأسنان)
      📅 المواعيد: السبت، الأحد، الاثنين، والجمعة.
      ⏰ الوقت: من 4:00 إلى 9:00 مساءً.

    • 👨‍⚕️ د/ خالد أبو زيد باشا (أخصائي طب وجراحة الفم والأسنان)
      📅 المواعيد: الثلاثاء والأربعاء.
      ⏰ الوقت: من 4:00 إلى 9:00 مساءً.

    • 👩‍⚕️ د/ الشيماء جمال (أخصائية طب وجراحة الفم والأسنان)
      📅 المواعيد: الخميس.
      ⏰ الوقت: من 4:00 إلى 9:00 مساءً.

    ----------------------------------------

    👁️ *[عيادة الرمد والعيون]:*

    • 👨‍⚕️ د/ أحمد مكاوي (أخصائي طب وجراحة العيون)
      📅 المواعيد: الثلاثاء والجمعة.
      ⏰ الوقت: من 4:00 إلى 7:00 مساءً.

    ----------------------------------------

    🩺 *[عيادة الباطنة العامة]:*

    • 👨‍⚕️ د/ إبراهيم عاطف الجندي (نائب الباطنة العامة بمستشفى الأحرار التعليمي بالزقازيق)
      📅 المواعيد: الأحد والجمعة.
      ⏰ الوقت: من 5:00 إلى 9:00 مساءً.

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

DEVELOPER_TEXT = textwrap.dedent("""\
    🏅 *Captain & Engineer: Badr Frere*
    ----------------------------------------
    💪 *[الجانب الرياضي والصحي]:*
    • التخصص: مدرب فيتنس وكوتش تغذية محترف (Professional Nutritionist).
    • المقر الحالي: أكاديمية جروكسي (Goroxi Academy) - العاشر من رمضان.
    • الخدمات: تصميم برامج تدريبية، خطط تغذية علمية وحساب ماكروز للتخسيس أو التضخيم.

    💻 *[الجانب التقني والبرمجي]:*
    • التخصص: Front-End Developer
    • الخدمات المتاحة لأصحاب الأعمال والمشاريع:
      - تصميم وتطوير مواقع احترافية للبرندات والشركات.
      - بناء أنظمة كاشير وإدارة ومبيعات متكاملة (ERP Systems).
      - تطوير سيستم كامل لإدارة الشركات التدريبية والأكاديميات.

    📞 *رقم التواصل والواتساب المباشر:* 01020549760
    ----------------------------------------
""")

EMERGENCY_PHARMACY_INFO = textwrap.dedent("""\
    👨‍⚕️ *صيدلية الطوارئ الليلة بالبلاشون هي:* صيدلية دكتور إبراهيم مصطفى خضر
    📍 *العنوان:* بجوار مسجد تلعب
    📞 *للتواصل:* 01002707560
    ⏰ *الشيفت مستمر حتى الساعة 3 صباحاً*

    💊 *صيدليات الدكتورة إيمان عبد الفتاح*
    ----------------------------------------
    📍 *[الفرع الأول]:*
    • العنوان: أمام الدكتور جمال عبد الناصر.
    • ⏰ مواعيد العمل: من 9:00 صباحاً حتى 1:00 ليلاً.

    📍 *[الفرع الثاني]:*
    • العنوان: أمام مضيفة موسى العراقي.
    • ⏰ مواعيد العمل: من 8:00 صباحاً حتى 3:00 ليلاً.

    ----------------------------------------
    📞 *[للتواصل والاستشارة الطبية]:*
    • د/ كريم السحت: 01206097087
    • أ/ نبيل عبد السلام: 01062786766
    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

EMERGENCY_DOCTOR_TEXT = textwrap.dedent("""\
    🚨 *د/ عبد الله نبيل (طبيب طوارئ 24 ساعة)*

    • أرقام التواصل الفوري:
    📞 اتصال مباشر: 01130396842
    💬 واتساب: 01069431963""")

EVENING_AZKAR_TEXT = textwrap.dedent("""\
    أَعُوذُ بِاللهِ مِنْ الشَّيْطَانِ الرَّجِيمِ
    {اللّهُ لاَ إِلَـهَ إِلاَّ هُوَ الْحَيُّ الْقَيُّومُ لاَ تَأْخُذُهُ سِنَةٌ وَلاَ نَوْمٌ لَّهُ مَا فِي السَّمَاوَاتِ وَمَا فِي الأَرْضِ مَن ذَا الَّذِي يَشْفَعُ عِنْدَهُ إِلاَّ بِإِذْنِهِ يَعْلَمُ مَا بَيْنَ أَيْدِيهِمْ وَمَا خَلْفَهُمْ وَلاَ يُحِيطُونَ بِشَيْءٍ مِّنْ عِلْمِهِ إِلاَّ بِمَا شَاء وَسِعَ كُرْسِيُّهُ السَّمَاوَاتِ وَالأَرْضَ وَلاَ يَؤُودُهُ حِفْظُهُمَا وَهُوَ الْعَلِيُّ الْعَظِيمُ}""")

SELF_CARE_TEXT = textwrap.dedent("""\
    ✨ *صيدلية د/ نهال محمد - Self Care* ✨
    ----------------------------------------

    🛍️ *[أقسام ومنتجات العيادة والتجميل]:*

    • 🇰🇷 المنتجات الكورية (Korean Skincare):
      - متوفر أحدث المنتجات الكورية الأصلية للعناية بالبشرة والشعر.

    • 🧪 براندات العناية العالمية (Skin & Hair Care):
      - متوفر منتجات (La Roche-Posay - CeraVe - Vichy).
      - جميع منتجات العناية بالبشرة والشعر بأرخص الأسعار.

    • 💄 البرفيوم والميك أب (Perfumes & Makeup):
      - تشكيلة مميزة من البرفيوم (Outlet & Original).
      - متوفر جميع المستلزمات الخاصة بالميك أب عالي الجودة.

    ----------------------------------------
    📍 *[العنوان]:*
    • الموقف بجانب الحاج فهمي صاحب الأسمنت

    📞 *[أرقام التواصل والطلب]:*
    • الخط الأرضي: 2804454
    • رقم المحمول: 01024559627
    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

DELIVERY_TEXT = textwrap.dedent("""\
    📦 *دليل كباتن الشحن والتوصيل (دليفري)*
    ----------------------------------------

    • 🛵 الكابتن: علي شاكر (دليفري)
      📍 العنوان: عزبة الشيمي
      📞 للتواصل: 01018226726

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\\\_services\\\\_bot""")

ALWAFAA_LIBRARY_TEXT = textwrap.dedent("""\
    📚✨ *مكتبة الوفاء - للخدمات الطلابية والمكتبية المتكاملة*
    ----------------------------------------

    🎒 *[الكتب والمناهج الدراسية]:*
    • متوفر جميع الكتب والمذكرات لجميع المراحل التعليمية (الابتدائية، الإعدادية، الثانوية).
    • توفير ملخصات وكتب خارجية لأقوى المدرسين.

    🖨️ *[خدمات الطباعة والتصوير]:*
    • طباعة وتصوير أوراق ومذكرات بجودة عالية (أبيض وأسود / ألوان).
    • طباعة مباشرة لملفات الـ PDF والـ Word والـ Excel من الموبايل أو الفلاشة.
    • خدمات التغليف (سلك / حراري) وتكعيب المذكرات.

    💼 *[أدوات مكتبية ومدرسية]:*
    • تشكيلة متكاملة من الأدوات المكتبية، الكشاكيل، الأقلام، والوسائل التعليمية.
    • هدايا وأدوات مبتكرة للأطفال وطلاب المدارس.

    💻 *[الخدمات الإلكترونية والأبحاث]:*
    • عمل أبحاث لجميع المراحل الدراسية والجامعية وتنسيق ملفات تخرج وطباعتها.
    • تحميل ملازم ومذكرات المراجعات النهائية وضبط الهوامش قبل الطباعة.

    ----------------------------------------
    📍 *[العنوان]:*
    • شارع الموقف بجانب فهمي صاحب الأسمنت

    📞 *[للتواصل أو إرسال ملفات الطباعة]:*
    • رقم المحمول: 01099661248
    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

SAAD_OFFICE_TEXT = textwrap.dedent("""\
    ⚖️ *مكتب السعد للمحاسبة والمراجعة والخدمات الضريبية* ⚖️
    👨‍💼 *المحاسب/ سعد عبد الحميد سعد (محاسب ومراجع قانوني وخبير ضرائب)*
    ----------------------------------------

    ✨ *[خدماتنا المتكاملة]:*

    💼 *1. تأسيس الشركات والتراخيص:*
    • تأسيس الشركات بكافة أنواعها (داخل الهيئة العامة للاستثمار).
    • استخراج كافة التراخيص (رخص نشاط صناعية ومحلية).
    • استخراج بطاقات الاستيراد والتصدير، وبطاقات الاحتياجات.
    • فتح البطاقات الضريبية (ضرائب عامة وقيمة مضافة).

    📊 *2. المحاسبة والمراجعة والميزانيات:*
    • مراجعة الحسابات بدقة وإعداد الميزانيات العمومية.
    • إعداد دراسات الجدوى المعتمدة.
    • إصدار شهادات الدخل للتقديم على شقق الإسكان الاجتماعي.

    📝 *3. الضرائب والإقرارات والمنازعات:*
    • إعداد الإقرارات الضريبية بكافة أنواعها (دخل - كسب عمل - قيمة مضافة - مرتبات وأجور).
    • إدارة وحل المنازعات الضريبية بكافة مستوياتها.
    • حل مشاكل التصرفات العقارية ودفع الضرائب الخاصة بها.

    👥 *4. التأمينات والاستشارات:*
    • فتح الملفات التأمينية، والتأمين على العمال أو فصلهم.
    • تقديم الاستشارات القانونية والضريبية (داخل المكتب أو عبر الواتساب).

    ----------------------------------------
    📍 *[الفروع والعناوين]:*
    • 🏬 الفرع الأول: البلاشون - آخر شارع الوحدة المحلية - بلبيس - الشرقية.
    • 🏬 الفرع الثاني: بلبيس - أمام مأمورية الضرائب العامة - بجوار مسجد الطاهرات.

    📞 *[أرقام التواصل والاستفسار]:*
    • 🟢 01099609882 (اتصال أو واتساب)
    • 💬 01067743223 (واتساب فقط)
    • 📞 01119461438 (اتصال فقط)
    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

STAR_METAL_TEXT = textwrap.dedent("""\
    🪟 *معرض استار ميتال للألوميتال*

    🏢 *اسم المعرض:* معرض استار ميتال للألوميتال
    👤 *صاحب المعرض:* محمود عبدالعظيم سعد
    📞 *رقم التواصل:* 01014770786""")

TUKTUK_TEXT = textwrap.dedent("""\
    🛺 *دليل سائقي التوك توك بالبلاشون:*

    👤 *الطالب:* كريم عماد
    • السن: 19 سنة
    📞 *رقم التواصل:* 01090305795
""")

WORKERS_TEXT = textwrap.dedent("""\
    🛠️ *دليل الصنايعية بالبلاشون:*

    يرجى اختيار تخصص الصنايعي المطلوب من الأزرار بالأسفل لعرض الأسماء وأرقام التواصل.

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

WOOD_WORKERS_TEXT = textwrap.dedent("""\
    🪵 *[أعمال الخشب والموبيليات]*
    ----------------------------------------

    • 🛠️ محمد كمال شديد
      📞 رقم التواصل: 01002803443 - 0552803443

    • 🛠️ أيمن جمال
      📞 رقم التواصل: 01002263168

    • 🛠️ السيد موسى
      📞 رقم التواصل: 01094143194

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

PAINT_WORKERS_TEXT = textwrap.dedent("""\
    🎨 *[أعمال تشطيب الدهانات]*
    ----------------------------------------

    • 🎨 حسن القربي
      📞 رقم التواصل: 01022443024 - 01103624415

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

ELEC_WORKERS_TEXT = textwrap.dedent("""\
    ⚡ *[تأسيس وتشطيب الكهرباء]*
    ----------------------------------------

    • ⚡ مصطفى حسين
      📞 رقم التواصل: 01010718608

    • ⚡ محمد حسن فاضل
      📞 رقم التواصل: 01023367875

    • ⚡ عمرو القمحاوي
      📞 رقم التواصل: 01093100354

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

CERAMIC_WORKERS_TEXT = textwrap.dedent("""\
    🧱 *[تركيب السيراميك والبورسلين]*
    ----------------------------------------

    • 🧱 محمد قاسم
      📞 رقم التواصل: 01093000617

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

RESTAURANTS_TEXT = textwrap.dedent("""\
    🍔 *قائمة المطاعم بالبلاشون:*

    🍕 *مطعم أبو صلاح*
    ▪️ *نوع الأكل:* بيتزا - كريب - برجر
    📞 *رقم التواصل:* 01030666675

    🍔 *مطعم أبو حنين*
    📍 *العنوان:* حفنا
    ▪️ *نوع الأكل:* برجر - كريب
    📞 *رقم التواصل:* 01009751224

    🍟 *مطعم Viva Food*
    📍 *العنوان:* البلاشون
    ▪️ *نوع الأكل:* كريب
    📞 *رقم التواصل:* 01094318213

    🥩 *مطعم أحمد*
    📍 *العنوان:* البلاشون
    ▪️ *نوع الأكل:* مشويات - حواوشي
    📞 *أرقام التواصل:*
    📱 01006586263
    ☎️ 0552805570""")

PITCH_TEXT = textwrap.dedent("""\
    🏟️ *ملعب البلاشون الخماسي*

    👤 *المسؤول عن الحجز:* أبو كريم
    📞 *رقم التواصل:* 01020840251""")

CHARITY_TEXT = textwrap.dedent("""\
    🏛️ *الجمعية الشرعية بالبلاشون* 🏛️
    ----------------------------------------

    📞 *[أرقام التواصل والاستعلام]:*
    • ☎️ الخط الأرضي: 0552803988
    • 📱 أ/ طارق محمود: 01062154844

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

# ─── لوحات المفاتيح ──────────────────────────
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🚨 حالات عاجلة"],
        ["self care ✨", "🚕 مشاركة المشاوير والمواصلات"],
        ["💼 وظائف خالية", "🛠️ الخدمات"],
        ["🩺 دليل الأطباء والعيادات", "الجمعية الشرعية 🏛️"],
        ["🛺 اطلب توك توك", "💻 مصمم البوت"]
    ],
    resize_keyboard=True,
)

URGENT_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🤝 طلب مساعدة", "🚨 طبيب طوارئ (24 ساعة)"],
        ["🏥 صيدليات الطوارئ الليلة", "🩸 التبرع بالدم والطوارئ"],
        ["🔙 رجوع للقائمة الرئيسية"]
    ],
    resize_keyboard=True,
)

SERVICES_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🏟️ حجز ملعب البلاشون", "🍔 مطاعم"],
        ["دليل الصنايعية 🛠️", "📦 خدمات الشحن والتوصيل (الطيارين)"],
        ["🪟 معرض استار ميتال للألوميتال", "مكتبة الوفاء 📚"],
        ["مكتب السعد للمحاسبة والمراجعة ⚖️"],
        ["🔙 رجوع للقائمة الرئيسية"]
    ],
    resize_keyboard=True,
)

# ─── Logging ────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════
#  قاعدة البيانات
# ════════════════════════════════════════════
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()

def register_user(user_id: int):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def get_all_user_ids() -> list:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT user_id FROM users").fetchall()
    conn.close()
    return [r[0] for r in rows]

def get_user_count() -> int:
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count

# ════════════════════════════════════════════
#  /start
# ════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    register_user(user_id)
    await update.message.reply_text(
        "💡 مرحباً بك في منصة خدمات البلاشون الذكية.\nاختر الخدمة المطلوبة من الأزرار بالأسفل:",
        reply_markup=MAIN_KEYBOARD,
    )
    return ConversationHandler.END

# ════════════════════════════════════════════
#  معالج اختيارات القوائم
# ════════════════════════════════════════════
async def handle_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text
    context.user_data["choice"] = text

    if "رجوع" in text:
        await update.message.reply_text("القائمة الرئيسية:", reply_markup=MAIN_KEYBOARD)
        return ConversationHandler.END

    if "الخدمات" in text and not "الشحن" in text:
        await update.message.reply_text("اختر الخدمة المطلوبة من القائمة:", reply_markup=SERVICES_KEYBOARD)
        return ConversationHandler.END

    if "حالات عاجلة" in text:
        await update.message.reply_text("اختر الخدمة المطلوبة من القائمة:", reply_markup=URGENT_KEYBOARD)
        return ConversationHandler.END

    if "دليل الأطباء" in text:
        doctors_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("طب وجراحة الفم والأسنان 🦷", callback_data="doc_dentist")],
            [InlineKeyboardButton("العلاج الطبيعي والتغذية 🦾", callback_data="doc_physio")],
            [InlineKeyboardButton("الباطنة والقلب والصدر 🫁", callback_data="doc_internal")],
            [InlineKeyboardButton("أمراض النساء والتوليد 🤰", callback_data="doc_obgyn")],
            [InlineKeyboardButton("الأنف والأذن والحنجرة 👂", callback_data="doc_ent")],
            [InlineKeyboardButton("مخ وأعصاب وجراحة عامة 🧠", callback_data="doc_neuro_surgery")],
            [InlineKeyboardButton("المسالك البولية والجلدية 🩸", callback_data="doc_uro_derma")],
            [InlineKeyboardButton("مراكز الأشعة والتحاليل 🔬", callback_data="doc_xray_labs")],
            [InlineKeyboardButton("طب الأطفال وحديثي الولادة 👶", callback_data="doc_pediatrics")],
            [InlineKeyboardButton("عيادات الفتح التخصصية 🏛️", callback_data="alfath_clinics")]
        ])
        await update.message.reply_text(DOCTORS_TEXT, parse_mode="Markdown", reply_markup=doctors_markup, disable_web_page_preview=True)
        return ConversationHandler.END

    if "مصمم البوت" in text:
        developer_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💻 تواصل مع مصمم البوت (واتساب)", url="https://wa.me/201020549760")]
        ])
        await update.message.reply_text(DEVELOPER_TEXT, parse_mode="Markdown", reply_markup=developer_markup)
        return ConversationHandler.END
        
    if "توك توك" in text:
        tuktuk_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💬 تواصل مع كريم (واتساب)", url="https://wa.me/201090305795")]
        ])
        await update.message.reply_text(TUKTUK_TEXT, parse_mode="Markdown", reply_markup=tuktuk_markup)
        return ConversationHandler.END
        
    elif "مطاعم" in text:
        restaurants_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍕 أبو صلاح", url="https://wa.me/201030666675"),
             InlineKeyboardButton("🍔 أبو حنين", url="https://wa.me/201009751224")],
            [InlineKeyboardButton("🍟 Viva Food", url="https://wa.me/201094318213"),
             InlineKeyboardButton("🥩 مطعم أحمد", url="https://wa.me/201006586263")]
        ])
        await update.message.reply_text(RESTAURANTS_TEXT, parse_mode="Markdown", reply_markup=restaurants_markup)
        return ConversationHandler.END

    elif "ملعب البلاشون" in text or "حجز ملعب" in text:
        contact_keyboard = [[InlineKeyboardButton("تواصل للحجز عبر واتساب 💬", url="https://wa.me/201020840251")]]
        contact_markup = InlineKeyboardMarkup(contact_keyboard)
        await update.message.reply_text(PITCH_TEXT, parse_mode="Markdown", reply_markup=contact_markup)
        return ConversationHandler.END

    elif "استار ميتال" in text:
        contact_keyboard = [[InlineKeyboardButton("تواصل عبر واتساب 💬", url="https://wa.me/201014770786")]]
        contact_markup = InlineKeyboardMarkup(contact_keyboard)
        await update.message.reply_text(STAR_METAL_TEXT, parse_mode="Markdown", reply_markup=contact_markup)
        return ConversationHandler.END

    elif "مكتبة الوفاء" in text:
        await update.message.reply_text(ALWAFAA_LIBRARY_TEXT, parse_mode="Markdown")
        return ConversationHandler.END

    elif "مكتب السعد" in text or "محاسبة" in text:
        await update.message.reply_text(SAAD_OFFICE_TEXT, parse_mode="Markdown")
        return ConversationHandler.END

    elif "طوارئ الليلة" in text or "صيدليات" in text:
        contact_keyboard = [
            [InlineKeyboardButton("تواصل مع صيدلية د. إبراهيم 💬", url="https://wa.me/201002707560")],
            [InlineKeyboardButton("د. كريم السحت (واتساب) 💬", url="https://wa.me/201206097087")],
            [InlineKeyboardButton("أ. نبيل عبد السلام (واتساب) 💬", url="https://wa.me/201062786766")]
        ]
        contact_markup = InlineKeyboardMarkup(contact_keyboard)
        await update.message.reply_text(EMERGENCY_PHARMACY_INFO, parse_mode="Markdown", reply_markup=contact_markup)
        return ConversationHandler.END

    elif "طبيب طوارئ" in text:
        contact_keyboard = [[InlineKeyboardButton("💬 تواصل طوارئ (واتساب)", url="https://wa.me/201069431963")]]
        contact_markup = InlineKeyboardMarkup(contact_keyboard)
        await update.message.reply_text(EMERGENCY_DOCTOR_TEXT, parse_mode="Markdown", reply_markup=contact_markup)
        return ConversationHandler.END
        
    elif "الصنايعية" in text:
        workers_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("أعمال الخشب والموبيليات 🪵", callback_data="work_wood")],
            [InlineKeyboardButton("أعمال تشطيب الدهانات 🎨", callback_data="work_paint")],
            [InlineKeyboardButton("تأسيس وتشطيب الكهرباء ⚡", callback_data="work_elec")],
            [InlineKeyboardButton("تركيب السيراميك والبورسلين 🧱", callback_data="work_ceramic")]
        ])
        await update.message.reply_text(WORKERS_TEXT, parse_mode="Markdown", reply_markup=workers_markup, disable_web_page_preview=True)
        return ConversationHandler.END

    elif "الشحن والتوصيل" in text:
        await update.message.reply_text(DELIVERY_TEXT, parse_mode="Markdown")
        return ConversationHandler.END

    # --- الردود التي تتطلب إدخال بيانات ---
    elif "التبرع بالدم" in text:
        await update.message.reply_text("🩸 اكتب تفاصيل الحالة الحرجة فوراً (مثال: الفصيلة، المستشفى، رقم التواصل):")
        return WAITING_FOR_REQUEST_DETAILS

    elif "وظائف" in text:
        await update.message.reply_text("💼 اكتب تفاصيل الوظيفة (التخصص، المرتب، رقم التواصل):")
        return WAITING_FOR_REQUEST_DETAILS

    elif "طلب مساعدة" in text:
        await update.message.reply_text("🚨 اكتب تفاصيل طلب المساعدة أو الاستغاثة ورقم التواصل:")
        return WAITING_FOR_REQUEST_DETAILS

    elif "شكاوى" in text or "مقترح" in text:
        await update.message.reply_text("📝 اكتب تفاصيل شكواك أو مقترحك وسيتم إرسالها للإدارة:")
        return WAITING_FOR_REQUEST_DETAILS

    elif "مفقودات" in text:
        await update.message.reply_text("📢 اكتب تفاصيل المفقودات أو الأمانات مع رقم للتواصل:")
        return WAITING_FOR_REQUEST_DETAILS

    elif "self care" in text.lower() or "self care ✨" in text:
        await update.message.reply_text(SELF_CARE_TEXT, parse_mode="Markdown")
        return ConversationHandler.END
        
    elif "مشاوير" in text or "مواصلات" in text:
        await update.message.reply_text("🚕 اكتب تفاصيل مشوارك (سواق ولا راكب، والميعاد):")
        return WAITING_FOR_REQUEST_DETAILS

    elif "الجمعية الشرعية" in text:
        await update.message.reply_text(CHARITY_TEXT, parse_mode="Markdown")
        return ConversationHandler.END

    else:
        # نص غير معروف
        await update.message.reply_text("اختر خدمة من القائمة 👇", reply_markup=MAIN_KEYBOARD)
        return ConversationHandler.END

# ════════════════════════════════════════════
#  معالج النص المُدخَل (نظام المراجعة الشامل)
# ════════════════════════════════════════════
async def process_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text or update.message.caption or ""
    photo_file_id = update.message.photo[-1].file_id if update.message.photo else None
    
    if user_text in ["🔙 رجوع للقائمة الرئيسية"]:
        await update.message.reply_text("القائمة الرئيسية:", reply_markup=MAIN_KEYBOARD)
        context.user_data.clear()
        return ConversationHandler.END

    KNOWN = ["🚨 حالات عاجلة", "🏥 صيدليات الطوارئ الليلة", "🩸 التبرع بالدم والطوارئ",
             "🤝 طلب مساعدة", "🚨 طبيب طوارئ (24 ساعة)", "self care ✨", 
             "🚕 مشاركة المشاوير والمواصلات", "💼 وظائف خالية", "🛠️ الخدمات", 
             "🩺 دليل الأطباء والعيادات", "🪟 معرض استار ميتال للألوميتال",
             "📦 خدمات الشحن والتوصيل (الطيارين)", "مكتبة الوفاء 📚", "دليل الصنايعية 🛠️",
             "مكتب السعد للمحاسبة والمراجعة ⚖️", "مكتب السعد", "الجمعية الشرعية 🏛️",
             "🛺 اطلب توك توك", "💻 مصمم البوت", "🔙 رجوع للقائمة الرئيسية", 
             "🚕 مشاركة المشاوير", "🛠 الخدمات", "🍔 مطاعم", "🏟️ حجز ملعب البلاشون",
             "مكتبة الوفاء", "دليل الصنايعية", "الجمعية الشرعية", "شكاوى", "مفقودات"]
             
    if user_text in KNOWN:
        context.user_data.clear()
        return await handle_choice(update, context)

    choice    = context.user_data.get("choice", "")
    user      = update.effective_user
    username  = f"@{user.username}" if user.username else str(user.id)

    try:
        # نظام طلبات النشر الموحد في القناة
        action_code = ""
        action_name = ""
        
        if "طلب مساعدة" in choice:
            action_code = "sos"
            action_name = "طلب مساعدة / استغاثة"
        elif "شكاوى" in choice or "مقترح" in choice:
            action_code = "complaint"
            action_name = "شكوى / مقترح"
        elif "مفقودات" in choice:
            action_code = "lost"
            action_name = "مفقودات وأمانات"
        elif "وظائف" in choice:
            action_code = "job"
            action_name = "وظيفة"
        elif "مشاركة المشاوير" in choice or "المواصلات" in choice:
            action_code = "ride"
            action_name = "مواصلة"
        elif "التبرع بالدم" in choice:
            action_code = "blood"
            action_name = "تبرع بالدم"
            
        if action_code:
            markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ موافقة ونشر", callback_data=f"app_{action_code}_{user.id}"),
                InlineKeyboardButton("❌ رفض الطلب", callback_data=f"rej_{action_code}_{user.id}")
            ]])
            req = f"🚨 {action_name} جديد\nمن: {username}\n\nالتفاصيل:\n{user_text}"
            
            for admin_id in [5481609181, 1049124970]:
                try:
                    if photo_file_id: await context.bot.send_photo(chat_id=admin_id, photo=photo_file_id, caption=req, reply_markup=markup)
                    else: await context.bot.send_message(chat_id=admin_id, text=req, reply_markup=markup)
                except Exception as e:
                    print(f"Error sending to admin {admin_id}: {e}")
                    if admin_id == 1049124970:
                        try:
                            await context.bot.send_message(
                                chat_id=5481609181,
                                text=f"⚠️ خطأ في الإرسال للآدمن الثاني:\n{str(e)}"
                            )
                        except Exception:
                            pass
            
            await update.message.reply_text("تم إرسال طلبك بنجاح إلى الإدارة وسنتواصل معك قريباً. ✅", reply_markup=MAIN_KEYBOARD)
        else:
            await update.message.reply_text("اختر خدمة من القائمة 👇", reply_markup=MAIN_KEYBOARD)

    except Exception as e:
        logger.error("process_input error: %s", e)
        await update.message.reply_text("❌ حدث خطأ.", reply_markup=MAIN_KEYBOARD)

    context.user_data.clear()
    return ConversationHandler.END


# ════════════════════════════════════════════
#  معالج الأزرار الإنلاين العالمية للإدارة
# ════════════════════════════════════════════
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "alfath_clinics":
        await query.message.reply_text(ALFATH_CLINICS_TEXT, parse_mode="Markdown", disable_web_page_preview=True)
        return
    elif data == "doc_dentist":
        await query.message.reply_text(DENTISTRY_TEXT, parse_mode="Markdown", disable_web_page_preview=True)
        return
    elif data == "doc_physio":
        await query.message.reply_text(PHYSIO_NUTRITION_TEXT, parse_mode="Markdown", disable_web_page_preview=True)
        return
    elif data == "doc_internal":
        await query.message.reply_text(INTERNAL_CARDIO_CHEST_TEXT, parse_mode="Markdown", disable_web_page_preview=True)
        return
    elif data == "doc_obgyn":
        await query.message.reply_text(OBSTETRICS_GYNECOLOGY_TEXT, parse_mode="Markdown", disable_web_page_preview=True)
        return
    elif data == "doc_ent":
        await query.message.reply_text(ENT_TEXT, parse_mode="Markdown", disable_web_page_preview=True)
        return
    elif data == "doc_neuro_surgery":
        await query.message.reply_text(NEURO_SURGERY_TEXT, parse_mode="Markdown", disable_web_page_preview=True)
        return
    elif data == "doc_uro_derma":
        await query.message.reply_text(UROLOGY_DERMA_TEXT, parse_mode="Markdown", disable_web_page_preview=True)
        return
    elif data == "doc_xray_labs":
        await query.message.reply_text(XRAY_LABS_TEXT, parse_mode="Markdown", disable_web_page_preview=True)
        return
    elif data == "work_wood":
        await query.message.reply_text(WOOD_WORKERS_TEXT, parse_mode="Markdown", disable_web_page_preview=True)
        return
    elif data == "work_paint":
        await query.message.reply_text(PAINT_WORKERS_TEXT, parse_mode="Markdown", disable_web_page_preview=True)
        return
    elif data == "work_elec":
        await query.message.reply_text(ELEC_WORKERS_TEXT, parse_mode="Markdown", disable_web_page_preview=True)
        return
    elif data == "work_ceramic":
        await query.message.reply_text(CERAMIC_WORKERS_TEXT, parse_mode="Markdown", disable_web_page_preview=True)
        return

    admin_msg = query.message
    admin_msg_text = admin_msg.text or admin_msg.caption or ""
    photo_file_id = admin_msg.photo[-1].file_id if admin_msg.photo else None
    
    # استخراج اسم المشرف الذي قام بالعملية
    admin_user = update.effective_user.username or update.effective_user.first_name
    
    parts = admin_msg_text.split("التفاصيل:\n", 1)
    details = parts[1].strip() if len(parts) > 1 else "تفاصيل غير معروفة"

    # --- الرفض الموحد ---
    if data.startswith("rej_"):
        user_id = data.split("_")[2]
        try:
            await context.bot.send_message(chat_id=user_id, text="❌ نعتذر، تم رفض طلب النشر من قبل الإدارة.")
            if photo_file_id: await query.edit_message_caption(caption=f"{admin_msg_text}\n\n❌ **تم الرفض بواسطة {admin_user}.**", parse_mode="Markdown")
            else: await query.edit_message_text(text=f"{admin_msg_text}\n\n❌ **تم الرفض بواسطة {admin_user}.**", parse_mode="Markdown")
        except: pass
        return

    # --- الموافقة والنشر الموحد ---
    if data.startswith("app_"):
        action = data.split("_")[1]
        user_id = data.split("_")[2]
        contact_url = f"tg://user?id={user_id}"

        markup = None
        if action == "sos":
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("تواصل مع الحالة 🚨", url=contact_url)]])
            text_to_send = f"🚨 *استغاثة عاجلة*\n\n{details}\n\n🤖 للتواصل عبر البوت: t.me/AlBalashon\\_services\\_bot"
        elif action == "blood":
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("تواصل مع حالة الطوارئ 🩸", url=contact_url)]])
            text_to_send = f"🚨 *نداء طوارئ عاجل - تبرع بالدم* 🚨\n\n{details}\n\n🤖 للتواصل عبر البوت: t.me/AlBalashon\\_services\\_bot"
        elif action == "ride":
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("تواصل مع صاحب المشوار 💬", url=contact_url)]])
            text_to_send = f"🚕 *إعلان مواصلة فوري*\n\n{details}\n\n🤖 للتواصل عبر البوت: t.me/AlBalashon\\_services\\_bot"
        elif action == "lost":
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("تواصل للإبلاغ 💬", url=contact_url)]])
            text_to_send = f"📢 *مفقودات وأمانات*\n\n{details}\n\n🤖 للتواصل عبر البوت: t.me/AlBalashon\\_services\\_bot"
        elif action == "job":
            text_to_send = f"💼 *وظائف خالية*\n\n{details}\n\n🤖 للتواصل عبر البوت: t.me/AlBalashon\\_services\\_bot"
        else:
            return

        try:
            if photo_file_id:
                if markup: await context.bot.send_photo(CHANNEL_ID, photo_file_id, caption=text_to_send, parse_mode="Markdown", reply_markup=markup)
                else: await context.bot.send_photo(CHANNEL_ID, photo_file_id, caption=text_to_send, parse_mode="Markdown")
            else:
                if markup: await context.bot.send_message(CHANNEL_ID, text=text_to_send, parse_mode="Markdown", reply_markup=markup)
                else: await context.bot.send_message(CHANNEL_ID, text=text_to_send, parse_mode="Markdown")
            
            await context.bot.send_message(chat_id=user_id, text="✅ تمت الموافقة على طلبك ونشره في القناة بنجاح!")
            if photo_file_id: await query.edit_message_caption(caption=f"{admin_msg_text}\n\n✅ **نُشر بواسطة {admin_user}.**", parse_mode="Markdown")
            else: await query.edit_message_text(text=f"{admin_msg_text}\n\n✅ **نُشر بواسطة {admin_user}.**", parse_mode="Markdown")
        except Exception as e:
            logger.error(e)
            if photo_file_id: await query.edit_message_caption(caption=f"{admin_msg_text}\n\n❌ **حدث خطأ أثناء النشر.**", parse_mode="Markdown")
            else: await query.edit_message_text(text=f"{admin_msg_text}\n\n❌ **حدث خطأ أثناء النشر.**", parse_mode="Markdown")

# ════════════════════════════════════════════
#  أوامر الأدمن والأذكار المجدولة
# ════════════════════════════════════════════
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMINS: return
    count = get_user_count()
    await update.message.reply_text(f"📊 عدد المشتركين في البوت حالياً: {count} شخص.")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMINS: return
    if not context.args: return await update.message.reply_text("⚠️ اكتب الرسالة بعد الأمر:\n/broadcast نص الرسالة")
    
    msg = " ".join(context.args)
    users = get_all_user_ids()
    sent = failed = 0
    status = await update.message.reply_text(f"📤 جاري الإرسال إلى {len(users)} مستخدم...")
    
    for uid in users:
        try:
            await context.bot.send_message(uid, f"📢 *تنويه عام:*\n\n{msg}", parse_mode="Markdown")
            sent += 1
        except Exception: failed += 1
        await asyncio.sleep(0.05)
        
    await status.edit_text(f"✅ أُرسلت لـ {sent} مستخدم.\n❌ فشل لـ {failed} مستخدم.")

async def send_daily_azkar(context: ContextTypes.DEFAULT_TYPE):
    now_date_str = str(datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date())
    last_morning = context.bot_data.get("last_morning_date")
    if last_morning == now_date_str:
        return
    context.bot_data["last_morning_date"] = now_date_str

    azkar_text = (
        "☀️ *أذكار الصباح | بنية فتح الأبواب والبركة* ☀️\n\n"
        "- سبحان الله\n- الحمد لله\n- لا إله إلا الله\n"
        "- صلى الله على محمد، صلى الله عليه وسلم (صلِّ على رسول الله)"
    )
    try: await context.bot.send_message(CHANNEL_ID, azkar_text, parse_mode="Markdown")
    except Exception: pass

async def send_daily_evening_azkar(context: ContextTypes.DEFAULT_TYPE):
    now_date_str = str(datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date())
    last_evening = context.bot_data.get("last_evening_date")
    if last_evening == now_date_str:
        return
    context.bot_data["last_evening_date"] = now_date_str

    try: await context.bot.send_message(CHANNEL_ID, f"🌆 *أذكار المساء*\n\n{EVENING_AZKAR_TEXT}", parse_mode="Markdown")
    except Exception: pass

# ════════════════════════════════════════════
#  خادم وهمي لمنع Railway من إيقاف البوت
# ════════════════════════════════════════════
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    try:
        server = HTTPServer(("0.0.0.0", port), DummyHandler)
        server.serve_forever()
    except Exception as e:
        logger.error(f"Dummy server error: {e}")

# ════════════════════════════════════════════
#  الإعداد والتشغيل
# ════════════════════════════════════════════
def main():
    # بدء الخادم الوهمي في خلفية التطبيق لإرضاء Railway
    threading.Thread(target=run_dummy_server, daemon=True).start()

    init_db()
    persistence = PicklePersistence(filepath=PERSISTENCE_PATH)
    app = Application.builder().token(BOT_TOKEN).persistence(persistence).build()
    
    tz = datetime.timezone(datetime.timedelta(hours=3))
    t_morning = datetime.time(hour=6, minute=0, tzinfo=tz)
    app.job_queue.run_daily(send_daily_azkar, time=t_morning)
    
    t_evening = datetime.time(hour=20, minute=0, tzinfo=tz)
    app.job_queue.run_daily(send_daily_evening_azkar, time=t_evening)

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_choice),
        ],
        states={
            WAITING_FOR_REQUEST_DETAILS: [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, process_input)],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=False,
        name="main_conversation",
        persistent=True
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("broadcast", broadcast))

    logger.info("🚀 AlBalashon Bot started. Send /start to begin.")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()