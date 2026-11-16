"""Course gateway: base URL, key, models, prices in CAD, one chat call with retries, plain error messages, a cost meter.

Every script in this folder calls the gateway through `chat()` (or, for the Inspect eval, through `inspect_model()`),
so the key, the models, the retries and the prices live in one place.

Environment variables (all optional except a key):
    KB_MCP_TOKEN        your course token (the key for the course gateway)
    LLM_API_KEY         another key; used instead of KB_MCP_TOKEN when set (README, extra exercise "Use your own API key")
    COURSE_GATEWAY_URL  base URL of an OpenAI-compatible API; default: the course gateway
    TASK_MODEL          the model that answers the cases; default qwen3.6-35b-a3b
    GEPA_REFLECTOR      GEPA's reflection model; default qwen3.8-27b (course choices: qwen3.8-27b, gpt-6-luna)
A model outside PRICES runs, but its cost is unknown: the kit says so and the CAD budget stop does not apply to it."""

from __future__ import annotations

import os
import re
import sys
import threading
import time

DEFAULT_URL = "https://oay6tcpsuv4gn5mubtlj7rnbl40gmrlv.lambda-url.ca-central-1.on.aws/v1"
WORKER = "qwen3.6-35b-a3b"     # default task model: answers the cases (env TASK_MODEL)
REFLECTOR = "qwen3.8-27b"      # default reflection model: reads failures, writes a new prompt (env GEPA_REFLECTOR)
LUNA = "gpt-6-luna"            # the other course reflection model; a weekly number of calls per key
REFLECTORS = (REFLECTOR, LUNA)
ALLOWED = (WORKER, REFLECTOR, LUNA, "qwen3-embedding-0.6b")

# CAD per million tokens, (input, output). Course gateway price list, 2026-11-16.
PRICES = {WORKER: (0.05, 0.10), REFLECTOR: (0.10, 0.20), LUNA: (0.145, 0.725), "qwen3-embedding-0.6b": (0.0, 0.0)}

WORKER_MAX_TOKENS = 1024       # caps the cost of one worker reply (thinking included)
REFLECTOR_MAX_TOKENS = int(os.environ.get("REFLECTOR_MAX_TOKENS", "16384"))  # cap on one reflection reply; a thinking model needs room (the course gateway clamps to 8192)
RETRIES_502 = 3                # the gateway sometimes returns 502 from upstream
CONCURRENCY = 4                # calls in flight at once, in the eval and in GEPA


class GatewayError(SystemExit):
    """A problem the student can fix, said in one plain sentence. Exits without a traceback."""


def base_url() -> str:
    return (os.environ.get("COURSE_GATEWAY_URL", "").strip() or DEFAULT_URL).rstrip("/")


def task_model() -> str:
    return os.environ.get("TASK_MODEL", "").strip() or WORKER


def reflector() -> str:
    return os.environ.get("GEPA_REFLECTOR", "").strip() or REFLECTOR


def key_name() -> str:
    """The variable the key comes from: LLM_API_KEY when it is set, else KB_MCP_TOKEN. The key itself is never printed."""
    return "LLM_API_KEY" if os.environ.get("LLM_API_KEY", "").strip() else "KB_MCP_TOKEN"


def token() -> str:
    t = os.environ.get(key_name(), "").strip()
    if not t:
        raise GatewayError("KB_MCP_TOKEN is not set. Set it to your course token (README section 2, Set up), "
                           "then open a new terminal or run the set command again.")
    return t


def is_gpt(model: str) -> bool:
    """OpenAI GPT and o-series names. gpt-6-luna on the course gateway refuses temperature 0 (tested 2026-11-16);
    OpenAI's newer reasoning models accept only the default temperature."""
    return bool(re.match(r"(openai/)?(gpt-|o\d)", model.lower()))


def on_course_gateway() -> bool:
    return base_url() == DEFAULT_URL.rstrip("/")


def sampling(model: str, max_tokens: int) -> dict:
    """The parameters chat() sends besides model and messages. Temperature 0 (repeatable replies) for every model
    except GPT and o-series models, which get the provider's default temperature.
    The token cap is max_tokens, which the course gateway reads to reserve the most a call can cost. Sent straight to
    OpenAI (base URL https://api.openai.com/v1, endpoint POST /chat/completions), a GPT or o-series model gets
    max_completion_tokens instead: OpenAI's chat completions reference says max_tokens "is now deprecated in favor of
    max_completion_tokens" and "is not compatible with o-series models", and the temperature default is 1, range 0-2
    (https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create, read 2026-11-16).
    check_gateway.py lists models with GET /models, which OpenAI serves at https://api.openai.com/v1/models
    (https://developers.openai.com/api/reference/resources/models/methods/list, read 2026-11-16).
    Inspect does the same rewrite for GPT-5 and later names (inspect_ai/model/_openai.py, needs_max_completion_tokens)."""
    p: dict = {} if is_gpt(model) else {"temperature": 0}
    if is_gpt(model) and not on_course_gateway():
        p["max_completion_tokens"] = max_tokens
    else:
        p["max_tokens"] = max_tokens
    return p


def price_known(model: str) -> bool:
    return model in PRICES


_warned: set[str] = set()
_warn_lock = threading.Lock()


def warn_unknown(model: str) -> None:
    """Prints the unknown-cost line once per model (chat() runs on several threads)."""
    with _warn_lock:
        if model in _warned or price_known(model):
            return
        _warned.add(model)
    print(f"cost unknown for {model}: not a course gateway price. "
          "Costs for it print as 0 and the CAD budget stop does not apply to it.", file=sys.stderr)


def cad(model: str, tokens_in: int, tokens_out: int) -> float:
    """CAD for the tokens. 0.0 for a model outside the course price list (warn_unknown says so)."""
    if not price_known(model):
        warn_unknown(model)
        return 0.0
    p_in, p_out = PRICES[model]
    return (tokens_in * p_in + tokens_out * p_out) / 1e6


def plain(e: Exception, model: str = "") -> str:
    """One sentence for an OpenAI SDK error from the gateway."""
    import openai

    if isinstance(e, openai.AuthenticationError):
        return (f"401: the gateway did not accept your key. Check {key_name()}: the whole key, no spaces or quote marks "
                "inside it.")
    if isinstance(e, openai.PermissionDeniedError):
        if model == LUNA:
            return (f"403: your key may not use {LUNA} now. Each key gets a set number of {LUNA} calls a week; "
                    f"they may not be on your key yet, or they are used up. Unset GEPA_REFLECTOR to use {REFLECTOR}.")
        return (f"403: your key may not use model '{model}'. Course models: {', '.join(ALLOWED)}. "
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
_client_for: tuple = ()


def client():
    """One OpenAI client, made again when the base URL or the key changes (a notebook can change them)."""
    global _client, _client_for
    want = (base_url(), token())
    if _client is None or _client_for != want:
        from openai import OpenAI

        _client, _client_for = OpenAI(base_url=want[0], api_key=want[1], max_retries=0, timeout=280), want
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
            r = client().chat.completions.create(model=model, messages=messages, **sampling(model, max_tokens))
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
        if not price_known(model):
            warn_unknown(model)  # no price, so no reserve: this call runs without the budget stop
            return
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


def inspect_model(model: str | None = None):
    """The same gateway as an Inspect model (Inspect's OpenAI-compatible provider), with the same temperature rule
    as chat(). Inspect itself sends max_completion_tokens for GPT-5 and later names."""
    from inspect_ai.model import GenerateConfig, get_model

    model = model or task_model()
    cfg = GenerateConfig(max_tokens=WORKER_MAX_TOKENS, temperature=sampling(model, 0).get("temperature"),
                         max_retries=RETRIES_502, timeout=280, max_connections=CONCURRENCY)
    return get_model(f"openai-api/course/{model}", base_url=base_url(), api_key=token(), config=cfg)
