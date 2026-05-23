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
    claude_summary: Optional[str] = None,
    claude_flags: Optional[list] = None,
    claude_positives: Optional[list] = None,
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
    if claude_summary:
        lines.append("")
        lines.append(f"**🤖 Claude:** {claude_summary}")
        if claude_flags:
            for f_ in claude_flags[:3]:
                lines.append(f"  ⚠ {f_}")
        if claude_positives:
            for p in claude_positives[:3]:
                lines.append(f"  ✓ {p}")
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


def send_batch_alert(
    webhook_url: str,
    watchlist_name: str,
    deals: list[dict],
    run_summary: dict = None,
) -> bool:
    """Send one Discord embed listing all qualifying deals, ranked by rating."""
    RATING_RANK = {"STEAL": 0, "GREAT": 1, "GOOD": 2, "FAIR": 3, "PASS": 4}
    sorted_deals = sorted(deals, key=lambda d: RATING_RANK.get(d.get("rating", "PASS"), 99))

    def fmt_money(v):
        return f"${v:,.0f}" if v is not None else "N/A"

    shown = sorted_deals[:10]
    remainder = len(sorted_deals) - len(shown)

    lines = [f"**{len(deals)} deal{'s' if len(deals) != 1 else ''} found — {watchlist_name}**", ""]

    for deal in shown:
        emoji = RATING_EMOJI.get(deal.get("rating", "PASS"), "📦")
        rating = deal.get("rating", "?")
        title = deal.get("title", "Unknown")[:60]
        price = deal.get("price")
        cons_val = deal.get("conservative_value")
        profit = deal.get("estimated_profit")
        url = deal.get("url", "")

        price_str = fmt_money(price)
        meta_parts = []
        if cons_val is not None:
            meta_parts.append(f"value: {fmt_money(cons_val)}")
        if profit is not None:
            meta_parts.append(f"profit: ~{fmt_money(profit)}")
        meta = f" ({', '.join(meta_parts)})" if meta_parts else ""

        lines.append(f"{emoji} **{rating}** — {title} — {price_str}{meta}")
        if url:
            lines.append(f"🔗 {url}")
        lines.append("")

    if remainder > 0:
        lines.append(f"*...and {remainder} more*")

    if run_summary:
        lines.append("")
        parts = []
        if "raw_count" in run_summary:
            parts.append(f"{run_summary['raw_count']} raw")
        if "parsed_count" in run_summary:
            parts.append(f"{run_summary['parsed_count']} new")
        if "duplicate_count" in run_summary:
            parts.append(f"{run_summary['duplicate_count']} dupes")
        if parts:
            lines.append(f"*Run: {', '.join(parts)}*")

    # Pick embed color from best deal rating
    best_rating = sorted_deals[0].get("rating", "PASS") if sorted_deals else "PASS"
    embed = {
        "description": "\n".join(lines),
        "color": _rating_color(best_rating),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "footer": {"text": "Platapicker — Batch Alert"},
    }
    payload = {"embeds": [embed]}
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
