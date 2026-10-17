"""Ollama LLM client: strict-JSON intent extraction + parameter memory.

The LLM NEVER sees secrets and NEVER receives execution tools.
Output is validated against INTENT_SCHEMA; invalid output triggers one retry,
then a controlled clarification fallback.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request

from . import config

INTENT_SCHEMA = {
    "intent_type": "one of: MARKET_QUERY, AUTOMATION_CREATE, CONDITION_CREATE, "
                   "AUTOMATION_CONTROL, HEALTH_QUERY, NEWS_QUERY, CHAT",
    "strategy": "EMA_CROSSOVER | VWAP_SUPERTREND | null",
    "symbol": "e.g. SOL-USDT or null",
    "timeframe_min": "int minutes (1,2,3,5,10,15,30,60) or null",
    "lookback_min": "int minutes or null",
    "aggregation_interval_min": "int minutes or null",
    "direction_preference": "BULLISH|BEARISH|ANY|null",
    "margin_usage_pct": "number 0-100 or null",
    "leverage": "number or null",
    "action": "PAUSE|RESUME|CANCEL|SKIP|LIST|null",
    "automation_id": "int or null",
    "analytics_requested": ("subset of: candles,movement,volume_flow,volume_profile,"
                            "order_book,ema,vwap,supertrend,crossover_estimate"),
    "missing_parameters": ["list of still-required params"],
    "reply_hint": "short natural-language reply for the user",
}

SYSTEM_PROMPT = (
    "You are Ophelia's conversational trading assistant. Translate the user's "
    "message into ONE JSON object. You never execute anything and never invent "
    "numbers.\\n"
    "CONTEXT = parameters already given earlier; reuse them. If the message changes "
    "only one parameter (e.g. 'make it 5 minute', 'use 20x'), output just that "
    "change plus intent fields you are sure of - omit unchanged CONTEXT keys.\\n"
    "Never guess missing critical automation params; list them in "
    "missing_parameters. DO NOT hallucinate default values (like margin, "
    "leverage, or timeframe). If a required parameter is missing from the "
    "message and CONTEXT, omit its key entirely and add its name to "
    "missing_parameters. CRITICAL: never copy values from the examples below - only "
    "use values explicitly present in the user's message or CONTEXT. "
    "reply_hint = max 2 short conversational sentences; if "
    "params are missing ask for the most important one as a friendly question.\\n"
    "direction_preference is a PREFERENCE only, never a restriction. Never promise "
    "execution; user must confirm later. Future crossovers are estimates only.\\n"
    "EXAMPLES:\\n"
    "U: whats sol doing / current price -> {\"intent_type\":\"MARKET_QUERY\",\"symbol\":\"SOL-USDT\"}\\n"
    "U: last 30 min movement / average 5m candle movement -> {\"intent_type\":\"MARKET_QUERY\",\"symbol\":\"SOL-USDT\",\"lookback_min\":30,\"aggregation_interval_min\":5,\"analytics_requested\":[\"movement\"]}\\n"
    "U: how is volume / buying pressure increasing? -> {\"intent_type\":\"MARKET_QUERY\",\"symbol\":\"SOL-USDT\",\"lookback_min\":30,\"analytics_requested\":[\"volume_flow\"]}\\n"
    "U: order book? -> {\"intent_type\":\"MARKET_QUERY\",\"symbol\":\"SOL-USDT\",\"analytics_requested\":[\"order_book\"]}\\n"
    "U: how many candles until ema cross / could crossover happen soon -> {\"intent_type\":\"MARKET_QUERY\",\"symbol\":\"SOL-USDT\",\"aggregation_interval_min\":5,\"analytics_requested\":[\"crossover_estimate\"]}\\n"
    "U: does sol look bullish or bearish -> {\"intent_type\":\"MARKET_QUERY\",\"symbol\":\"SOL-USDT\",\"lookback_min\":30,\"analytics_requested\":[\"ema\",\"movement\"]}\\n"
    "U: start ema crossover bullish preferred on sol 50% margin 20x -> {\"intent_type\":\"AUTOMATION_CREATE\",\"strategy\":\"EMA_CROSSOVER\",\"symbol\":\"SOL-USDT\",\"direction_preference\":\"BULLISH\",\"margin_usage_pct\":50,\"leverage\":20,\"missing_parameters\":[\"timeframe_min\"]}\\n"
    "U: 5 minute / actually make it 1m / use 20x / change margin to 30 -> "
    "{\"intent_type\":\"AUTOMATION_CREATE\",\"<only the changed key>\":<value>}\\n"
    "U: if that crossover happens prepare the trade -> {\"intent_type\":\"CONDITION_CREATE\",\"strategy\":\"EMA_CROSSOVER\",\"symbol\":\"SOL-USDT\"}\\n"
    "U: cancel the automation / skip it -> {\"intent_type\":\"AUTOMATION_CONTROL\",\"action\":\"CANCEL\"}\\n"
    "U: show automations -> {\"intent_type\":\"AUTOMATION_CONTROL\",\"action\":\"LIST\"}\\n"
    "U: health / how is ophelia / vps okay? -> {\"intent_type\":\"HEALTH_QUERY\"}\\n"
    "U: macro bias / news -> {\"intent_type\":\"NEWS_QUERY\"}\\n"
    "U: thanks / hello / show me the configuration -> {\"intent_type\":\"CHAT\",\"reply_hint\":\"...\"}\\n"
    "Keys: intent_type(MARKET_QUERY|AUTOMATION_CREATE|CONDITION_CREATE|HEALTH_QUERY|NEWS_QUERY|CHAT), symbol, lookback_min, aggregation_interval_min, timeframe_min, strategy(EMA_CROSSOVER|VWAP_SUPERTREND), direction_preference(BULLISH|BEARISH|ANY), margin_usage_pct, leverage, action(PAUSE|RESUME|CANCEL|SKIP|LIST), automation_id, analytics_requested(array), missing_parameters(array), reply_hint(string).\\n"
    "Output ONLY the JSON object.\\n"
)

_TOOL_DENYLIST = ("execute", "place_order", "cancel_exchange_order", "modify_order",
                  "withdraw", "transfer")

_last_error: dict = {"ts": 0.0, "detail": ""}


def last_error() -> str:
    """Most recent LLM failure reason (for /status, /health; never secrets)."""
    if not _last_error["detail"]:
        return ""
    age_min = int((time.time() - _last_error["ts"]) / 60)
    return f"{_last_error['detail']} ({age_min} min ago)"


def _note_error(detail: str) -> None:
    _last_error.update(ts=time.time(), detail=detail)
    print(f"[llm] ERROR: {detail}", flush=True)


def _post(payload: dict) -> dict:
    req = urllib.request.Request(
        config.OLLAMA_URL + "/api/chat",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=config.LLM_TIMEOUT_S) as r:
        return json.loads(r.read().decode())


def ping() -> dict:
    """Lightweight Ollama reachability check (no generation)."""
    try:
        with urllib.request.urlopen(config.OLLAMA_URL + "/api/tags",
                                    timeout=4) as r:
            tags = json.loads(r.read().decode())
        names = [m.get("name", "") for m in tags.get("models", [])]
        return {"ok": True, "models": names}
    except Exception as e:                                        # noqa: BLE001
        return {"ok": False, "error": str(e)[:120]}


def warmup() -> bool:
    """Load the primary model into memory and keep it resident (keep_alive).

    Called at startup and periodically; eliminates 20-60s cold-load latency
    on the first user message after idle periods.
    """
    try:
        payload = {"model": config.LLM_PRIMARY,
                   "messages": [{"role": "user", "content": "ok"}],
                   "stream": False, "think": False,
                   "keep_alive": config.LLM_KEEP_ALIVE,
                   "options": {"num_predict": 1, "num_ctx": config.LLM_NUM_CTX}}
        _post(payload)
        print(f"[llm] warmup ok ({config.LLM_PRIMARY}, "
              f"keep_alive={config.LLM_KEEP_ALIVE})", flush=True)
        return True
    except Exception as e:                                        # noqa: BLE001
        _note_error(f"warmup failed: {str(e)[:160]}")
        return False


def _extract_json(text: str):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def validate_intent(intent: dict) -> tuple[dict | None, str]:
    if not isinstance(intent, dict):
        return None, "not a JSON object"
    it = intent.get("intent_type")
    allowed = {"MARKET_QUERY", "AUTOMATION_CREATE", "CONDITION_CREATE",
               "AUTOMATION_CONTROL", "HEALTH_QUERY", "NEWS_QUERY", "CHAT"}
    if it not in allowed:
        return None, f"intent_type '{it}' not allowed"
    tools = [t.lower() for t in intent.get("tools", [])] if "tools" in intent else []
    for bad in _TOOL_DENYLIST:
        if any(bad in t for t in tools):
            return None, f"forbidden tool referenced: {bad}"
    if intent.get("symbol"):
        s = str(intent["symbol"]).upper().replace("_", "-").replace("/", "-").strip()
        if not s or not s.replace("-", "").isalnum():
            return None, f"unsupported symbol format: {s}"
        if s.endswith("-USDT"):
            pass
        elif s.endswith("USDT"):
            s = f"{s[:-4]}-USDT"
        else:
            s = f"{s}-USDT"
        intent["symbol"] = s
    tf = intent.get("timeframe_min")
    if tf is not None and int(tf) not in (1, 2, 3, 5, 10, 15, 30, 60):
        return None, f"timeframe {tf} not constructible from 1m base"
    mu = intent.get("margin_usage_pct")
    if mu is not None and not (0 < float(mu) <= 100):
        return None, "margin_usage_pct must be within (0,100]"
    lv = intent.get("leverage")
    if lv is not None and not (1 <= float(lv) <= config.RISK_DEFAULTS["max_leverage"]):
        return None, "leverage out of allowed range"
    # fill schema defaults
    for key, default in (("strategy", None), ("symbol", None), ("timeframe_min", None),
                         ("lookback_min", None), ("aggregation_interval_min", None),
                         ("direction_preference", None), ("margin_usage_pct", None),
                         ("leverage", None), ("action", None), ("automation_id", None)):
        intent.setdefault(key, default)
    intent.setdefault("analytics_requested", [])
    intent.setdefault("missing_parameters", [])
    intent.setdefault("reply_hint", "")
    intent["confidence"] = intent.get("confidence", 0.8)
    return intent, ""


def parse_intent(user_text: str, context_params: dict,
                 history: list[dict] | None = None) -> tuple[dict | None, str, str]:
    """Returns (intent, model_used, error). Applies CONTEXT params after validation.

    `history` carries recent conversation turns ([{"role","content"}, ...]) so
    follow-ups like "5 minute" or "use 20x" resolve against earlier context.
    """
    context_note = ""
    if context_params:
        context_note = ("\nCONTEXT already supplied by user earlier (do NOT ask again): "
                        + json.dumps(context_params))
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT + context_note}]
    for turn in (history or [])[-4:]:
        if turn.get("role") in ("user", "assistant") and turn.get("content"):
            messages.append({"role": turn["role"], "content": str(turn["content"])[:400]})
    messages.append({"role": "user", "content": user_text})
    payload: dict = {
        "model": config.LLM_PRIMARY,
        "messages": messages,
        "stream": False,
        "format": "json",
        "think": False,
        "keep_alive": config.LLM_KEEP_ALIVE,
        "options": {"temperature": 0.1, "num_ctx": config.LLM_NUM_CTX,
                    "num_predict": 220},
    }
    model_used = config.LLM_PRIMARY
    t0 = time.time()
    try:
        resp = _post(payload)
    except Exception as e:                                        # noqa: BLE001
        _note_error(f"primary {config.LLM_PRIMARY} failed after "
                    f"{time.time() - t0:.1f}s: {str(e)[:140]}")
        payload["model"] = config.LLM_FALLBACK
        model_used = config.LLM_FALLBACK
        t1 = time.time()
        try:
            resp = _post(payload)
            print(f"[llm] fallback {config.LLM_FALLBACK} used "
                  f"({time.time() - t1:.1f}s)", flush=True)
        except Exception as e2:                                   # noqa: BLE001
            _note_error(f"fallback {config.LLM_FALLBACK} also failed after "
                        f"{time.time() - t1:.1f}s: {str(e2)[:140]}")
            return None, "none", f"llm_unavailable: {str(e2)[:120]}"
    raw = resp.get("message", {}).get("content", "")
    intent = _extract_json(raw)
    if intent is None:
        payload["options"]["num_predict"] = 512
        resp = _post(payload)
        intent = _extract_json(resp.get("message", {}).get("content", ""))
        if intent is None:
            return None, model_used, "llm produced unparseable output"
    validated, err = validate_intent(intent)
    if validated is None:
        # one retry with the validator complaint
        payload["messages"].append({"role": "user",
                                    "content": f"Fix this JSON to comply: {err}"})
        resp = _post(payload)
        validated, err = validate_intent(_extract_json(
            resp.get("message", {}).get("content", "")) or {})
        if validated is None:
            return None, model_used, f"schema violation: {err}"
    # merge remembered context params (LLM was told; enforce deterministically)
    for k, v in (context_params or {}).items():
        if v is not None and validated.get(k) in (None, "", []):
            validated[k] = v
    return validated, model_used, ""
