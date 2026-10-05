"""Bounded, public progress from official CLI JSONL events.

Only assistant text and tool lifecycle summaries cross into the task record.
Reasoning, tool arguments/results, account metadata and raw JSON are ignored.
"""
from __future__ import annotations

from collections import OrderedDict
import json
import re
import threading
import time

from ..transfer_bundle import now_iso

MAX_LIVE_TEXT = 64_000
MAX_EVENT = 1_000_000
MAX_ACTIVITY = 40


class TaskStream:
    def __init__(self, agent, persist):
        self.agent = agent
        self.persist = persist
        self.lock = threading.RLock()
        self.buffer = ""
        self.discarding = False
        self.messages = OrderedDict()
        self.activity = OrderedDict()
        self.current = ""
        self.blocks = {}
        self.sequence = 0
        self.final = ""
        self.has_result = False
        self.session_id = ""
        self.reported_model = ""
        self.error = ""
        self.dirty = False
        self.last_flush = 0.0
        self._activity("agent", "Starting agent", "running")

    def _activity(self, key, title=None, status="running"):
        key = str(key)[:200]
        previous = self.activity.get(key, {})
        self.activity[key] = {"id": key, "title": title or previous.get("title", "Tool"),
                              "status": status, "at": now_iso()}
        while len(self.activity) > MAX_ACTIVITY:
            self.activity.popitem(last=False)
        self.dirty = True

    def _message(self, key, value):
        if not isinstance(value, str) or not value:
            return
        key = str(key)[:200]
        self.messages[key] = value[-MAX_LIVE_TEXT:]
        while len(self.messages) > 1 and sum(map(len, self.messages.values())) > MAX_LIVE_TEXT:
            self.messages.popitem(last=False)
        self.dirty = True

    def feed(self, channel, chunk):
        if channel != "stdout":
            return
        with self.lock:
            if self.discarding:
                if "\n" not in chunk:
                    return
                chunk = chunk.split("\n", 1)[1]
                self.discarding = False
            self.buffer += chunk
            while "\n" in self.buffer:
                line, self.buffer = self.buffer.split("\n", 1)
                if len(line) <= MAX_EVENT:
                    self._line(line)
            if len(self.buffer) > MAX_EVENT:
                self.buffer = ""
                self.discarding = True
            self.flush()

    def _line(self, line):
        try:
            event = json.loads(line)
            if not isinstance(event, dict):
                return
            if self.agent == "claude-code":
                self._claude(event)
            else:
                self._codex(event)
        except (ValueError, TypeError, AttributeError, KeyError):
            # An unknown/malformed event must never become raw user-visible text.
            return

    def _codex(self, event):
        kind = event.get("type")
        if kind == "thread.started":
            self._session(event.get("thread_id"))
        if kind in {"thread.started", "turn.started"}:
            self._activity("agent", "Agent connected", "running")
        elif kind == "turn.completed":
            self.error = ""
        elif kind in {"item.started", "item.updated", "item.completed"}:
            item = event.get("item", {})
            key = item.get("id", "item")
            item_type = item.get("type")
            if item_type == "agent_message":
                self._message(key, item.get("text", ""))
                if kind == "item.completed":
                    self.final = item.get("text", "")[:200_000]
            elif item_type in {"command_execution", "file_change", "mcp_tool_call", "web_search"}:
                title = {"command_execution": "Run command", "file_change": "Update project files",
                         "mcp_tool_call": "Use connected tool", "web_search": "Search the web"}[item_type]
                status = "running" if kind != "item.completed" else "completed"
                if item.get("status") == "failed" or item.get("exit_code") not in (None, 0):
                    status = "failed"
                self._activity(key, title, status)
        elif kind in {"turn.failed", "error"}:
            detail = event.get("error", {}).get("message", "") if kind == "turn.failed" else event.get("message", "")
            self.error = detail[:4000] if isinstance(detail, str) else "Agent reported an error."
            self._activity("agent", "Agent reported an error", "failed")

    def _claude(self, event):
        if event.get("parent_tool_use_id"):
            return
        kind = event.get("type")
        if kind == "system" and event.get("subtype") in {"init", "api_retry"}:
            self._session(event.get("session_id"))
            title = "Retrying provider request" if event.get("subtype") == "api_retry" else "Agent connected"
            self._activity("agent", title, "running")
        elif kind == "stream_event":
            part = event.get("event", {})
            if part.get("type") == "message_start":
                self.sequence += 1
                self.current = part.get("message", {}).get("id") or f"message-{self.sequence}"
                self.blocks = {}
            elif part.get("type") == "content_block_start":
                block = part.get("content_block", {})
                if block.get("type") == "tool_use":
                    self._tool(block)
                elif block.get("type") == "text":
                    self.blocks[part.get("index", 0)] = block.get("text", "")
            elif part.get("type") == "content_block_delta":
                delta = part.get("delta", {})
                if delta.get("type") == "text_delta" and isinstance(delta.get("text"), str):
                    index = part.get("index", 0)
                    self.blocks[index] = (self.blocks.get(index, "") + delta["text"])[-MAX_LIVE_TEXT:]
                    # Message text blocks share the same budget as retained output.
                    if sum(map(len, self.blocks.values())) > MAX_LIVE_TEXT:
                        self.blocks = {index: self.blocks[index]}
                    self._message(self.current, "\n\n".join(self.blocks.values()))
        elif kind == "assistant":
            message = event.get("message", {})
            reported_model = message.get('model')
            if isinstance(reported_model, str) and re.fullmatch(r'[\w./:\[\]-]{1,120}', reported_model):
                self.reported_model = reported_model
                self.dirty = True
            blocks = message.get("content", [])
            text = "\n\n".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text")
            self._message(message.get("id") or self.current, text)
            for block in blocks:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    self._tool(block)
        elif kind == "user":
            for block in event.get("message", {}).get("content", []):
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    self._activity(block.get("tool_use_id", "tool"), status="failed" if block.get("is_error") else "completed")
        elif kind == "result":
            self._session(event.get("session_id"))
            value = event.get("result", "")
            if not isinstance(value, str):
                return
            self.has_result = True
            self.final = value[:200_000]
            if event.get("is_error"):
                self.error = self.final or "Claude Code reported an error."

    def _tool(self, block):
        name = block.get("name", "")
        title = {"Bash": "Run command", "Read": "Read file", "Write": "Write file", "Edit": "Edit file",
                 "Glob": "Find files", "Grep": "Search files", "WebSearch": "Search the web",
                 "WebFetch": "Read web page", "Agent": "Run subtask"}.get(name, "Use connected tool")
        key = block.get("id", "tool")
        if key not in self.activity:
            self._activity(key, title)

    def _session(self, value):
        if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,200}", value):
            self.session_id = value
            self.dirty = True

    def flush(self, force=False):
        with self.lock:
            if not self.dirty or (not force and time.monotonic() - self.last_flush < 0.5):
                return
            self.persist(liveOutput="\n\n".join(self.messages.values())[-MAX_LIVE_TEXT:],
                         activity=list(self.activity.values()), streamUpdatedAt=now_iso(), agentSessionID=self.session_id,
                         reportedModel=self.reported_model)
            self.dirty = False
            self.last_flush = time.monotonic()

    def end_input(self):
        with self.lock:
            if self.buffer and not self.discarding:
                self._line(self.buffer)
            self.buffer = ""

    def finish(self, status):
        with self.lock:
            self.end_input()
            for item in list(self.activity.values()):
                if item["status"] == "running":
                    self._activity(item["id"], status="completed" if status == "completed" else "stopped")
            self._activity("agent", "Task finished" if status == "completed" else "Task " + status.replace("_", " "),
                           "completed" if status == "completed" else "stopped")
            self.flush(force=True)
