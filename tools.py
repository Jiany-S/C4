"""Local business sources, read tools, and the two record-writing tools from C3."""
from __future__ import annotations

import json
import math
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent
WRITE_LOCK = threading.Lock()
CATALOG = {
    "Project Clarity": {"minutes": 30, "price_usd": 15, "billing": "per student", "capacity": 1,
                        "purpose": "Scope an idea and choose manageable next steps."},
    "Prototype Clinic": {"minutes": 60, "price_usd": 30, "billing": "per student", "capacity": 1,
                         "purpose": "Work through debugging and testing blockers."},
    "Team Sprint": {"minutes": 90, "price_usd": 60, "billing": "per team", "capacity": 4,
                    "purpose": "Plan a project with a team of up to four students."},
}


def load_business(root=ROOT):
    folder = Path(root) / "me"
    summary = (folder / "business_summary.txt").read_text(encoding="utf-8").strip()
    pdf = "\n".join(p.extract_text() or "" for p in PdfReader(folder / "about_business.pdf").pages).strip()
    if not summary or not pdf:
        raise ValueError("The PDF and summary must both contain text.")
    # Guard the structured read tools against accidental drift from the C3 fact sheet.
    for name, item in CATALOG.items():
        for text in (summary, pdf):
            if name not in text or f"USD {item['price_usd']}" not in text:
                raise ValueError("The service catalog and business sources disagree.")
    return f"[business_summary.txt]\n{summary}\n\n[about_business.pdf]\n{pdf}"


class JsonLog:
    def __init__(self, folder):
        self.folder = Path(folder)

    def append(self, kind, payload):
        record = {"id": str(uuid.uuid4()), "timestamp": datetime.now(timezone.utc).isoformat(), **payload}
        with WRITE_LOCK:
            self.folder.mkdir(parents=True, exist_ok=True)
            with (self.folder / f"{kind}.jsonl").open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record["id"]


def declaration(name, description, properties):
    return {"type": "function", "function": {"name": name, "description": description,
        "strict": True, "parameters": {"type": "object", "properties": properties,
            "required": list(properties), "additionalProperties": False}}}


TOOL_SCHEMAS = [
    declaration("lookup_service", "Read published service facts before recommending a service or answering a service price/duration question.",
                {"service": {"type": "string", "description": "Exact service name or all for a comparison"}}),
    declaration("calculate_quote", "Calculate a published-price estimate for people and sessions. This is not a booking.", {
        "service": {"type": "string", "enum": list(CATALOG)},
        "people": {"type": "integer", "minimum": 1, "maximum": 100},
        "sessions": {"type": "integer", "minimum": 1, "maximum": 20}}),
    declaration("record_customer_interest", "Save a requested staff follow-up after customer-supplied name, email, and service notes are available.", {
        "email": {"type": "string"}, "name": {"type": "string"}, "message": {"type": "string"}}),
    declaration("record_feedback", "Save feedback or a business question missing from the published sources.",
                {"question": {"type": "string"}}),
]


class Tools:
    def __init__(self, folder):
        self.log = JsonLog(folder)

    def lookup_service(self, service):
        if not isinstance(service, str):
            return {"ok": False, "error": "Provide a service name or all."}
        names = list(CATALOG) if service.casefold() == "all" else [n for n in CATALOG if n.casefold() == service.casefold()]
        if not names:
            return {"ok": False, "error": "Unknown service. Choose Project Clarity, Prototype Clinic, or Team Sprint."}
        return {"ok": True, "services": {n: dict(CATALOG[n]) for n in names}, "source": "CedarBridge published profile"}

    def calculate_quote(self, service, people, sessions):
        if service not in CATALOG or any(type(v) is not int for v in (people, sessions)):
            return {"ok": False, "error": "Use an exact service name and integer people/sessions."}
        if not 1 <= people <= 100 or not 1 <= sessions <= 20:
            return {"ok": False, "error": "People must be 1–100; sessions must be 1–20."}
        item = CATALOG[service]
        units = math.ceil(people / item["capacity"])
        return {"ok": True, "service": service, "people": people, "sessions": sessions,
                "billing_units_per_session": units, "total_usd": units * item["price_usd"] * sessions,
                "basis": "Published prices; no discounts assumed", "booking_confirmed": False}

    def record_customer_interest(self, email, name, message):
        if not all(isinstance(v, str) and v.strip() for v in (email, name, message)):
            return {"ok": False, "error": "Name, email, and service/project notes are required."}
        email, name, message = (v.strip() for v in (email, name, message))
        if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+", email):
            return {"ok": False, "error": "Please provide a valid email address."}
        if len(name) > 120 or len(message) > 3000 or any(c in name + email for c in "\r\n"):
            return {"ok": False, "error": "Contact details exceed the supported format or length."}
        return self._save("leads", {"email": email, "name": name, "message": message})

    def record_feedback(self, question):
        if not isinstance(question, str) or not question.strip() or len(question) > 4000:
            return {"ok": False, "error": "Provide feedback of 1–4000 characters."}
        return self._save("feedback", {"question": question.strip()})

    def _save(self, kind, payload):
        try:
            record_id = self.log.append(kind, payload)
            return {"ok": True, "record_id": record_id, "kind": kind, "storage": "local JSONL"}
        except OSError:
            return {"ok": False, "error": "Local storage unavailable; nothing confirmed as saved."}

    def execute(self, name, arguments, user_text):
        schema = next((d["function"] for d in TOOL_SCHEMAS if d["function"]["name"] == name), None)
        if schema is None:
            return {"ok": False, "error": "Unknown tool."}
        try:
            args = json.loads(arguments)
        except (ValueError, TypeError):
            return {"ok": False, "error": "Arguments must be valid JSON."}
        if not isinstance(args, dict) or set(args) != set(schema["parameters"]["required"]):
            return {"ok": False, "error": "Missing or unexpected tool fields."}
        for key, value in args.items():
            expected = schema["parameters"]["properties"][key]["type"]
            if (expected == "string" and not isinstance(value, str)) or (expected == "integer" and type(value) is not int):
                return {"ok": False, "error": "Wrong argument type."}
        if name == "record_customer_interest":
            for field in ("name", "email"):
                if not args[field].strip() or args[field].strip().casefold() not in user_text.casefold():
                    return {"ok": False, "error": f"Ask the customer for their {field}; it was not supplied."}
        return getattr(self, name)(**args)
