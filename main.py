import os
import logging
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup

# Load environment variables from .env file
load_dotenv()
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ConversationHandler, MessageHandler, ContextTypes, filters
)
from data_store import DataStore, PLAN_BASIC, PLAN_VIP
from email_sender import EmailSender
from ai_generator import AIGenerator
from tg_reporter import TGReporter

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# States for conversation handlers
(ACC_EMAIL, ACC_PASSWORD, MSG_SUBJECT, MSG_BODY,
 REC_NAME, REC_EMAILS, SEND_SELECT_MSG, SEND_SELECT_REC, SEND_SELECT_ACC,
 SEND_COUNT, SEND_DELAY, AI_GENERATE,
 OWNER_ADD_ID, OWNER_ADD_USERNAME, OWNER_ADD_PLAN, OWNER_ADD_EXPIRE,
 OWNER_REMOVE_ID, OWNER_EDIT_PLAN, OWNER_EDIT_EXPIRE,
 TG_API_ID, TG_API_HASH, TG_PHONE, TG_CODE, TG_2FA,
 REP_NAME, REP_TARGETS,
 REP_SELECT_TARGET, REP_SELECT_REASON, REP_CUSTOM_TEXT, REP_COUNT, REP_DELAY,
 SEND_MONITOR) = range(32)

TELEGRAM_SUPPORT_EMAILS = [
    "support@telegram.org",
    "recover@telegram.org",
    "security@telegram.org",
    "sms@telegram.org",
    "abuse@telegram.org",
    "dmca@telegram.org",
    "privacy@telegram.org",
    "spam@telegram.org",
    "jobs@telegram.org",
    "info@telegram.org",
    "media@telegram.org",
    "press@telegram.org",
    "android@telegram.org",
    "ios@telegram.org",
    "login@stel.com",
    "stopca@telegram.org",
    "sticker@telegram.org",
    "notifications@telegram.org",
]

data_store = DataStore()
email_sender = EmailSender()
ai_generator = AIGenerator()
tg_reporter = TGReporter()

OWNER_ID = int(os.environ.get("OWNER_ID", "0"))
OWNER_ID_2 = int(os.environ.get("OWNER_ID_2", "0"))
OWNER_IDS = {uid for uid in (OWNER_ID, OWNER_ID_2) if uid != 0}


def is_owner(user_id: int) -> bool:
    return user_id in OWNER_IDS


async def check_subscription(update: Update, feature: str = None) -> bool:
    """Returns True if user is allowed. Sends blocked message and returns False otherwise."""
    user_id = update.effective_user.id
    if is_owner(user_id):
        return True
    if not data_store.is_subscribed(user_id):
        text = (
            "🔒 *عذراً، ليس لديك اشتراك نشط!*\n\n"
            "للوصول إلى البوت يجب أن يكون لديك اشتراك.\n"
            "تواصل مع المالك لتفعيل اشتراكك."
        )
        keyboard = [[InlineKeyboardButton("📩 تواصل مع المالك", url=f"tg://user?id={OWNER_ID}")]]
        if update.callback_query:
            await update.callback_query.answer("🔒 ليس لديك اشتراك!", show_alert=True)
            await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return False
    if feature and not data_store.has_feature(user_id, feature):
        text = (
            "⭐ *هذه الميزة متاحة لخطة VIP فقط!*\n\n"
            "ميزاتك الحالية (خطة Basic) لا تشمل هذه الخاصية.\n"
            "تواصل مع المالك للترقية إلى VIP."
        )
        keyboard = [[InlineKeyboardButton("📩 تواصل مع المالك", url=f"tg://user?id={OWNER_ID}")]]
        if update.callback_query:
            await update.callback_query.answer("⭐ خطة VIP مطلوبة!", show_alert=True)
            await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return False
    return True


# Main Menu
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # Owner sees full menu + owner panel button
    if is_owner(user_id):
        keyboard = [
            [InlineKeyboardButton("📧 إدارة الحسابات", callback_data='menu_accounts')],
            [InlineKeyboardButton("📝 إدارة الرسائل", callback_data='menu_messages')],
            [InlineKeyboardButton("👥 إدارة المستلمين", callback_data='menu_recipients')],
            [InlineKeyboardButton("🚀 إرسال بريد", callback_data='menu_send')],
            [InlineKeyboardButton("� الشد الداخلي", callback_data='menu_tg_report')],
            [InlineKeyboardButton("� حالة الإرسال", callback_data='menu_status')],
            [InlineKeyboardButton("👑 لوحة تحكم المالك", callback_data='owner_panel')],
        ]
        welcome_text = "👋 مرحباً يا مالك البوت!\n\nاختر من القائمة أدناه:"
    elif not data_store.is_subscribed(user_id):
        # Non-subscribed user
        text = (
            "🔒 *مرحباً!*\n\n"
            "هذا البوت خاص وللوصول إليه تحتاج اشتراكاً نشطاً.\n\n"
            "تواصل مع المالك لتفعيل اشتراكك."
        )
        keyboard = [[InlineKeyboardButton("📩 تواصل مع المالك", url=f"tg://user?id={OWNER_ID}")]]
        if update.message:
            await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.callback_query.edit_message_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
        return
    else:
        # Subscribed user
        user = data_store.get_user(user_id)
        plan_label = "⭐ VIP" if user["plan"] == PLAN_VIP else "🔵 Basic"
        keyboard = [
            [InlineKeyboardButton("📧 إدارة الحسابات", callback_data='menu_accounts')],
            [InlineKeyboardButton("📝 إدارة الرسائل", callback_data='menu_messages')],
            [InlineKeyboardButton("👥 إدارة المستلمين", callback_data='menu_recipients')],
            [InlineKeyboardButton("🚀 إرسال بريد", callback_data='menu_send')],
            [InlineKeyboardButton("📱 الشد الداخلي", callback_data='menu_tg_report')],
            [InlineKeyboardButton("📊 حالة الإرسال", callback_data='menu_status')],
        ]
        welcome_text = (
            f"👋 مرحباً بك!\n\n"
            f"خطتك: {plan_label}\n"
            f"ينتهي الاشتراك: {user['expire_date']}\n\n"
            "اختر من القائمة أدناه:"
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(welcome_text, reply_markup=reply_markup)

# Accounts Menu
async def menu_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await check_subscription(update, "accounts"):
        return
    uid = update.effective_user.id
    accounts = data_store.user(uid).get_accounts()
    accounts_text = "📧 الحسابات المضافة:\n\n"
    for acc in accounts:
        accounts_text += f"ID: {acc['id']} - {acc['email']}\n"
    
    if not accounts:
        accounts_text = "لا توجد حسابات مضافة."
    
    keyboard = [
        [InlineKeyboardButton("➕ إضافة حساب", callback_data='add_account')],
        [InlineKeyboardButton("🗑️ حذف حساب", callback_data='remove_account')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='back_main')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(accounts_text, reply_markup=reply_markup)

# Add Account - Email
async def add_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='cancel_add_account')]]
    await query.edit_message_text(
        "📧 أرسل بريد Gmail:\n\n"
        "ملاحظة: يجب تفعيل المصادقة الثنائية وإنشاء App Password",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ACC_EMAIL

async def cancel_add_account_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel account addition and end conversation"""
    query = update.callback_query
    await query.answer()
    await menu_accounts(update, context)
    return ConversationHandler.END

async def add_account_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    
    # Validate email format
    import re
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(email_pattern, email):
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='cancel_add_account')]]
        await update.message.reply_text(
            "❌ صيغة البريد غير صحيحة!\n\n"
            "مثال صحيح: example@gmail.com\n\n"
            "أرسل البريد مرة أخرى:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ACC_EMAIL
    
    # Check if email is Gmail
    if not email.endswith('@gmail.com'):
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='cancel_add_account')]]
        await update.message.reply_text(
            "⚠️ يجب استخدام Gmail فقط!\n\n"
            "أرسل بريد Gmail صحيح:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ACC_EMAIL
    
    context.user_data['acc_email'] = email
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='cancel_add_account')]]
    await update.message.reply_text(
        "🔑 أرسل App Password:\n\n"
        "(يمكنك إنشاؤه من إعدادات أمان Google)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ACC_PASSWORD

async def add_account_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = context.user_data['acc_email']
    password = update.message.text.strip()
    
    # Check if account already exists
    uid = update.effective_user.id
    if any(acc["email"] == email for acc in data_store.user(uid).get_accounts()):
        keyboard = [[InlineKeyboardButton("🔙 رجوع للحسابات", callback_data='menu_accounts')]]
        await update.message.reply_text(
            "❌ الحساب موجود مسبقاً!",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
    
    # Verify account credentials
    await update.message.reply_text("🔄 جاري التحقق من الحساب...")
    
    result = email_sender.test_login(email, password)
    
    if not result['success']:
        keyboard = [
            [InlineKeyboardButton("🔄 إعادة المحاولة", callback_data='add_account')],
            [InlineKeyboardButton("🔙 رجوع للحسابات", callback_data='menu_accounts')]
        ]
        await update.message.reply_text(
            f"❌ {result['error']}\n\n"
            "تأكد من:\n"
            "• صحة البريد الإلكتروني\n"
            "• App Password صحيح (وليس كلمة مرور Gmail)\n"
            "• تفعيل المصادقة الثنائية في Google",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
    
    uid = update.effective_user.id
    data_store.user(uid).add_account(email, password)
    keyboard = [[InlineKeyboardButton("🔙 رجوع للحسابات", callback_data='menu_accounts')]]
    await update.message.reply_text(
        f"✅ تم إضافة الحساب بنجاح: {email}\n\n"
        "✓ تم التحقق من صحة الحساب",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return ConversationHandler.END

# Remove Account
async def remove_account_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = update.effective_user.id
    accounts = data_store.user(uid).get_accounts()
    if not accounts:
        await query.edit_message_text(
            "لا توجد حسابات لحذفها.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='menu_accounts')]])
        )
        return
    
    keyboard = []
    for acc in accounts:
        keyboard.append([InlineKeyboardButton(f"🗑️ {acc['email']}", callback_data=f"del_acc_{acc['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='menu_accounts')])
    
    await query.edit_message_text(
        "اختر الحساب للحذف:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def remove_account_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    acc_id = int(query.data.split('_')[2])
    data_store.user(update.effective_user.id).remove_account(acc_id)
    
    await menu_accounts(update, context)

# Messages Menu
async def menu_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = update.effective_user.id
    messages = data_store.user(uid).get_messages()
    msg_text = "📝 الرسائل المحفوظة:\n\n"
    for msg in messages:
        msg_text += f"ID: {msg['id']} - {msg['subject']}\n"
    
    if not messages:
        msg_text = "لا توجد رسائل محفوظة."
    
    keyboard = [
        [InlineKeyboardButton("➕ إضافة رسالة", callback_data='add_message')],
        [InlineKeyboardButton("🤖 توليد بالذكاء الاصطناعي", callback_data='ai_generate')],
        [InlineKeyboardButton("👀 عرض تفاصيل", callback_data='view_message')],
        [InlineKeyboardButton("🗑️ حذف رسالة", callback_data='remove_message')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='back_main')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(msg_text, reply_markup=reply_markup)

# Add Message
async def add_message_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await check_subscription(update, "messages"):
        return
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_messages')]]
    await query.edit_message_text(
        "📝 أرسل عنوان الرسالة (الموضوع):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MSG_SUBJECT

async def add_message_subject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() in ['cancel', 'إلغاء', '/cancel']:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_messages')]]
        await update.message.reply_text("❌ تم الإلغاء.", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
    
    context.user_data['msg_subject'] = text
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_messages')]]
    await update.message.reply_text("📄 أرسل محتوى الرسالة:", reply_markup=InlineKeyboardMarkup(keyboard))
    return MSG_BODY

async def add_message_body(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() in ['cancel', 'إلغاء', '/cancel']:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_messages')]]
        await update.message.reply_text("❌ تم الإلغاء.", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
    
    subject = context.user_data['msg_subject']
    body = text
    
    uid = update.effective_user.id
    msg_id = data_store.user(uid).add_message(subject, body)
    keyboard = [[InlineKeyboardButton("🔙 رجوع للرسائل", callback_data='menu_messages')]]
    await update.message.reply_text(f"✅ تم حفظ الرسالة برقم: {msg_id}", reply_markup=InlineKeyboardMarkup(keyboard))
    
    return ConversationHandler.END

# AI Generate Message
async def ai_generate_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await check_subscription(update, "ai"):
        return

    if not ai_generator.is_available():
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_messages')]]
        await query.edit_message_text(
            "❌ لم يتم إعداد مفتاح API للذكاء الاصطناعي.\n\n"
            "لاستخدام هذه الميزة:\n"
            "تأكد من تعيين OPENROUTER_API_KEY في ملف .env",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
    
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_messages')]]
    await query.edit_message_text(
        "🤖 وصف الرسالة التي تريدها:\n\n"
        "مثال:\n"
        "- رسالة شكوى لدعم تليجرام\n"
        "- طلب وظيفة مطور برمجيات\n"
        "- تذكير بموعد اجتماع\n\n"
        "اكتب وصفاً واضحاً:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return AI_GENERATE

async def ai_generate_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    description = update.message.text
    
    # Check for cancel
    if description.lower() in ['cancel', 'إلغاء', '/cancel']:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_messages')]]
        await update.message.reply_text(
            "❌ تم الإلغاء.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
    
    # Show typing indicator
    await update.message.chat.send_action(action="typing")
    
    try:
        # Generate email
        result = ai_generator.generate_email(description, language="arabic")
        
        if "error" in result:
            keyboard = [
                [InlineKeyboardButton("🔄 إعادة المحاولة", callback_data='ai_generate')],
                [InlineKeyboardButton("🔙 رجوع", callback_data='menu_messages')]
            ]
            await update.message.reply_text(
                f"❌ خطأ في التوليد:\n{result['error'][:200]}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return ConversationHandler.END
        
        # Validate result
        if not result.get('subject') or not result.get('body'):
            keyboard = [
                [InlineKeyboardButton("� إعادة المحاولة", callback_data='ai_generate')],
                [InlineKeyboardButton("�� رجوع", callback_data='menu_messages')]
            ]
            await update.message.reply_text(
                "❌ فشل في توليد الرسالة. جرب وصفاً مختلفاً.",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return ConversationHandler.END
        
        # Preview the generated email
        preview = (
            f"🤖 تم توليد الرسالة!\n\n"
            f"📌 الموضوع:\n{result['subject'][:100]}\n\n"
            f"📄 المحتوى (أول 400 حرف):\n{result['body'][:400]}"
        )
        if len(result['body']) > 400:
            preview += "..."
        
        # Save to user_data for approval
        context.user_data['ai_subject'] = result['subject']
        context.user_data['ai_body'] = result['body']
        
        keyboard = [
            [InlineKeyboardButton("✅ حفظ الرسالة", callback_data='ai_save')],
            [InlineKeyboardButton("🔄 إعادة المحاولة", callback_data='ai_generate')],
            [InlineKeyboardButton("❌ إلغاء", callback_data='menu_messages')],
        ]
        await update.message.reply_text(preview, reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        keyboard = [
            [InlineKeyboardButton("🔄 إعادة المحاولة", callback_data='ai_generate')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='menu_messages')]
        ]
        await update.message.reply_text(
            f"❌ خطأ: {str(e)[:200]}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    return ConversationHandler.END

async def ai_save_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    subject = context.user_data.get('ai_subject')
    body = context.user_data.get('ai_body')
    
    if subject and body:
        uid = query.from_user.id
        msg_id = data_store.user(uid).add_message(subject, body)
        await query.edit_message_text(
            f"✅ تم حفظ الرسالة برقم: {msg_id}\n\n"
            f"الموضوع: {subject[:50]}...",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع للقائمة", callback_data='menu_messages')]])
        )
    else:
        await menu_messages(update, context)

# View Message
async def view_message_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = update.effective_user.id
    messages = data_store.user(uid).get_messages()
    if not messages:
        await query.edit_message_text(
            "لا توجد رسائل لعرضها.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='menu_messages')]])
        )
        return
    
    keyboard = []
    for msg in messages:
        keyboard.append([InlineKeyboardButton(f"📄 {msg['subject']}", callback_data=f"view_msg_{msg['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='menu_messages')])
    
    await query.edit_message_text(
        "اختر رسالة لعرض التفاصيل:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def view_message_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    msg_id = int(query.data.split('_')[2])
    msg = data_store.user(update.effective_user.id).get_message(msg_id)
    
    if msg:
        text = f"📄 الموضوع: {msg['subject']}\n\n{msg['body']}"
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='menu_messages')]])
        )
    else:
        await menu_messages(update, context)

# Remove Message
async def remove_message_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = update.effective_user.id
    messages = data_store.user(uid).get_messages()
    if not messages:
        await query.edit_message_text(
            "لا توجد رسائل لحذفها.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='menu_messages')]])
        )
        return
    
    keyboard = []
    for msg in messages:
        keyboard.append([InlineKeyboardButton(f"🗑️ {msg['subject']}", callback_data=f"del_msg_{msg['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='menu_messages')])
    
    await query.edit_message_text(
        "اختر رسالة للحذف:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def remove_message_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    msg_id = int(query.data.split('_')[2])
    data_store.user(update.effective_user.id).remove_message(msg_id)
    
    await menu_messages(update, context)

# Recipients Menu
async def menu_recipients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = update.effective_user.id
    recipients = data_store.user(uid).get_recipients()
    rec_text = "👥 قوائم المستلمين:\n\n"
    for rec in recipients:
        rec_text += f"ID: {rec['id']} - {rec['name']} ({len(rec['emails'])} بريد)\n"
    
    if not recipients:
        rec_text = "لا توجد قوائم مستلمين."
    
    keyboard = [
        [InlineKeyboardButton("➕ إضافة قائمة", callback_data='add_recipients')],
        [InlineKeyboardButton("👁️ عرض التفاصيل", callback_data='view_recipients')],
        [InlineKeyboardButton("🗑️ حذف قائمة", callback_data='remove_recipients')],
        [InlineKeyboardButton("📨 إيميلات دعم تيليجرام", callback_data='tg_emails_menu')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='back_main')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(rec_text, reply_markup=reply_markup)

# Add Recipients
async def add_recipients_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_recipients')]]
    await query.edit_message_text(
        "👥 أرسل اسم للقائمة (مثال: عملاء - أصدقاء):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REC_NAME

async def add_recipients_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() in ['cancel', 'إلغاء', '/cancel']:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_recipients')]]
        await update.message.reply_text("❌ تم الإلغاء.", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
    
    context.user_data['rec_name'] = text
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_recipients')]]
    await update.message.reply_text(
        "📧 أرسل عناوين البريد مفصولة بفاصلة أو سطر جديد:\n\n"
        "مثال: email1@gmail.com, email2@gmail.com",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REC_EMAILS

async def add_recipients_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() in ['cancel', 'إلغاء', '/cancel']:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_recipients')]]
        await update.message.reply_text("❌ تم الإلغاء.", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
    
    import re
    name = context.user_data['rec_name']
    emails_text = text
    
    # Parse emails (split by comma or newline)
    raw_emails = [e.strip() for e in emails_text.replace(',', '\n').split('\n') if e.strip()]
    
    # Validate emails
    email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    valid_emails = []
    invalid_emails = []
    
    for email in raw_emails:
        if re.match(email_pattern, email):
            valid_emails.append(email)
        else:
            invalid_emails.append(email)
    
    if not valid_emails:
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_recipients')]]
        await update.message.reply_text(
            "❌ لا يوجد بريد صحيح!\n\n"
            "تأكد من صيغة البريد:\n"
            "example@domain.com",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return REC_EMAILS
    
    rec_id = data_store.user(update.effective_user.id).add_recipients(name, valid_emails)
    
    result_text = f"✅ تم حفظ القائمة '{name}' برقم: {rec_id}\n📧 {len(valid_emails)} بريد صحيح"
    if invalid_emails:
        result_text += f"\n⚠️ {len(invalid_emails)} بريد مرفوض: {', '.join(invalid_emails[:3])}"
    
    keyboard = [[InlineKeyboardButton("🔙 رجوع للمستلمين", callback_data='menu_recipients')]]
    await update.message.reply_text(result_text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    return ConversationHandler.END

# View Recipients
async def view_recipients_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = update.effective_user.id
    recipients = data_store.user(uid).get_recipients()
    if not recipients:
        await query.edit_message_text(
            "لا توجد قوائم لعرضها.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='menu_recipients')]])
        )
        return
    
    keyboard = []
    for rec in recipients:
        keyboard.append([InlineKeyboardButton(f"👀 {rec['name']}", callback_data=f"view_rec_{rec['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='menu_recipients')])
    
    await query.edit_message_text(
        "اختر قائمة لعرض التفاصيل:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def view_recipients_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    rec_id = int(query.data.split('_')[2])
    rec = data_store.user(update.effective_user.id).get_recipient(rec_id)
    
    if rec:
        emails_text = '\n'.join(rec['emails'])
        text = f"👥 {rec['name']}\n\n{emails_text}"
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='menu_recipients')]])
        )
    else:
        await menu_recipients(update, context)

# Remove Recipients
async def remove_recipients_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = update.effective_user.id
    recipients = data_store.user(uid).get_recipients()
    if not recipients:
        await query.edit_message_text(
            "لا توجد قوائم لحذفها.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='menu_recipients')]])
        )
        return
    
    keyboard = []
    for rec in recipients:
        keyboard.append([InlineKeyboardButton(f"🗑️ {rec['name']}", callback_data=f"del_rec_{rec['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='menu_recipients')])
    
    await query.edit_message_text(
        "اختر قائمة للحذف:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def remove_recipients_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    rec_id = int(query.data.split('_')[2])
    data_store.user(update.effective_user.id).remove_recipients(rec_id)
    
    await menu_recipients(update, context)

# Send Menu - Step 1: Select Message
async def menu_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await check_subscription(update, "send"):
        return
    uid = update.effective_user.id
    messages = data_store.user(uid).get_messages()
    if not messages:
        await query.edit_message_text(
            "لا توجد رسائل محفوظة. أضف رسالة أولاً.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back_main')]])
        )
        return
    
    keyboard = []
    for msg in messages:
        keyboard.append([InlineKeyboardButton(f"📄 {msg['subject']}", callback_data=f"send_msg_{msg['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='back_main')])
    
    await query.edit_message_text(
        "🚀 اختر الرسالة للإرسال:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Send Menu - Step 2: Select Recipients
async def send_select_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    msg_id = int(query.data.split('_')[2])
    uid = update.effective_user.id
    context.user_data['send_msg_id'] = msg_id
    context.user_data['send_uid'] = uid
    recipients = data_store.user(uid).get_recipients()
    keyboard = []
    for rec in recipients:
        keyboard.append([InlineKeyboardButton(f"👥 {rec['name']} ({len(rec['emails'])})", callback_data=f"send_rec_{rec['id']}")])
    keyboard.append([InlineKeyboardButton("📨 إيميلات دعم تيليجرام", callback_data='send_tg_emails')])
    keyboard.append([InlineKeyboardButton("✏️ إدخال يدوي", callback_data='send_rec_manual')])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='menu_send')])
    
    await query.edit_message_text(
        "👥 اختر قائمة المستلمين:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def send_manual_recipients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "📧 أرسل عناوين البريد مفصولة بفاصلة أو سطر جديد:\n\n"
        "مثال: email1@gmail.com, email2@gmail.com"
    )
    return SEND_SELECT_REC

async def send_recipients_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    emails_text = update.message.text
    emails = [e.strip() for e in emails_text.replace(',', '\n').split('\n') if e.strip()]
    context.user_data['send_emails'] = emails
    
    await update.message.reply_text(f"✅ تم اختيار {len(emails)} بريد إلكتروني")
    
    # Proceed to account selection
    await send_select_accounts_message(update, context)
    return ConversationHandler.END

async def send_select_rec(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    rec_id = int(query.data.split('_')[2])
    rec = data_store.user(update.effective_user.id).get_recipient(rec_id)
    
    if rec:
        context.user_data['send_emails'] = rec['emails']
        await query.edit_message_text(f"✅ تم اختيار قائمة: {rec['name']} ({len(rec['emails'])} بريد)")
        await send_select_accounts(query, context)
    else:
        await menu_send(update, context)

# Send Menu - Step 3: Select Accounts
async def send_select_accounts_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    accounts = data_store.user(update.effective_user.id).get_accounts()
    if not accounts:
        await update.message.reply_text(
            "❌ لا توجد حسابات Gmail مضافة!\n"
            "أضف حساباً أولاً من 'إدارة الحسابات'",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back_main')]])
        )
        return
    
    keyboard = []
    for acc in accounts:
        keyboard.append([InlineKeyboardButton(
            f"📧 {acc['email']}", 
            callback_data=f"send_acc_{acc['id']}"
        )])
    keyboard.append([InlineKeyboardButton("🚀 إرسال من الكل", callback_data='send_acc_all')])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='back_main')])
    
    await update.message.reply_text(
        "📧 اختر الحسابات للإرسال:\n\n"
        "(يمكنك اختيار حساب واحد أو الإرسال من جميع الحسابات)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# After account selection, ask for message count
async def send_save_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # Get accounts
    uid = update.effective_user.id
    if query.data == 'send_acc_all':
        accounts = data_store.user(uid).get_accounts()
    else:
        acc_id = int(query.data.split('_')[2])
        acc = None
        for a in data_store.user(uid).get_accounts():
            if a['id'] == acc_id:
                acc = a
                break
        accounts = [acc] if acc else []
    
    if not accounts:
        await query.edit_message_text(
            "❌ لا توجد حسابات!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back_main')]])
        )
        return
    
    # Save accounts to user_data
    context.user_data['send_accounts'] = accounts
    
    # Ask for message count
    keyboard = [
        [InlineKeyboardButton("1 مرة", callback_data='count_1')],
        [InlineKeyboardButton("5 مرات", callback_data='count_5')],
        [InlineKeyboardButton("10 مرات", callback_data='count_10')],
        [InlineKeyboardButton("25 مرة", callback_data='count_25')],
        [InlineKeyboardButton("50 مرة", callback_data='count_50')],
        [InlineKeyboardButton("✏️ عدد مخصص", callback_data='count_custom')],
        [InlineKeyboardButton("� رجوع", callback_data='back_main')],
    ]
    await query.edit_message_text(
        "🔢 كم مرة تريد إرسال الرسالة؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def send_count_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔢 أرسل عدد مرات الإرسال (رقم):\n\n"
        "مثال: 100"
    )
    return SEND_COUNT

async def send_count_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text.strip())
        if count < 1:
            await update.message.reply_text("❌ العدد يجب أن يكون 1 أو أكثر")
            return SEND_COUNT
        if count > 1000:
            await update.message.reply_text("❌ الحد الأقصى 1000 رسالة")
            return SEND_COUNT
        
        context.user_data['send_count'] = count
        await update.message.reply_text(f"✅ عدد المرات: {count}")
        await send_ask_delay_message(update, context)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ أرسل رقماً صحيحاً")
        return SEND_COUNT

async def send_select_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    count = int(query.data.split('_')[1])
    context.user_data['send_count'] = count
    
    await send_ask_delay(query, context)

async def send_ask_delay(query, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⚡ سريع جداً (بدون تأخير)", callback_data='delay_0')],
        [InlineKeyboardButton("🚀 سريع (1 ثانية)", callback_data='delay_1')],
        [InlineKeyboardButton("⏱️ 5 ثواني", callback_data='delay_5')],
        [InlineKeyboardButton("⏱️ 10 ثواني", callback_data='delay_10')],
        [InlineKeyboardButton("⏱️ 30 ثانية", callback_data='delay_30')],
        [InlineKeyboardButton("⏱️ 60 ثانية", callback_data='delay_60')],
        [InlineKeyboardButton("✏️ مدة مخصصة", callback_data='delay_custom')],
        [InlineKeyboardButton("🔙 رجوع لعدد الرسائل", callback_data='back_to_count')],
    ]
    await query.edit_message_text(
        "⏱️ اختر سرعة الإرسال (الفاصل بين كل رسالة):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def send_ask_delay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⚡ سريع جداً (بدون تأخير)", callback_data='delay_0')],
        [InlineKeyboardButton("🚀 سريع (1 ثانية)", callback_data='delay_1')],
        [InlineKeyboardButton("⏱️ 5 ثواني", callback_data='delay_5')],
        [InlineKeyboardButton("⏱️ 10 ثواني", callback_data='delay_10')],
        [InlineKeyboardButton("⏱️ 30 ثانية", callback_data='delay_30')],
        [InlineKeyboardButton("⏱️ 60 ثانية", callback_data='delay_60')],
        [InlineKeyboardButton("✏️ مدة مخصصة", callback_data='delay_custom')],
        [InlineKeyboardButton("🔙 رجوع لعدد الرسائل", callback_data='back_to_count')],
    ]
    await update.message.reply_text(
        "⏱️ اختر سرعة الإرسال (الفاصل بين كل رسالة):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def send_delay_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "⏱️ أرسل عدد الثواني بين كل رسالة:\n\n"
        "مثال: 5 (للإرسال كل 5 ثواني)\n"
        "0 = بدون تأخير (أسرع ما يمكن)"
    )
    return SEND_DELAY

async def send_delay_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        delay = int(update.message.text.strip())
        if delay < 0:
            delay = 0
        if delay > 3600:
            await update.message.reply_text("❌ الحد الأقصى 3600 ثانية (ساعة)")
            return SEND_DELAY
        
        context.user_data['send_delay'] = delay
        await update.message.reply_text(f"✅ التأخير: {delay} ثانية")
        await execute_send_final(update, context)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ أرسل رقماً صحيحاً")
        return SEND_DELAY

async def send_select_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    delay = int(query.data.split('_')[1])
    context.user_data['send_delay'] = delay
    
    await execute_send_final_query(query, context)

async def send_select_accounts(query, context: ContextTypes.DEFAULT_TYPE):
    uid = context.user_data.get('send_uid', 0)
    accounts = data_store.user(uid).get_accounts()
    if not accounts:
        await query.edit_message_text(
            "❌ لا توجد حسابات Gmail مضافة!\n"
            "أضف حساباً أولاً من 'إدارة الحسابات'",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back_to_recipients')]])
        )
        return
    
    keyboard = []
    for acc in accounts:
        keyboard.append([InlineKeyboardButton(
            f"📧 {acc['email']}", 
            callback_data=f"send_acc_{acc['id']}"
        )])
    keyboard.append([InlineKeyboardButton("🚀 إرسال من الكل", callback_data='send_acc_all')])
    keyboard.append([InlineKeyboardButton("🔙 رجوع لاختيار المستلمين", callback_data='back_to_recipients')])
    
    await query.edit_message_text(
        "📧 اختر الحسابات للإرسال:\n\n"
        "(يمكنك اختيار حساب واحد أو الإرسال من جميع الحسابات)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# Execute Send
async def execute_send_final_query(query, context: ContextTypes.DEFAULT_TYPE):
    uid = query.from_user.id
    # Send a new message so we can edit it for live progress
    sent = await context.bot.send_message(chat_id=uid, text="⏳ جاري تجهيز الإرسال...")
    await execute_send_common(sent, context, uid)

async def execute_send_final(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sent = await update.message.reply_text("⏳ جاري تجهيز الإرسال...")
    await execute_send_common(sent, context, uid)

async def execute_send_common(progress_msg, context: ContextTypes.DEFAULT_TYPE, uid: int = 0):
    """progress_msg: a Message object we can edit for live updates."""
    msg_id = context.user_data.get('send_msg_id')
    emails = context.user_data.get('send_emails', [])
    accounts = context.user_data.get('send_accounts', [])
    count = context.user_data.get('send_count', 1)
    delay = context.user_data.get('send_delay', 0)

    uid = uid or context.user_data.get('send_uid', 0)
    msg = data_store.user(uid).get_message(msg_id) if msg_id else None

    if not msg or not emails or not accounts:
        await progress_msg.edit_text(
            "❌ بيانات غير مكتملة!",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='back_main')]])
        )
        return

    total_expected = len(emails) * len(accounts) * count
    job = {
        "message_id": msg_id,
        "message_subject": msg['subject'],
        "recipients": emails,
        "accounts": [a['email'] for a in accounts],
        "count": count,
        "delay": delay
    }
    job_id = data_store.user(uid).add_send_job(job)

    def _progress_text(sent, success, failed, batch, total_batches, status="🚀 جاري الإرسال..."):
        bar_len = 10
        filled = int(bar_len * sent / total_expected) if total_expected else bar_len
        bar = "█" * filled + "░" * (bar_len - filled)
        return (
            f"{status}\n\n"
            f"📄 الرسالة: {msg['subject']}\n"
            f"📊 [{bar}] {sent}/{total_expected}\n"
            f"✅ ناجح: {success}   ❌ فاشل: {failed}\n"
            f"🔄 الدفعة: {batch}/{total_batches}\n"
            f"⏱️ التأخير: {delay}ث   🆔 مهمة: {job_id}"
        )

    await progress_msg.edit_text(_progress_text(0, 0, 0, 0, count))

    all_results = []
    sent_so_far = 0
    success_so_far = 0
    failed_so_far = 0

    for batch in range(count):
        batch_results = await email_sender.send_from_multiple_accounts(
            accounts, emails, msg['subject'], msg['body']
        )
        all_results.extend(batch_results)
        for r in batch_results:
            sent_so_far += 1
            if r['success']:
                success_so_far += 1
            else:
                failed_so_far += 1

        try:
            await progress_msg.edit_text(
                _progress_text(sent_so_far, success_so_far, failed_so_far, batch + 1, count)
            )
        except Exception:
            pass

        if batch < count - 1 and delay > 0:
            await asyncio.sleep(delay)

    data_store.user(uid).update_send_job(job_id, "completed", all_results)

    # Final summary
    result_text = (
        f"✅ اكتمل الإرسال!\n\n"
        f"📊 الإحصائيات:\n"
        f"• إجمالي المحاولات: {sent_so_far}\n"
        f"• الناجح: {success_so_far}\n"
        f"• الفاشل: {failed_so_far}\n\n"
        f"📧 تفاصيل الحسابات:\n"
    )
    account_stats = {}
    for r in all_results:
        acc = r['from']
        if acc not in account_stats:
            account_stats[acc] = {'success': 0, 'failed': 0}
        if r['success']:
            account_stats[acc]['success'] += 1
        else:
            account_stats[acc]['failed'] += 1
    for acc, stats in account_stats.items():
        status_icon = "✅" if stats['failed'] == 0 else "⚠️"
        result_text += f"{status_icon} {acc}: {stats['success']} نجاح, {stats['failed']} فشل\n"
    errors = [r for r in all_results if r.get('error') and not r['success']]
    if errors:
        result_text += "\n❌ بعض الأخطاء:\n"
        for i, r in enumerate(errors[:3], 1):
            result_text += f"{i}. {r['from']}: {str(r['error'])[:40]}\n"

    context.user_data['last_job_id'] = job_id
    context.user_data['send_uid'] = uid
    keyboard = [
        [InlineKeyboardButton("🔍 مراقبة قناة/حساب منتهك", callback_data='ask_monitor_target')],
        [InlineKeyboardButton("🔙 رجوع للقائمة", callback_data='back_main')],
    ]
    await progress_msg.edit_text(result_text[:4000], reply_markup=InlineKeyboardMarkup(keyboard))

# Old execute_send - redirect to new flow
async def execute_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_save_accounts(update, context)

# Status Menu
async def menu_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    uid = update.effective_user.id
    jobs = data_store.user(uid).get_send_jobs()
    
    monitor_status_map = {
        "watching": "⏳ قيد التنفيذ",
        "deleted":  "✅ تم الحذف",
        "stopped":  "⛔ موقوف",
        "expired":  "⌛ انتهت المهلة",
    }

    if not jobs:
        status_text = "لا توجد مهام إرسال سابقة."
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='back_main')]]
    else:
        status_text = "📊 حالة المهام:\n\n"
        keyboard = []
        for job in jobs[-5:]:
            status_icon = "🟡" if job['status'] == 'pending' else \
                         "🟢" if job['status'] == 'completed' else "🔴"
            mon = job.get('monitor_status')
            mon_label = ""
            if job.get('monitor_target'):
                mon_label = f"\n   🔍 {job['monitor_target']} → {monitor_status_map.get(mon, mon)}"
            status_text += f"{status_icon} مهمة #{job['id']}: {job.get('message_subject', 'N/A')}{mon_label}\n\n"
            if mon == "watching":
                keyboard.append([InlineKeyboardButton(
                    f"⛔ إيقاف مراقبة مهمة #{job['id']}",
                    callback_data=f"stop_monitor_{job['id']}"
                )])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='back_main')])
    
    await query.edit_message_text(status_text, reply_markup=InlineKeyboardMarkup(keyboard))

# Back handlers
async def back_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await start(update, context)

async def back_to_accounts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to account selection in send flow"""
    query = update.callback_query
    await query.answer()
    await send_select_accounts(query, context)

async def back_to_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to message count selection in send flow"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("1 مرة", callback_data='count_1')],
        [InlineKeyboardButton("5 مرات", callback_data='count_5')],
        [InlineKeyboardButton("10 مرات", callback_data='count_10')],
        [InlineKeyboardButton("25 مرة", callback_data='count_25')],
        [InlineKeyboardButton("50 مرة", callback_data='count_50')],
        [InlineKeyboardButton("✏️ عدد مخصص", callback_data='count_custom')],
        [InlineKeyboardButton("🔙 رجوع للحسابات", callback_data='back_to_accounts')],
    ]
    await query.edit_message_text(
        "🔢 كم مرة تريد إرسال الرسالة؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def back_to_recipients(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Go back to recipient selection in send flow"""
    query = update.callback_query
    await query.answer()
    
    uid = update.effective_user.id
    recipients = data_store.user(uid).get_recipients()
    keyboard = []
    for rec in recipients:
        keyboard.append([InlineKeyboardButton(f"👥 {rec['name']} ({len(rec['emails'])})", callback_data=f"send_rec_{rec['id']}")])
    keyboard.append([InlineKeyboardButton("📨 إيميلات دعم تيليجرام", callback_data='send_tg_emails')])
    keyboard.append([InlineKeyboardButton("✏️ إدخال يدوي", callback_data='send_rec_manual')])
    keyboard.append([InlineKeyboardButton("🔙 رجوع لاختيار الرسالة", callback_data='menu_send')])
    
    await query.edit_message_text(
        "👥 اختر قائمة المستلمين:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ───────────────────────── TELEGRAM EMAILS SELECTOR ─────────────────────────

def _build_tg_emails_keyboard(selected: set, from_send: bool = False):
    """Build inline keyboard with checkboxes for each Telegram support email."""
    keyboard = []
    for email in TELEGRAM_SUPPORT_EMAILS:
        mark = "✅" if email in selected else "❌"
        keyboard.append([InlineKeyboardButton(
            f"{mark} {email}",
            callback_data=f"tge_toggle_{TELEGRAM_SUPPORT_EMAILS.index(email)}"
        )])
    keyboard.append([
        InlineKeyboardButton("☑️ تحديد الكل", callback_data='tge_all'),
        InlineKeyboardButton("🔲 إلغاء الكل", callback_data='tge_none'),
    ])
    keyboard.append([InlineKeyboardButton("💾 حفظ كقائمة", callback_data='tge_save')])
    if from_send:
        keyboard.append([InlineKeyboardButton("✅ استخدام الآن للإرسال", callback_data='tge_use_send')])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='menu_recipients' if not from_send else 'back_to_recipients')])
    return keyboard


async def tg_emails_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.setdefault('tge_selected', set())
    context.user_data['tge_from_send'] = False
    keyboard = _build_tg_emails_keyboard(context.user_data['tge_selected'], from_send=False)
    await query.edit_message_text(
        "📨 *إيميلات دعم تيليجرام*\n\n"
        "اختر الإيميلات التي تريد استخدامها:\n"
        "(✅ = محدد، ❌ = غير محدد)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def send_tg_emails(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Called from send flow recipient selection."""
    query = update.callback_query
    await query.answer()
    context.user_data.setdefault('tge_selected', set())
    context.user_data['tge_from_send'] = True
    keyboard = _build_tg_emails_keyboard(context.user_data['tge_selected'], from_send=True)
    await query.edit_message_text(
        "📨 *إيميلات دعم تيليجرام*\n\n"
        "اختر الإيميلات للإرسال:\n"
        "(✅ = محدد، ❌ = غير محدد)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def tge_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    idx = int(query.data.split('_')[2])
    email = TELEGRAM_SUPPORT_EMAILS[idx]
    selected: set = context.user_data.setdefault('tge_selected', set())
    if email in selected:
        selected.discard(email)
    else:
        selected.add(email)
    from_send = context.user_data.get('tge_from_send', False)
    keyboard = _build_tg_emails_keyboard(selected, from_send=from_send)
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))


async def tge_select_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['tge_selected'] = set(TELEGRAM_SUPPORT_EMAILS)
    from_send = context.user_data.get('tge_from_send', False)
    keyboard = _build_tg_emails_keyboard(context.user_data['tge_selected'], from_send=from_send)
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))


async def tge_deselect_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['tge_selected'] = set()
    from_send = context.user_data.get('tge_from_send', False)
    keyboard = _build_tg_emails_keyboard(set(), from_send=from_send)
    await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(keyboard))


async def tge_use_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Use selected emails directly in send flow without saving."""
    query = update.callback_query
    await query.answer()
    selected = list(context.user_data.get('tge_selected', []))
    if not selected:
        await query.answer("⚠️ لم تحدد أي إيميل!", show_alert=True)
        return
    context.user_data['send_emails'] = selected
    await query.edit_message_text(f"✅ تم اختيار {len(selected)} إيميل من دعم تيليجرام")
    await send_select_accounts(query, context)


async def tge_save_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for list name to save the selected TG emails."""
    query = update.callback_query
    await query.answer()
    selected = context.user_data.get('tge_selected', set())
    if not selected:
        await query.answer("⚠️ لم تحدد أي إيميل!", show_alert=True)
        return
    context.user_data['tge_save_list'] = list(selected)
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_recipients')]]
    await query.edit_message_text(
        f"💾 أرسل اسماً للقائمة ({len(selected)} إيميل):",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REC_NAME


async def tge_save_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("❌ الاسم فارغ. أرسل اسماً صالحاً:")
        return REC_NAME
    emails = context.user_data.get('tge_save_list', [])
    uid = update.effective_user.id
    rec_id = data_store.user(uid).add_recipients(name, emails)
    keyboard = [[InlineKeyboardButton("🔙 رجوع للمستلمين", callback_data='menu_recipients')]]
    await update.message.reply_text(
        f"✅ تم حفظ قائمة *{name}* (رقم {rec_id}) بـ {len(emails)} إيميل.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


# ───────────────────────── CHANNEL MONITOR ─────────────────────────

import urllib.request

async def ask_monitor_target(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask user if they want to monitor a target channel after send."""
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("🔙 رجوع للقائمة", callback_data='back_main')],
    ]
    await query.edit_message_text(
        "🔍 *مراقبة القناة/الحساب المنتهك*\n\n"
        "أرسل يوزر أو رابط القناة/الحساب المستهدف:\n\n"
        "مثال: `@channelname` أو `https://t.me/channelname`\n\n"
        "سيفحص البوت كل 5 دقائق ويُبلغك عند الحذف.\n"
        "_(أو أرسل /skip للتخطي)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return SEND_MONITOR


async def monitor_target_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() in ['/skip', 'skip', 'تخطي']:
        keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة", callback_data='back_main')]]
        await update.message.reply_text("✅ تم التخطي.", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END

    target = text.replace("https://t.me/", "@").strip()
    if not target.startswith("@") and not target.lstrip("+").isdigit():
        target = "@" + target.lstrip("@")

    job_id = context.user_data.get('last_job_id')
    uid = context.user_data.get('send_uid', update.effective_user.id)

    if job_id:
        from datetime import datetime as _dt
        data_store.user(uid).update_send_job_monitor(
            job_id,
            monitor_target=target,
            monitor_status="watching",
            monitor_started=_dt.now().isoformat(),
            monitor_last_check=None,
            monitor_checks_count=0,
        )

    keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة", callback_data='back_main')]]
    await update.message.reply_text(
        f"✅ تم بدء مراقبة `{target}`\n\n"
        f"🔍 سيفحص البوت كل 5 دقائق.\n"
        f"⌛ يتوقف تلقائياً بعد يومين.\n"
        f"📊 يمكنك متابعة الحالة من *حالة الإرسال*.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

    asyncio.create_task(monitor_channel_loop(uid, job_id, target, context))
    return ConversationHandler.END


async def monitor_channel_loop(uid: int, job_id: int, target: str, context):
    """Background task: checks t.me/<target> every 5 min for up to 2 days."""
    from datetime import datetime as _dt, timedelta as _td
    import urllib.request as _req

    max_duration = _td(days=2)
    interval = 300  # 5 minutes
    started = _dt.now()

    username = target.lstrip("@")
    url = f"https://t.me/{username}"

    while True:
        await asyncio.sleep(interval)
        elapsed = _dt.now() - started

        store = data_store.user(uid)
        jobs = store.get_send_jobs()
        job = next((j for j in jobs if j.get("id") == job_id), None)
        if not job or job.get("monitor_status") != "watching":
            break

        if elapsed >= max_duration:
            store.update_send_job_monitor(job_id, monitor_status="expired")
            try:
                await context.bot.send_message(
                    chat_id=uid,
                    text=f"⌛ انتهت مهلة مراقبة `{target}` (يومين) بدون حذف.",
                    parse_mode="Markdown"
                )
            except Exception:
                pass
            break

        try:
            def _check():
                try:
                    r = _req.urlopen(url, timeout=10)
                    return r.status == 200
                except Exception:
                    return False

            still_exists = await asyncio.to_thread(_check)
            store.update_send_job_monitor(
                job_id,
                monitor_last_check=_dt.now().isoformat(),
                monitor_checks_count=job.get("monitor_checks_count", 0) + 1,
            )

            if not still_exists:
                store.update_send_job_monitor(job_id, monitor_status="deleted")
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"🎉 تم حذف `{target}` بنجاح!\n\n✅ القناة/الحساب لم تعد موجودة.",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
                break
        except Exception:
            pass


async def stop_monitor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    job_id = int(query.data.split('_')[2])
    uid = update.effective_user.id
    data_store.user(uid).update_send_job_monitor(job_id, monitor_status="stopped")
    await menu_status(update, context)


# ───────────────────────── TELEGRAM INTERNAL REPORT ─────────────────────────

async def menu_tg_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await check_subscription(update, "telegram"):
        return
    keyboard = [
        [InlineKeyboardButton("📱 إدارة الجلسات", callback_data='menu_tg_sessions')],
        [InlineKeyboardButton("🎯 إدارة الأهداف", callback_data='menu_tg_targets')],
        [InlineKeyboardButton("🚀 تنفيذ إبلاغ", callback_data='menu_tg_execute')],
        [InlineKeyboardButton("📊 حالة الإبلاغات", callback_data='menu_tg_status')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='back_main')],
    ]
    await query.edit_message_text(
        "📱 *الشد الداخلي*\n\n"
        "إبلاغ داخلي عبر حسابك الشخصي في تليجرام.\n\n"
        "اختر من القائمة:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── Sessions ──
async def menu_tg_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await check_subscription(update, "telegram"):
        return
    uid = update.effective_user.id
    sessions = data_store.user(uid).get_telegram_sessions()
    text = "📱 الجلسات:\n\n"
    for s in sessions:
        text += f"ID: {s['id']} - {s['phone']}\n"
    if not sessions:
        text = "لا توجد جلسات مسجلة."
    keyboard = [
        [InlineKeyboardButton("➕ إضافة جلسة", callback_data='add_tg_session')],
        [InlineKeyboardButton("🗑️ حذف جلسة", callback_data='remove_tg_session')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_report')],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def add_tg_session_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_tg_sessions')]]
    await query.edit_message_text(
        "🔧 أرسل API ID من my.telegram.org:\n\n"
        "(رقم مثل: 12345)",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TG_API_ID


async def add_tg_api_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        api_id = int(text)
    except ValueError:
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_tg_sessions')]]
        await update.message.reply_text(
            "❌ API ID يجب أن يكون رقماً. أرسل مرة أخرى:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return TG_API_ID
    context.user_data['tg_api_id'] = api_id
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_tg_sessions')]]
    await update.message.reply_text(
        "🔑 أرسل API Hash من my.telegram.org:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TG_API_HASH


async def add_tg_api_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    api_hash = update.message.text.strip()
    if len(api_hash) < 5:
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_tg_sessions')]]
        await update.message.reply_text(
            "❌ API Hash غير صحيح. أرسل مرة أخرى:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return TG_API_HASH
    context.user_data['tg_api_hash'] = api_hash
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_tg_sessions')]]
    await update.message.reply_text(
        "📱 أرسل رقم الهاتف مع رمز الدولة:\n\n"
        "مثال: +1234567890",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TG_PHONE


async def add_tg_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not phone.startswith('+') or len(phone) < 8:
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_tg_sessions')]]
        await update.message.reply_text(
            "❌ رقم الهاتف يجب أن يبدأ بـ + ويكون صحيحاً. أرسل مرة أخرى:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return TG_PHONE
    context.user_data['tg_phone'] = phone
    api_id = context.user_data['tg_api_id']
    api_hash = context.user_data['tg_api_hash']
    await update.message.reply_text("🔄 جاري إرسال كود التحقق...")
    result = await tg_reporter.send_code(api_id, api_hash, phone)
    if not result['success']:
        keyboard = [
            [InlineKeyboardButton("🔄 إعادة المحاولة", callback_data='add_tg_session')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_sessions')]
        ]
        await update.message.reply_text(
            f"❌ {result['error']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
    context.user_data['tg_phone_code_hash'] = result['phone_code_hash']
    context.user_data['tg_temp_session'] = result['temp_session']
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_tg_sessions')]]
    await update.message.reply_text(
        "📨 أرسل كود التحقق الذي وصلك في تليجرام:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return TG_CODE


async def add_tg_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    api_id = context.user_data['tg_api_id']
    api_hash = context.user_data['tg_api_hash']
    phone = context.user_data['tg_phone']
    phone_code_hash = context.user_data['tg_phone_code_hash']
    temp_session = context.user_data['tg_temp_session']
    await update.message.reply_text("🔄 جاري التحقق من الكود...")
    result = await tg_reporter.verify_code(
        api_id, api_hash, phone, code, phone_code_hash, temp_session
    )
    if result.get('needs_password'):
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_tg_sessions')]]
        await update.message.reply_text(
            "🔐 مطلوب كلمة مرور المصادقة الثنائية (2FA):\n\n"
            "أرسل كلمة المرور:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return TG_2FA
    if not result['success']:
        keyboard = [
            [InlineKeyboardButton("🔄 إعادة المحاولة", callback_data='add_tg_session')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_sessions')]
        ]
        await update.message.reply_text(
            f"❌ {result['error']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
    uid = update.effective_user.id
    data_store.user(uid).add_telegram_session(
        phone, api_id, api_hash, result['session_string']
    )
    keyboard = [[InlineKeyboardButton("🔙 رجوع للجلسات", callback_data='menu_tg_sessions')]]
    await update.message.reply_text(
        f"✅ تم تسجيل الدخول بنجاح!\n\n📱 {phone}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


async def add_tg_2fa(update: Update, context: ContextTypes.DEFAULT_TYPE):
    password = update.message.text.strip()
    api_id = context.user_data['tg_api_id']
    api_hash = context.user_data['tg_api_hash']
    phone = context.user_data['tg_phone']
    phone_code_hash = context.user_data['tg_phone_code_hash']
    temp_session = context.user_data['tg_temp_session']
    await update.message.reply_text("🔄 جاري التحقق من كلمة المرور...")
    result = await tg_reporter.verify_code(
        api_id, api_hash, phone, "", phone_code_hash, temp_session, password
    )
    if not result['success']:
        keyboard = [
            [InlineKeyboardButton("🔄 إعادة المحاولة", callback_data='add_tg_session')],
            [InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_sessions')]
        ]
        await update.message.reply_text(
            f"❌ {result['error']}",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return ConversationHandler.END
    uid = update.effective_user.id
    data_store.user(uid).add_telegram_session(
        phone, api_id, api_hash, result['session_string']
    )
    keyboard = [[InlineKeyboardButton("🔙 رجوع للجلسات", callback_data='menu_tg_sessions')]]
    await update.message.reply_text(
        f"✅ تم تسجيل الدخول بنجاح!\n\n📱 {phone}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


async def cancel_add_tg_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await menu_tg_sessions(update, context)
    return ConversationHandler.END


async def remove_tg_session_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    sessions = data_store.user(uid).get_telegram_sessions()
    if not sessions:
        await query.edit_message_text(
            "لا توجد جلسات لحذفها.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_sessions')]]
            )
        )
        return
    keyboard = []
    for s in sessions:
        keyboard.append([InlineKeyboardButton(f"🗑️ {s['phone']}", callback_data=f"del_tgs_{s['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_sessions')])
    await query.edit_message_text("اختر الجلسة للحذف:", reply_markup=InlineKeyboardMarkup(keyboard))


async def remove_tg_session_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    sess_id = int(query.data.split('_')[2])
    data_store.user(update.effective_user.id).remove_telegram_session(sess_id)
    await menu_tg_sessions(update, context)


# ── Targets ──
async def menu_tg_targets(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await check_subscription(update, "telegram"):
        return
    uid = update.effective_user.id
    targets = data_store.user(uid).get_report_targets()
    text = "🎯 قوائم الأهداف:\n\n"
    for t in targets:
        text += f"ID: {t['id']} - {t['name']} ({len(t['targets'])} هدف)\n"
    if not targets:
        text = "لا توجد قوائم أهداف."
    keyboard = [
        [InlineKeyboardButton("➕ إضافة قائمة", callback_data='add_tg_target')],
        [InlineKeyboardButton("👀 عرض التفاصيل", callback_data='view_tg_target')],
        [InlineKeyboardButton("🗑️ حذف قائمة", callback_data='remove_tg_target')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_report')],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def add_tg_target_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_tg_targets')]]
    await query.edit_message_text(
        "🎯 أرسل اسم للقائمة:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REP_NAME


async def add_tg_target_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() in ['cancel', 'إلغاء', '/cancel']:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_targets')]]
        await update.message.reply_text("❌ تم الإلغاء.", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
    context.user_data['rep_name'] = text
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_tg_targets')]]
    await update.message.reply_text(
        "🎯 أرسل اليوزرات أو الأيدي مفصولة بفاصلة أو سطر جديد:\n\n"
        "مثال: @user1, @user2, @channel1",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REP_TARGETS


async def add_tg_target_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text.lower() in ['cancel', 'إلغاء', '/cancel']:
        keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_targets')]]
        await update.message.reply_text("❌ تم الإلغاء.", reply_markup=InlineKeyboardMarkup(keyboard))
        return ConversationHandler.END
    name = context.user_data['rep_name']
    targets = [t.strip() for t in text.replace(',', '\n').split('\n') if t.strip()]
    if not targets:
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_tg_targets')]]
        await update.message.reply_text(
            "❌ لا يوجد هدف صحيح. أرسل مرة أخرى:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return REP_TARGETS
    rec_id = data_store.user(update.effective_user.id).add_report_targets(name, targets)
    keyboard = [[InlineKeyboardButton("🔙 رجوع للأهداف", callback_data='menu_tg_targets')]]
    await update.message.reply_text(
        f"✅ تم حفظ القائمة '{name}' برقم: {rec_id}\n🎯 {len(targets)} هدف",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


async def remove_tg_target_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    targets = data_store.user(uid).get_report_targets()
    if not targets:
        await query.edit_message_text(
            "لا توجد قوائم لحذفها.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_targets')]]
            )
        )
        return
    keyboard = []
    for t in targets:
        keyboard.append([InlineKeyboardButton(f"🗑️ {t['name']}", callback_data=f"del_tgr_{t['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_targets')])
    await query.edit_message_text("اختر قائمة للحذف:", reply_markup=InlineKeyboardMarkup(keyboard))


async def remove_tg_target_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rec_id = int(query.data.split('_')[2])
    data_store.user(update.effective_user.id).remove_report_targets(rec_id)
    await menu_tg_targets(update, context)


async def view_tg_target_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    targets = data_store.user(uid).get_report_targets()
    if not targets:
        await query.edit_message_text(
            "لا توجد قوائم لعرضها.",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_targets')]]
            )
        )
        return
    keyboard = []
    for t in targets:
        keyboard.append([InlineKeyboardButton(f"👀 {t['name']}", callback_data=f"view_tgr_{t['id']}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_targets')])
    await query.edit_message_text("اختر قائمة لعرض التفاصيل:", reply_markup=InlineKeyboardMarkup(keyboard))


async def view_tg_target_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    rec_id = int(query.data.split('_')[2])
    rec = data_store.user(update.effective_user.id).get_report_target(rec_id)
    if rec:
        targets_text = '\n'.join(rec['targets'])
        text = f"🎯 {rec['name']}\n\n{targets_text}"
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_targets')]]
            )
        )
    else:
        await menu_tg_targets(update, context)


# ── Execute Report ──
async def menu_tg_execute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await check_subscription(update, "telegram"):
        return
    uid = update.effective_user.id
    sessions = data_store.user(uid).get_telegram_sessions()
    targets = data_store.user(uid).get_report_targets()
    if not sessions:
        await query.edit_message_text(
            "❌ لا توجد جلسات مسجلة!\n"
            "أضف جلسة أولاً من 'إدارة الجلسات'",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_report')]]
            )
        )
        return
    if not targets:
        await query.edit_message_text(
            "❌ لا توجد قوائم أهداف!\n"
            "أضف قائمة أولاً من 'إدارة الأهداف'",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_report')]]
            )
        )
        return
    keyboard = []
    for t in targets:
        keyboard.append([InlineKeyboardButton(
            f"🎯 {t['name']} ({len(t['targets'])} هدف)",
            callback_data=f"rep_sel_target_{t['id']}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_report')])
    await query.edit_message_text(
        "🚀 اختر قائمة الأهداف للإبلاغ:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def tg_select_target_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_id = int(query.data.split('_')[3])
    rec = data_store.user(update.effective_user.id).get_report_target(target_id)
    if rec:
        context.user_data['rep_target_id'] = target_id
        context.user_data['rep_targets'] = rec['targets']
        keyboard = []
        for key, label in tg_reporter.get_reason_choices():
            keyboard.append([InlineKeyboardButton(label, callback_data=f"rep_reason_{key}")])
        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_execute')])
        await query.edit_message_text(
            "⚠️ اختر نوع الإبلاغ:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await menu_tg_execute(update, context)


async def tg_select_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    reason = query.data.split('_')[2]
    context.user_data['rep_reason'] = reason
    keyboard = [
        [InlineKeyboardButton("1 مرة", callback_data='rep_count_1')],
        [InlineKeyboardButton("5 مرات", callback_data='rep_count_5')],
        [InlineKeyboardButton("10 مرات", callback_data='rep_count_10')],
        [InlineKeyboardButton("25 مرة", callback_data='rep_count_25')],
        [InlineKeyboardButton("50 مرة", callback_data='rep_count_50')],
        [InlineKeyboardButton("✏️ عدد مخصص", callback_data='rep_count_custom')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_execute')],
    ]
    await query.edit_message_text(
        "🔢 كم مرة تريد الإبلاغ على كل هدف؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def tg_custom_text_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['rep_reason'] = 'other'
    keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_tg_execute')]]
    await query.edit_message_text(
        "✏️ أرسل نص الرسالة/الكليشة للإبلاغ:\n\n"
        "هذا النص سيُرسل كتفاصيل إضافية مع الإبلاغ من نوع 'أخرى'.",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return REP_CUSTOM_TEXT


async def tg_custom_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text:
        keyboard = [[InlineKeyboardButton("❌ إلغاء", callback_data='menu_tg_execute')]]
        await update.message.reply_text(
            "❌ النص فارغ. أرسل نصاً صالحاً:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return REP_CUSTOM_TEXT
    context.user_data['rep_custom_text'] = text
    await update.message.reply_text(f"✅ تم حفظ نص الإبلاغ: {text[:50]}{'...' if len(text) > 50 else ''}")
    keyboard = [
        [InlineKeyboardButton("1 مرة", callback_data='rep_count_1')],
        [InlineKeyboardButton("5 مرات", callback_data='rep_count_5')],
        [InlineKeyboardButton("10 مرات", callback_data='rep_count_10')],
        [InlineKeyboardButton("25 مرة", callback_data='rep_count_25')],
        [InlineKeyboardButton("50 مرة", callback_data='rep_count_50')],
        [InlineKeyboardButton("✏️ عدد مخصص", callback_data='rep_count_custom')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_execute')],
    ]
    await update.message.reply_text(
        "🔢 كم مرة تريد الإبلاغ على كل هدف؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


async def tg_count_custom_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔢 أرسل عدد مرات الإبلاغ (رقم):\n\n"
        "مثال: 100"
    )
    return REP_COUNT


async def tg_count_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text.strip())
        if count < 1:
            await update.message.reply_text("❌ العدد يجب أن يكون 1 أو أكثر")
            return REP_COUNT
        if count > 1000:
            await update.message.reply_text("❌ الحد الأقصى 1000")
            return REP_COUNT
        context.user_data['rep_count'] = count
        await update.message.reply_text(f"✅ عدد المرات: {count}")
        await tg_ask_delay_message(update, context)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ أرسل رقماً صحيحاً")
        return REP_COUNT


async def tg_select_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    count = int(query.data.split('_')[2])
    context.user_data['rep_count'] = count
    await tg_ask_delay(query, context)


async def tg_ask_delay(query, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⚡ بدون تأخير", callback_data='rep_delay_0')],
        [InlineKeyboardButton("🚀 1 ثانية", callback_data='rep_delay_1')],
        [InlineKeyboardButton("⏱️ 5 ثواني", callback_data='rep_delay_5')],
        [InlineKeyboardButton("⏱️ 10 ثواني", callback_data='rep_delay_10')],
        [InlineKeyboardButton("⏱️ 30 ثانية", callback_data='rep_delay_30')],
        [InlineKeyboardButton("⏱️ 60 ثانية", callback_data='rep_delay_60')],
        [InlineKeyboardButton("✏️ مدة مخصصة", callback_data='rep_delay_custom')],
        [InlineKeyboardButton("🔙 رجوع لعدد المرات", callback_data='back_to_rep_count')],
    ]
    await query.edit_message_text(
        "⏱️ اختر الفاصل بين كل إبلاغ:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def tg_ask_delay_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("⚡ بدون تأخير", callback_data='rep_delay_0')],
        [InlineKeyboardButton("🚀 1 ثانية", callback_data='rep_delay_1')],
        [InlineKeyboardButton("⏱️ 5 ثواني", callback_data='rep_delay_5')],
        [InlineKeyboardButton("⏱️ 10 ثواني", callback_data='rep_delay_10')],
        [InlineKeyboardButton("⏱️ 30 ثانية", callback_data='rep_delay_30')],
        [InlineKeyboardButton("⏱️ 60 ثانية", callback_data='rep_delay_60')],
        [InlineKeyboardButton("✏️ مدة مخصصة", callback_data='rep_delay_custom')],
        [InlineKeyboardButton("🔙 رجوع لعدد المرات", callback_data='back_to_rep_count')],
    ]
    await update.message.reply_text(
        "⏱️ اختر الفاصل بين كل إبلاغ:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def tg_delay_custom_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "⏱️ أرسل عدد الثواني بين كل إبلاغ:\n\n"
        "مثال: 5\n"
        "0 = بدون تأخير"
    )
    return REP_DELAY


async def tg_delay_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        delay = int(update.message.text.strip())
        if delay < 0:
            delay = 0
        if delay > 3600:
            await update.message.reply_text("❌ الحد الأقصى 3600 ثانية (ساعة)")
            return REP_DELAY
        context.user_data['rep_delay'] = delay
        await update.message.reply_text(f"✅ التأخير: {delay} ثانية")
        await execute_tg_report(update, context)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ أرسل رقماً صحيحاً")
        return REP_DELAY


async def tg_select_delay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    delay = int(query.data.split('_')[2])
    context.user_data['rep_delay'] = delay
    await execute_tg_report_query(query, context)


async def execute_tg_report_query(query, context: ContextTypes.DEFAULT_TYPE):
    uid = query.from_user.id
    await execute_tg_report_common(query.edit_message_text, context, uid)


async def execute_tg_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await execute_tg_report_common(update.message.reply_text, context, uid)


async def execute_tg_report_common(reply_func, context: ContextTypes.DEFAULT_TYPE, uid: int):
    targets = context.user_data.get('rep_targets', [])
    reason = context.user_data.get('rep_reason', 'spam')
    count = context.user_data.get('rep_count', 1)
    delay = context.user_data.get('rep_delay', 0)
    if not targets:
        await reply_func(
            "❌ بيانات غير مكتملة!",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_report')]]
            )
        )
        return
    sessions = data_store.user(uid).get_telegram_sessions()
    if not sessions:
        await reply_func(
            "❌ لا توجد جلسات مسجلة!",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_report')]]
            )
        )
        return
    # Use the first session for reporting
    session = sessions[0]
    job = {
        "reason": reason,
        "targets": targets,
        "session_phone": session['phone'],
        "count": count,
        "delay": delay
    }
    job_id = data_store.user(uid).add_report_job(job)
    status_text = (
        f"🚀 بدء الإبلاغ...\n\n"
        f"🎯 الأهداف: {len(targets)}\n"
        f"📱 الجلسة: {session['phone']}\n"
        f"⚠️ السبب: {tg_reporter.REASON_LABELS.get(reason, reason)}\n"
        f"🔢 عدد المرات لكل هدف: {count}\n"
        f"⏱️ التأخير: {delay} ثانية\n"
        f"📊 إجمالي الإبلاغات: {len(targets) * count}\n"
        f"🆔 رقم المهمة: {job_id}"
    )
    await reply_func(status_text)
    all_results = []
    total_batches = count
    custom_message = context.user_data.get('rep_custom_text', '')
    for batch in range(total_batches):
        batch_results = []
        for target in targets:
            result = await tg_reporter.report(
                session['api_id'],
                session['api_hash'],
                session['session_string'],
                target,
                reason,
                custom_message=custom_message
            )
            batch_results.append({
                "target": target,
                "success": result['success'],
                "error": result.get('error')
            })
            if delay > 0:
                await asyncio.sleep(delay)
        all_results.extend(batch_results)
        if batch < total_batches - 1 and delay > 0:
            await reply_func(
                f"🔄 الدفعة {batch + 1}/{total_batches} اكتملت..."
            )
    success_count = sum(1 for r in all_results if r['success'])
    total_sent = len(all_results)
    data_store.user(uid).update_report_job(job_id, "completed", all_results)
    result_text = (
        f"✅ اكتمل الإبلاغ!\n\n"
        f"📊 الإحصائيات:\n"
        f"• إجمالي المحاولات: {total_sent}\n"
        f"• الناجح: {success_count}\n"
        f"• الفاشل: {total_sent - success_count}\n\n"
    )
    errors = [r for r in all_results if r['error'] and not r['success']]
    if errors:
        result_text += "❌ بعض الأخطاء:\n"
        for i, r in enumerate(errors[:5], 1):
            result_text += f"{i}. {r['target']}: {r['error'][:40]}...\n"
    keyboard = [[InlineKeyboardButton("🔙 رجوع للقائمة", callback_data='menu_tg_report')]]
    await reply_func(result_text[:4000], reply_markup=InlineKeyboardMarkup(keyboard))


async def back_to_rep_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("1 مرة", callback_data='rep_count_1')],
        [InlineKeyboardButton("5 مرات", callback_data='rep_count_5')],
        [InlineKeyboardButton("10 مرات", callback_data='rep_count_10')],
        [InlineKeyboardButton("25 مرة", callback_data='rep_count_25')],
        [InlineKeyboardButton("50 مرة", callback_data='rep_count_50')],
        [InlineKeyboardButton("✏️ عدد مخصص", callback_data='rep_count_custom')],
        [InlineKeyboardButton("🔙 رجوع لاختيار الهدف", callback_data='menu_tg_execute')],
    ]
    await query.edit_message_text(
        "🔢 كم مرة تريد الإبلاغ على كل هدف؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ── Status ──
async def menu_tg_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    uid = update.effective_user.id
    jobs = data_store.user(uid).get_report_jobs()
    if not jobs:
        status_text = "لا توجد مهام إبلاغ سابقة."
    else:
        status_text = "📊 حالة مهام الإبلاغ:\n\n"
        for job in jobs[-5:]:
            status_icon = "🟡" if job['status'] == 'pending' else \
                         "🟢" if job['status'] == 'completed' else "🔴"
            status_text += f"{status_icon} مهمة #{job['id']}: {job.get('reason', 'N/A')} - {job['status']}\n"
    keyboard = [[InlineKeyboardButton("🔙 رجوع", callback_data='menu_tg_report')]]
    await query.edit_message_text(status_text, reply_markup=InlineKeyboardMarkup(keyboard))


# ───────────────────────── OWNER PANEL ─────────────────────────

async def owner_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        await query.answer("⛔ غير مسموح!", show_alert=True)
        return

    users = data_store.get_all_users()
    active = sum(1 for u in users if data_store.is_subscribed(u["user_id"]))
    keyboard = [
        [InlineKeyboardButton("➕ إضافة مشترك", callback_data='owner_add')],
        [InlineKeyboardButton("✏️ تعديل مشترك", callback_data='owner_edit')],
        [InlineKeyboardButton("🗑️ حذف مشترك", callback_data='owner_remove')],
        [InlineKeyboardButton("👥 عرض المشتركين", callback_data='owner_list')],
        [InlineKeyboardButton("🔙 رجوع", callback_data='back_main')],
    ]
    await query.edit_message_text(
        f"👑 *لوحة تحكم المالك*\n\n"
        f"إجمالي المشتركين: {len(users)}\n"
        f"النشطون حالياً: {active}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def owner_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return

    users = data_store.get_all_users()
    if not users:
        await query.edit_message_text(
            "لا يوجد مشتركون.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='owner_panel')]])
        )
        return

    text = "👥 *قائمة المشتركين:*\n\n"
    for u in users:
        status = "✅" if data_store.is_subscribed(u["user_id"]) else "❌ منتهي"
        plan_label = "⭐ VIP" if u["plan"] == PLAN_VIP else "🔵 Basic"
        name = u.get("username") or str(u["user_id"])
        text += f"• {name} | {plan_label} | ينتهي: {u['expire_date']} {status}\n  ID: `{u['user_id']}`\n\n"

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='owner_panel')]])
    )


async def owner_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return
    await query.edit_message_text(
        "➕ *إضافة مشترك جديد*\n\nأرسل الـ User ID الخاص بالمستخدم:\n(رقم مثل: 123456789)",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data='owner_panel')]])
    )
    return OWNER_ADD_ID


async def owner_add_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        uid = int(text)
    except ValueError:
        await update.message.reply_text("❌ أرسل رقماً صحيحاً (User ID).")
        return OWNER_ADD_ID
    context.user_data['new_sub_id'] = uid
    keyboard = [
        [InlineKeyboardButton("🔵 Basic", callback_data='subplan_basic')],
        [InlineKeyboardButton("⭐ VIP", callback_data='subplan_vip')],
        [InlineKeyboardButton("❌ إلغاء", callback_data='owner_panel')],
    ]
    await update.message.reply_text("📋 اختر الخطة:", reply_markup=InlineKeyboardMarkup(keyboard))
    return OWNER_ADD_PLAN


async def owner_add_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = PLAN_VIP if query.data == 'subplan_vip' else PLAN_BASIC
    context.user_data['new_sub_plan'] = plan
    await query.edit_message_text(
        "📅 أرسل تاريخ انتهاء الاشتراك بصيغة YYYY-MM-DD\n\nمثال: 2025-12-31",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data='owner_panel')]])
    )
    return OWNER_ADD_EXPIRE


async def owner_add_expire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    from datetime import datetime as dt
    try:
        dt.strptime(text, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("❌ صيغة التاريخ غير صحيحة. أرسل بصيغة YYYY-MM-DD مثل: 2025-12-31")
        return OWNER_ADD_EXPIRE

    uid = context.user_data['new_sub_id']
    plan = context.user_data['new_sub_plan']
    is_new = data_store.add_user(uid, str(uid), plan, text)
    plan_label = "⭐ VIP" if plan == PLAN_VIP else "🔵 Basic"
    action = "تم إضافة" if is_new else "تم تحديث"
    keyboard = [[InlineKeyboardButton("🔙 لوحة التحكم", callback_data='owner_panel')]]
    await update.message.reply_text(
        f"✅ *{action} المشترك بنجاح!*\n\n"
        f"🆔 ID: `{uid}`\n"
        f"📋 الخطة: {plan_label}\n"
        f"📅 ينتهي: {text}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


async def owner_remove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return

    users = data_store.get_all_users()
    if not users:
        await query.edit_message_text(
            "لا يوجد مشتركون لحذفهم.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='owner_panel')]])
        )
        return

    keyboard = []
    for u in users:
        name = u.get("username") or str(u["user_id"])
        status = "✅" if data_store.is_subscribed(u["user_id"]) else "❌"
        keyboard.append([InlineKeyboardButton(f"{status} {name}", callback_data=f"del_sub_{u['user_id']}")])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='owner_panel')])
    await query.edit_message_text("🗑️ اختر المشترك للحذف:", reply_markup=InlineKeyboardMarkup(keyboard))


async def owner_remove_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return
    uid = int(query.data.split('_')[2])
    data_store.remove_user(uid)
    await owner_panel(update, context)


async def owner_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return

    users = data_store.get_all_users()
    if not users:
        await query.edit_message_text(
            "لا يوجد مشتركون للتعديل.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data='owner_panel')]])
        )
        return

    keyboard = []
    for u in users:
        status = "✅" if data_store.is_subscribed(u["user_id"]) else "❌"
        plan_label = "VIP" if u["plan"] == PLAN_VIP else "Basic"
        keyboard.append([InlineKeyboardButton(
            f"{status} {u['user_id']} | {plan_label} | {u['expire_date']}",
            callback_data=f"edit_sub_{u['user_id']}"
        )])
    keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data='owner_panel')])
    await query.edit_message_text("✏️ اختر المشترك للتعديل:", reply_markup=InlineKeyboardMarkup(keyboard))


async def owner_edit_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_owner(update.effective_user.id):
        return

    uid = int(query.data.split('_')[2])
    context.user_data['edit_sub_id'] = uid
    u = data_store.get_user(uid)
    plan_label = "⭐ VIP" if u["plan"] == PLAN_VIP else "🔵 Basic"

    keyboard = [
        [InlineKeyboardButton("🔵 Basic", callback_data='editplan_basic')],
        [InlineKeyboardButton("⭐ VIP", callback_data='editplan_vip')],
        [InlineKeyboardButton("❌ إلغاء", callback_data='owner_panel')],
    ]
    await query.edit_message_text(
        f"✏️ *تعديل المشترك `{uid}`*\n\nالخطة الحالية: {plan_label}\nتنتهي: {u['expire_date']}\n\nاختر الخطة الجديدة:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return OWNER_EDIT_PLAN


async def owner_edit_plan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    plan = PLAN_VIP if query.data == 'editplan_vip' else PLAN_BASIC
    context.user_data['edit_sub_plan'] = plan
    await query.edit_message_text(
        "📅 أرسل تاريخ انتهاء الاشتراك الجديد بصيغة YYYY-MM-DD\n\nمثال: 2025-12-31",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ إلغاء", callback_data='owner_panel')]])
    )
    return OWNER_EDIT_EXPIRE


async def owner_edit_expire(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    from datetime import datetime as dt
    try:
        dt.strptime(text, "%Y-%m-%d")
    except ValueError:
        await update.message.reply_text("❌ صيغة التاريخ غير صحيحة. أرسل بصيغة YYYY-MM-DD مثل: 2025-12-31")
        return OWNER_EDIT_EXPIRE

    uid = context.user_data['edit_sub_id']
    plan = context.user_data['edit_sub_plan']
    u = data_store.get_user(uid)
    data_store.add_user(uid, u.get("username", str(uid)), plan, text)
    plan_label = "⭐ VIP" if plan == PLAN_VIP else "🔵 Basic"
    keyboard = [[InlineKeyboardButton("🔙 لوحة التحكم", callback_data='owner_panel')]]
    await update.message.reply_text(
        f"✅ *تم تحديث المشترك بنجاح!*\n\n"
        f"🆔 ID: `{uid}`\n"
        f"📋 الخطة الجديدة: {plan_label}\n"
        f"📅 ينتهي: {text}",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ConversationHandler.END


async def owner_panel_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Fallback: cancel owner_add/edit conversation and return to owner panel."""
    await owner_panel(update, context)
    return ConversationHandler.END


# Cancel conversation
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم الإلغاء.")
    return ConversationHandler.END

def main():
    import sys
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    token = os.environ.get("BOT_TOKEN")
    if not token:
        print("Error: BOT_TOKEN environment variable not set!")
        print("Get your bot token from @BotFather on Telegram")
        return
    
    application = Application.builder().token(token).build()
    
    # Add account conversation
    add_account_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_account_start, pattern='^add_account$')],
        states={
            ACC_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_account_email)],
            ACC_PASSWORD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_account_password)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(cancel_add_account_handler, pattern='^cancel_add_account$'),
        ],
    )
    
    # Add message conversation
    add_message_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_message_start, pattern='^add_message$')],
        states={
            MSG_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_message_subject)],
            MSG_BODY: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_message_body)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Add recipients conversation
    add_recipients_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_recipients_start, pattern='^add_recipients$')],
        states={
            REC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_recipients_name)],
            REC_EMAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_recipients_emails)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Manual recipients input for send flow
    send_recipients_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(send_manual_recipients, pattern='^send_rec_manual$')],
        states={
            SEND_SELECT_REC: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_recipients_input)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # Count and delay conversations
    send_count_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(send_count_custom, pattern='^count_custom$')],
        states={
            SEND_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_count_input)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    send_delay_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(send_delay_custom, pattern='^delay_custom$')],
        states={
            SEND_DELAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_delay_input)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    # AI generate conversation
    ai_generate_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ai_generate_start, pattern='^ai_generate$')],
        states={
            AI_GENERATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ai_generate_process)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Owner edit subscriber conversation
    owner_edit_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(owner_edit_select, pattern='^edit_sub_')],
        states={
            OWNER_EDIT_PLAN:   [CallbackQueryHandler(owner_edit_plan, pattern='^editplan_')],
            OWNER_EDIT_EXPIRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, owner_edit_expire)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(owner_panel_cancel, pattern='^owner_panel$'),
        ],
    )

    # Owner add subscriber conversation
    owner_add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(owner_add_start, pattern='^owner_add$')],
        states={
            OWNER_ADD_ID:     [MessageHandler(filters.TEXT & ~filters.COMMAND, owner_add_id)],
            OWNER_ADD_PLAN:   [CallbackQueryHandler(owner_add_plan, pattern='^subplan_')],
            OWNER_ADD_EXPIRE: [MessageHandler(filters.TEXT & ~filters.COMMAND, owner_add_expire)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(owner_panel_cancel, pattern='^owner_panel$'),
        ],
    )

    # Telegram session login conversation
    add_tg_session_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_tg_session_start, pattern='^add_tg_session$')],
        states={
            TG_API_ID:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tg_api_id)],
            TG_API_HASH: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tg_api_hash)],
            TG_PHONE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tg_phone)],
            TG_CODE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tg_code)],
            TG_2FA:     [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tg_2fa)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CallbackQueryHandler(cancel_add_tg_session, pattern='^menu_tg_sessions$'),
        ],
    )

    # Add report targets conversation
    add_tg_target_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_tg_target_start, pattern='^add_tg_target$')],
        states={
            REP_NAME:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tg_target_name)],
            REP_TARGETS: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_tg_target_input)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Report custom text conversation (for 'other' reason)
    rep_custom_text_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(tg_custom_text_start, pattern='^rep_reason_other$')],
        states={
            REP_CUSTOM_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tg_custom_text_input)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Report count and delay conversations
    rep_count_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(tg_count_custom_start, pattern='^rep_count_custom$')],
        states={
            REP_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, tg_count_input)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    rep_delay_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(tg_delay_custom_start, pattern='^rep_delay_custom$')],
        states={
            REP_DELAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, tg_delay_input)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # TG emails save-as-list conversation
    tge_save_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(tge_save_start, pattern='^tge_save$')],
        states={
            REC_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, tge_save_name)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    # Monitor target input conversation
    monitor_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_monitor_target, pattern='^ask_monitor_target$')],
        states={
            SEND_MONITOR: [MessageHandler(filters.TEXT & ~filters.COMMAND, monitor_target_input)],
        },
        fallbacks=[
            CommandHandler('cancel', cancel),
            CommandHandler('skip', monitor_target_input),
        ],
    )

    # Add handlers
    application.add_handler(CommandHandler('start', start))
    application.add_handler(add_account_conv)
    application.add_handler(add_message_conv)
    application.add_handler(add_recipients_conv)
    application.add_handler(send_recipients_conv)
    application.add_handler(send_count_conv)
    application.add_handler(send_delay_conv)
    application.add_handler(ai_generate_conv)
    application.add_handler(owner_add_conv)
    application.add_handler(owner_edit_conv)
    application.add_handler(add_tg_session_conv)
    application.add_handler(add_tg_target_conv)
    application.add_handler(rep_custom_text_conv)
    application.add_handler(rep_count_conv)
    application.add_handler(rep_delay_conv)
    application.add_handler(tge_save_conv)
    application.add_handler(monitor_conv)
    
    # Menu callbacks
    application.add_handler(CallbackQueryHandler(menu_accounts, pattern='^menu_accounts$'))
    application.add_handler(CallbackQueryHandler(menu_messages, pattern='^menu_messages$'))
    application.add_handler(CallbackQueryHandler(menu_recipients, pattern='^menu_recipients$'))
    application.add_handler(CallbackQueryHandler(menu_send, pattern='^menu_send$'))
    application.add_handler(CallbackQueryHandler(menu_status, pattern='^menu_status$'))
    application.add_handler(CallbackQueryHandler(menu_tg_report, pattern='^menu_tg_report$'))
    
    # Remove handlers
    application.add_handler(CallbackQueryHandler(remove_account_start, pattern='^remove_account$'))
    application.add_handler(CallbackQueryHandler(remove_account_confirm, pattern='^del_acc_'))
    application.add_handler(CallbackQueryHandler(remove_message_start, pattern='^remove_message$'))
    application.add_handler(CallbackQueryHandler(remove_message_confirm, pattern='^del_msg_'))
    application.add_handler(CallbackQueryHandler(remove_recipients_start, pattern='^remove_recipients$'))
    application.add_handler(CallbackQueryHandler(remove_recipients_confirm, pattern='^del_rec_'))
    
    # View handlers
    application.add_handler(CallbackQueryHandler(view_message_start, pattern='^view_message$'))
    application.add_handler(CallbackQueryHandler(view_message_details, pattern='^view_msg_'))
    application.add_handler(CallbackQueryHandler(view_recipients_start, pattern='^view_recipients$'))
    application.add_handler(CallbackQueryHandler(view_recipients_details, pattern='^view_rec_'))
    
    # TG emails selector callbacks
    application.add_handler(CallbackQueryHandler(tg_emails_menu, pattern='^tg_emails_menu$'))
    application.add_handler(CallbackQueryHandler(send_tg_emails, pattern='^send_tg_emails$'))
    application.add_handler(CallbackQueryHandler(tge_toggle, pattern='^tge_toggle_'))
    application.add_handler(CallbackQueryHandler(tge_select_all, pattern='^tge_all$'))
    application.add_handler(CallbackQueryHandler(tge_deselect_all, pattern='^tge_none$'))
    application.add_handler(CallbackQueryHandler(tge_use_send, pattern='^tge_use_send$'))

    # Monitor callbacks
    application.add_handler(CallbackQueryHandler(stop_monitor, pattern='^stop_monitor_'))

    # Send flow
    application.add_handler(CallbackQueryHandler(send_select_msg, pattern='^send_msg_'))
    application.add_handler(CallbackQueryHandler(send_select_rec, pattern='^send_rec_'))
    application.add_handler(CallbackQueryHandler(send_save_accounts, pattern='^send_acc_'))
    application.add_handler(CallbackQueryHandler(send_save_accounts, pattern='^send_acc_all$'))
    
    # Count and delay selection
    application.add_handler(CallbackQueryHandler(send_select_count, pattern='^count_'))
    application.add_handler(CallbackQueryHandler(send_select_delay, pattern='^delay_'))
    
    # AI handlers
    application.add_handler(CallbackQueryHandler(ai_save_message, pattern='^ai_save$'))
    
    # Back buttons - main menu
    application.add_handler(CallbackQueryHandler(back_main, pattern='^back_main$'))
    
    # Back buttons - send flow navigation
    application.add_handler(CallbackQueryHandler(back_to_accounts, pattern='^back_to_accounts$'))
    application.add_handler(CallbackQueryHandler(back_to_count, pattern='^back_to_count$'))
    application.add_handler(CallbackQueryHandler(back_to_recipients, pattern='^back_to_recipients$'))
    application.add_handler(CallbackQueryHandler(back_to_rep_count, pattern='^back_to_rep_count$'))

    # Telegram report menu callbacks
    application.add_handler(CallbackQueryHandler(menu_tg_sessions, pattern='^menu_tg_sessions$'))
    application.add_handler(CallbackQueryHandler(menu_tg_targets, pattern='^menu_tg_targets$'))
    application.add_handler(CallbackQueryHandler(menu_tg_execute, pattern='^menu_tg_execute$'))
    application.add_handler(CallbackQueryHandler(menu_tg_status, pattern='^menu_tg_status$'))

    # Telegram session callbacks
    application.add_handler(CallbackQueryHandler(remove_tg_session_start, pattern='^remove_tg_session$'))
    application.add_handler(CallbackQueryHandler(remove_tg_session_confirm, pattern='^del_tgs_'))

    # Telegram target callbacks
    application.add_handler(CallbackQueryHandler(remove_tg_target_start, pattern='^remove_tg_target$'))
    application.add_handler(CallbackQueryHandler(remove_tg_target_confirm, pattern='^del_tgr_'))
    application.add_handler(CallbackQueryHandler(view_tg_target_start, pattern='^view_tg_target$'))
    application.add_handler(CallbackQueryHandler(view_tg_target_details, pattern='^view_tgr_'))

    # Telegram report execution callbacks
    application.add_handler(CallbackQueryHandler(tg_select_target_list, pattern='^rep_sel_target_'))
    application.add_handler(CallbackQueryHandler(tg_select_reason, pattern='^rep_reason_'))
    application.add_handler(CallbackQueryHandler(tg_select_count, pattern='^rep_count_'))
    application.add_handler(CallbackQueryHandler(tg_select_delay, pattern='^rep_delay_'))

    # Owner panel callbacks
    application.add_handler(CallbackQueryHandler(owner_panel, pattern='^owner_panel$'))
    application.add_handler(CallbackQueryHandler(owner_list, pattern='^owner_list$'))
    application.add_handler(CallbackQueryHandler(owner_edit_start, pattern='^owner_edit$'))
    application.add_handler(CallbackQueryHandler(owner_remove_start, pattern='^owner_remove$'))
    application.add_handler(CallbackQueryHandler(owner_remove_confirm, pattern='^del_sub_'))

    print("Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
