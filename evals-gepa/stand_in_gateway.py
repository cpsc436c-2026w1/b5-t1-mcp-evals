"""Stand-in for the course gateway: a local OpenAI-compatible server with canned, deterministic answers.
No model runs here. Use it to try the whole flow without a token or any cost.

    uv run python stand_in_gateway.py                 # serves http://127.0.0.1:8765/v1, token "stand-in-token"
    uv run python stand_in_gateway.py --fail-once     # the first chat call returns 502
    uv run python stand_in_gateway.py --no-luna       # a key that may not use gpt-6-luna (403)

Then, in a second terminal: COURSE_GATEWAY_URL=http://127.0.0.1:8765/v1 and KB_MCP_TOKEN=stand-in-token.

What it does, like the real gateway: checks the bearer token (401), allows only the models of this key (403; the
default key may use all course models, gpt-6-luna included; `--no-luna` makes a key without it), refuses
temperature 0 for a GPT model with a 400 as the provider does, answers GET /v1/models and POST /v1/chat/completions
with a usage block.
How the worker answers: it takes the reference SQL of the question from data/cases.jsonl and breaks it in a way
you can name, unless the system prompt has a rule that prevents that failure:
  - credit-card questions use payment code 2 (cash) unless the prompt says that 1 is credit card
  - percentage questions return a fraction unless the prompt says to multiply by 100
  - about one question in three gets a sentence after the query unless the prompt says to reply with SQL only
  - "or later in the day" questions use > where >= is right (no rule fixes this one)
The reflection model (any model, when the request is GEPA's reflection prompt) adds one rule for each failure it reads about in GEPA's feedback, and answers in the
JSON format dspy.GEPA asks for."""

from __future__ import annotations

import argparse
import json
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
TOKEN = "stand-in-token"
MODELS = ["qwen3.6-35b-a3b", "qwen3.8-27b", "gpt-6-luna", "qwen3-embedding-0.6b"]
REFLECTORS = ("qwen3.8-27b", "gpt-6-luna")

RULES = {
    "code": "payment_type codes: 1 = credit card, 2 = cash, 3 = no charge, 4 = dispute.",
    "percent": "For a percentage, return 100.0 * part / whole, not a fraction between 0 and 1.",
    "sql_only": "Reply with the SQL only: one SELECT statement, no explanation before or after it.",
}


def _has(prompt: str, rule: str) -> bool:
    p = prompt.lower()
    return {"code": "1 = credit card" in p, "percent": "100.0 *" in p or "multiply by 100" in p,
            "sql_only": "sql only" in p or "only the sql" in p}[rule]


def worker_reply(system: str, question: str) -> str:
    refs = {c["question"]: c["sql"] for c in map(json.loads, (HERE / "data" / "cases.jsonl").read_text(encoding="utf-8").splitlines())}
    sql = refs.get(question.strip())
    if sql is None:
        return "Hello. I am the stand-in model."
    q = question.lower()
    if "credit" in q and not _has(system, "code"):
        sql = sql.replace("payment_type = 1", "payment_type = 2")
    if "percentage" in q and not _has(system, "percent"):
        sql = sql.replace("100.0 * ", "1.0 * ")
    if "or later in the day" in q:
        sql = sql.replace(">=", ">")
    if sum(map(ord, question)) % 3 == 0 and not _has(system, "sql_only"):
        sql += "\n\nThis query counts the matching rows and returns the answer."
    return sql


def reflection_reply(prompt: str) -> str:
    """Two reflection formats: dspy.GEPA's (fields, JSON reply) and plain gepa's (``` blocks)."""
    dspy_format = "[[ ## current_instruction ## ]]" in prompt
    if dspy_format:
        m = re.search(r"\[\[ ## current_instruction ## \]\]\n(.*?)\n\n\[\[ ## examples_with_feedback", prompt, re.S)
        prompt = prompt.replace("\\n", "\n")  # the examples arrive as JSON, with escaped newlines
    else:
        m = re.search(r"```\n?(.*?)\n?```", prompt, re.S)
    current = m.group(1).strip() if m else ""
    add = []
    if re.search(r"Reference SQL: [^\n]*payment_type = 1[^\n]*\n[^\n]*\nFAILURE: wrong value[^\n]*\n"
                 r"Model SQL: [^\n]*payment_type = 2", prompt) and not _has(current, "code"):
        add.append(RULES["code"])
    if "fraction where a percentage" in prompt and not _has(current, "percent"):
        add.append(RULES["percent"])
    if "not one SQL query" in prompt and not _has(current, "sql_only"):
        add.append(RULES["sql_only"])
    text = current + ("\n" + "\n".join(add) if add else "")
    return json.dumps({"new_instruction": text}) if dspy_format else "```\n" + text + "\n```"


class Handler(BaseHTTPRequestHandler):
    server_version = "StandIn/1"

    def log_message(self, *a):  # quiet
        pass

    def _send(self, code: int, body: dict) -> None:
        data = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _auth(self) -> bool:
        if self.headers.get("Authorization", "") != f"Bearer {self.server.token}":
            self._send(401, {"error": {"message": "invalid token", "type": "authentication_error"}})
            return False
        return True

    def do_GET(self):
        if not self._auth():
            return
        if self.path.rstrip("/").endswith("/models"):
            return self._send(200, {"object": "list", "data": [{"id": m, "object": "model"} for m in self.server.models]})
        self._send(404, {"error": {"message": "not found"}})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        if not self._auth():
            return
        if not self.path.rstrip("/").endswith("/chat/completions"):
            return self._send(404, {"error": {"message": "not found"}})
        model = body.get("model", "")
        if model not in self.server.models:
            return self._send(403, {"error": {"message": f"model {model} is not allowed for this key"}})
        if model.startswith("gpt-") and body.get("temperature") == 0:
            return self._send(400, {"error": {"message": "Unsupported value: 'temperature' does not support 0 with this "
                                              "model. Only the default (1) value is supported.",
                                              "type": "invalid_request_error", "param": "temperature",
                                              "code": "unsupported_value"}})
        with self.server.lock:
            self.server.chat_calls += 1
            if self.server.fail_502 > 0:
                self.server.fail_502 -= 1
                return self._send(502, {"error": {"message": "upstream error"}})
        msgs = body.get("messages", [])
        system = "\n".join(str(m.get("content", "")) for m in msgs if m.get("role") == "system")
        user = next((str(m.get("content", "")) for m in reversed(msgs) if m.get("role") == "user"), "")
        reflect = model in REFLECTORS or "[[ ## current_instruction ## ]]" in user
        with self.server.lock:
            self.server.calls_by_model[model] = self.server.calls_by_model.get(model, 0) + 1
            self.server.requests.append({k: v for k, v in body.items() if k != "messages"})
        if os.environ.get("STAND_IN_DUMP") and reflect:
            with open(os.environ["STAND_IN_DUMP"], "a", encoding="utf-8") as f:
                f.write(json.dumps(msgs) + "\n")
        text = reflection_reply(user) if reflect else worker_reply(system, user)
        t_in = sum(len(str(m.get("content", ""))) for m in msgs) // 4 + 5
        t_out = len(text) // 4 + 1
        self._send(200, {"id": "standin", "object": "chat.completion", "created": 0, "model": model,
                         "choices": [{"index": 0, "finish_reason": "stop",
                                      "message": {"role": "assistant", "content": text}}],
                         "usage": {"prompt_tokens": t_in, "completion_tokens": t_out, "total_tokens": t_in + t_out}})


def serve(port: int = 8765, fail_502: int = 0, token: str = TOKEN, models: list[str] | None = None) -> ThreadingHTTPServer:
    """Starts the server in a background thread and returns it (call .shutdown() to stop).
    `models`: the models this key may use (default MODELS). `calls_by_model` and `requests` record each chat call."""
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    srv.token, srv.fail_502, srv.chat_calls, srv.lock = token, fail_502, 0, threading.Lock()
    srv.models = list(MODELS if models is None else models)
    srv.calls_by_model, srv.requests = {}, []
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--fail-once", action="store_true", help="the first chat call returns 502")
    ap.add_argument("--no-luna", action="store_true", help="a key that may not use gpt-6-luna")
    a = ap.parse_args()
    srv = serve(a.port, 1 if a.fail_once else 0, models=[m for m in MODELS if not (a.no_luna and m == "gpt-6-luna")])
    print(f"stand-in gateway on http://127.0.0.1:{a.port}/v1  token: {TOKEN}  (Ctrl+C to stop)")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        srv.shutdown()
