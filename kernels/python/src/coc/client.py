"""Authenticated COC-PROTOCOL/1 client. Credentials never enter envelopes."""
from __future__ import annotations
import datetime as dt
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import urllib.parse
import uuid
from typing import Any, Iterator
import jsonschema

VERSION = "COC-PROTOCOL/1"

def envelope(agent: str, method: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": method, "params": {
        "protocol_version": VERSION, "message_id": uuid.uuid4().hex, "agent_id": agent,
        "parent_agent_id": None, "child_agent_id": None, "host_id": payload.get("host_id"),
        "session_id": payload.get("session_id"), "task_id": payload.get("task_id"),
        "correlation_id": None, "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": [], "payload": payload, "status": "request", "error": None, "integrity": {}}}

def protocol_schema() -> dict:
    packaged = Path(__file__).with_name("message.schema.json")
    source = Path(__file__).resolve().parents[4] / "specifications/schemas/message.schema.json"
    return json.loads((packaged if packaged.exists() else source).read_text(encoding="utf-8"))

class COCError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code

class Client:
    def __init__(self, url: str, token: str, agent: str, timeout: float = 15):
        parsed=urllib.parse.urlparse(url)
        if parsed.username or parsed.password or parsed.query or parsed.fragment or not parsed.hostname:
            raise ValueError("invalid broker URL")
        if parsed.scheme!='https' and not (parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost','::1')):
            raise ValueError("remote connections require HTTPS")
        self.url, self._token, self.agent, self.timeout = url.rstrip("/"), token, agent, timeout
        self.validator = jsonschema.Draft7Validator(protocol_schema(), format_checker=jsonschema.FormatChecker())
        self.opener=urllib.request.build_opener(NoRedirect(),urllib.request.ProxyHandler({}) if parsed.hostname in ('127.0.0.1','localhost','::1') else urllib.request.ProxyHandler())

    @classmethod
    def from_env(cls):
        return cls(os.environ.get("COC_URL", "http://127.0.0.1:7310"), os.environ["COC_TOKEN"], os.environ.get("COC_AGENT", "operator"))

    def call(self, method: str, payload: dict | None = None) -> Any:
        message = envelope(self.agent, method, payload or {})
        self.validator.validate(message)
        request = urllib.request.Request(self.url + "/rpc", json.dumps(message).encode(), {
            "Content-Type": "application/json", "Authorization": "Bearer " + self._token})
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                result = json.load(response)
        except urllib.error.HTTPError as exc:
            raise COCError("HTTP_" + str(exc.code), "broker request rejected") from None
        if "error" in result:
            error = result["error"]
            raise COCError(error.get("data", {}).get("type", str(error["code"])), error["message"])
        if result["id"] != message["id"]:
            raise COCError("CORRELATION", "response id mismatch")
        return result["result"]["payload"]["data"]

    def issue(self, principal: str, scopes: list[str], ttl: int = 3600) -> "Client":
        issued = self.call("COC.AUTHENTICATE", {"principal": principal, "scopes": scopes, "ttl_seconds": ttl})
        return Client(self.url, issued["token"], principal, self.timeout)

    def submit(self, host: str, tool: str, arguments: dict, *, parent_id: str = "", key: str | None = None, budget: dict | None = None, timeout: int = 120) -> dict:
        return self.call("COC.DELEGATE" if parent_id else "COC.TOOL_REQUEST", {
            "host_id": host, "tool": tool, "arguments": arguments, "parent_id": parent_id,
            "idempotency_key": key or uuid.uuid4().hex, "timeout_seconds": timeout, "budget": budget or {}})

    def wait(self, task_id: str, timeout: float = 120) -> dict:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            task = self.call("COC.RECOVER", {"task_id": task_id})
            if task["state"] in {"succeeded", "failed", "cancelled", "outcome_unknown"}:
                return task
            time.sleep(.1)
        raise TimeoutError("task wait deadline exceeded; operation may still be executing")

    def events(self, after: int = 0) -> Iterator[dict]:
        request = urllib.request.Request(f"{self.url}/events?after={after}", headers={"Authorization": "Bearer " + self._token})
        with self.opener.open(request, timeout=self.timeout) as response:
            for raw in response:
                if raw.startswith(b"data: "):
                    yield json.loads(raw[6:])

    def discover_capabilities(self): return self.call("COC.CAPABILITIES")
    def get_task_status(self, task_id): return self.call("COC.RECOVER", {"task_id": task_id})
    def cancel_task(self, task_id): return self.call("COC.CANCEL", {"task_id": task_id})
    def detach_agent(self, host_id): return self.call("COC.DETACH", {"host_id": host_id})

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise COCError('REDIRECT_DENIED','broker redirects are prohibited')
