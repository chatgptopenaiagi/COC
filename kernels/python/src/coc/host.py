"""Cooperative host adapter with independent lease/cancellation heartbeat."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import math
import signal
import statistics
import threading
import time
from typing import Callable
import jsonschema
from .client import Client

NUMBER_ARRAY = {"type": "array", "items": {"type": "number"}, "minItems": 1, "maxItems": 10000}
def capability(name, description, input_schema, output_schema, *, idempotent=True, cancellable=True):
    return {"name": name, "description": description, "input_schema": input_schema, "output_schema": output_schema,
            "idempotent": idempotent, "cancellable": cancellable, "version": "1.0"}

class HostAdapter:
    def __init__(self, client: Client, host_id: str, name: str, tools: dict[str, tuple[dict, Callable]], language="python"):
        self.client, self.id, self.name, self.tools, self.language = client, host_id, name, tools, language
        self.stopped = threading.Event()
        self._active: dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        self.last_error = None

    def discover_capabilities(self): return [descriptor for descriptor, _ in self.tools.values()]
    def list_available_tools(self): return list(self.tools)
    def read_application_state(self): return {"host_id": self.id, "active_tasks": list(self._active), "last_error": self.last_error}
    def register(self):
        return self.client.call("COC.REGISTER", {"kind": "host", "id": self.id, "name": self.name, "language": self.language, "capabilities": self.discover_capabilities()})
    def execute_authorized_tool(self, task: dict, cancelled: threading.Event):
        descriptor, function = self.tools[task["tool"]]
        jsonschema.validate(task["arguments"], descriptor["input_schema"])
        result = function(task["arguments"], cancelled, task)
        jsonschema.validate(result, descriptor["output_schema"])
        return result
    def usage_tokens(self,result):return 0
    def subscribe_to_events(self, after=0): return self.client.events(after)
    def get_task_status(self, task_id): return self.client.get_task_status(task_id)
    def cancel_task(self, task_id):
        with self._lock:
            if task_id in self._active: self._active[task_id].set()
    def report_error(self, task_id, error):
        self.last_error = type(error).__name__
        return self.client.call("COC.ERROR", {"task_id": task_id, "category": type(error).__name__, "message": "host execution failed"})
    def request_operator_assistance(self, task_id, reason):
        return self.client.call("COC.EVENT", {"task_id": task_id, "kind": "operator_assistance", "reason": reason})
    def detach_agent(self):
        self.stopped.set()
        with self._lock:
            for event in self._active.values(): event.set()
        return self.client.detach_agent(self.id)

    def _heartbeat(self):
        while not self.stopped.wait(.4):
            try:
                response = self.client.call("COC.HEARTBEAT", {"host_id": self.id})
                for task_id in response["cancel_task_ids"]: self.cancel_task(task_id)
            except Exception:
                # Lost authority/connection: cooperative tools must stop rather than keep writing.
                with self._lock:
                    for event in self._active.values(): event.set()

    def run(self, once=False):
        self.register()
        heartbeat = threading.Thread(target=self._heartbeat, daemon=True)
        heartbeat.start()
        try:
            while not self.stopped.is_set():
                try: task = self.client.call("COC.RECOVER", {"action": "claim", "host_id": self.id})["task"]
                except (OSError, RuntimeError):
                    self.stopped.wait(.5)
                    continue
                if not task:
                    self.stopped.wait(.1)
                    continue
                cancelled = threading.Event()
                with self._lock: self._active[task["id"]] = cancelled
                result, error, outcome = None, None, "succeeded"
                try:
                    result = self.execute_authorized_tool(task, cancelled)
                except InterruptedError:
                    outcome = "cancelled"
                except Exception as exc:
                    outcome, error = "failed", {"type": type(exc).__name__, "message": str(exc)[:500]}
                    self.report_error(task["id"], exc)
                receipt = {"task_id": task["id"], "claim_id": task["claim_id"], "outcome": outcome, "result": result, "error": error, "usage_tokens":self.usage_tokens(result) if result else 0}
                # A stable claim/result may be retried; the broker deduplicates identical receipts.
                for attempt in range(3):
                    try:
                        self.client.call("COC.TOOL_RESULT", receipt)
                        break
                    except OSError:
                        self.stopped.wait(.25 * (attempt + 1))
                with self._lock: self._active.pop(task["id"], None)
                if once: break
        finally:
            self.stopped.set()
            heartbeat.join(timeout=2)

def scientific_tools():
    def stats(args, cancelled, task):
        values = args["values"]
        if not all(math.isfinite(x) for x in values): raise ValueError("finite numbers required")
        return {"count": len(values), "mean": statistics.mean(values), "sum": math.fsum(values)}
    def delay(args, cancelled, task):
        if cancelled.wait(args["seconds"]): raise InterruptedError()
        return {"elapsed": args["seconds"]}
    return {
        "statistics": (capability("statistics", "Compute mean and sum of supplied finite numbers", {"type":"object","properties":{"values":NUMBER_ARRAY},"required":["values"],"additionalProperties":False}, {"type":"object","required":["count","mean","sum"],"properties":{"count":{"type":"integer"},"mean":{"type":"number"},"sum":{"type":"number"}},"additionalProperties":False}), stats),
        "cooperative_wait": (capability("cooperative_wait", "Cancellable bounded wait", {"type":"object","properties":{"seconds":{"type":"number","minimum":0,"maximum":30}},"required":["seconds"],"additionalProperties":False},{"type":"object","required":["elapsed"],"properties":{"elapsed":{"type":"number"}}}), delay)
    }

def main():
    parser=argparse.ArgumentParser();parser.add_argument("--id",default="python-science");parser.add_argument("--once",action="store_true");args=parser.parse_args()
    host=HostAdapter(Client.from_env(),args.id,"Python scientific application",scientific_tools())
    signal.signal(signal.SIGINT,lambda *_:host.stopped.set())
    host.run(args.once)
if __name__ == "__main__": main()
