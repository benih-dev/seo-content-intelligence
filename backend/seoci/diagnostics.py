import json
import logging
import os
import re
import time
from contextvars import ContextVar
from functools import wraps
from urllib.parse import urlsplit

import httpx
from pydantic import ValidationError
from sqlalchemy import delete, select

from seoci.app_settings import SECRET_FIELDS, resolve_settings
from seoci.db import Session
from seoci.models import DiagnosticEvent, now

context = ContextVar("diagnostic_context", default={})
events = ContextVar("diagnostic_events", default=None)
log = logging.getLogger("seoci.diagnostics")
_secrets = set()


def redact(value, config=None):
    """Scrub credentials centrally, including URLs and common header/token forms."""
    if config:
        for key in (*SECRET_FIELDS, "dataforseo_login"):
            secret = config.get(key)
            if secret:
                _secrets.add(secret)
                _secrets.add(json.dumps(secret)[1:-1])
                if key == "gsc_service_account_json":
                    try:
                        account = json.loads(secret)
                        for item in account.values() if isinstance(account, dict) else ():
                            if isinstance(item, str) and item:
                                _secrets.update((item, json.dumps(item)[1:-1]))
                    except (ValueError, TypeError, RecursionError):
                        pass
        _secrets.update(v for k, v in os.environ.items() if v and any(x in k for x in ("API_KEY", "TOKEN", "PASSWORD", "AUTH_SECRET")))
    text = str(value)
    for secret in sorted(_secrets, key=len, reverse=True):
        text = text.replace(secret, "[redacted]")
    text = re.sub(r"https?://[^\s<>\"']+", lambda m: safe_host(m[0]), text, flags=re.I)
    text = re.sub(r"(?i)(?:authorization|x-api-key|api[_-]?key|password|token)\s*[\"']?\s*[:=]\s*[^\n,;}]+", "[redacted credential]", text)
    text = re.sub(r"(?i)\bBearer\s+\S+|\bsk-[\w-]+", "[redacted]", text)
    return text[:2000]


def safe_host(url):
    try:
        return urlsplit(url).hostname or "configured endpoint"
    except ValueError:
        return "configured endpoint"


class RedactingFilter(logging.Filter):
    def filter(self, record):
        def scrub(value):
            if isinstance(value, str):
                return redact(value)
            if isinstance(value, tuple):
                return tuple(scrub(item) for item in value)
            if isinstance(value, list):
                return [scrub(item) for item in value]
            if isinstance(value, dict):
                return {key: "[redacted]" if re.search(r"(?i)authorization|x-api-key|password|token|api_key", str(key)) else scrub(item) for key, item in value.items()}
            return value if value is None or isinstance(value, (int, float, bool)) else redact(repr(value))
        if record.name == "uvicorn.access":
            record.msg, record.args = redact(record.msg), scrub(record.args)
        else:
            record.msg, record.args = redact(record.getMessage()), ()
        if record.exc_info:
            record.msg += " " + redact(record.exc_info[1])
            record.exc_info = None
            record.exc_text = None
        return True


def protect_logging(config):
    redact("", config)
    loggers = [logging.getLogger(), *(logger for logger in logging.Logger.manager.loggerDict.values() if isinstance(logger, logging.Logger))]
    handlers = {handler for logger in loggers for handler in logger.handlers}
    if logging.lastResort:
        handlers.add(logging.lastResort)
    for handler in handlers:
        if not any(isinstance(f, RedactingFilter) for f in handler.filters):
            handler.addFilter(RedactingFilter())


class ProviderFailure(RuntimeError):
    def __init__(self, error):
        self.error = error
        super().__init__(error["message"] + " " + error["hint"])


def classify(exc, provider="pipeline", model="", endpoint="", config=None):
    if isinstance(exc, ProviderFailure):
        return exc.error
    config = config if config is not None else resolve_settings().values
    raw = str(exc).lower()
    kind = type(exc).__name__.lower()
    llm_provider = getattr(exc, "llm_provider", None)
    is_llm = provider == "LLM" or bool(llm_provider) or type(exc).__module__.startswith("litellm.")
    if is_llm:
        if provider in {"pipeline", "LLM"} and isinstance(llm_provider, str) and llm_provider:
            provider = llm_provider
        model = model or getattr(exc, "model", "") or config.get("llm_model", "")
        endpoint = endpoint or config.get("llm_api_base", "")
    status = getattr(exc, "status_code", None) or getattr(getattr(exc, "response", None), "status_code", None)
    status = status if isinstance(status, int) else None
    category = None
    if isinstance(exc, (ValidationError, json.JSONDecodeError)):
        category = "invalid_output"
    elif isinstance(exc, (httpx.TimeoutException, TimeoutError)) or "timeout" in kind:
        category = "timeout"
    elif isinstance(exc, (httpx.ConnectError, ConnectionError)) or any(x in kind for x in ("connection", "transport", "dns")):
        credentials_error = any(x in raw for x in ("api key", "api_key", "unauthorized"))
        network_error = any(x in raw for x in ("connection error", "connection refused", "dns", "name or service not known", "failed to establish", "network is unreachable"))
        category = "auth" if kind == "apiconnectionerror" and credentials_error and not network_error else "unreachable"
        if status == 500:
            status = None
    elif status in (401, 403) or any(x in kind for x in ("authentication", "permissiondenied", "refresherror", "malformederror")):
        category = "auth"
    elif status == 404 or "notfound" in kind:
        category = "model_not_found"
    elif status == 429 or "ratelimit" in kind:
        category = "rate_limit"
    elif status in (400, 405, 415, 422) or "badrequest" in kind:
        category = "bad_request"
    elif is_llm and (status is None or 200 <= status < 300 or 500 <= status < 600) and any(
        marker in raw for marker in ("empty or invalid response from llm endpoint", "<!doctype html", "<html")
    ):
        category = "bad_endpoint"
    if category is None:
        if "invalid model output" in raw:
            category = "invalid_output"
        elif any(x in raw for x in ("authentication", "permissiondenied", "invalid api key", "api key is not configured", "api_key", "service-account json", "invalid_grant", "invalid_client")):
            category = "auth"
        elif any(x in raw for x in ("model not found", "model_not_found", "unknown model", "model does not exist", "unsupported model")):
            category = "model_not_found"
        elif raw == "run budget exhausted" or any(x in raw for x in ("quota", "rate limit")):
            category = "rate_limit"
        elif "timed out" in raw:
            category = "timeout"
        elif any(x in raw for x in ("connection error", "connection refused", "name or service not known", "dns resolution")):
            category = "unreachable"
        elif "bad request" in raw:
            category = "bad_request"
    if category == "bad_endpoint":
        explanation = "LLM endpoint returned HTML/non-JSON instead of an API response."
        hint = "LLM_API_BASE likely needs the API path, e.g. https://host/v1"
    elif category == "auth":
        category, explanation, hint = "auth", "Authentication failed or credentials are missing.", "Check the API key or service-account access in Settings."
    elif category == "model_not_found":
        category, explanation, hint = "model_not_found", "The model or endpoint is not available.", "Check the model name and whether this endpoint supports it."
    elif category == "rate_limit" and raw == "run budget exhausted":
        category, explanation, hint = "rate_limit", "Run budget exhausted.", "Increase RUN_BUDGET_USD or reduce provider usage before retrying."
    elif category == "rate_limit":
        category, explanation, hint = "rate_limit", "Rate limit or quota exceeded.", "Wait before retrying; check provider quota and billing."
    elif category == "timeout":
        category, explanation, hint = "timeout", "The provider request timed out.", "Retry later or check the endpoint and network timeout."
        if status == 500:
            status = None
    elif category == "unreachable":
        category, explanation, hint = "unreachable", f"Cannot connect to {safe_host(endpoint) if endpoint else 'the provider host'}.", "Check the host and network. For OpenAI-compatible APIs, ensure LLM_API_BASE ends in /v1."
        if status == 500:
            status = None
    elif category == "invalid_output":
        category, explanation, hint = "invalid_output", "The provider returned invalid or non-JSON output.", "Use a model supporting JSON output and retry."
    elif category == "bad_request":
        category, explanation, hint = "bad_request", "The provider rejected the request.", "Check endpoint compatibility, including response_format=json_object, and model options."
    else:
        category, explanation, hint = "unknown", "The operation failed.", "Check provider configuration and Logs, then retry."
    name = redact(provider + (f" / {model}" if model else ""), config)
    return {"category": category, "message": redact(f"{name} request failed{f' (HTTP {status})' if status else ''}: {explanation}", config),
            "hint": hint, "provider": redact(provider), "model": redact(model), "status": status}


def record_event(*, level="info", message, provider="pipeline", model="", status=None, duration_ms=None, error=None):
    data = {**context.get(), "time": now(), "level": level, "provider": redact(provider), "model": redact(model),
            "status": status, "duration_ms": duration_ms, "message": redact(message), "error": error}
    if error and error.get("stage"):
        data["stage"] = error["stage"]
    log.log(logging.ERROR if level == "error" else logging.INFO, "%s", json.dumps(data))
    if events.get() is not None:
        events.get().append(data)
    else:
        persist_events([data])


def persist_events(rows):
    if not rows:
        return
    with Session() as db:
        db.add_all(DiagnosticEvent(data=row, created_at=row["time"], level=row["level"], run_id=row.get("run_id")) for row in rows)
        db.flush()
        keep = select(DiagnosticEvent.id).order_by(DiagnosticEvent.created_at.desc(), DiagnosticEvent.id.desc()).limit(500)
        db.execute(delete(DiagnosticEvent).where(DiagnosticEvent.id.not_in(keep)))
        db.commit()


def observed(provider, *, llm=False, endpoint=""):
    def decorate(fn):
        @wraps(fn)
        def call(*args, **kwargs):
            config = resolve_settings().values
            protect_logging(config)
            model = config["llm_model"] if llm else ""
            start = time.monotonic()
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                error = classify(exc, provider, model, config["llm_api_base"] if llm else endpoint, config)
                record_event(level="error", message=error["message"], provider=error["provider"], model=error["model"], status=error["status"],
                             duration_ms=round((time.monotonic()-start)*1000), error=error)
                raise ProviderFailure(error) from None
            record_event(message="Provider call succeeded", provider=provider, model=model, status=200,
                         duration_ms=round((time.monotonic()-start)*1000))
            return result
        return call
    return decorate
