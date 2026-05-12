import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.functions.account import ReportPeerRequest
from telethon.tl.types import (
    InputReportReasonSpam,
    InputReportReasonViolence,
    InputReportReasonChildAbuse,
    InputReportReasonPornography,
    InputReportReasonFake,
    InputReportReasonOther,
)
from telethon.errors import SessionPasswordNeededError, FloodWaitError, PhoneCodeInvalidError


class TGReporter:
    REASON_MAP = {
        "spam": InputReportReasonSpam,
        "violence": InputReportReasonViolence,
        "child_abuse": InputReportReasonChildAbuse,
        "pornography": InputReportReasonPornography,
        "fake": InputReportReasonFake,
        "other": InputReportReasonOther,
    }

    REASON_LABELS = {
        "spam": "🚫 سبام",
        "violence": "⚔️ عنف",
        "child_abuse": "🛡️ إساءة للأطفال",
        "pornography": "🔞 إباحية",
        "fake": "🎭 حساب/قناة مزيفة",
        "other": "📌 أخرى",
    }

    @classmethod
    def get_reason_choices(cls):
        return list(cls.REASON_LABELS.items())

    @staticmethod
    async def send_code(api_id: int, api_hash: str, phone: str):
        """Start login by sending code request. Returns dict."""
        client = None
        try:
            session = StringSession()
            client = TelegramClient(session, api_id, api_hash)
            await client.connect()
            sent = await client.send_code_request(phone)
            phone_code_hash = sent.phone_code_hash
            # We must keep session state; save it as string
            temp_session = session.save()
            await client.disconnect()
            return {
                "success": True,
                "phone_code_hash": phone_code_hash,
                "temp_session": temp_session,
                "error": None,
            }
        except FloodWaitError as e:
            return {
                "success": False,
                "phone_code_hash": None,
                "temp_session": None,
                "error": f"انتظار {e.seconds} ثانية قبل إعادة المحاولة.",
            }
        except Exception as e:
            return {
                "success": False,
                "phone_code_hash": None,
                "temp_session": None,
                "error": str(e)[:200],
            }
        finally:
            if client and client.is_connected():
                await client.disconnect()

    @staticmethod
    async def verify_code(
        api_id: int,
        api_hash: str,
        phone: str,
        code: str,
        phone_code_hash: str,
        temp_session: str,
        password: str = None,
    ):
        """Verify code and optionally 2FA password. Returns dict with session_string."""
        client = None
        try:
            session = StringSession(temp_session)
            client = TelegramClient(session, api_id, api_hash)
            await client.connect()
            try:
                await client.sign_in(
                    phone, code=code, phone_code_hash=phone_code_hash
                )
            except SessionPasswordNeededError:
                if password:
                    await client.sign_in(password=password)
                else:
                    await client.disconnect()
                    return {
                        "success": False,
                        "session_string": None,
                        "needs_password": True,
                        "error": "مطلوب كلمة مرور المصادقة الثنائية (2FA)",
                    }
            session_string = session.save()
            await client.disconnect()
            return {
                "success": True,
                "session_string": session_string,
                "needs_password": False,
                "error": None,
            }
        except PhoneCodeInvalidError:
            return {
                "success": False,
                "session_string": None,
                "needs_password": False,
                "error": "❌ كود التحقق غير صحيح.",
            }
        except Exception as e:
            return {
                "success": False,
                "session_string": None,
                "needs_password": False,
                "error": str(e)[:200],
            }
        finally:
            if client and client.is_connected():
                await client.disconnect()

    @classmethod
    async def report(
        cls, api_id: int, api_hash: str, session_string: str, target: str, reason: str, custom_message: str = ""
    ):
        """Send a Telegram report on target. Returns dict with success/error."""
        client = None
        try:
            session = StringSession(session_string)
            client = TelegramClient(session, api_id, api_hash)
            await client.connect()

            if not await client.is_user_authorized():
                await client.disconnect()
                return {"success": False, "error": "الجلسة منتهية أو غير مصرح بها"}

            entity = await client.get_entity(target)
            reason_cls = cls.REASON_MAP.get(reason, InputReportReasonOther)
            reason_obj = reason_cls()

            result = await client(
                ReportPeerRequest(peer=entity, reason=reason_obj, message=custom_message or "")
            )

            await client.disconnect()
            return {"success": True, "error": None, "result": str(result)}
        except FloodWaitError as e:
            return {
                "success": False,
                "error": f"FloodWait: انتظر {e.seconds} ثانية",
            }
        except Exception as e:
            return {"success": False, "error": str(e)[:200]}
        finally:
            if client and client.is_connected():
                await client.disconnect()

    @staticmethod
    async def test_session(api_id: int, api_hash: str, session_string: str):
        """Test if a session is valid. Returns dict with success, name, error."""
        client = None
        try:
            session = StringSession(session_string)
            client = TelegramClient(session, api_id, api_hash)
            await client.connect()
            if not await client.is_user_authorized():
                await client.disconnect()
                return {"success": False, "name": None, "error": "الجلسة غير مصرح بها"}
            me = await client.get_me()
            await client.disconnect()
            name = f"{me.first_name} {me.last_name or ''}".strip()
            return {"success": True, "name": name, "error": None}
        except Exception as e:
            return {"success": False, "name": None, "error": str(e)[:200]}
        finally:
            if client and client.is_connected():
                await client.disconnect()
