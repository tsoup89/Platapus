"""Expo push notification service — fires alongside Discord alerts."""
import logging
import httpx

logger = logging.getLogger("platapicker.push")

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"

_RATING_EMOJI = {
    "STEAL": "🔥🔥",
    "GREAT": "🔥",
    "GOOD": "✅",
    "FAIR": "💛",
}


def send_deal_push(
    token: str,
    title: str,
    price: float,
    rating: str,
    listing_id: int,
    source: str = "",
    estimated_profit: float | None = None,
) -> bool:
    if not token or not token.startswith("ExponentPushToken"):
        return False

    emoji = _RATING_EMOJI.get(rating, "")
    profit_str = f" · Est. profit ${estimated_profit:.0f}" if estimated_profit else ""

    message = {
        "to": token,
        "sound": "default",
        "title": f"{emoji} {rating} — {title[:60]}",
        "body": f"${price:.0f} on {source}{profit_str}",
        "data": {"listing_id": listing_id, "rating": rating},
        "priority": "high" if rating in ("STEAL", "GREAT") else "normal",
        "channelId": "deals",
    }

    try:
        resp = httpx.post(EXPO_PUSH_URL, json=message, timeout=8)
        resp.raise_for_status()
        result = resp.json().get("data", [{}])[0]
        if result.get("status") == "ok":
            logger.info(f"Push sent for listing {listing_id} ({rating})")
            return True
        logger.warning(f"Expo push rejected: {result}")
        return False
    except Exception as exc:
        logger.warning(f"Push notification error for listing {listing_id}: {exc}")
        return False
