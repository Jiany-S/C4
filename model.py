"""Small OpenAI adapter; every request retains its settings and token usage."""
from __future__ import annotations
import os
import threading
import time
from dotenv import load_dotenv
from tools import ROOT, TOOL_SCHEMAS


class ModelError(RuntimeError):
    """An error safe to display without credentials or request bodies."""

    def __init__(self, message, *, result=None):
        super().__init__(message)
        self.result = result


class CallBudget:
    def __init__(self, limit=600):
        self.limit, self.calls = limit, 0
        self.lock = threading.Lock()

    def take(self):
        with self.lock:
            if self.calls >= self.limit:
                raise ModelError("This run reached its API-call budget.")
            self.calls += 1


class OpenAIModel:
    mode = "live"

    def __init__(self, budget=None, client=None):
        from openai import OpenAI
        load_dotenv(ROOT / ".env")
        self.budget = budget or CallBudget()
        if client is None:
            key = os.getenv("OPENAI_API_KEY", "").strip()
            if not key or key.startswith("your-"):
                raise ModelError("Add OPENAI_API_KEY to C4/.env to enable live replies.")
            client = OpenAI(api_key=key, timeout=40, max_retries=0)
        self.client = client

    def complete(self, messages, generation):
        from openai import OpenAIError
        self.budget.take()
        options = {**generation.options(), "messages": messages, "tools": TOOL_SCHEMAS,
                   "tool_choice": "auto", "parallel_tool_calls": False,
                   "response_format": {"type": "json_object"}, "store": False}
        start = time.perf_counter()
        try:
            response = self.client.chat.completions.create(**options)
        except OpenAIError as exc:
            status = getattr(exc, "status_code", None)
            detail = {401: "Check the local API key.", 429: "Check quota or retry later.",
                      400: "Check model and parameter support."}.get(status, "Check the connection and retry.")
            raise ModelError("Model request failed. " + detail) from None
        if not response.choices:
            raise ModelError("The model returned no choices.")
        choice = response.choices[0]
        msg = choice.message
        parsed = {"role": "assistant", "content": msg.content}
        if msg.tool_calls:
            parsed["tool_calls"] = [{"id": c.id, "type": "function", "function": {
                "name": c.function.name, "arguments": c.function.arguments}} for c in msg.tool_calls]
        result = {"message": parsed, "usage": response.usage.model_dump() if response.usage else {},
                "model": response.model, "response_id": response.id,
                "finish_reason": choice.finish_reason, "seconds": time.perf_counter() - start,
                "settings": generation.options()}
        if choice.finish_reason in {"length", "content_filter"}:
            raise ModelError("The model response was incomplete; increase the token limit or shorten the request.",
                             result=result)
        return result
