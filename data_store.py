import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime

GLOBAL_DATA_FILE = "bot_data.json"
USER_DATA_DIR = "user_data"

PLAN_BASIC = "basic"
PLAN_VIP = "vip"

PLAN_FEATURES = {
    PLAN_BASIC: ["accounts", "messages", "recipients", "send", "telegram"],
    PLAN_VIP:   ["accounts", "messages", "recipients", "send", "ai", "telegram"],
}


# ─────────────────────────────────────────────
#  Per-user isolated data  (user_data/<id>.json)
# ─────────────────────────────────────────────
class UserDataStore:
    def __init__(self, user_id: int):
        self.user_id = user_id
        os.makedirs(USER_DATA_DIR, exist_ok=True)
        self.file = os.path.join(USER_DATA_DIR, f"{user_id}.json")
        self.data: Dict[str, Any] = {
            "accounts": [],
            "messages": [],
            "recipients": [],
            "send_jobs": [],
            "telegram_sessions": [],
            "report_targets": [],
            "report_jobs": [],
        }
        self._load()

    def _load(self):
        if os.path.exists(self.file):
            with open(self.file, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                self.data.update(loaded)

    def _save(self):
        with open(self.file, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    # Accounts
    def add_account(self, email: str, app_password: str) -> bool:
        if any(acc["email"] == email for acc in self.data["accounts"]):
            return False
        self.data["accounts"].append({
            "id": len(self.data["accounts"]) + 1,
            "email": email,
            "app_password": app_password
        })
        self._save()
        return True

    def get_accounts(self) -> List[Dict]:
        return self.data["accounts"]

    def remove_account(self, account_id: int) -> bool:
        for i, acc in enumerate(self.data["accounts"]):
            if acc["id"] == account_id:
                self.data["accounts"].pop(i)
                self._save()
                return True
        return False

    # Messages
    def add_message(self, subject: str, body: str) -> int:
        msg_id = len(self.data["messages"]) + 1
        self.data["messages"].append({
            "id": msg_id,
            "subject": subject,
            "body": body
        })
        self._save()
        return msg_id

    def get_messages(self) -> List[Dict]:
        return self.data["messages"]

    def get_message(self, msg_id: int) -> Optional[Dict]:
        for msg in self.data["messages"]:
            if msg["id"] == msg_id:
                return msg
        return None

    def remove_message(self, msg_id: int) -> bool:
        for i, msg in enumerate(self.data["messages"]):
            if msg["id"] == msg_id:
                self.data["messages"].pop(i)
                self._save()
                return True
        return False

    # Recipients
    def add_recipients(self, name: str, emails: List[str]) -> int:
        rec_id = len(self.data["recipients"]) + 1
        self.data["recipients"].append({
            "id": rec_id,
            "name": name,
            "emails": emails
        })
        self._save()
        return rec_id

    def get_recipients(self) -> List[Dict]:
        return self.data["recipients"]

    def get_recipient(self, rec_id: int) -> Optional[Dict]:
        for rec in self.data["recipients"]:
            if rec["id"] == rec_id:
                return rec
        return None

    def remove_recipients(self, rec_id: int) -> bool:
        for i, rec in enumerate(self.data["recipients"]):
            if rec["id"] == rec_id:
                self.data["recipients"].pop(i)
                self._save()
                return True
        return False

    # Send Jobs
    def add_send_job(self, job: Dict) -> int:
        job_id = len(self.data["send_jobs"]) + 1
        job["id"] = job_id
        job["status"] = "pending"
        self.data["send_jobs"].append(job)
        self._save()
        return job_id

    def update_send_job(self, job_id: int, status: str, results: Any = None):
        for job in self.data["send_jobs"]:
            if job["id"] == job_id:
                job["status"] = status
                if results:
                    job["results"] = results
                self._save()
                return

    def get_send_jobs(self) -> List[Dict]:
        return self.data["send_jobs"]

    def update_send_job_monitor(self, job_id: int, **fields):
        for job in self.data["send_jobs"]:
            if job["id"] == job_id:
                job.update(fields)
                self._save()
                return

    def get_active_monitors(self) -> List[Dict]:
        return [
            j for j in self.data["send_jobs"]
            if j.get("monitor_status") == "watching"
        ]

    # Telegram Sessions
    def add_telegram_session(
        self, phone: str, api_id: int, api_hash: str, session_string: str
    ) -> int:
        sess_id = len(self.data["telegram_sessions"]) + 1
        self.data["telegram_sessions"].append({
            "id": sess_id,
            "phone": phone,
            "api_id": api_id,
            "api_hash": api_hash,
            "session_string": session_string,
        })
        self._save()
        return sess_id

    def get_telegram_sessions(self) -> List[Dict]:
        return self.data["telegram_sessions"]

    def get_telegram_session(self, sess_id: int) -> Optional[Dict]:
        for s in self.data["telegram_sessions"]:
            if s["id"] == sess_id:
                return s
        return None

    def remove_telegram_session(self, sess_id: int) -> bool:
        for i, s in enumerate(self.data["telegram_sessions"]):
            if s["id"] == sess_id:
                self.data["telegram_sessions"].pop(i)
                self._save()
                return True
        return False

    # Report Targets
    def add_report_targets(self, name: str, targets: List[str]) -> int:
        rec_id = len(self.data["report_targets"]) + 1
        self.data["report_targets"].append({
            "id": rec_id,
            "name": name,
            "targets": targets,
        })
        self._save()
        return rec_id

    def get_report_targets(self) -> List[Dict]:
        return self.data["report_targets"]

    def get_report_target(self, rec_id: int) -> Optional[Dict]:
        for r in self.data["report_targets"]:
            if r["id"] == rec_id:
                return r
        return None

    def remove_report_targets(self, rec_id: int) -> bool:
        for i, r in enumerate(self.data["report_targets"]):
            if r["id"] == rec_id:
                self.data["report_targets"].pop(i)
                self._save()
                return True
        return False

    # Report Jobs
    def add_report_job(self, job: Dict) -> int:
        job_id = len(self.data["report_jobs"]) + 1
        job["id"] = job_id
        job["status"] = "pending"
        self.data["report_jobs"].append(job)
        self._save()
        return job_id

    def update_report_job(self, job_id: int, status: str, results: Any = None):
        for job in self.data["report_jobs"]:
            if job["id"] == job_id:
                job["status"] = status
                if results:
                    job["results"] = results
                self._save()
                return

    def get_report_jobs(self) -> List[Dict]:
        return self.data["report_jobs"]


# ─────────────────────────────────────────────
#  Global data  (bot_data.json) — subscriptions only
# ─────────────────────────────────────────────
class DataStore:
    def __init__(self):
        self.data: Dict[str, Any] = {"users": []}
        self._load()
        self._user_cache: Dict[int, UserDataStore] = {}

    def _load(self):
        if os.path.exists(GLOBAL_DATA_FILE):
            with open(GLOBAL_DATA_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                self.data.update(loaded)
                if "users" not in self.data:
                    self.data["users"] = []

    def _save(self):
        with open(GLOBAL_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)

    def user(self, user_id: int) -> UserDataStore:
        """Return the per-user data store (cached)."""
        if user_id not in self._user_cache:
            self._user_cache[user_id] = UserDataStore(user_id)
        return self._user_cache[user_id]

    # Users / Subscriptions
    def add_user(self, user_id: int, username: str, plan: str, expire_date: str) -> bool:
        for u in self.data["users"]:
            if u["user_id"] == user_id:
                u["plan"] = plan
                u["expire_date"] = expire_date
                u["username"] = username
                self._save()
                return False
        self.data["users"].append({
            "user_id": user_id,
            "username": username,
            "plan": plan,
            "expire_date": expire_date,
            "added_date": datetime.now().strftime("%Y-%m-%d")
        })
        self._save()
        return True

    def remove_user(self, user_id: int) -> bool:
        for i, u in enumerate(self.data["users"]):
            if u["user_id"] == user_id:
                self.data["users"].pop(i)
                self._save()
                return True
        return False

    def get_user(self, user_id: int) -> Optional[Dict]:
        for u in self.data["users"]:
            if u["user_id"] == user_id:
                return u
        return None

    def get_all_users(self) -> List[Dict]:
        return self.data["users"]

    def is_subscribed(self, user_id: int) -> bool:
        u = self.get_user(user_id)
        if not u:
            return False
        try:
            expire = datetime.strptime(u["expire_date"], "%Y-%m-%d")
            return expire >= datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        except Exception:
            return False

    def get_plan(self, user_id: int) -> Optional[str]:
        u = self.get_user(user_id)
        return u["plan"] if u else None

    def has_feature(self, user_id: int, feature: str) -> bool:
        if not self.is_subscribed(user_id):
            return False
        plan = self.get_plan(user_id)
        return feature in PLAN_FEATURES.get(plan, [])
