"""Tests for Discord alert formatting."""
import pytest
from unittest.mock import patch, MagicMock
from backend.services.discord import (
    send_deal_alert, send_health_alert, send_test_message,
    send_heartbeat, _rating_color,
)


class TestRatingColor:
    def test_steal_is_red(self):
        assert _rating_color("STEAL") == 0xFF0000

    def test_pass_is_gray(self):
        assert _rating_color("PASS") == 0x888888

    def test_unknown_returns_gray(self):
        assert _rating_color("UNKNOWN") == 0x888888


class TestSendDealAlert:
    def _mock_post(self, status=200):
        mock_resp = MagicMock()
        mock_resp.status_code = status
        return mock_resp

    def test_sends_embed(self):
        with patch("httpx.post") as mock_post:
            mock_post.return_value = self._mock_post(204)
            result = send_deal_alert(
                webhook_url="https://discord.com/api/webhooks/test",
                title="Nintendo GameCube Bundle",
                price=180,
                rating="GREAT",
                estimated_value=400,
                conservative_value=320,
                target_buy_price=220,
                estimated_profit=120,
                source="Facebook Marketplace",
                watchlist_name="GameCube",
                url="https://example.com/listing/1",
                location="Brooklyn, NY",
                reasons=["Mario Kart Double Dash matched"],
                warnings=["Low confidence match"],
            )
            assert result is True
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs.args[1]
            assert "embeds" in payload
            embed = payload["embeds"][0]
            assert "description" in embed
            assert "GREAT" in embed["description"]
            assert "$180" in embed["description"]

    def test_returns_false_on_error(self):
        with patch("httpx.post") as mock_post:
            mock_post.side_effect = Exception("connection refused")
            result = send_deal_alert(
                webhook_url="https://discord.com/api/webhooks/bad",
                title="Test",
                price=100,
                rating="GOOD",
                estimated_value=None,
                conservative_value=None,
                target_buy_price=None,
                estimated_profit=None,
                source="mock",
                watchlist_name="Test",
                url="https://example.com",
            )
            assert result is False

    def test_http_failure_returns_false(self):
        with patch("httpx.post") as mock_post:
            mock_post.return_value = self._mock_post(400)
            result = send_test_message("https://discord.com/api/webhooks/bad")
            assert result is False


class TestSendHeartbeat:
    def test_heartbeat_formats(self):
        with patch("httpx.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.status_code = 204
            mock_post.return_value = mock_resp
            result = send_heartbeat(
                webhook_url="https://discord.com/api/webhooks/test",
                source_summaries=[
                    {"name": "facebook", "status": "healthy", "raw_count": 10, "parsed_count": 8, "alert_count": 2},
                    {"name": "auctionninja", "status": "healthy", "raw_count": 30, "parsed_count": 28, "alert_count": 0},
                ],
                errors=["Facebook session may expire soon"],
            )
            assert result is True
            payload = mock_post.call_args.kwargs.get("json") or mock_post.call_args.args[1]
            assert "facebook" in payload["content"]
            assert "auctionninja" in payload["content"]
