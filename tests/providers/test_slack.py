"""Unit tests for SlackProvider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from qa_cortex.providers.slack import SlackProvider


@pytest.fixture
def valid_config() -> dict:
    return {"bot_token": "xoxb-fake-token"}


def _mock_response(data: dict) -> MagicMock:
    """Mock slack_sdk WebClient response object (dict-like with .get and indexing)."""
    response = MagicMock()
    response.get.side_effect = lambda key, default=None: data.get(key, default)
    response.__getitem__.side_effect = lambda key: data[key]
    return response


class TestConfigValidation:
    def test_missing_token_raises(self) -> None:
        with pytest.raises(ValueError, match="missing required keys"):
            SlackProvider({})

    def test_valid_config(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.slack.WebClient"):
            SlackProvider(valid_config)


class TestListChannels:
    def test_returns_normalized_channels(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.slack.WebClient") as MockClient:
            MockClient.return_value.conversations_list.return_value = _mock_response({
                "channels": [
                    {
                        "id": "C001",
                        "name": "general",
                        "is_private": False,
                        "num_members": 50,
                        "topic": {"value": "Company-wide chat"},
                    },
                ]
            })
            provider = SlackProvider(valid_config)

            channels = provider.list_channels()
            assert len(channels) == 1
            assert channels[0]["id"] == "C001"
            assert channels[0]["name"] == "general"
            assert channels[0]["topic"] == "Company-wide chat"

    def test_include_private_passes_groups_type(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.slack.WebClient") as MockClient:
            MockClient.return_value.conversations_list.return_value = _mock_response({"channels": []})
            provider = SlackProvider(valid_config)

            provider.list_channels(include_private=True)
            _, kwargs = MockClient.return_value.conversations_list.call_args
            assert "private_channel" in kwargs.get("types", "")


class TestGetChannelHistory:
    def test_returns_normalized_messages(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.slack.WebClient") as MockClient:
            MockClient.return_value.conversations_history.return_value = _mock_response({
                "messages": [
                    {
                        "ts": "1731600000.000100",
                        "user": "U001",
                        "text": "Hello team",
                        "reactions": [{"name": "thumbsup", "count": 3}],
                    },
                ]
            })
            provider = SlackProvider(valid_config)

            messages = provider.get_channel_history("C001")
            assert len(messages) == 1
            assert messages[0]["body"] == "Hello team"
            assert messages[0]["user"] == "U001"
            assert messages[0]["reactions"]["thumbsup"] == 3


class TestPostMessage:
    def test_preview_does_not_post(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.slack.WebClient") as MockClient:
            MockClient.return_value.conversations_info.return_value = _mock_response({
                "channel": {"name": "general"}
            })
            provider = SlackProvider(valid_config)

            result = provider.post_message("C001", "Hello", approved=False)

            assert result["preview"] is True
            assert result["payload"]["body"] == "Hello"
            assert result["payload"]["channel_name"] == "general"
            MockClient.return_value.chat_postMessage.assert_not_called()

    def test_approved_posts(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.slack.WebClient") as MockClient:
            MockClient.return_value.chat_postMessage.return_value = _mock_response({
                "ts": "1731600000.000100",
                "channel": "C001",
                "permalink": "https://workspace.slack.com/archives/C001/p123",
            })
            provider = SlackProvider(valid_config)

            result = provider.post_message("C001", "Hello", approved=True)

            MockClient.return_value.chat_postMessage.assert_called_once()
            assert result["id"] == "1731600000.000100"

    def test_thread_reply_passes_thread_ts(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.slack.WebClient") as MockClient:
            MockClient.return_value.chat_postMessage.return_value = _mock_response({
                "ts": "1.0", "channel": "C001"
            })
            provider = SlackProvider(valid_config)

            provider.post_message("C001", "reply", thread_ts="1731600000.000100", approved=True)
            _, kwargs = MockClient.return_value.chat_postMessage.call_args
            assert kwargs.get("thread_ts") == "1731600000.000100"

    def test_empty_body_raises(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.slack.WebClient"):
            provider = SlackProvider(valid_config)
            with pytest.raises(ValueError, match="non-empty body"):
                provider.post_message("C001", "")


class TestAddReaction:
    def test_preview(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.slack.WebClient") as MockClient:
            provider = SlackProvider(valid_config)

            result = provider.add_reaction("C001", "1731600000.000100", "thumbsup", approved=False)

            assert result["preview"] is True
            MockClient.return_value.reactions_add.assert_not_called()

    def test_strips_colons_from_emoji(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.slack.WebClient") as MockClient:
            provider = SlackProvider(valid_config)

            provider.add_reaction("C001", "1.0", ":thumbsup:", approved=True)
            _, kwargs = MockClient.return_value.reactions_add.call_args
            assert kwargs.get("name") == "thumbsup"


class TestFindUser:
    def test_email_lookup(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.slack.WebClient") as MockClient:
            MockClient.return_value.users_lookupByEmail.return_value = _mock_response({
                "user": {
                    "id": "U001",
                    "name": "alice",
                    "real_name": "Alice Tester",
                    "profile": {"email": "alice@example.com"},
                    "is_bot": False,
                }
            })
            provider = SlackProvider(valid_config)

            user = provider.find_user("alice@example.com")
            assert user is not None
            assert user["id"] == "U001"
            assert user["email"] == "alice@example.com"
