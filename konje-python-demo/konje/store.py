"""The encrypted directory of trusted people, plus reminders and the event log.

Everything is kept in one file, data/directory.enc, scrambled with a secret key
(data/secret.key). Without the key, the file is unreadable gibberish.
"""
import json
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path

from cryptography.fernet import Fernet

DATA = Path(__file__).resolve().parent.parent / "data"
KEY_FILE = DATA / "secret.key"
DB_FILE = DATA / "directory.enc"

EMPTY = {"people": [], "reminders": [], "events": [], "settings": {"alert_topic": ""}}


def now():
    return datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self):
        DATA.mkdir(mode=0o700, exist_ok=True)
        if not KEY_FILE.exists():
            KEY_FILE.write_bytes(Fernet.generate_key())
            KEY_FILE.chmod(0o600)
        self.fernet = Fernet(KEY_FILE.read_bytes())
        self.lock = threading.Lock()
        if DB_FILE.exists():
            self.data = json.loads(self.fernet.decrypt(DB_FILE.read_bytes()))
        else:
            self.data = json.loads(json.dumps(EMPTY))
            self._save()

    def _save(self):
        tmp = DB_FILE.with_suffix(".tmp")
        tmp.write_bytes(self.fernet.encrypt(json.dumps(self.data).encode()))
        tmp.chmod(0o600)
        tmp.replace(DB_FILE)  # swap in one step so a crash never leaves half a file

    # ---- people ----------------------------------------------------------
    def people(self):
        return self.data["people"]

    def public_people(self):
        """People without their face numbers, safe to send to the web page."""
        return [{k: v for k, v in p.items() if k != "embeddings"} for p in self.data["people"]]

    def add_person(self, name, relationship, intro, reminder, consent_by, embeddings):
        person = {
            "id": uuid.uuid4().hex[:8],
            "name": name,
            "relationship": relationship,
            "intro": intro,
            "reminder": reminder,
            "consent": {"given_by": consent_by, "at": now()},
            "embeddings": [e.tolist() for e in embeddings],
            "interactions": [],
            "last_seen": None,
        }
        with self.lock:
            self.data["people"].append(person)
            self._log("enrolled", f"{name} ({relationship}) enrolled with consent from {consent_by}")
            self._save()
        return person

    def remove_person(self, person_id):
        with self.lock:
            before = len(self.data["people"])
            gone = [p for p in self.data["people"] if p["id"] == person_id]
            self.data["people"] = [p for p in self.data["people"] if p["id"] != person_id]
            if gone:
                self._log("removed", f"{gone[0]['name']} removed; their face data was deleted")
            self._save()
            return len(self.data["people"]) < before

    def update_person(self, person_id, **fields):
        with self.lock:
            for p in self.data["people"]:
                if p["id"] == person_id:
                    p.update({k: v for k, v in fields.items() if k in ("intro", "reminder", "relationship")})
                    self._save()
                    return True
        return False

    def add_interaction(self, person_id, note):
        with self.lock:
            for p in self.data["people"]:
                if p["id"] == person_id:
                    p["interactions"].append({"at": now(), "note": note})
                    self._save()
                    return True
        return False

    def mark_seen(self, person_id):
        with self.lock:
            for p in self.data["people"]:
                if p["id"] == person_id:
                    p["last_seen"] = now()
                    self._log("recognized", f"Recognized {p['name']}")
                    self._save()

    # ---- reminders ---------------------------------------------------------
    def reminders(self):
        return self.data["reminders"]

    def add_reminder(self, at_time, text):
        with self.lock:
            r = {"id": uuid.uuid4().hex[:8], "time": at_time, "text": text, "last_fired": ""}
            self.data["reminders"].append(r)
            self._save()
            return r

    def remove_reminder(self, reminder_id):
        with self.lock:
            self.data["reminders"] = [r for r in self.data["reminders"] if r["id"] != reminder_id]
            self._save()

    def due_reminders(self):
        """Reminders whose time (HH:MM) has arrived today and haven't fired yet today."""
        today, hhmm = time.strftime("%Y-%m-%d"), time.strftime("%H:%M")
        due = []
        with self.lock:
            for r in self.data["reminders"]:
                if r["time"] <= hhmm and r["last_fired"] != today:
                    r["last_fired"] = today
                    due.append(r)
                    self._log("reminder", r["text"])
            if due:
                self._save()
        return due

    # ---- settings & log ------------------------------------------------------
    def settings(self):
        return self.data["settings"]

    def set_setting(self, key, value):
        with self.lock:
            self.data["settings"][key] = value
            self._save()

    def _log(self, kind, text):
        self.data["events"].append({"at": now(), "kind": kind, "text": text})
        self.data["events"] = self.data["events"][-200:]

    def log(self, kind, text):
        with self.lock:
            self._log(kind, text)
            self._save()

    def events(self):
        return list(reversed(self.data["events"]))
