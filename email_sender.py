import smtplib
import asyncio
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Any

class EmailSender:
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587

    async def send_single(self, from_email: str, app_password: str, to_emails: List[str], 
                          subject: str, body: str) -> Dict[str, Any]:
        try:
            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = ', '.join(to_emails)
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain'))

            await asyncio.to_thread(self._send_sync, from_email, app_password, to_emails, msg)
            
            return {
                "success": True,
                "from": from_email,
                "to": to_emails,
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "from": from_email,
                "to": to_emails,
                "error": str(e)
            }

    def _send_sync(self, from_email: str, app_password: str, to_emails: List[str], msg: MIMEMultipart):
        server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15)
        server.starttls()
        server.login(from_email, app_password)
        server.send_message(msg)
        server.quit()

    FATAL_ERRORS = ("5.4.5", "daily", "limit", "quota", "suspended", "disabled")

    def _send_bulk_sync(self, from_email: str, app_password: str,
                        messages: List[MIMEMultipart]) -> List[Dict[str, Any]]:
        """Send multiple messages over a single SMTP connection.
        Stops immediately on daily/quota limit errors."""
        results = []
        server = None
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15)
            server.starttls()
            server.login(from_email, app_password)
            for msg in messages:
                try:
                    server.send_message(msg)
                    results.append({"success": True, "error": None})
                except smtplib.SMTPRecipientsRefused as e:
                    results.append({"success": False, "error": str(e)})
                except smtplib.SMTPResponseException as e:
                    err = str(e)
                    results.append({"success": False, "error": err})
                    if any(k in err.lower() for k in self.FATAL_ERRORS):
                        # Account hit daily limit — stop immediately
                        remaining = len(messages) - len(results)
                        for _ in range(remaining):
                            results.append({"success": False, "error": "⛔ الحد اليومي للحساب — تم إيقاف الإرسال"})
                        return results
                except Exception as e:
                    err = str(e)
                    results.append({"success": False, "error": err})
                    if any(k in err.lower() for k in self.FATAL_ERRORS):
                        remaining = len(messages) - len(results)
                        for _ in range(remaining):
                            results.append({"success": False, "error": "⛔ الحد اليومي للحساب — تم إيقاف الإرسال"})
                        return results
        except smtplib.SMTPAuthenticationError:
            for _ in messages:
                results.append({"success": False, "error": "❌ فشل تسجيل الدخول — تحقق من App Password"})
        except Exception as e:
            for _ in messages:
                results.append({"success": False, "error": str(e)})
        finally:
            if server:
                try:
                    server.quit()
                except Exception:
                    pass
        return results

    def test_login(self, email: str, app_password: str) -> Dict[str, Any]:
        """Test if account credentials are valid without sending email"""
        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(email, app_password)
            server.quit()
            return {"success": True, "error": None}
        except smtplib.SMTPAuthenticationError as e:
            return {"success": False, "error": "فشل المصادقة: تأكد من صحة البريد وApp Password"}
        except Exception as e:
            return {"success": False, "error": f"خطأ: {str(e)[:100]}"}

    async def send_from_multiple_accounts(self, accounts: List[Dict], to_emails: List[str],
                                          subject: str, body: str) -> List[Dict[str, Any]]:
        """Send one email per recipient per account (each recipient gets their own email)."""
        tasks = []
        task_meta = []
        for acc in accounts:
            for to in to_emails:
                tasks.append(
                    self.send_single(acc["email"], acc["app_password"], [to], subject, body)
                )
                task_meta.append((acc["email"], to))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        processed_results = []
        for (from_email, to), result in zip(task_meta, results):
            if isinstance(result, Exception):
                processed_results.append({
                    "success": False,
                    "from": from_email,
                    "to": to,
                    "error": str(result),
                })
            else:
                result['to'] = to
                processed_results.append(result)

        return processed_results
