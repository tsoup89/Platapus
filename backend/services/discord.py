"""Discord webhook alerting service."""
import json
import logging
from datetime import datetime, timezone
from typing import Optional
import httpx

logger = logging.getLogger("platapicker.discord")

RATING_EMOJI = {
    "STEAL": "🔥",
    "GREAT": "⭐",
    "GOOD": "✅",
    "FAIR": "🟡",
    "PASS": "⛔",
}


def _post_webhook(webhook_url: str, payload: dict) -> bool:
    try:
        resp = httpx.post(webhook_url, json=payload, timeout=10)
        if resp.status_code in (200, 204):
            return True
        logger.error(f"Discord webhook returned {resp.status_code}: {resp.text}")
        return False
    except Exception as e:
        logger.error(f"Discord webhook failed: {e}")
        return False


def send_deal_alert(
    webhook_url: str,
    title: str,
    price: float,
    rating: str,
    estimated_value: Optional[float],
    conservative_value: Optional[float],
    target_buy_price: Optional[float],
    estimated_profit: Optional[float],
    source: str,
    watchlist_name: str,
    url: str,
    location: Optional[str] = None,
    reasons: Optional[list] = None,
    warnings: Optional[list] = None,
    image_url: Optional[str] = None,
) -> bool:
    emoji = RATING_EMOJI.get(rating, "📦")

    def fmt_money(v):
        return f"${v:,.0f}" if v is not None else "N/A"

    profit_margin = ""
    if estimated_profit and conservative_value and conservative_value > 0:
        margin = (estimated_profit / conservative_value) * 100
        profit_margin = f" ({margin:.0f}%)"

    lines = [
        f"**{emoji} Platapicker Deal Found**",
        "",
        f"**Rating:** {rating}",
        f"**Source:** {source}",
        f"**Watchlist:** {watchlist_name}",
        f"**Title:** {title}",
        f"**Price:** {fmt_money(price)}",
    ]
    if conservative_value:
        lines.append(f"**Conservative Value:** {fmt_money(conservative_value)}")
    if target_buy_price:
        lines.append(f"**Target Buy Price:** {fmt_money(target_buy_price)}")
    if estimated_profit:
        lines.append(f"**Estimated Profit:** {fmt_money(estimated_profit)}{profit_margin}")
    if location:
        lines.append(f"**Location:** {location}")
    if reasons:
        lines.append("")
        lines.append("**Top Reasons:**")
        for r in reasons[:5]:
            lines.append(f"- {r}")
    if warnings:
        lines.append("")
        lines.append("**⚠️ Warnings:**")
        for w in warnings[:3]:
            lines.append(f"- {w}")
    lines.append("")
    lines.append(f"🔗 {url}")

    embed = {
        "description": "\n".join(lines),
        "color": _rating_color(rating),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "Platapicker"},
    }
    if image_url:
        embed["thumbnail"] = {"url": image_url}

    payload = {"embeds": [embed]}
    return _post_webhook(webhook_url, payload)


def send_health_alert(
    webhook_url: str,
    source: str,
    error: str,
    last_success: Optional[datetime],
    suggested_action: Optional[str] = None,
) -> bool:
    last_str = last_success.strftime("%b %d %I:%M %p") if last_success else "Never"
    lines = [
        "**⚠️ Platapicker Health Alert**",
        "",
        f"**Source:** {source}",
        f"**Error:** {error}",
        f"**Last Successful Run:** {last_str}",
    ]
    if suggested_action:
        lines.append(f"**Suggested Action:** {suggested_action}")

    payload = {"content": "\n".join(lines)}
    return _post_webhook(webhook_url, payload)


def send_heartbeat(
    webhook_url: str,
    source_summaries: list[dict],
    errors: Optional[list[str]] = None,
) -> bool:
    lines = ["**✅ Platapicker Heartbeat**", ""]
    for s in source_summaries:
        status_icon = "✅" if s.get("status") == "healthy" else "⚠️"
        line = (
            f"{status_icon} **{s['name']}**: "
            f"{s.get('raw_count', 0)} raw, "
            f"{s.get('parsed_count', 0)} parsed, "
            f"{s.get('alert_count', 0)} alerts"
        )
        if s.get("note"):
            line += f" — {s['note']}"
        lines.append(line)

    if errors:
        lines.append("")
        lines.append("**Errors:**")
        for e in errors:
            lines.append(f"- {e}")

    payload = {"content": "\n".join(lines)}
    return _post_webhook(webhook_url, payload)


def send_test_message(webhook_url: str) -> bool:
    payload = {
        "content": "✅ **Platapicker** — Discord webhook is working! Your deal alerts will appear here."
    }
    return _post_webhook(webhook_url, payload)


def _rating_color(rating: str) -> int:
    colors = {
        "STEAL": 0xFF0000,
        "GREAT": 0xFF8C00,
        "GOOD": 0x00CC44,
        "FAIR": 0xFFD700,
        "PASS": 0x888888,
    }
    return colors.get(rating, 0x888888)
