"""
Local-LLM resale-value estimator (Ollama) with optional maker-checker cross-check.

Fills the gap left by eBay sold-comps: for table-less categories (furniture,
grills, apparel, etc.) eBay only returns a usable comp ~15% of the time, so the
other ~85% of listings get no value and can never score as a deal. When eBay has
nothing, we ask model(s) running locally via Ollama ("what does this resell for
used?") and use that as the conservative comp.

Maker-checker (added 2026-06-14):
- The **maker** (default qwen3:30b) prices the item.
- The **checker** (default qwen3-coder:30b) independently prices the SAME item.
- They must AGREE (within tolerance) for a confident value. On disagreement we use
  the LOWER estimate and flag `needs_review=True`, so a bad/loose match can't
  masquerade as a STEAL by being over-valued.
This is a free, local sanity-guard against false deals — both models run on the
user's machine, so the second opinion costs only a little extra latency.

Design notes:
- Free + private: runs entirely on the user's machine, no API cost, no rate limits.
- Cached in MarketValueCache (source="local_llm") keyed by keyword+category, so we
  value each distinct "brand model" once per TTL instead of per listing — and the
  existing get_market_value() cache read picks the final value up automatically.
  The full maker/checker breakdown is stored in the row's details_json so the UI can
  show it even on a cache hit (no model re-query).
- Fail-open: any error (Ollama down, model not pulled, bad JSON) returns no estimate
  and never raises, so scoring degrades gracefully to "no comp" rather than breaking.

Settings (all optional, sensible defaults):
  local_llm_pricing_enabled    bool  default True
  local_llm_base_url           str   default "http://localhost:11434"
  local_llm_model              str   default "qwen3:30b"          (maker)
  local_llm_checker_enabled    bool  default True
  local_llm_checker_model      str   default "qwen3-coder:30b"    (checker)
  local_llm_agreement_tolerance float default 0.25  (≤25% apart counts as agreement)
  local_llm_timeout_seconds    int   default 60
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import requests
from sqlalchemy.orm import Session

from backend.models.models import MarketValueCache

logger = logging.getLogger("platapicker.local_llm_pricing")

DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "qwen3:30b"
DEFAULT_CHECKER_MODEL = "qwen3-coder:30b"
DEFAULT_TIMEOUT = 60
DEFAULT_TOLERANCE = 0.25
CACHE_TTL_HOURS = 24
# Keep models resident in Ollama between calls so alternating maker/checker doesn't
# pay a cold reload every listing (only matters when both fit in memory).
KEEP_ALIVE = "10m"

# Implausible estimates are treated as "no value" — guards against a model that
# hallucinates a price of $0 or a comma-mangled six-figure number.
MIN_PLAUSIBLE = 2.0
MAX_PLAUSIBLE = 100_000.0

# Ollama structured-output schema — forces a parseable JSON object back.
_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "estimated_resale_usd": {"type": "number"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["estimated_resale_usd", "confidence"],
}

_SYSTEM_PROMPT = (
    "You are a secondhand-resale pricing expert. Given a used item, estimate the "
    "typical price it actually SELLS for used on Facebook Marketplace or eBay in the "
    "United States (not the original retail price, not a wishful asking price). "
    "Account for normal used condition. If the item is generic or you are unsure, give "
    "your best realistic estimate and mark confidence low. Respond with JSON only."
)


@dataclass
class LocalEstimate:
    """Result of a single-model price query.

    Carries the raw I/O (prompt + verbatim model reply + latency + model name) so
    the audit tool can show exactly what each model was asked and what it said."""
    estimated_value: Optional[float]
    confidence: Optional[str] = None
    source: str = "local_llm"
    error: Optional[str] = None
    model: Optional[str] = None
    prompt: Optional[str] = None
    raw_response: Optional[str] = None
    latency_ms: Optional[int] = None


@dataclass
class DualEstimate:
    """Reconciled maker-checker result, with full breakdown for the UI."""
    estimated_value: Optional[float]            # final reconciled value
    confidence: Optional[str] = None            # low | medium | high
    source: str = "local_llm"
    needs_review: bool = False
    agreement: Optional[float] = None           # 0..1 (min/max of the two prices)
    maker_value: Optional[float] = None
    maker_confidence: Optional[str] = None
    maker_model: Optional[str] = None
    maker_prompt: Optional[str] = None
    maker_raw: Optional[str] = None
    maker_latency_ms: Optional[int] = None
    maker_error: Optional[str] = None
    checker_value: Optional[float] = None
    checker_confidence: Optional[str] = None
    checker_model: Optional[str] = None
    checker_prompt: Optional[str] = None
    checker_raw: Optional[str] = None
    checker_latency_ms: Optional[int] = None
    checker_error: Optional[str] = None
    error: Optional[str] = None

    def to_breakdown(self) -> dict:
        return {
            "source": "maker_checker" if self.checker_value is not None else "local_llm",
            "final_value": self.estimated_value,
            "confidence": self.confidence,
            "needs_review": self.needs_review,
            "agreement": round(self.agreement, 3) if self.agreement is not None else None,
            "maker": {
                "model": self.maker_model,
                "value": self.maker_value,
                "confidence": self.maker_confidence,
                "prompt": self.maker_prompt,
                "raw_response": self.maker_raw,
                "latency_ms": self.maker_latency_ms,
                "error": self.maker_error,
            },
            "checker": {
                "model": self.checker_model,
                "value": self.checker_value,
                "confidence": self.checker_confidence,
                "prompt": self.checker_prompt,
                "raw_response": self.checker_raw,
                "latency_ms": self.checker_latency_ms,
                "error": self.checker_error,
            },
        }


def _cfg(settings: dict, key: str, default):
    val = (settings or {}).get(key)
    return default if val in (None, "") else val


# ── Cache helpers ───────────────────────────────────────────────────────────
def _fresh_cache_row(db: Session, keyword: str, category: Optional[str]) -> Optional[MarketValueCache]:
    if db is None:
        return None
    row = (
        db.query(MarketValueCache)
        .filter(
            MarketValueCache.keyword == keyword,
            MarketValueCache.category == category,
            MarketValueCache.source == "local_llm",
        )
        .first()
    )
    if row and row.expires_at and row.expires_at > datetime.utcnow() and row.median_price:
        return row
    return None


def _store(db: Session, keyword: str, category: Optional[str], value: float, details: Optional[dict] = None):
    if db is None:
        return
    now = datetime.utcnow()
    expires = now + timedelta(hours=CACHE_TTL_HOURS)
    details_json = json.dumps(details) if details is not None else None
    row = (
        db.query(MarketValueCache)
        .filter(
            MarketValueCache.keyword == keyword,
            MarketValueCache.category == category,
            MarketValueCache.source == "local_llm",
        )
        .first()
    )
    if row:
        row.median_price = value
        row.mean_price = value
        row.min_price = value
        row.max_price = value
        row.sample_count = 1
        row.fetched_at = now
        row.expires_at = expires
        row.details = details
    else:
        new_row = MarketValueCache(
            keyword=keyword,
            category=category,
            median_price=value,
            mean_price=value,
            min_price=value,
            max_price=value,
            sample_count=1,
            source="local_llm",
            fetched_at=now,
            expires_at=expires,
        )
        new_row.details = details
        db.add(new_row)
    try:
        db.flush()
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to cache local estimate for '{keyword}': {e}")


def get_cached_breakdown(db: Session, keyword: str, category: Optional[str]) -> Optional[dict]:
    """Return the stored maker-checker breakdown for a keyword, if a fresh row exists.

    Used when get_market_value() already returned the local value from cache and the
    runner just needs the breakdown for display (no model query)."""
    row = _fresh_cache_row(db, keyword, category)
    return row.details if row else None


# ── Single-model query ──────────────────────────────────────────────────────
def _query_ollama(keyword: str, category: Optional[str], settings: dict, model: str) -> LocalEstimate:
    base_url = str(_cfg(settings, "local_llm_base_url", DEFAULT_BASE_URL)).rstrip("/")
    timeout = int(_cfg(settings, "local_llm_timeout_seconds", DEFAULT_TIMEOUT))

    cat = f" (category: {category})" if category else ""
    user_prompt = (
        f"Item{cat}: {keyword}\n\n"
        "What is the typical USED resale value in USD? Respond with JSON only."
    )
    # Full prompt text kept for the audit trail (system + user, as sent).
    full_prompt = f"[system]\n{_SYSTEM_PROMPT}\n\n[user]\n{user_prompt}"
    payload = {
        "model": model,
        "stream": False,
        "format": _RESPONSE_SCHEMA,
        "keep_alive": KEEP_ALIVE,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    }
    started = datetime.utcnow()
    try:
        resp = requests.post(f"{base_url}/api/chat", json=payload, timeout=timeout)
    except requests.exceptions.RequestException as e:
        return LocalEstimate(None, error=f"Ollama unreachable: {e}", model=model,
                             prompt=full_prompt)
    latency_ms = int((datetime.utcnow() - started).total_seconds() * 1000)

    def _fail(err: str, raw: Optional[str] = None) -> LocalEstimate:
        return LocalEstimate(None, error=err, model=model, prompt=full_prompt,
                             raw_response=raw, latency_ms=latency_ms)

    if resp.status_code == 404:
        return _fail(f"Model '{model}' not found in Ollama (run: ollama pull {model})")
    if resp.status_code != 200:
        return _fail(f"Ollama HTTP {resp.status_code}", raw=resp.text[:2000])

    content = resp.json().get("message", {}).get("content", "")
    try:
        parsed = json.loads(content)
        value = float(parsed.get("estimated_resale_usd"))
        confidence = parsed.get("confidence")
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as e:
        return _fail(f"Unparseable model output: {e}", raw=content)

    if not (MIN_PLAUSIBLE <= value <= MAX_PLAUSIBLE):
        return _fail(f"Implausible estimate ${value}", raw=content)

    return LocalEstimate(round(value, 2), confidence=confidence, model=model,
                         prompt=full_prompt, raw_response=content, latency_ms=latency_ms)


# ── Public single-model entrypoint (kept for back-compat) ───────────────────
def estimate_value_local(
    keyword: str,
    category: Optional[str],
    db: Session = None,
    settings: dict = None,
) -> LocalEstimate:
    """Estimate used resale value via the maker model only. Cache-first, fail-open."""
    if not keyword or not keyword.strip():
        return LocalEstimate(None, error="empty keyword")

    cached = _fresh_cache_row(db, keyword, category)
    if cached:
        logger.debug(f"Local-LLM cache hit for '{keyword}' (category={category})")
        return LocalEstimate(cached.median_price, source="local_llm")

    settings = settings or {}
    model = _cfg(settings, "local_llm_model", DEFAULT_MODEL)
    est = _query_ollama(keyword, category, settings, model)
    if est.estimated_value is not None:
        logger.info(
            f"💡 Local LLM priced '{keyword}'{f' ({category})' if category else ''} "
            f"→ ${est.estimated_value} ({est.confidence})"
        )
        _store(db, keyword, category, est.estimated_value)
    else:
        logger.warning(f"Local LLM no estimate for '{keyword}': {est.error}")
    return est


# ── Reconciliation ──────────────────────────────────────────────────────────
def _reconcile(maker: LocalEstimate, checker: LocalEstimate, tolerance: float,
               maker_model: str, checker_model: str) -> DualEstimate:
    m, c = maker.estimated_value, checker.estimated_value
    base = DualEstimate(
        estimated_value=None,
        maker_value=m, maker_confidence=maker.confidence, maker_model=maker_model,
        maker_prompt=maker.prompt, maker_raw=maker.raw_response,
        maker_latency_ms=maker.latency_ms, maker_error=maker.error,
        checker_value=c, checker_confidence=checker.confidence, checker_model=checker_model,
        checker_prompt=checker.prompt, checker_raw=checker.raw_response,
        checker_latency_ms=checker.latency_ms, checker_error=checker.error,
    )

    if m is not None and c is not None:
        lo, hi = sorted((m, c))
        agreement = lo / hi if hi else 0.0
        base.agreement = agreement
        if agreement >= (1.0 - tolerance):
            # Agree → blend, confident.
            base.estimated_value = round((m + c) / 2, 2)
            base.needs_review = False
            base.confidence = "high" if agreement >= 0.85 else "medium"
        else:
            # Disagree → conservative (lower) + flag for review.
            base.estimated_value = round(lo, 2)
            base.needs_review = True
            base.confidence = "low"
        return base

    # Only one model produced a value — use it, no cross-check available.
    if m is not None:
        base.estimated_value = m
        base.confidence = maker.confidence
        base.needs_review = (checker.error is not None)  # couldn't verify
        base.error = checker.error
        return base
    if c is not None:
        base.estimated_value = c
        base.confidence = checker.confidence
        base.needs_review = (maker.error is not None)
        base.error = maker.error
        return base

    # Neither produced a value.
    base.error = maker.error or checker.error or "no estimate"
    return base


def estimate_value_dual(
    keyword: str,
    category: Optional[str],
    db: Session = None,
    settings: dict = None,
) -> DualEstimate:
    """Price an item with the maker (and, if enabled, the checker) model.

    Cache-first (reconstructs the full breakdown from the cached row), then queries
    Ollama. Reconciles the two estimates: agreement → confident blend; disagreement →
    lower value + needs_review. Fail-open — never raises."""
    if not keyword or not keyword.strip():
        return DualEstimate(None, error="empty keyword")

    cached = _fresh_cache_row(db, keyword, category)
    if cached:
        logger.debug(f"Local-LLM cache hit (dual) for '{keyword}' (category={category})")
        details = cached.details or {}
        maker = details.get("maker", {})
        checker = details.get("checker", {})
        return DualEstimate(
            estimated_value=cached.median_price,
            confidence=details.get("confidence"),
            needs_review=bool(details.get("needs_review")),
            agreement=details.get("agreement"),
            maker_value=maker.get("value"), maker_confidence=maker.get("confidence"),
            maker_model=maker.get("model"), maker_prompt=maker.get("prompt"),
            maker_raw=maker.get("raw_response"), maker_latency_ms=maker.get("latency_ms"),
            maker_error=maker.get("error"),
            checker_value=checker.get("value"), checker_confidence=checker.get("confidence"),
            checker_model=checker.get("model"), checker_prompt=checker.get("prompt"),
            checker_raw=checker.get("raw_response"), checker_latency_ms=checker.get("latency_ms"),
            checker_error=checker.get("error"),
        )

    settings = settings or {}
    maker_model = _cfg(settings, "local_llm_model", DEFAULT_MODEL)
    checker_enabled = _cfg(settings, "local_llm_checker_enabled", True)
    checker_model = _cfg(settings, "local_llm_checker_model", DEFAULT_CHECKER_MODEL)
    tolerance = float(_cfg(settings, "local_llm_agreement_tolerance", DEFAULT_TOLERANCE))

    maker = _query_ollama(keyword, category, settings, maker_model)

    if checker_enabled and checker_model and checker_model != maker_model:
        checker = _query_ollama(keyword, category, settings, checker_model)
    else:
        checker = LocalEstimate(None, error="checker disabled")

    result = _reconcile(maker, checker, tolerance, maker_model, checker_model)

    if result.estimated_value is not None:
        flag = " ⚠️REVIEW" if result.needs_review else ""
        logger.info(
            f"💡 Maker-checker priced '{keyword}'{f' ({category})' if category else ''} → "
            f"${result.estimated_value} ({result.confidence}){flag} "
            f"[maker {maker_model}=${result.maker_value} / "
            f"checker {checker_model}=${result.checker_value} / "
            f"agree {result.agreement if result.agreement is None else round(result.agreement, 2)}]"
        )
        _store(db, keyword, category, result.estimated_value, details=result.to_breakdown())
    else:
        logger.warning(f"Maker-checker no estimate for '{keyword}': {result.error}")
    return result


# ── Live diagnosis (audit tool) ───────────────────────────────────────────────
def diagnose_pricing(keyword: str, category: Optional[str], settings: dict = None) -> dict:
    """Re-query both models LIVE (bypassing cache, no DB write) and return the full
    breakdown — both models' raw responses, latency, agreement, and the reconciled
    verdict. Used by the audit tool's 'Run live diagnosis' button to prove the
    pricing logic is online and to inspect exactly what each model returns."""
    settings = settings or {}
    if not keyword or not keyword.strip():
        return {"error": "empty keyword"}

    maker_model = _cfg(settings, "local_llm_model", DEFAULT_MODEL)
    checker_enabled = _cfg(settings, "local_llm_checker_enabled", True)
    checker_model = _cfg(settings, "local_llm_checker_model", DEFAULT_CHECKER_MODEL)
    tolerance = float(_cfg(settings, "local_llm_agreement_tolerance", DEFAULT_TOLERANCE))

    maker = _query_ollama(keyword, category, settings, maker_model)
    if checker_enabled and checker_model and checker_model != maker_model:
        checker = _query_ollama(keyword, category, settings, checker_model)
    else:
        checker = LocalEstimate(None, error="checker disabled", model=checker_model)

    result = _reconcile(maker, checker, tolerance, maker_model, checker_model)
    out = result.to_breakdown()
    out["keyword"] = keyword
    out["category"] = category
    out["tolerance"] = tolerance
    out["error"] = result.error
    return out


def ollama_status(settings: dict = None) -> dict:
    """Probe the Ollama server: reachable? which models are pulled? are the
    configured maker/checker models present?  Fail-soft — never raises."""
    settings = settings or {}
    base_url = str(_cfg(settings, "local_llm_base_url", DEFAULT_BASE_URL)).rstrip("/")
    maker_model = _cfg(settings, "local_llm_model", DEFAULT_MODEL)
    checker_model = _cfg(settings, "local_llm_checker_model", DEFAULT_CHECKER_MODEL)
    info = {
        "base_url": base_url,
        "reachable": False,
        "models": [],
        "maker_model": maker_model,
        "checker_model": checker_model,
        "maker_present": False,
        "checker_present": False,
        "error": None,
    }
    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        resp.raise_for_status()
        models = [m.get("name") for m in resp.json().get("models", []) if m.get("name")]
        info["reachable"] = True
        info["models"] = models
        # Ollama tags carry a :tag suffix; match on the bare name too.
        bare = {m.split(":")[0] for m in models}
        info["maker_present"] = maker_model in models or maker_model.split(":")[0] in bare
        info["checker_present"] = checker_model in models or checker_model.split(":")[0] in bare
    except requests.exceptions.RequestException as e:
        info["error"] = str(e)
    return info
