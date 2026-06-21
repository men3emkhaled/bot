import logging
import sqlite3
import psycopg2
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
ADMIN_ID_3 = int(os.getenv("ADMIN_ID_3", "7986800995"))
ADMINS     = [ADMIN_ID, ADMIN_ID_2, ADMIN_ID_3]  # قائمة جميع الآدمنز لتوجيه الطلبات
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
    • 👨‍⚕️ د/ إبراهيم عاطف (طوارئ 24 ساعة)
      📞 رقم الهاتف: 01062925584
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

    • 👨‍⚕️ د/ عبدالرحمن خالد عبدالرحمن الزفتاوي
      📝 أخصائي العلاج الطبيعي، التغذية العلاجية، والحجامة الطبية
      📍 العنوان: مركز د/ أمل - بجوار مكتبة وحيد.
      📅 المواعيد: السبت، الإثنين، والأربعاء.
      📞 رقم التواصل: 01091590054

    • 👨‍⚕️ د/ أحمد صقر (أخصائي العلاج الطبيعي، التغذية العلاجية، والحجامة الطبية)
      📍 العنوان: البلاشون - مركز بلبيس.
      📞 رقم التواصل: 01064348233

    • 👨‍⚕️ د/ أحمد سامي عزام (العلاج الطبيعي، الجلسات المنزلية، والحجامة)
      📝 التخصص: حالات الجراحة، الكسور، الجلطات، والمسنين.
      📞 أرقام التواصل: 01050915289 - 01113997889

    • 👨‍⚕️ د/ يوسف محمد محمد
      ✨ أخصائي العلاج الطبيعي
      📝 التخصص: جلسات الحجامة المنزلية - التغذية العلاجية - والإصابات والتأهيل
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
      📅 المواعيد: السبت والاتنين والأربع والجمعة من 6:00 مساءً لـ 11:00 مساءً.
      📞 0552802394 - 01008499653

    • 👨‍⚕️ د/ عبد الرحمن (الجلدية)
      📍 العنوان: عمارة الأطباء.

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

XRAY_LABS_TEXT = textwrap.dedent("""\
    🔬 *[مراكز الأشعة والتحاليل]*
    ----------------------------------------

    • 🏢 مركز أ.د/ محمد عبد الخالق باشا للأشعة التشخيصية
      📍 العنوان: البلاشون - بجوار بنزينة رمضان عبد الكريم.
      📅 المواعيد:
      - يومياً: من 2:30 ظهراً إلى 10:30 مساءً.
      - الجمعة: من 3:00 عصراً إلى 10:00 مساءً.
      📞 أرقام التواصل: 0552801774 - 01025071770 - 01289740450

    ----------------------------------------
    🧪 *[معامل التحاليل الطبية]*
    ----------------------------------------

    • معمل الفاروق للتحاليل الطبية
      📍 العنوان: خلف صهاريج المياه - شارع مقلة الفخراني.
      📞 رقم التواصل: 01226215599 - 01011145856 - 01550393362
      📝 خدمة طوارئ 24 ساعة وسحب عينات من المنزل.

    • معمل الايمان للتحاليل الطبية
      📍 العنوان: عمارة مدني امام مكتبة وحيد.
      📞 رقم التواصل: 01555772043 - 01099405953 - 0552803579
      📝 خدمة سحب العينات من المنزل.

    • معمل رسالة للتحاليل الطبية
      💼 الإدارة: دكتور غنيمي عزام
      📍 العنوان: بجوار مكتبة معوض.
      📞 رقم التواصل: 01020408604 - 01124373151

    • معمل المصطفى للتحاليل الطبية
      📍 العنوان: منزل م. أيمن جلال حمرة بجوار المسجد الكبير.
      📞 رقم التواصل: 01012436822

    • معمل الدكتور محمد الخولي للتحاليل الطبية
      📞 للتواصل: 01001095354

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")
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
    💻 *مصمم ومطور البوت:*
    ----------------------------------------
    💻 *[الجانب التقني والبرمجي]:*
    • التخصص: Front-End Developer
    • الخدمات المتاحة لأصحاب الأعمال والمشاريع:
      - تصميم وتطوير مواقع احترافية للبرندات والشركات.
      - بناء أنظمة كاشير وإدارة ومبيعات متكاملة (ERP Systems).
      - تطوير سيستم كامل لإدارة الشركات التدريبية والأكاديميات.
      - تصميم وتطوير بوتات تيليجرام احترافية.

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
    🚨 *د/ إبراهيم عاطف (طبيب طوارئ 24 ساعة)*
 
    📞 رقم الهاتف: 01062925584""")

EVENING_AZKAR_TEXT = textwrap.dedent("""\
    أَعُوذُ بِاللهِ مِنْ الشَّيْطَانِ الرَّجِيمِ
    {اللّهُ لاَ إِلَـهَ إِلاَّ هُوَ الْحَيُّ الْقَيُّومُ لاَ تَأْخُذُهُ سِنَةٌ وَلاَ نَوْمٌ لَّهُ مَا فِي السَّمَاوَاتِ وَمَا فِي الأَرْضِ مَن ذَا الَّذِي يَشْفَعُ عِنْدَهُ إِلاَّ بِإِذْنِهِ يَعْلَمُ مَا بَيْنَ أَيْدِيهِمْ وَمَا خَلْفَهُمْ وَلاَ يُحِيطُونَ بِشَيْءٍ مِّنْ عِلْمِهِ إِلاَّ بِمَا شَاء وَسِعَ كُرْسِيُّهُ السَّمَاوَاتِ وَالأَرْضَ وَلاَ يَؤُودُهُ حِفْظُهُمَا وَهُوَ الْعَلِيُّ الْعَظِيمُ}

    ┈┈┈┈┈┈┈┈┈┈┈┈
    🔹 *[مرة واحدة]:*
    أمسينا على فطرةِ الإسلام، وعلى كلمةِ الإخلاص، وعلى دين نبينا محمدٍ صلى الله عليه وسلم، وعلى ملة أبينا إبراهيم حنيفاً مسلماً وما كان من المشركين.
    _(رواه أحمد)_""")

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

LESSONS_TEXT = textwrap.dedent("""\
    📚 *دليل الدروس والمدرسين بالبلاشون:*

    يرجى اختيار القسم المطلوب من الأسفل لعرض المدرسين وأرقام التواصل:
""")

WORKERS_TEXT = textwrap.dedent("""\
    🛠️ *دليل الصنايعية بالبلاشون:*

    يرجى اختيار تخصص الصنايعي المطلوب من الأزرار بالأسفل لعرض الأسماء وأرقام التواصل.

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

WOOD_WORKERS_TEXT = textwrap.dedent("""\
    🪵 *[نجار]*
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
    🎨 *[نقاش]*
    ----------------------------------------

    • 🎨 حسن القربي
      📞 رقم التواصل: 01022443024 - 01103624415

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

ELEC_WORKERS_TEXT = textwrap.dedent("""\
    ⚡ *[كهربائي]*
    ----------------------------------------

    • ⚡ عبدالله ممدوح
      📞 رقم التواصل: 01272807797

    • ⚡ مصطفى حسين
      📞 رقم التواصل: 01010718608

    • ⚡ محمد حسن فاضل
      📞 رقم التواصل: 01023367875

    • ⚡ عمرو القمحاوي
      📞 رقم التواصل: 01093100354

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

CERAMIC_WORKERS_TEXT = textwrap.dedent("""\
    🧱 *[مبلط]*
    ----------------------------------------

    • 🧱 محمد قاسم
      📞 رقم التواصل: 01093000617

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

WASHING_MACHINE_WORKERS_TEXT = textwrap.dedent("""\
    🧼 *[صيانة غسالات]*
    ----------------------------------------

    • 🛠️ وجيه علي منصور
      📞 رقم التواصل: 01024085243

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

EMERGENCY_CARS_TEXT = textwrap.dedent("""\
    🚗 *[سيارات الطوارئ والمشاوير بالبلاشون]*
    ----------------------------------------

    • 🚗 الكابتن: حسن سامي (من البلاشون)
      ⚙️ السيارة: ملاكي ميتسوبيشي لانسر
      📍 العنوان: البلاشون - شارع الموقف
      📞 رقم التواصل: 01062398885
      ℹ️ الخدمة: مشاوير خاصة وحالات طارئة (24 ساعة)

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

BRANDS_TEXT = textwrap.dedent("""\
    🏷️ *دليل البراندات بالبلاشون:*

    تصفح البراندات المتاحة من الأزرار بالأسفل، أو أضف البراند الخاص بك مجاناً!

    ----------------------------------------
    🤖 للبوت والخدمات: t.me/AlBalashon\\_services\\_bot""")

# ─── لوحات المفاتيح ──────────────────────────
MAIN_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🚨 حالات عاجلة", "إضافة شغلك ➕"],
        ["self care ✨", "🚕 مشاركة المشاوير والمواصلات"],
        ["💼 وظائف خالية", "🛠️ الخدمات"],
        ["🩺 دليل الأطباء والعيادات", "الجمعية الشرعية 🏛️"],
        ["الدروس 📚", "💻 مصمم البوت"]
    ],
    resize_keyboard=True,
)

URGENT_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["طلب استغاثة", "🚨 طبيب طوارئ (24 ساعة)"],
        ["🏥 صيدليات الطوارئ الليلة", "🩸 التبرع بالدم والطوارئ"],
        ["🚗 سيارات الطوارئ والمشاوير", "🔙 رجوع للقائمة الرئيسية"]
    ],
    resize_keyboard=True,
)

SERVICES_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["🤝 طلب مساعدة", "🏟️ حجز ملعب البلاشون"],
        ["🍔 مطاعم", "دليل الصنايعية 🛠️"],
        ["📦 خدمات الشحن والتوصيل (الطيارين)", "🪟 معرض استار ميتال للألوميتال"],
        ["مكتبة الوفاء 📚", "مكتب السعد للمحاسبة والمراجعة ⚖️"],
        ["براند 🏷️", "🔙 رجوع للقائمة الرئيسية"]
    ],
    resize_keyboard=True,
)

BRANDS_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["self care ✨"],
        ["🔙 رجوع للخدمات"]
    ],
    resize_keyboard=True,
)

ADD_WORK_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["إضافة طبيب/عيادة 🩺", "إضافة صنايعي 🛠️"],
        ["إضافة براند 🏷️", "إضافة مطعم 🍔"],
        ["إضافة كابتن توصيل 🛵", "إضافة مدرس 📚"],
        ["🔙 رجوع للقائمة الرئيسية"]
    ],
    resize_keyboard=True,
)

ADD_WORKER_CRAFT_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["نجار 🪵", "نقاش 🎨"],
        ["كهربائي ⚡", "مبلط 🧱"],
        ["صيانة غسالات 🧼"],
        ["🔙 رجوع للقائمة الرئيسية"]
    ],
    resize_keyboard=True,
)

ADD_DOCTOR_SPECIALTY_KEYBOARD = ReplyKeyboardMarkup(
    [
        ["طب وجراحة الفم والأسنان 🦷", "العلاج الطبيعي والتغذية 🦾"],
        ["الباطنة والقلب والصدر 🫁", "أمراض النساء والتوليد 🤰"],
        ["الأنف والأذن والحنجرة 👂", "مخ وأعصاب وجراحة عامة 🧠"],
        ["المسالك البولية والجلدية 🩸", "مراكز الأشعة والتحاليل 🔬"],
        ["طب الأطفال وحديثي الولادة 👶", "عيادات الفتح التخصصية 🏛️"],
        ["🔙 رجوع للقائمة الرئيسية"]
    ],
    resize_keyboard=True,
)

def get_db_additions(category: str) -> str:
    try:
        rows, _ = fetch_query("SELECT details FROM department_additions WHERE category = %s", (category,))
        if not rows:
            return ""
        extra_text = ""
        for row in rows:
            raw = row[0] or ""
            clean_lines = []
            for line in raw.splitlines():
                stripped = line.strip().replace("-", "").replace("_", "").replace("—", "").replace("═", "").replace("━", "").replace("=", "").strip()
                if stripped:
                    clean_lines.append(line.strip())
            clean_text = escape_markdown("\n".join(clean_lines))
            extra_text += f"\n{clean_text}\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        return extra_text
    except Exception as e:
        logger.error(f"Error reading additions from db: {e}")
        return ""

DOCTORS_MARKUP = InlineKeyboardMarkup([
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

WORKERS_MARKUP = InlineKeyboardMarkup([
    [InlineKeyboardButton("نجار 🪵", callback_data="work_wood")],
    [InlineKeyboardButton("نقاش 🎨", callback_data="work_paint")],
    [InlineKeyboardButton("كهربائي ⚡", callback_data="work_elec")],
    [InlineKeyboardButton("مبلط 🧱", callback_data="work_ceramic")],
    [InlineKeyboardButton("صيانة غسالات 🧼", callback_data="work_washing_machine")]
])

BACK_DOCTORS_BTN = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔙 رجوع للتخصصات", callback_data="back_doctors")]
])

BACK_WORKERS_BTN = InlineKeyboardMarkup([
    [InlineKeyboardButton("🔙 رجوع للصنايعية", callback_data="back_workers")]
])

# (تم إزالتها واستبدالها بلوحة أزرار الرد العادية)

DOC_TEXT_MAP = {
    "doc_dentist":       DENTISTRY_TEXT,
    "doc_physio":        PHYSIO_NUTRITION_TEXT,
    "doc_internal":      INTERNAL_CARDIO_CHEST_TEXT,
    "doc_obgyn":         OBSTETRICS_GYNECOLOGY_TEXT,
    "doc_ent":           ENT_TEXT,
    "doc_neuro_surgery": NEURO_SURGERY_TEXT,
    "doc_uro_derma":     UROLOGY_DERMA_TEXT,
    "doc_xray_labs":     XRAY_LABS_TEXT,
    "doc_pediatrics":    PEDIATRICS_TEXT,
    "alfath_clinics":    ALFATH_CLINICS_TEXT,
}

WORK_TEXT_MAP = {
    "work_wood":            WOOD_WORKERS_TEXT,
    "work_paint":           PAINT_WORKERS_TEXT,
    "work_elec":            ELEC_WORKERS_TEXT,
    "work_ceramic":         CERAMIC_WORKERS_TEXT,
    "work_washing_machine": WASHING_MACHINE_WORKERS_TEXT,
}

# ─── Logging ────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════
#  قاعدة البيانات
# ════════════════════════════════════════════
POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://neondb_owner:npg_gqp6MIP2DcaK@ep-falling-wind-atgrr0p1.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require")

# ─── Connection Pool ───
_pg_pool = None

def get_pg_pool():
    global _pg_pool
    if _pg_pool is None:
        try:
            from psycopg2 import pool as pg_pool_mod
            _pg_pool = pg_pool_mod.ThreadedConnectionPool(
                minconn=1, maxconn=5, dsn=POSTGRES_URL
            )
            logger.info("PostgreSQL connection pool created.")
        except Exception as e:
            logger.error(f"Failed to create PG pool: {e}")
    return _pg_pool

def _get_pg_conn():
    p = get_pg_pool()
    return p.getconn() if p else None

def _put_pg_conn(conn, broken=False):
    p = get_pg_pool()
    if p and conn:
        p.putconn(conn, close=broken)

def execute_query(query_str, params=None):
    """Executes a query (INSERT/UPDATE/DELETE) on PostgreSQL and falls back to SQLite if it fails."""
    pg_success = False
    conn = None
    try:
        conn = _get_pg_conn()
        if conn:
            cursor = conn.cursor()
            cursor.execute(query_str, params or ())
            conn.commit()
            _put_pg_conn(conn)
            pg_success = True
    except Exception as e:
        logger.error(f"PostgreSQL execute error: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
            _put_pg_conn(conn, broken=True)

    try:
        sqlite_conn = sqlite3.connect(DB_PATH)
        sqlite_query = query_str.replace("%s", "?")
        sqlite_conn.execute(sqlite_query, params or ())
        sqlite_conn.commit()
        sqlite_conn.close()
    except Exception as e:
        logger.error(f"SQLite execute error: {e}")
        
    return pg_success

def fetch_query(query_str, params=None):
    """Fetches rows from PostgreSQL (preferred) or SQLite (fallback)."""
    conn = None
    try:
        conn = _get_pg_conn()
        if conn:
            cursor = conn.cursor()
            cursor.execute(query_str, params or ())
            rows = cursor.fetchall()
            _put_pg_conn(conn)
            return rows, True
    except Exception as e:
        logger.error(f"PostgreSQL fetch error, falling back to SQLite: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
            _put_pg_conn(conn, broken=True)

    try:
        sqlite_conn = sqlite3.connect(DB_PATH)
        sqlite_query = query_str.replace("%s", "?")
        cursor = sqlite_conn.cursor()
        cursor.execute(sqlite_query, params or ())
        rows = cursor.fetchall()
        sqlite_conn.close()
        return rows, False
    except Exception as e:
        logger.error(f"SQLite fetch error: {e}")
        return [], False

def init_db():
    # Initialize PostgreSQL
    pg_conn = None
    try:
        pg_conn = psycopg2.connect(POSTGRES_URL)
        cursor = pg_conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id BIGINT PRIMARY KEY, joined_at VARCHAR(100), last_seen VARCHAR(100))")
        cursor.execute("CREATE TABLE IF NOT EXISTS workers (id SERIAL PRIMARY KEY, name VARCHAR(255), craft VARCHAR(255), phone VARCHAR(100))")
        cursor.execute("CREATE TABLE IF NOT EXISTS department_additions (id SERIAL PRIMARY KEY, category VARCHAR(50), details TEXT)")
        cursor.execute("CREATE TABLE IF NOT EXISTS lesson_categories (id SERIAL PRIMARY KEY, name VARCHAR(255) UNIQUE)")
        cursor.execute("SELECT COUNT(*) FROM lesson_categories")
        if cursor.fetchone()[0] == 0:
            for cat in ["علوم متكاملة", "عربي", "انجليزي", "رياضة"]:
                cursor.execute("INSERT INTO lesson_categories (name) VALUES (%s) ON CONFLICT DO NOTHING", (cat,))
        pg_conn.commit()
        logger.info("PostgreSQL database initialized successfully.")
    except Exception as e:
        logger.error(f"PostgreSQL initialization failed: {e}")
    finally:
        if pg_conn:
            pg_conn.close()

    # Initialize SQLite (local backup)
    try:
        sqlite_conn = sqlite3.connect(DB_PATH)
        sqlite_conn.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, joined_at TEXT, last_seen TEXT)")
        sqlite_conn.execute("CREATE TABLE IF NOT EXISTS workers (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, craft TEXT, phone TEXT)")
        sqlite_conn.execute("CREATE TABLE IF NOT EXISTS department_additions (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, details TEXT)")
        sqlite_conn.execute("CREATE TABLE IF NOT EXISTS lesson_categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)")
        cursor = sqlite_conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM lesson_categories")
        if cursor.fetchone()[0] == 0:
            for cat in ["علوم متكاملة", "عربي", "انجليزي", "رياضة"]:
                cursor.execute("INSERT OR IGNORE INTO lesson_categories (name) VALUES (?)", (cat,))
        sqlite_conn.commit()
        sqlite_conn.close()
        logger.info("SQLite database initialized successfully.")
    except Exception as e:
        logger.error(f"SQLite database initialization failed: {e}")

def update_activity(user_id: int):
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date().isoformat()
    rows, _ = fetch_query("SELECT user_id FROM users WHERE user_id = %s", (user_id,))
    if rows:
        execute_query("UPDATE users SET last_seen = %s WHERE user_id = %s", (today, user_id))
    else:
        execute_query("INSERT INTO users (user_id, joined_at, last_seen) VALUES (%s, %s, %s)", (user_id, today, today))

def save_worker_to_db(name, craft, phone):
    try:
        execute_query("INSERT INTO workers (name, craft, phone) VALUES (%s, %s, %s)", (name, craft, phone))
        logger.info(f"Worker {name} ({craft}) saved to database.")
    except Exception as e:
        logger.error(f"Error saving worker to db: {e}")

def escape_markdown(text: str) -> str:
    if not text:
        return ""
    escaped = ""
    for char in text:
        if char in ['_', '*', '[', '`']:
            escaped += '\\' + char
        else:
            escaped += char
    return escaped

def get_db_workers(craft_key):
    try:
        rows, _ = fetch_query("SELECT name, phone FROM workers WHERE craft = %s", (craft_key,))
        if not rows:
            return ""
        
        extra_text = "\n\n• *فنيين إضافيين تم تسجيلهم عبر البوت:*"
        for row in rows:
            name, phone = escape_markdown(row[0]), escape_markdown(row[1])
            extra_text += f"\n\n  • 🛠️ {name}\n    📞 رقم التواصل: {phone}"
        return extra_text
    except Exception as e:
        logger.error(f"Error reading workers from db: {e}")
        return ""


def get_lesson_categories():
    try:
        rows, _ = fetch_query("SELECT name FROM lesson_categories ORDER BY id ASC")
        return [row[0] for row in rows]
    except Exception as e:
        logger.error(f"Error fetching lesson categories: {e}")
        return ["علوم متكاملة", "عربي", "انجليزي", "رياضة"]

def get_lessons_markup():
    cats = get_lesson_categories()
    keyboard = []
    # Grid of 2 columns
    for i in range(0, len(cats), 2):
        row = []
        row.append(InlineKeyboardButton(cats[i], callback_data=f"lesscat_{cats[i]}"))
        if i + 1 < len(cats):
            row.append(InlineKeyboardButton(cats[i+1], callback_data=f"lesscat_{cats[i+1]}"))
        keyboard.append(row)
    
    # Add addition button for users
    keyboard.append([InlineKeyboardButton("➕ إضافة مدرس", callback_data="add_teacher_start")])
    return InlineKeyboardMarkup(keyboard)

def register_user(user_id: int):
    update_activity(user_id)

def get_all_user_ids() -> list:
    rows, _ = fetch_query("SELECT user_id FROM users")
    return [r[0] for r in rows]

def get_user_count() -> int:
    rows, _ = fetch_query("SELECT COUNT(*) FROM users")
    return rows[0][0] if rows else 0

def get_stats_data() -> dict:
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date().isoformat()
    total_rows, _ = fetch_query("SELECT COUNT(*) FROM users")
    active_rows, _ = fetch_query("SELECT COUNT(*) FROM users WHERE last_seen = %s", (today,))
    new_rows, _ = fetch_query("SELECT COUNT(*) FROM users WHERE joined_at = %s", (today,))
    
    total = total_rows[0][0] if total_rows else 0
    active_today = active_rows[0][0] if active_rows else 0
    new_today = new_rows[0][0] if new_rows else 0
    
    return {
        "total": total,
        "active_today": active_today,
        "new_today": new_today
    }

# ════════════════════════════════════════════
#  التحقق من الاشتراك في القناة
# ════════════════════════════════════════════
async def check_subscription(user_id: int, bot) -> bool:
    if user_id in ADMINS:
        update_activity(user_id)
        return True
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ["creator", "administrator", "member"]:
            update_activity(user_id)
            return True
    except Exception as e:
        logger.error(f"Error checking membership for {user_id}: {e}")
    return False

async def prompt_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    channel_url = f"https://t.me/{CHANNEL_ID.lstrip('@')}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("الانضمام للقناة", url=channel_url)],
        [InlineKeyboardButton("تحقق من الانضمام", callback_data="check_sub")]
    ])
    msg_text = (
        "عذراً، يجب عليك الاشتراك في القناة أولاً لتتمكن من استخدام البوت.\n\n"
        "اشترك في القناة من الزر بالأسفل ثم اضغط على تحقق من الانضمام."
    )
    if update.callback_query:
        await update.callback_query.message.reply_text(msg_text, reply_markup=keyboard)
    else:
        await update.message.reply_text(msg_text, reply_markup=keyboard)

# ════════════════════════════════════════════
#  /start
# ════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if not await check_subscription(user_id, context.bot):
        await prompt_subscription(update, context)
        return ConversationHandler.END
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
    user_id = update.effective_user.id
    text = update.message.text or ""
    
    # Redirect to process_input if they are in an active addition flow
    interrupts = [
        "🚨 حالات عاجلة", "إضافة شغلك ➕", "self care ✨",
        "🚕 مشاركة المشاوير والمواصلات", "💼 وظائف خالية",
        "🛠️ الخدمات", "🛠 الخدمات", "🩺 دليل الأطباء والعيادات",
        "الجمعية الشرعية 🏛️", "الدروس 📚", "💻 مصمم البوت",
        "🔙 رجوع للقائمة الرئيسية", "🔙 رجوع للخدمات",
        "براند 🏷️", "براند", "🍔 مطاعم", "دليل الصنايعية 🛠️",
        "مكتبة الوفاء 📚", "مكتب السعد للمحاسبة والمراجعة ⚖️",
        "📦 خدمات الشحن والتوصيل (الطيارين)",
        "🪟 معرض استار ميتال للألوميتال",
        "🤝 طلب مساعدة", "🏟️ حجز ملعب البلاشون",
        "🚗 سيارات الطوارئ والمشاوير",
    ]
    if "choice" in context.user_data and context.user_data["choice"].startswith("إضافة") and text not in interrupts:
        return await process_input(update, context)

    if user_id in ADMINS and "admin_action" in context.user_data:
        action = context.user_data.pop("admin_action")
        
        if action == "admin_add_worker_name":
            context.user_data["admin_add_worker_name"] = text.strip()
            context.user_data["admin_action"] = "admin_add_worker_phone"
            await update.message.reply_text("📞 يرجى إرسال **رقم الهاتف** للفني الجديد:")
            return ConversationHandler.END
            
        elif action == "admin_add_worker_phone":
            name = context.user_data.pop("admin_add_worker_name", "فني")
            craft = context.user_data.pop("admin_add_worker_craft", "work_wood")
            phone = text.strip()
            save_worker_to_db(name, craft, phone)
            
            keyboard = [[InlineKeyboardButton("🔙 رجوع لإدارة الفنيين", callback_data="adm_manage_workers")]]
            await update.message.reply_text(f"✅ تم إضافة الفني *{name}* بنجاح إلى القسم.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END
            
        elif action == "admin_add_doctor_details":
            spec = context.user_data.pop("admin_add_doctor_spec", "doc_dentist")
            execute_query("INSERT INTO department_additions (category, details) VALUES (%s, %s)", (spec, text.strip()))
            keyboard = [[InlineKeyboardButton("🔙 رجوع لإدارة الأطباء", callback_data="adm_manage_doctors")]]
            await update.message.reply_text("✅ تم إضافة الطبيب بنجاح إلى القسم.", reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END
            
        elif action == "admin_add_brand_details":
            execute_query("INSERT INTO department_additions (category, details) VALUES (%s, %s)", ("brand", text.strip()))
            keyboard = [[InlineKeyboardButton("🔙 رجوع لإدارة البراندات", callback_data="adm_manage_brands")]]
            await update.message.reply_text("✅ تم إضافة البراند بنجاح إلى القسم.", reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END
            
        elif action == "admin_add_restaurant_details":
            execute_query("INSERT INTO department_additions (category, details) VALUES (%s, %s)", ("restaurant", text.strip()))
            keyboard = [[InlineKeyboardButton("🔙 رجوع لإدارة المطاعم", callback_data="adm_manage_restaurants")]]
            await update.message.reply_text("✅ تم إضافة المطعم بنجاح إلى القسم.", reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END
            
        elif action == "admin_add_captain_details":
            execute_query("INSERT INTO department_additions (category, details) VALUES (%s, %s)", ("captain", text.strip()))
            keyboard = [[InlineKeyboardButton("🔙 رجوع لإدارة الكباتن", callback_data="adm_manage_captains")]]
            await update.message.reply_text("✅ تم إضافة كابتن التوصيل بنجاح إلى القسم.", reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END

        elif action == "admin_add_lesscat_name":
            new_cat = text.strip()
            if new_cat:
                execute_query("INSERT INTO lesson_categories (name) VALUES (%s) ON CONFLICT DO NOTHING", (new_cat,))
                keyboard = [[InlineKeyboardButton("🔙 رجوع لإدارة الدروس", callback_data="adm_manage_lessons")]]
                await update.message.reply_text(f"✅ تم إضافة القسم الدراسي *{new_cat}* بنجاح.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update.message.reply_text("⚠️ اسم القسم غير صالح.")
            return ConversationHandler.END

        elif action == "admin_add_teacher_details":
            cat_name = context.user_data.pop("admin_add_teacher_cat", "عربي")
            execute_query("INSERT INTO department_additions (category, details) VALUES (%s, %s)", (f"lesson_{cat_name}", text.strip()))
            keyboard = [[InlineKeyboardButton("🔙 رجوع لإدارة الدروس", callback_data="adm_manage_lessons")]]
            await update.message.reply_text("✅ تم إضافة المدرس بنجاح إلى القسم.", reply_markup=InlineKeyboardMarkup(keyboard))
            return ConversationHandler.END
            
        elif action == "waiting_for_del_user_id":
            try:
                target_id = int(text.strip())
                execute_query("DELETE FROM users WHERE user_id = %s", (target_id,))
                await update.message.reply_text(f"✅ تم حذف المستخدم {target_id} من قاعدة البيانات بنجاح.")
            except ValueError:
                await update.message.reply_text("⚠️ يرجى إرسال رقم صحيح (ID) للمستخدم.")
            except Exception as e:
                await update.message.reply_text(f"❌ حدث خطأ أثناء الحذف: {e}")
            return ConversationHandler.END

    if not await check_subscription(user_id, context.bot):
        await prompt_subscription(update, context)
        return ConversationHandler.END

    text = update.message.text
    context.user_data["choice"] = text

    if "رجوع للخدمات" in text:
        await update.message.reply_text("اختر الخدمة المطلوبة من القائمة:", reply_markup=SERVICES_KEYBOARD)
        return ConversationHandler.END

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
        await update.message.reply_text(DOCTORS_TEXT, parse_mode="Markdown", reply_markup=DOCTORS_MARKUP, disable_web_page_preview=True)
        return ConversationHandler.END

    if "مصمم البوت" in text:
        developer_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("💻 تواصل مع مصمم البوت (واتساب)", url="https://wa.me/201020549760")]
        ])
        await update.message.reply_text(DEVELOPER_TEXT, parse_mode="Markdown", reply_markup=developer_markup)
        return ConversationHandler.END
        
    if "الدروس" in text or "الدروس 📚" in text:
        await update.message.reply_text(LESSONS_TEXT, parse_mode="Markdown", reply_markup=get_lessons_markup())
        return ConversationHandler.END
        
    elif "مطاعم" in text:
        restaurants_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍕 أبو صلاح", url="https://wa.me/201030666675"),
             InlineKeyboardButton("🍔 أبو حنين", url="https://wa.me/201009751224")],
            [InlineKeyboardButton("🍟 Viva Food", url="https://wa.me/201094318213"),
             InlineKeyboardButton("🥩 مطعم أحمد", url="https://wa.me/201006586263")]
        ])
        extra = get_db_additions("restaurant")
        await update.message.reply_text(RESTAURANTS_TEXT + extra, parse_mode="Markdown", reply_markup=restaurants_markup)
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
        contact_keyboard = [
            [InlineKeyboardButton("تواصل عبر واتساب (الفرع الرئيسي)", url="https://wa.me/201099609882")],
            [InlineKeyboardButton("تواصل عبر واتساب (الفرع الثاني)", url="https://wa.me/201067743223")]
        ]
        contact_markup = InlineKeyboardMarkup(contact_keyboard)
        await update.message.reply_text(SAAD_OFFICE_TEXT, parse_mode="Markdown", reply_markup=contact_markup)
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
        contact_keyboard = [[InlineKeyboardButton("💬 تواصل طوارئ (واتساب)", url="https://wa.me/201062925584")]]
        contact_markup = InlineKeyboardMarkup(contact_keyboard)
        await update.message.reply_text(EMERGENCY_DOCTOR_TEXT, parse_mode="Markdown", reply_markup=contact_markup)
        return ConversationHandler.END

    elif "سيارات" in text or "سيارة" in text:
        contact_keyboard = [[InlineKeyboardButton("تواصل عبر واتساب 💬", url="https://wa.me/201062398885")]]
        contact_markup = InlineKeyboardMarkup(contact_keyboard)
        await update.message.reply_text(EMERGENCY_CARS_TEXT, parse_mode="Markdown", reply_markup=contact_markup)
        return ConversationHandler.END
        
    elif "الصنايعية" in text:
        await update.message.reply_text(WORKERS_TEXT, parse_mode="Markdown", reply_markup=WORKERS_MARKUP, disable_web_page_preview=True)
        return ConversationHandler.END

    elif "براند" in text and not "إضافة" in text and not "رجوع" in text:
        extra = get_db_additions("brand")
        await update.message.reply_text(BRANDS_TEXT + extra, parse_mode="Markdown", reply_markup=BRANDS_KEYBOARD)
        return ConversationHandler.END

    elif "إضافة شغلك" in text:
        await update.message.reply_text(
            "💼 *قسم إضافة عملك/شغلك:* \n\n"
            "اختر القسم المناسب لعملك من القائمة بالأسفل لإرسال تفاصيله للإدارة:",
            reply_markup=ADD_WORK_KEYBOARD,
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    elif "إضافة طبيب/عيادة" in text:
        await update.message.reply_text(
            "اختر التخصص الطبي الخاص بك من القائمة بالأسفل لتصنيفه بشكل صحيح:",
            reply_markup=ADD_DOCTOR_SPECIALTY_KEYBOARD
        )
        context.user_data["choice"] = "إضافة طبيب"
        return WAITING_FOR_REQUEST_DETAILS

    elif "إضافة صنايعي" in text:
        await update.message.reply_text(
            "اختر الحرفة الخاصة بك من القائمة بالأسفل لتصنيفها بشكل صحيح داخل البوت:",
            reply_markup=ADD_WORKER_CRAFT_KEYBOARD
        )
        context.user_data["choice"] = "إضافة صنايعي"
        return WAITING_FOR_REQUEST_DETAILS

    elif "إضافة براند" in text:
        await update.message.reply_text(
            "📝 يرجى إدخال تفاصيل البراند الخاص بك في رسالة واحدة كالتالي:\n\n"
            "1. اسم البراند:\n"
            "2. وصف البراند/المنتجات:\n"
            "3. الرابط (قناة/موقع/واتساب):\n\n"
            "سيتم مراجعة طلبك وإضافته لقسم البراندات فور موافقة الإدارة. ✅"
        )
        context.user_data["choice"] = "إضافة براند"
        return WAITING_FOR_REQUEST_DETAILS

    elif "إضافة مطعم" in text:
        await update.message.reply_text(
            "📝 يرجى إدخال تفاصيل المطعم في رسالة واحدة كالتالي:\n\n"
            "1. اسم المطعم:\n"
            "2. نوع الأكل/الخدمات التي يقدمها:\n"
            "3. العنوان ورقم التواصل:\n\n"
            "سيتم مراجعة طلبك وإضافته لقسم المطاعم فور موافقة الإدارة. ✅"
        )
        context.user_data["choice"] = "إضافة مطعم"
        return WAITING_FOR_REQUEST_DETAILS

    elif "إضافة كابتن توصيل" in text:
        await update.message.reply_text(
            "📝 يرجى إدخال تفاصيل التوصيل في رسالة واحدة كالتالي:\n\n"
            "1. الاسم:\n"
            "2. وسيلة التوصيل (موتوسيكل، سيارة، إلخ):\n"
            "3. رقم التواصل:\n\n"
            "سيتم مراجعة طلبك وإضافته لقسم كباتن التوصيل فور موافقة الإدارة. ✅"
        )
        context.user_data["choice"] = "إضافة كابتن"
        return WAITING_FOR_REQUEST_DETAILS

    elif "إضافة مدرس" in text:
        cats = get_lesson_categories()
        keyboard = []
        for i in range(0, len(cats), 2):
            row = []
            row.append(cats[i])
            if i + 1 < len(cats):
                row.append(cats[i+1])
            keyboard.append(row)
        keyboard.append(["🔙 رجوع للقائمة الرئيسية"])
        await update.message.reply_text(
            "اختر القسم الدراسي الخاص بك لتصنيفه بشكل صحيح:",
            reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        )
        context.user_data["choice"] = "إضافة مدرس"
        return WAITING_FOR_REQUEST_DETAILS

    elif "الشحن والتوصيل" in text:
        extra = get_db_additions("captain")
        await update.message.reply_text(DELIVERY_TEXT + extra, parse_mode="Markdown")
        return ConversationHandler.END

    # --- الردود التي تتطلب إدخال بيانات ---
    elif "التبرع بالدم" in text:
        await update.message.reply_text("🩸 اكتب تفاصيل الحالة الحرجة فوراً (مثال: الفصيلة، المستشفى، رقم التواصل):")
        return WAITING_FOR_REQUEST_DETAILS

    elif "وظائف" in text:
        await update.message.reply_text("💼 اكتب تفاصيل الوظيفة (التخصص، المرتب، رقم التواصل):")
        return WAITING_FOR_REQUEST_DETAILS

    elif "طلب استغاثة" in text:
        await update.message.reply_text("اكتب تفاصيل الاستغاثة العاجلة ورقم التواصل:")
        return WAITING_FOR_REQUEST_DETAILS

    elif "طلب مساعدة" in text:
        await update.message.reply_text("اكتب تفاصيل طلب المساعدة ورقم التواصل:")
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
    user_id = update.effective_user.id
    if not await check_subscription(user_id, context.bot):
        await prompt_subscription(update, context)
        return ConversationHandler.END

    user_text = update.message.text or update.message.caption or ""
    photo_file_id = update.message.photo[-1].file_id if update.message.photo else None
    
    if user_text in ["🔙 رجوع للقائمة الرئيسية"]:
        await update.message.reply_text("القائمة الرئيسية:", reply_markup=MAIN_KEYBOARD)
        context.user_data.clear()
        return ConversationHandler.END

    KNOWN = ["🚨 حالات عاجلة", "🏥 صيدليات الطوارئ الليلة", "🩸 التبرع بالدم والطوارئ",
             "🤝 طلب مساعدة", "طلب استغاثة", "🚨 طبيب طوارئ (24 ساعة)", "self care ✨", 
             "🚕 مشاركة المشاوير والمواصلات", "💼 وظائف خالية", "🛠️ الخدمات", 
             "🩺 دليل الأطباء والعيادات", "🪟 معرض استار ميتال للألوميتال",
             "📦 خدمات الشحن والتوصيل (الطيارين)", "مكتبة الوفاء 📚", "دليل الصنايعية 🛠️",
             "مكتب السعد للمحاسبة والمراجعة ⚖️", "مكتب السعد", "الجمعية الشرعية 🏛️",
             "الدروس 📚", "الدروس", "💻 مصمم البوت", "🔙 رجوع للقائمة الرئيسية", 
             "🚕 مشاركة المشاوير", "🛠 الخدمات", "🍔 مطاعم", "🏟️ حجز ملعب البلاشون",
             "مكتبة الوفاء", "دليل الصنايعية", "الجمعية الشرعية", "شكاوى", "مفقودات",
             "🚗 سيارات الطوارئ والمشاوير", "براند 🏷️", "براند", "🔙 رجوع للخدمات",
             "إضافة شغلك ➕", "إضافة شغلك", "إضافة طبيب/عيادة 🩺",
             "إضافة صنايعي 🛠️", "إضافة براند 🏷️", "إضافة مطعم 🍔", "إضافة كابتن توصيل 🛵",
             "إضافة مدرس 📚", "إضافة مدرس"]
             
    if user_text in KNOWN:
        context.user_data.clear()
        return await handle_choice(update, context)

    choice    = context.user_data.get("choice", "")
    user      = update.effective_user
    username  = f"@{user.username}" if user.username else str(user.id)

    # ─── التحقق من اختيار القسم الدراسي أولاً ───
    if choice == "إضافة مدرس":
        cats = get_lesson_categories()
        matched_cat = None
        for cat in cats:
            if cat in user_text:
                matched_cat = cat
                break
        
        if matched_cat:
            context.user_data["temp_teacher_cat"] = matched_cat
            context.user_data["choice"] = f"إضافة مدرس: {matched_cat}"
            
            await update.message.reply_text(
                f"📝 يرجى إدخال تفاصيل المدرس في رسالة واحدة كالتالي:\n\n"
                "1. اسم المدرس:\n"
                "2. الوصف/المادة والصف:\n"
                "3. رقم الموبايل:\n\n"
                "سيتم مراجعة طلبك وإضافته لقسم المدرسين فور موافقة الإدارة. ✅"
            )
            return WAITING_FOR_REQUEST_DETAILS
        else:
            keyboard = []
            for i in range(0, len(cats), 2):
                row = []
                row.append(cats[i])
                if i + 1 < len(cats):
                    row.append(cats[i+1])
                keyboard.append(row)
            keyboard.append(["🔙 رجوع للقائمة الرئيسية"])
            await update.message.reply_text(
                "⚠️ عذراً، يرجى اختيار القسم الدراسي الخاص بك من القائمة بالأسفل أولاً لتصنيفه بشكل صحيح:",
                reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            )
            return WAITING_FOR_REQUEST_DETAILS

    # ─── التحقق من مرحلة اختيار التخصص الطبي أولاً ───
    if choice == "إضافة طبيب":
        specialties_map = {
            "طب وجراحة الفم والأسنان": "doc_dentist",
            "العلاج الطبيعي والتغذية": "doc_physio",
            "الباطنة والقلب والصدر": "doc_internal",
            "أمراض النساء والتوليد": "doc_obgyn",
            "الأنف والأذن والحنجرة": "doc_ent",
            "مخ وأعصاب وجراحة عامة": "doc_neuro_surgery",
            "المسالك البولية والجلدية": "doc_uro_derma",
            "مراكز الأشعة والتحاليل": "doc_xray_labs",
            "طب الأطفال وحديثي الولادة": "doc_pediatrics",
            "عيادات الفتح التخصصية": "alfath_clinics"
        }
        matched_key = None
        matched_name = None
        for name, key in specialties_map.items():
            if name in user_text:
                matched_key = key
                matched_name = name
                break
        
        if matched_key:
            context.user_data["temp_doctor_specialty"] = matched_key
            context.user_data["temp_doctor_specialty_name"] = matched_name
            context.user_data["choice"] = f"إضافة طبيب: {matched_name}"
            
            await update.message.reply_text(
                f"📝 يرجى إدخال تفاصيل العيادة/الطبيب في رسالة واحدة كالتالي:\n\n"
                "1. اسم الطبيب والتخصص:\n"
                "2. العنوان بالتفصيل:\n"
                "3. المواعيد:\n"
                "4. رقم التواصل:\n\n"
                "سيتم مراجعة طلبك وإضافته لقسم الأطباء فور موافقة الإدارة. ✅"
            )
            return WAITING_FOR_REQUEST_DETAILS
        else:
            await update.message.reply_text(
                "⚠️ عذراً، يرجى اختيار التخصص الطبي الخاص بك من القائمة بالأسفل أولاً لتصنيفه بشكل صحيح:",
                reply_markup=ADD_DOCTOR_SPECIALTY_KEYBOARD
            )
            return WAITING_FOR_REQUEST_DETAILS

    # ─── التحقق من مرحلة اختيار الحرفة أولاً ───
    if choice == "إضافة صنايعي":
        if any(c in user_text for c in ["نجار", "نقاش", "كهربائي", "مبلط", "غسالات"]):
            craft_key = "work_wood"
            craft_name = "نجار"
            if "نجار" in user_text:
                craft_key = "work_wood"
                craft_name = "نجار"
            elif "نقاش" in user_text:
                craft_key = "work_paint"
                craft_name = "نقاش"
            elif "كهربائي" in user_text:
                craft_key = "work_elec"
                craft_name = "كهربائي"
            elif "مبلط" in user_text:
                craft_key = "work_ceramic"
                craft_name = "مبلط"
            elif "غسالات" in user_text:
                craft_key = "work_washing_machine"
                craft_name = "صيانة غسالات"

            context.user_data["temp_craft_key"] = craft_key
            context.user_data["temp_craft_name"] = craft_name
            context.user_data["choice"] = f"إضافة صنايعي: {craft_name}"

            await update.message.reply_text(
                f"📝 يرجى إدخال بياناتك كـ ({craft_name}) في رسالة واحدة كالتالي:\n\n"
                "1. الاسم:\n"
                "2. رقم التواصل:\n\n"
                "سيتم مراجعة طلبك وإضافته لقسم الصنايعية ونشره في القناة فور موافقة الإدارة. ✅"
            )
            return WAITING_FOR_REQUEST_DETAILS
        else:
            await update.message.reply_text(
                "⚠️ عذراً، يرجى اختيار الحرفة الخاصة بك من القائمة بالأسفل أولاً لتصنيفها بشكل صحيح داخل البوت:",
                reply_markup=ADD_WORKER_CRAFT_KEYBOARD
            )
            return WAITING_FOR_REQUEST_DETAILS

    try:
        # نظام طلبات النشر الموحد في القناة
        action_code = ""
        action_name = ""
        
        if "طلب استغاثة" in choice:
            action_code = "sos"
            action_name = "طلب استغاثة عاجل"
        elif "طلب مساعدة" in choice:
            action_code = "help"
            action_name = "طلب مساعدة"
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
        elif "إضافة طبيب" in choice:
            action_code = "add_doctor"
            action_name = "طلب إضافة طبيب/عيادة"
            specialty_key = context.user_data.get("temp_doctor_specialty", "doc_dentist")
            req_data_key = f"doctor_data_{user.id}"
            context.bot_data[req_data_key] = {
                "specialty": specialty_key
            }
        elif "إضافة مدرس" in choice:
            action_code = "add_teacher"
            action_name = "طلب إضافة مدرس"
            teacher_cat = context.user_data.get("temp_teacher_cat", "عربي")
            req_data_key = f"teacher_data_{user.id}"
            context.bot_data[req_data_key] = {
                "category": teacher_cat
            }
        elif "إضافة صنايعي" in choice:
            action_code = "add_worker"
            action_name = "طلب إضافة صنايعي"
            
            craft_key = context.user_data.get("temp_craft_key", "work_wood")
            craft_name = context.user_data.get("temp_craft_name", "نجار")
            
            name = ""
            phone = ""
            for line in user_text.split("\n"):
                if "الاسم" in line:
                    name = line.split("الاسم:")[-1].strip().replace("•", "").strip()
                elif "التواصل" in line or "الهاتف" in line or "التليفون" in line or "رقم" in line:
                    phone = line.split(":")[-1].strip().replace("•", "").strip()
            
            if not name or not phone:
                lines = [l.strip() for l in user_text.split("\n") if l.strip()]
                if len(lines) >= 2:
                    if not name:
                        name = lines[0]
                    if not phone:
                        phone = lines[1]
            
            if not name:
                name = "فني غير مسمى"
            if not phone:
                phone = user_text.strip()
                
            req_data_key = f"worker_data_{user.id}"
            context.bot_data[req_data_key] = {
                "name": name,
                "phone": phone,
                "craft": craft_key
            }
        elif "إضافة براند" in choice:
            action_code = "add_brand"
            action_name = "طلب إضافة براند"
        elif "إضافة مطعم" in choice:
            action_code = "add_restaurant"
            action_name = "طلب إضافة مطعم"
        elif "إضافة كابتن" in choice:
            action_code = "add_captain"
            action_name = "طلب إضافة كابتن توصيل"
            
        if action_code:
            markup = InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ موافقة ونشر", callback_data=f"app_{action_code}_{user.id}"),
                InlineKeyboardButton("❌ رفض الطلب", callback_data=f"rej_{action_code}_{user.id}")
            ]])
            req = f"🚨 {action_name} جديد\nمن: {username}\n\nالتفاصيل:\n{user_text}"
            
            admin_msgs = {}
            for admin_id in ADMINS:
                try:
                    if photo_file_id: sent_msg = await context.bot.send_photo(chat_id=admin_id, photo=photo_file_id, caption=req, reply_markup=markup)
                    else: sent_msg = await context.bot.send_message(chat_id=admin_id, text=req, reply_markup=markup)
                    admin_msgs[str(admin_id)] = sent_msg.message_id
                except Exception as e:
                    print(f"Error sending to admin {admin_id}: {e}")
                    if admin_id != ADMIN_ID:
                        try:
                            await context.bot.send_message(
                                chat_id=ADMIN_ID,
                                text=f"⚠️ خطأ في الإرسال للآدمن {admin_id}:\n{str(e)}"
                            )
                        except Exception:
                            pass
            context.bot_data[f"req_{action_code}_{user.id}"] = admin_msgs
            
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
    user_id = update.effective_user.id

    # ─── لوحة تحكم المشرف (الحذف والتعديل) ───
    if data.startswith("adm_"):
        if user_id not in ADMINS:
            return
        
        if data == "adm_back_menu":
            keyboard = [
                [InlineKeyboardButton("🛠️ إدارة الفنيين (الصنايعية)", callback_data="adm_manage_workers")],
                [InlineKeyboardButton("🩺 إدارة الأطباء والعيادات", callback_data="adm_manage_doctors")],
                [InlineKeyboardButton("📚 إدارة الدروس والمدرسين", callback_data="adm_manage_lessons")],
                [InlineKeyboardButton("🏷️ إدارة البراندات والمنتجات", callback_data="adm_manage_brands")],
                [InlineKeyboardButton("🍔 إدارة المطاعم والأكلات", callback_data="adm_manage_restaurants")],
                [InlineKeyboardButton("🛵 إدارة كباتن التوصيل", callback_data="adm_manage_captains")],
                [InlineKeyboardButton("👤 إدارة المستخدمين والأمان", callback_data="adm_manage_users_security")]
            ]
            await query.edit_message_text("👮‍♂️ *لوحة تحكم وإدارة البوت للأدمن:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return
            
        # ─── 1. إدارة الفنيين ───
        elif data == "adm_manage_workers":
            keyboard = [
                [InlineKeyboardButton("➕ إضافة فني يدوياً", callback_data="adm_add_worker_select")],
                [InlineKeyboardButton("❌ حذف فني محدد", callback_data="adm_del_worker_select")],
                [InlineKeyboardButton("⚠️ مسح قسم فني بالكامل", callback_data="adm_del_craft_select")],
                [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="adm_back_menu")]
            ]
            await query.edit_message_text("🛠️ *إدارة قسم الفنيين (الصنايعية):*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return
            
        elif data == "adm_add_worker_select":
            keyboard = [
                [InlineKeyboardButton("نجار 🪵", callback_data="adm_add_wcraft_work_wood")],
                [InlineKeyboardButton("نقاش 🎨", callback_data="adm_add_wcraft_work_paint")],
                [InlineKeyboardButton("كهربائي ⚡", callback_data="adm_add_wcraft_work_elec")],
                [InlineKeyboardButton("مبلط 🧱", callback_data="adm_add_wcraft_work_ceramic")],
                [InlineKeyboardButton("صيانة غسالات 🧼", callback_data="adm_add_wcraft_work_washing_machine")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="adm_manage_workers")]
            ]
            await query.edit_message_text("اختر القسم لإضافة الفني الجديد فيه:", reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        elif data.startswith("adm_add_wcraft_"):
            craft_key = data.replace("adm_add_wcraft_", "")
            context.user_data["admin_action"] = "admin_add_worker_name"
            context.user_data["admin_add_worker_craft"] = craft_key
            await query.edit_message_text("📝 يرجى إرسال **اسم الفني** الجديد في رسالة:")
            return
            
        elif data == "adm_del_worker_select":
            keyboard = [
                [InlineKeyboardButton("نجار 🪵", callback_data="adm_del_wlist_work_wood")],
                [InlineKeyboardButton("نقاش 🎨", callback_data="adm_del_wlist_work_paint")],
                [InlineKeyboardButton("كهربائي ⚡", callback_data="adm_del_wlist_work_elec")],
                [InlineKeyboardButton("مبلط 🧱", callback_data="adm_del_wlist_work_ceramic")],
                [InlineKeyboardButton("صيانة غسالات 🧼", callback_data="adm_del_wlist_work_washing_machine")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="adm_manage_workers")]
            ]
            await query.edit_message_text("اختر القسم لعرض الفنيين وحذف فني محدد:", reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        elif data == "adm_del_craft_select":
            keyboard = [
                [InlineKeyboardButton("مسح نجارين 🪵", callback_data="adm_del_craft_work_wood")],
                [InlineKeyboardButton("مسح نقاشين 🎨", callback_data="adm_del_craft_work_paint")],
                [InlineKeyboardButton("مسح كهربائية ⚡", callback_data="adm_del_craft_work_elec")],
                [InlineKeyboardButton("مسح مبلطين 🧱", callback_data="adm_del_craft_work_ceramic")],
                [InlineKeyboardButton("مسح صيانة غسالات 🧼", callback_data="adm_del_craft_work_washing_machine")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="adm_manage_workers")]
            ]
            await query.edit_message_text("⚠️ اختر القسم لمسح جميع الفنيين المسجلين فيه بالكامل:", reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        elif data.startswith("adm_del_wlist_"):
            craft_key = data.replace("adm_del_wlist_", "")
            rows, _ = fetch_query("SELECT id, name, phone FROM workers WHERE craft = %s", (craft_key,))
            
            if not rows:
                keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_del_worker_select")]]
                await query.edit_message_text("⚠️ لا يوجد فنيين مسجلين في هذا القسم حالياً.", reply_markup=InlineKeyboardMarkup(keyboard))
                return
                
            keyboard = []
            for row in rows:
                w_id, name, phone = row[0], row[1], row[2]
                keyboard.append([InlineKeyboardButton(f"❌ {name} ({phone})", callback_data=f"adm_del_worker_{w_id}")])
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_del_worker_select")])
            await query.edit_message_text("اختر الفني الذي تريد حذفه نهائياً من البوت:", reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        elif data.startswith("adm_del_worker_"):
            w_id = int(data.replace("adm_del_worker_", ""))
            rows, _ = fetch_query("SELECT name, craft FROM workers WHERE id = %s", (w_id,))
            if rows:
                name, craft = rows[0][0], rows[0][1]
                execute_query("DELETE FROM workers WHERE id = %s", (w_id,))
                keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_del_worker_select")]]
                await query.edit_message_text(f"✅ تم حذف الفني *{name}* من قاعدة البيانات بنجاح.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_del_worker_select")]]
                await query.edit_message_text("⚠️ لم يتم العثور على الفني في قاعدة البيانات.", reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        elif data.startswith("adm_del_craft_"):
            craft_key = data.replace("adm_del_craft_", "")
            execute_query("DELETE FROM workers WHERE craft = %s", (craft_key,))
            
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_manage_workers")]]
            await query.edit_message_text("✅ تم مسح جميع الفنيين في هذا القسم بنجاح.", reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        # ─── 2. إدارة الأطباء ───
        elif data == "adm_manage_doctors":
            keyboard = [
                [InlineKeyboardButton("➕ إضافة طبيب يدوياً", callback_data="adm_add_doctor_direct")],
                [InlineKeyboardButton("❌ عرض وحذف طبيب", callback_data="adm_del_docspec_select")],
                [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="adm_back_menu")]
            ]
            await query.edit_message_text("🩺 *إدارة قسم الأطباء والعيادات:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return
            
        elif data == "adm_add_doctor_direct":
            keyboard = [
                [InlineKeyboardButton("طب وجراحة الفم والأسنان 🦷", callback_data="adm_add_docspec_doc_dentist")],
                [InlineKeyboardButton("العلاج الطبيعي والتغذية 🦾", callback_data="adm_add_docspec_doc_physio")],
                [InlineKeyboardButton("الباطنة والقلب والصدر 🫁", callback_data="adm_add_docspec_doc_internal")],
                [InlineKeyboardButton("أمراض النساء والتوليد 🤰", callback_data="adm_add_docspec_doc_obgyn")],
                [InlineKeyboardButton("الأنف والأذن والحنجرة 👂", callback_data="adm_add_docspec_doc_ent")],
                [InlineKeyboardButton("مخ وأعصاب وجراحة عامة 🧠", callback_data="adm_add_docspec_doc_neuro_surgery")],
                [InlineKeyboardButton("المسالك البولية والجلدية 🩸", callback_data="adm_add_docspec_doc_uro_derma")],
                [InlineKeyboardButton("مراكز الأشعة والتحاليل 🔬", callback_data="adm_add_docspec_doc_xray_labs")],
                [InlineKeyboardButton("طب الأطفال وحديثي الولادة 👶", callback_data="adm_add_docspec_doc_pediatrics")],
                [InlineKeyboardButton("عيادات الفتح التخصصية 🏛️", callback_data="adm_add_docspec_alfath_clinics")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="adm_manage_doctors")]
            ]
            await query.edit_message_text("اختر التخصص الطبي لإضافة الطبيب الجديد فيه:", reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        elif data.startswith("adm_add_docspec_"):
            spec_key = data.replace("adm_add_docspec_", "")
            context.user_data["admin_action"] = "admin_add_doctor_details"
            context.user_data["admin_add_doctor_spec"] = spec_key
            await query.edit_message_text(
                "📝 يرجى إرسال تفاصيل الطبيب/العيادة في رسالة واحدة كالتالي:\n\n"
                "1. اسم الطبيب والتخصص:\n"
                "2. العنوان بالتفصيل:\n"
                "3. المواعيد:\n"
                "4. رقم التواصل:"
            )
            return
            
        elif data == "adm_del_docspec_select":
            keyboard = [
                [InlineKeyboardButton("طب وجراحة الفم والأسنان 🦷", callback_data="adm_del_addlist_doc_dentist")],
                [InlineKeyboardButton("العلاج الطبيعي والتغذية 🦾", callback_data="adm_del_addlist_doc_physio")],
                [InlineKeyboardButton("الباطنة والقلب والصدر 🫁", callback_data="adm_del_addlist_doc_internal")],
                [InlineKeyboardButton("أمراض النساء والتوليد 🤰", callback_data="adm_del_addlist_doc_obgyn")],
                [InlineKeyboardButton("الأنف والأذن والحنجرة 👂", callback_data="adm_del_addlist_doc_ent")],
                [InlineKeyboardButton("مخ وأعصاب وجراحة عامة 🧠", callback_data="adm_del_addlist_doc_neuro_surgery")],
                [InlineKeyboardButton("المسالك البولية والجلدية 🩸", callback_data="adm_del_addlist_doc_uro_derma")],
                [InlineKeyboardButton("مراكز الأشعة والتحاليل 🔬", callback_data="adm_del_addlist_doc_xray_labs")],
                [InlineKeyboardButton("طب الأطفال وحديثي الولادة 👶", callback_data="adm_del_addlist_doc_pediatrics")],
                [InlineKeyboardButton("عيادات الفتح التخصصية 🏛️", callback_data="adm_del_addlist_alfath_clinics")],
                [InlineKeyboardButton("🔙 رجوع", callback_data="adm_manage_doctors")]
            ]
            await query.edit_message_text("اختر التخصص لعرض الأطباء وحذف طبيب محدد:", reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        # ─── 3. إدارة البراندات ───
        elif data == "adm_manage_brands":
            keyboard = [
                [InlineKeyboardButton("➕ إضافة براند يدوياً", callback_data="adm_add_brand_direct")],
                [InlineKeyboardButton("❌ عرض وحذف براند", callback_data="adm_del_addlist_brand")],
                [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="adm_back_menu")]
            ]
            await query.edit_message_text("🏷️ *إدارة قسم البراندات والمنتجات:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return
            
        elif data == "adm_add_brand_direct":
            context.user_data["admin_action"] = "admin_add_brand_details"
            await query.edit_message_text(
                "📝 يرجى إرسال تفاصيل البراند في رسالة واحدة كالتالي:\n\n"
                "1. اسم البراند:\n"
                "2. وصف البراند/المنتجات:\n"
                "3. الرابط (قناة/موقع/واتساب):"
            )
            return
            
        # ─── 4. إدارة المطاعم ───
        elif data == "adm_manage_restaurants":
            keyboard = [
                [InlineKeyboardButton("➕ إضافة مطعم يدوياً", callback_data="adm_add_restaurant_direct")],
                [InlineKeyboardButton("❌ عرض وحذف مطعم", callback_data="adm_del_addlist_restaurant")],
                [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="adm_back_menu")]
            ]
            await query.edit_message_text("🍔 *إدارة قسم المطاعم والأكلات:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return
            
        elif data == "adm_add_restaurant_direct":
            context.user_data["admin_action"] = "admin_add_restaurant_details"
            await query.edit_message_text(
                "📝 يرجى إرسال تفاصيل المطعم في رسالة واحدة كالتالي:\n\n"
                "1. اسم المطعم:\n"
                "2. نوع الأكل/الخدمات التي يقدمها:\n"
                "3. العنوان ورقم التواصل:"
            )
            return
            
        # ─── 5. إدارة الكباتن ───
        elif data == "adm_manage_captains":
            keyboard = [
                [InlineKeyboardButton("➕ إضافة كابتن يدوياً", callback_data="adm_add_captain_direct")],
                [InlineKeyboardButton("❌ عرض وحذف كابتن", callback_data="adm_del_addlist_captain")],
                [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="adm_back_menu")]
            ]
            await query.edit_message_text("🛵 *إدارة قسم كباتن التوصيل (دليفري):*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return
            
        elif data == "adm_add_captain_direct":
            context.user_data["admin_action"] = "admin_add_captain_details"
            await query.edit_message_text(
                "📝 يرجى إرسال تفاصيل كابتن التوصيل في رسالة واحدة كالتالي:\n\n"
                "1. الاسم:\n"
                "2. وسيلة التوصيل (موتوسيكل، سيارة، إلخ):\n"
                "3. رقم التواصل:"
            )
            return

        # ─── 5.5. إدارة الدروس ───
        elif data == "adm_manage_lessons":
            keyboard = [
                [InlineKeyboardButton("➕ إضافة قسم جديد", callback_data="adm_add_lesscat")],
                [InlineKeyboardButton("❌ حذف قسم بالكامل", callback_data="adm_del_lesscat_select")],
                [InlineKeyboardButton("➕ إضافة مدرس يدوياً", callback_data="adm_add_teacher_direct")],
                [InlineKeyboardButton("❌ عرض وحذف مدرس", callback_data="adm_del_teacher_select")],
                [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="adm_back_menu")]
            ]
            await query.edit_message_text("📚 *إدارة قسم الدروس والمدرسين:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return

        elif data == "adm_add_lesscat":
            context.user_data["admin_action"] = "admin_add_lesscat_name"
            await query.edit_message_text("📝 يرجى إرسال اسم القسم الدراسي الجديد في الرسالة التالية (مثال: فيزياء):")
            return

        elif data == "adm_del_lesscat_select":
            cats = get_lesson_categories()
            keyboard = []
            for cat in cats:
                keyboard.append([InlineKeyboardButton(f"❌ {cat}", callback_data=f"adm_del_lesscat_{cat}")])
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_manage_lessons")])
            await query.edit_message_text("⚠️ اختر القسم الذي تريد حذفه بالكامل (سيتم حذف جميع مدرسيه أيضاً):", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        elif data.startswith("adm_del_lesscat_"):
            cat_name = data.replace("adm_del_lesscat_", "")
            execute_query("DELETE FROM lesson_categories WHERE name = %s", (cat_name,))
            execute_query("DELETE FROM department_additions WHERE category = %s", (f"lesson_{cat_name}",))
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_manage_lessons")]]
            await query.edit_message_text(f"✅ تم حذف قسم *{cat_name}* وجميع مدرسيه بنجاح.", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        elif data == "adm_add_teacher_direct":
            cats = get_lesson_categories()
            keyboard = []
            for cat in cats:
                keyboard.append([InlineKeyboardButton(cat, callback_data=f"adm_add_teachdirect_{cat}")])
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_manage_lessons")])
            await query.edit_message_text("اختر القسم الدراسي لإضافة المدرس الجديد فيه:", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        elif data.startswith("adm_add_teachdirect_"):
            cat_name = data.replace("adm_add_teachdirect_", "")
            context.user_data["admin_action"] = "admin_add_teacher_details"
            context.user_data["admin_add_teacher_cat"] = cat_name
            await query.edit_message_text(
                f"📝 يرجى إرسال تفاصيل المدرس للقسم ({cat_name}) كرسالة واحدة كالتالي:\n\n"
                "1. اسم المدرس:\n"
                "2. الوصف/المادة والصف:\n"
                "3. رقم الموبايل:"
            )
            return

        elif data == "adm_del_teacher_select":
            cats = get_lesson_categories()
            keyboard = []
            for cat in cats:
                keyboard.append([InlineKeyboardButton(cat, callback_data=f"adm_del_teachspec_{cat}")])
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_manage_lessons")])
            await query.edit_message_text("اختر القسم لعرض المدرسين وحذف مدرس محدد:", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        elif data.startswith("adm_del_teachspec_"):
            cat_name = data.replace("adm_del_teachspec_", "")
            rows, _ = fetch_query("SELECT id, details FROM department_additions WHERE category = %s", (f"lesson_{cat_name}",))
            if not rows:
                keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data="adm_del_teacher_select")]]
                await query.edit_message_text("⚠️ لا توجد مدرسون مسجلون في هذا القسم حالياً.", reply_markup=InlineKeyboardMarkup(keyboard))
                return
            keyboard = []
            for row in rows:
                item_id, details = row[0], row[1]
                short_text = details.replace("\n", " ")[:25] + "..."
                keyboard.append([InlineKeyboardButton(f"❌ {short_text}", callback_data=f"adm_del_teachitem_{item_id}")])
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="adm_del_teacher_select")])
            await query.edit_message_text(f"اختر المدرس الذي تريد حذفه نهائياً من قسم {cat_name}:", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        elif data.startswith("adm_del_teachitem_"):
            item_id = int(data.replace("adm_del_teachitem_", ""))
            rows, _ = fetch_query("SELECT category FROM department_additions WHERE id = %s", (item_id,))
            cat = rows[0][0] if rows else "lesson_عربي"
            execute_query("DELETE FROM department_additions WHERE id = %s", (item_id,))
            cat_name = cat.replace("lesson_", "")
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data=f"adm_del_teachspec_{cat_name}")]]
            await query.edit_message_text("✅ تم حذف المدرس من قاعدة البيانات بنجاح.", reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        # ─── 6. إدارة المستخدمين والأمان ───
        elif data == "adm_manage_users_security":
            keyboard = [
                [InlineKeyboardButton("👤 حذف مستخدم من البوت", callback_data="adm_del_user")],
                [InlineKeyboardButton("⚠️ تصفير قاعدة البيانات بالكامل", callback_data="adm_reset_db_confirm")],
                [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="adm_back_menu")]
            ]
            await query.edit_message_text("👤 *إدارة المستخدمين والأمان:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
            return
            
        elif data == "adm_del_user":
            context.user_data["admin_action"] = "waiting_for_del_user_id"
            await query.edit_message_text("💬 يرجى إرسال الـ User ID الخاص بالمستخدم الذي تريد حذفه من قاعدة البيانات في الرسالة التالية:")
            return
            
        elif data == "adm_reset_db_confirm":
            keyboard = [
                [InlineKeyboardButton("نعم، متأكد وموافق ⚠️", callback_data="adm_reset_db_yes")],
                [InlineKeyboardButton("🔙 تراجع وإلغاء", callback_data="adm_back_menu")]
            ]
            await query.edit_message_text("⚠️ *تحذير هام جداً:*\n\nهل أنت متأكد من تصفير قاعدة البيانات بالكامل؟\nسيتم مسح جميع الفنيين والمستخدمين المسجلين ولا يمكن استعادة البيانات!", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        elif data.startswith("adm_del_addlist_"):
            cat = data.replace("adm_del_addlist_", "")
            rows, _ = fetch_query("SELECT id, details FROM department_additions WHERE category = %s", (cat,))
            
            doctor_specialties = [
                "doc_dentist", "doc_physio", "doc_internal", "doc_obgyn", "doc_ent",
                "doc_neuro_surgery", "doc_uro_derma", "doc_xray_labs", "doc_pediatrics", "alfath_clinics"
            ]
            if cat in doctor_specialties:
                back_cb = "adm_del_docspec_select"
            else:
                back_map = {
                    "brand": "adm_manage_brands",
                    "restaurant": "adm_manage_restaurants",
                    "captain": "adm_manage_captains"
                }
                back_cb = back_map.get(cat, "adm_back_menu")
            
            if not rows:
                keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data=back_cb)]]
                await query.edit_message_text("⚠️ لا توجد إضافات مسجلة في هذا القسم حالياً.", reply_markup=InlineKeyboardMarkup(keyboard))
                return
                
            keyboard = []
            for row in rows:
                item_id, details = row[0], row[1]
                short_text = details.replace("\n", " ")[:25] + "..."
                keyboard.append([InlineKeyboardButton(f"❌ {short_text}", callback_data=f"adm_del_additem_{item_id}")])
            keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data=back_cb)])
            await query.edit_message_text("اختر العنصر الذي تريد حذفه نهائياً من البوت:", reply_markup=InlineKeyboardMarkup(keyboard))
            return
            
        elif data.startswith("adm_del_additem_"):
            item_id = int(data.replace("adm_del_additem_", ""))
            rows, _ = fetch_query("SELECT category FROM department_additions WHERE id = %s", (item_id,))
            cat = rows[0][0] if rows else "doc_dentist"
            execute_query("DELETE FROM department_additions WHERE id = %s", (item_id,))
            
            doctor_specialties = [
                "doc_dentist", "doc_physio", "doc_internal", "doc_obgyn", "doc_ent",
                "doc_neuro_surgery", "doc_uro_derma", "doc_xray_labs", "doc_pediatrics", "alfath_clinics"
            ]
            if cat in doctor_specialties:
                back_cb = "adm_del_docspec_select"
            else:
                back_map = {
                    "brand": "adm_manage_brands",
                    "restaurant": "adm_manage_restaurants",
                    "captain": "adm_manage_captains"
                }
                back_cb = back_map.get(cat, "adm_back_menu")
            
            keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data=back_cb)]]
            await query.edit_message_text("✅ تم حذف العنصر من قاعدة البيانات بنجاح.", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        elif data == "adm_reset_db_yes":
            execute_query("DELETE FROM users")
            execute_query("DELETE FROM workers")
            execute_query("DELETE FROM department_additions")
            keyboard = [[InlineKeyboardButton("🔙 العودة للوحة التحكم", callback_data="adm_back_menu")]]
            await query.edit_message_text("✅ تم تصفير قاعدة البيانات وحذف جميع البيانات بنجاح.", reply_markup=InlineKeyboardMarkup(keyboard))
            return

    if data == "check_sub":
        subscribed = await check_subscription(user_id, context.bot)
        if subscribed:
            try:
                await query.delete_message()
            except Exception:
                pass
            register_user(user_id)
            await query.message.reply_text(
                "💡 مرحباً بك في منصة خدمات البلاشون الذكية.\nاختر الخدمة المطلوبة من الأزرار بالأسفل:",
                reply_markup=MAIN_KEYBOARD,
            )
        else:
            channel_url = f"https://t.me/{CHANNEL_ID.lstrip('@')}"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("الانضمام للقناة", url=channel_url)],
                [InlineKeyboardButton("تحقق من الانضمام", callback_data="check_sub")]
            ])
            await query.message.reply_text(
                "لم نتمكن من التحقق من انضمامك للقناة بعد. يرجى الاشتراك أولاً ثم الضغط على الزر.",
                reply_markup=keyboard
            )
        return

    # Check subscription for other actions
    if not await check_subscription(user_id, context.bot):
        await prompt_subscription(update, context)
        return

    if data.startswith("lesscat_"):
        cat_name = data.replace("lesscat_", "")
        extra_teachers = get_db_additions(f"lesson_{cat_name}")
        text_to_send = f"📚 *قسم {cat_name}:*\n\n"
        if extra_teachers:
            text_to_send += extra_teachers
        else:
            text_to_send += "⚠️ لا يوجد مدرسون مسجلون في هذا القسم حالياً."
        keyboard = [
            [InlineKeyboardButton("➕ إضافة مدرس", callback_data=f"add_teacher_for_{cat_name}")],
            [InlineKeyboardButton("🔙 رجوع للأقسام", callback_data="back_to_lessons")]
        ]
        await query.message.reply_text(text_to_send, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard), disable_web_page_preview=True)
        return

    if data == "back_to_lessons":
        await query.message.edit_text(LESSONS_TEXT, parse_mode="Markdown", reply_markup=get_lessons_markup())
        return

    if data == "add_teacher_start":
        cats = get_lesson_categories()
        keyboard = []
        for cat in cats:
            keyboard.append([InlineKeyboardButton(cat, callback_data=f"add_teacher_for_{cat}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="back_to_lessons")])
        await query.message.edit_text("اختر القسم الدراسي أولاً لإضافة المدرس فيه:", reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("add_teacher_for_"):
        cat_name = data.replace("add_teacher_for_", "")
        context.user_data["choice"] = f"إضافة مدرس: {cat_name}"
        context.user_data["temp_teacher_cat"] = cat_name
        await query.message.reply_text(
            f"📝 يرجى إدخال تفاصيل المدرس للقسم ({cat_name}) في رسالة واحدة كالتالي:\n\n"
            "1. اسم المدرس:\n"
            "2. الوصف/المادة والصف:\n"
            "3. رقم الموبايل:\n\n"
            "سيتم مراجعة طلبك وإضافته لقسم المدرسين فور موافقة الإدارة. ✅"
        )
        return
    
    if data in DOC_TEXT_MAP:
        markup = BACK_DOCTORS_BTN
        if data == "doc_physio":
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 تواصل مباشر (واتساب)", url="https://wa.me/201091590054")],
                [InlineKeyboardButton("🔙 رجوع للتخصصات", callback_data="back_doctors")]
            ])
        extra = get_db_additions(data)
        await query.message.reply_text(DOC_TEXT_MAP[data] + extra, parse_mode="Markdown", reply_markup=markup, disable_web_page_preview=True)
        return

    if data in WORK_TEXT_MAP:
        extra_workers = get_db_workers(data)
        full_text = WORK_TEXT_MAP[data] + extra_workers
        await query.message.reply_text(full_text, parse_mode="Markdown", reply_markup=BACK_WORKERS_BTN, disable_web_page_preview=True)
        return

    if data == "back_doctors":
        await query.message.edit_text(DOCTORS_TEXT, parse_mode="Markdown", reply_markup=DOCTORS_MARKUP)
        return

    if data == "back_workers":
        await query.message.edit_text(WORKERS_TEXT, parse_mode="Markdown", reply_markup=WORKERS_MARKUP)
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
        parts = data.split("_")
        user_id = parts[-1]
        action = "_".join(parts[1:-1])
        key = f"req_{action}_{user_id}"
        admin_msgs = context.bot_data.get(key, {})
        
        try:
            await context.bot.send_message(chat_id=int(user_id), text="❌ نعتذر، تم رفض طلب النشر من قبل الإدارة.")
        except:
            pass

        if not admin_msgs:
            try:
                if photo_file_id: await query.edit_message_caption(caption=f"{admin_msg_text}\n\n❌ **تم الرفض بواسطة {admin_user}.**", parse_mode="Markdown")
                else: await query.edit_message_text(text=f"{admin_msg_text}\n\n❌ **تم الرفض بواسطة {admin_user}.**", parse_mode="Markdown")
            except: pass
        else:
            for adm_id_str, msg_id in admin_msgs.items():
                try:
                    if photo_file_id:
                        await context.bot.edit_message_caption(
                            chat_id=int(adm_id_str),
                            message_id=msg_id,
                            caption=f"{admin_msg_text}\n\n❌ **تم الرفض بواسطة {admin_user}.**",
                            parse_mode="Markdown"
                        )
                    else:
                        await context.bot.edit_message_text(
                            chat_id=int(adm_id_str),
                            message_id=msg_id,
                            text=f"{admin_msg_text}\n\n❌ **تم الرفض بواسطة {admin_user}.**",
                            parse_mode="Markdown"
                        )
                except Exception as e:
                    logger.error(f"Error editing admin message for {adm_id_str}: {e}")
        
        context.bot_data.pop(key, None)
        return

    # --- الموافقة والنشر الموحد ---
    if data.startswith("app_"):
        parts = data.split("_")
        user_id = parts[-1]
        action = "_".join(parts[1:-1])
        contact_url = f"tg://user?id={user_id}"
        is_direct_addition = action in ["add_worker", "add_doctor", "add_brand", "add_restaurant", "add_captain", "add_teacher"]

        markup = None
        if action == "sos":
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("تواصل مع الحالة 🚨", url=contact_url)]])
            text_to_send = f"🚨 *استغاثة عاجلة*\n\n{details}\n\n🤖 للتواصل عبر البوت: t.me/AlBalashon\\_services\\_bot"
        elif action == "help":
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("تواصل لتقديم المساعدة", url=contact_url)]])
            text_to_send = f"طلب مساعدة\n\n{details}\n\n🤖 للتواصل عبر البوت: t.me/AlBalashon\\_services\\_bot"
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
        elif action == "add_doctor":
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("تواصل مع الطبيب/العيادة 📞", url=contact_url)]])
            text_to_send = f"🩺 *طبيب/عيادة جديدة بالبلاشون*\n\n{details}\n\n🤖 للتواصل عبر البوت: t.me/AlBalashon\\_services\\_bot"
        elif action == "add_worker":
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("تواصل مع الصنايعي 📞", url=contact_url)]])
            text_to_send = f"🛠️ *صنايعي/حرفة جديدة بالبلاشون*\n\n{details}\n\n🤖 للتواصل عبر البوت: t.me/AlBalashon\\_services\\_bot"
        elif action == "add_brand":
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("تواصل مع صاحب البراند 💬", url=contact_url)]])
            text_to_send = f"🏷️ *براند جديد بالبلاشون*\n\n{details}\n\n🤖 للتواصل عبر البوت: t.me/AlBalashon\\_services\\_bot"
        elif action == "add_restaurant":
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("تواصل مع المطعم 📞", url=contact_url)]])
            text_to_send = f"🍔 *مطعم جديد بالبلاشون*\n\n{details}\n\n🤖 للتواصل عبر البوت: t.me/AlBalashon\\_services\\_bot"
        elif action == "add_captain":
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("تواصل مع الكابتن 📞", url=contact_url)]])
            text_to_send = f"🛵 *كابتن توصيل جديد بالبلاشون*\n\n{details}\n\n🤖 للتواصل عبر البوت: t.me/AlBalashon\\_services\\_bot"
        else:
            return

        try:
            if is_direct_addition:
                # Save data directly to the database and bypass channel notification
                if action == "add_worker":
                    req_data_key = f"worker_data_{user_id}"
                    worker_data = context.bot_data.pop(req_data_key, None)
                    if worker_data:
                        save_worker_to_db(worker_data["name"], worker_data["craft"], worker_data["phone"])
                elif action == "add_doctor":
                    req_data_key = f"doctor_data_{user_id}"
                    doc_data = context.bot_data.pop(req_data_key, None)
                    spec = doc_data["specialty"] if doc_data else "doc_dentist"
                    execute_query("INSERT INTO department_additions (category, details) VALUES (%s, %s)", (spec, details))
                elif action == "add_teacher":
                    req_data_key = f"teacher_data_{user_id}"
                    teach_data = context.bot_data.pop(req_data_key, None)
                    cat_name = teach_data["category"] if teach_data else "عربي"
                    execute_query("INSERT INTO department_additions (category, details) VALUES (%s, %s)", (f"lesson_{cat_name}", details))
                else:
                    cat_map = {
                        "add_brand": "brand",
                        "add_restaurant": "restaurant",
                        "add_captain": "captain"
                    }
                    if action in cat_map:
                        execute_query("INSERT INTO department_additions (category, details) VALUES (%s, %s)", (cat_map[action], details))
                
                await context.bot.send_message(chat_id=int(user_id), text="✅ تمت الموافقة على طلبك وإضافته إلى الأقسام بنجاح!")
                status_text = f"✅ **تمت الإضافة بنجاح بواسطة {admin_user}.**"
            else:
                # Normal alerts get published to the channel
                if photo_file_id:
                    if markup: await context.bot.send_photo(CHANNEL_ID, photo_file_id, caption=text_to_send, parse_mode="Markdown", reply_markup=markup)
                    else: await context.bot.send_photo(CHANNEL_ID, photo_file_id, caption=text_to_send, parse_mode="Markdown")
                else:
                    if markup: await context.bot.send_message(CHANNEL_ID, text=text_to_send, parse_mode="Markdown", reply_markup=markup)
                    else: await context.bot.send_message(CHANNEL_ID, text=text_to_send, parse_mode="Markdown")
                
                await context.bot.send_message(chat_id=int(user_id), text="✅ تمت الموافقة على طلبك ونشره في القناة بنجاح!")
                status_text = f"✅ **نُشر بواسطة {admin_user}.**"

            key = f"req_{action}_{user_id}"
            admin_msgs = context.bot_data.get(key, {})
            if not admin_msgs:
                if photo_file_id: await query.edit_message_caption(caption=f"{admin_msg_text}\n\n{status_text}", parse_mode="Markdown")
                else: await query.edit_message_text(text=f"{admin_msg_text}\n\n{status_text}", parse_mode="Markdown")
            else:
                for adm_id_str, msg_id in admin_msgs.items():
                    try:
                        if photo_file_id:
                            await context.bot.edit_message_caption(
                                chat_id=int(adm_id_str),
                                message_id=msg_id,
                                caption=f"{admin_msg_text}\n\n{status_text}",
                                parse_mode="Markdown"
                            )
                        else:
                            await context.bot.edit_message_text(
                                chat_id=int(adm_id_str),
                                message_id=msg_id,
                                text=f"{admin_msg_text}\n\n{status_text}",
                                parse_mode="Markdown"
                            )
                    except Exception as e:
                        logger.error(f"Error editing admin message for {adm_id_str}: {e}")
            context.bot_data.pop(key, None)
        except Exception as e:
            logger.error(e)
            if photo_file_id: await query.edit_message_caption(caption=f"{admin_msg_text}\n\n❌ **حدث خطأ أثناء الموافقة.**", parse_mode="Markdown")
            else: await query.edit_message_text(text=f"{admin_msg_text}\n\n❌ **حدث خطأ أثناء الموافقة.**", parse_mode="Markdown")

# ════════════════════════════════════════════
#  أوامر الأدمن والأذكار المجدولة
# ════════════════════════════════════════════
async def admin_menu_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMINS: return
    
    keyboard = [
        [InlineKeyboardButton("🛠️ إدارة الفنيين (الصنايعية)", callback_data="adm_manage_workers")],
        [InlineKeyboardButton("🩺 إدارة الأطباء والعيادات", callback_data="adm_manage_doctors")],
        [InlineKeyboardButton("📚 إدارة الدروس والمدرسين", callback_data="adm_manage_lessons")],
        [InlineKeyboardButton("🏷️ إدارة البراندات والمنتجات", callback_data="adm_manage_brands")],
        [InlineKeyboardButton("🍔 إدارة المطاعم والأكلات", callback_data="adm_manage_restaurants")],
        [InlineKeyboardButton("🛵 إدارة كباتن التوصيل", callback_data="adm_manage_captains")],
        [InlineKeyboardButton("👤 إدارة المستخدمين والأمان", callback_data="adm_manage_users_security")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("👮‍♂️ *لوحة تحكم وإدارة البوت للأدمن:*", reply_markup=reply_markup, parse_mode="Markdown")

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMINS: return
    stats_data = get_stats_data()
    msg = (
        "إحصائيات البوت:\n\n"
        f"المستخدمين الجدد اليوم: {stats_data['new_today']} مستخدم\n"
        f"المستخدمين النشطين اليوم: {stats_data['active_today']} مستخدم\n"
        f"إجمالي مستخدمي البوت: {stats_data['total']} مستخدم"
    )
    await update.message.reply_text(msg)

async def send_daily_stats(context: ContextTypes.DEFAULT_TYPE):
    stats_data = get_stats_data()
    msg = (
        "تقرير الإحصائيات اليومي للبوت:\n\n"
        f"المستخدمين الجدد اليوم: {stats_data['new_today']} مستخدم\n"
        f"المستخدمين النشطين اليوم: {stats_data['active_today']} مستخدم\n"
        f"إجمالي مستخدمي البوت: {stats_data['total']} مستخدم"
    )
    for admin_id in ADMINS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=msg)
        except Exception as e:
            logger.error(f"Error sending daily stats to admin {admin_id}: {e}")

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
        "☀️ *أذكار الصباح* ☀️\n\n"
        "🔹 *[ثلاث مرات]:*\n"
        "سبحان الله وبحمده عدد خلقه، ورضى نفسه، وزنة عرشه، ومداد كلماته.\n"
        "_(رواه مسلم)_\n\n"
        "🔹 *[مرة واحدة]:*\n"
        "اصبحنا واصبح الملك لله، والحمدُ لله، لا إله إلا الله وحده لا شريك له، له الملكُ وله الحمدُ وهو على كل شيءٍ قدير، ربِّ أسألك خير ما في هذا اليوم وخير ما بعده، وأعوذُ بك من شرِّ ما في هذا اليوم وشرِّ ما بعده، ربِّ أعوذُ بك من الكسل وسُوءِ الكِبَر، ربِّ أعوذُ بك من عذابٍ في النار وعذابٍ في القبر.\n"
        "_(رواه مسلم)_"
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
    
    t_stats = datetime.time(hour=23, minute=59, tzinfo=tz)
    app.job_queue.run_daily(send_daily_stats, time=t_stats)

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
    app.add_handler(CommandHandler("admin", admin_menu_cmd))

    logger.info("🚀 AlBalashon Bot started. Send /start to begin.")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == "__main__":
    main()