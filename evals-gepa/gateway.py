"""Course gateway: base URL, token, prices in CAD, one chat call with retries, plain error messages, a cost meter.

Every script in this folder calls the gateway through `chat()` (or, for the Inspect eval, through `inspect_model()`),
so the token, the retries and the prices live in one place."""

from __future__ import annotations

import os
import sys
import threading
import time

DEFAULT_URL = "https://oay6tcpsuv4gn5mubtlj7rnbl40gmrlv.lambda-url.ca-central-1.on.aws/v1"
WORKER = "qwen3.6-35b-a3b"     # answers the cases
REFLECTOR = "qwen3.8-27b"      # GEPA's reflection model: reads failures, writes a new prompt
ALLOWED = (WORKER, REFLECTOR, "qwen3-embedding-0.6b")

# CAD per million tokens, (input, output). Course gateway price list, 2026-11-16.
PRICES = {WORKER: (0.05, 0.10), REFLECTOR: (0.10, 0.20), "qwen3-embedding-0.6b": (0.0, 0.0)}

WORKER_MAX_TOKENS = 1024       # caps the cost of one worker reply (thinking included)
REFLECTOR_MAX_TOKENS = 4096    # caps the cost of one reflection reply
RETRIES_502 = 3                # the gateway sometimes returns 502 from upstream
CONCURRENCY = 4                # calls in flight at once, in the eval and in GEPA


class GatewayError(SystemExit):
    """A problem the student can fix, said in one plain sentence. Exits without a traceback."""


def base_url() -> str:
    return os.environ.get("COURSE_GATEWAY_URL", DEFAULT_URL).rstrip("/")


def token() -> str:
    t = os.environ.get("KB_MCP_TOKEN", "").strip()
    if not t:
        raise GatewayError("KB_MCP_TOKEN is not set. Set it to your course token (README section 2, Set up), "
                           "then open a new terminal or run the set command again.")
    return t


def cad(model: str, tokens_in: int, tokens_out: int) -> float:
    p_in, p_out = PRICES.get(model, (0.0, 0.0))
    return (tokens_in * p_in + tokens_out * p_out) / 1e6


def plain(e: Exception, model: str = "") -> str:
    """One sentence for an OpenAI SDK error from the gateway."""
    import openai

    if isinstance(e, openai.AuthenticationError):
        return "401: the gateway did not accept your token. Check KB_MCP_TOKEN: the whole token, no spaces or quote marks inside it."
    if isinstance(e, openai.PermissionDeniedError):
        return (f"403: your key may not use model '{model}'. Allowed: {', '.join(ALLOWED)}. "
                "Check the spelling of the model name.")
    if isinstance(e, openai.RateLimitError):
        return (f"429: too many requests (120 a minute per key) after {RETRIES_502} retries, or your 2 CAD term budget is used up. "
                "Wait a minute and run the step again.")
    if isinstance(e, openai.APIStatusError) and e.status_code in (502, 503, 504):
        return f"{e.status_code}: the model behind the gateway did not answer, after {RETRIES_502} retries. Try again in a minute."
    if isinstance(e, openai.APITimeoutError):
        return (f"the model took longer than 90 s to answer, after {RETRIES_502} retries. The gateway may be busy: "
                "wait a minute and run the step again.")
    if isinstance(e, openai.APIConnectionError):
        return f"no connection to the gateway at {base_url()}. Check your Wi-Fi, then COURSE_GATEWAY_URL if you set it."
    return f"{type(e).__name__}: {str(e)[:200]}"


_client = None


def client():
    global _client
    if _client is None:
        from openai import OpenAI

        _client = OpenAI(base_url=base_url(), api_key=token(), max_retries=0, timeout=90)
    return _client


def chat(model: str, messages: list[dict], max_tokens: int, meter: "Meter | None" = None,
         role: str = "") -> dict:
    """One chat completion. Retries a 502/503/504 or a timeout up to RETRIES_502 times (1 s, 2 s, 4 s), a 429 with 5 s, 10 s, 20 s.
    Returns text, tokens_in, tokens_out, cad. Raises GatewayError with a plain message on anything else."""
    import openai

    if meter:
        meter.reserve(model, messages, max_tokens)
    for attempt in range(RETRIES_502 + 1):
        try:
            r = client().chat.completions.create(model=model, messages=messages, max_tokens=max_tokens,
                                                 temperature=0)
            break
        except (openai.APIStatusError, openai.APITimeoutError) as e:
            code = getattr(e, "status_code", "timeout")
            if code in (429, 502, 503, 504, "timeout") and attempt < RETRIES_502:
                wait = float(os.environ.get("GATEWAY_BACKOFF_S", "1")) * (5 if code == 429 else 1) * 2 ** attempt
                print(f"{code} from the gateway, retry {attempt + 1} of {RETRIES_502} in {wait:g} s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise GatewayError(plain(e, model)) from None
        except openai.APIConnectionError as e:
            raise GatewayError(plain(e, model)) from None
    u = r.usage
    t_in, t_out = (u.prompt_tokens or 0, u.completion_tokens or 0) if u else (0, 0)
    out = dict(text=r.choices[0].message.content or "", tokens_in=t_in, tokens_out=t_out, cad=cad(model, t_in, t_out))
    if meter:
        meter.add(model, role, t_in, t_out)
    return out


class BudgetExceeded(RuntimeError):
    pass


class Meter:
    """Running cost in CAD. Before each call it adds the worst case of that call (prompt length / 3 tokens in,
    max_tokens out) to what is spent; if that would pass the budget, it refuses the call."""

    def __init__(self, budget_cad: float):
        self.budget, self.spent, self.lock = budget_cad, 0.0, threading.Lock()
        self.calls: dict[str, int] = {}
        self.tokens = {"in": 0, "out": 0}
        self.abort: BaseException | None = None  # the first budget or gateway error (optimize.py)

    @staticmethod
    def worst_case(model: str, messages: list[dict], max_tokens: int) -> float:
        chars = sum(len(str(m.get("content", ""))) for m in messages)
        return cad(model, chars // 3 + 20, max_tokens)

    def reserve(self, model: str, messages: list[dict], max_tokens: int) -> None:
        w = self.worst_case(model, messages, max_tokens)
        if self.spent + w > self.budget:
            raise BudgetExceeded(f"cost meter: {self.spent:.4f} CAD spent; the next call could cost up to {w:.4f} CAD "
                                 f"and pass the budget of {self.budget:.4f} CAD. Stopped before the call.")

    def add(self, model: str, role: str, t_in: int, t_out: int) -> None:
        with self.lock:
            self.spent += cad(model, t_in, t_out)
            self.calls[role] = self.calls.get(role, 0) + 1
            self.tokens["in"] += t_in
            self.tokens["out"] += t_out


def inspect_model(model: str = WORKER):
    """The same gateway as an Inspect model (Inspect's OpenAI-compatible provider)."""
    from inspect_ai.model import GenerateConfig, get_model

    cfg = GenerateConfig(max_tokens=WORKER_MAX_TOKENS, temperature=0, max_retries=RETRIES_502, timeout=90,
                         max_connections=CONCURRENCY)
    return get_model(f"openai-api/course/{model}", base_url=base_url(), api_key=token(), config=cfg)
