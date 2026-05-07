"""SlackProvider — concrete ChatProvider for Slack.

Wraps the official ``slack-sdk`` library.

Per CLAUDE.md trust tiering: write methods (post_message, add_reaction)
are Tier 3 (explicit approval). Read methods (list_channels, history) are Tier 1.

Status: Phase 2 Step 5.
"""

from __future__ import annotations

from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from ._normalizers import normalize_iso8601


class SlackProvider:
    """ChatProvider for Slack workspace.

    Config dict shape::

        {
            "bot_token": "xoxb-...",       # Bot User OAuth token
            "default_channel": "C0...",   # optional default for posts
        }

    Required: bot_token.

    Required Slack scopes (configure in Slack app):
    - channels:read, channels:history (read public)
    - groups:read, groups:history (read private — optional)
    - chat:write (post messages)
    - reactions:write (add reactions)
    - users:read, users:read.email (find user by email)
    """

    REQUIRED_CONFIG_KEYS = {"bot_token"}

    def __init__(self, config: dict[str, Any]) -> None:
        missing = self.REQUIRED_CONFIG_KEYS - set(config.keys())
        if missing:
            raise ValueError(
                f"SlackProvider config missing required keys: {sorted(missing)}"
            )

        self.config = config
        self._client = WebClient(token=config["bot_token"])

    # ============================================================
    # Read methods (Tier 1)
    # ============================================================

    def list_channels(self, include_private: bool = False) -> list[dict[str, Any]]:
        """List accessible channels.

        Args:
            include_private: If True, include private channels (requires groups:read scope).
        """
        types = "public_channel"
        if include_private:
            types += ",private_channel"

        try:
            response = self._client.conversations_list(types=types, limit=200)
        except SlackApiError as e:
            raise ConnectionError(f"Slack list_channels failed: {e.response['error']}") from e

        channels = response.get("channels", [])
        return [
            {
                "id": c.get("id", ""),
                "name": c.get("name", ""),
                "is_private": c.get("is_private", False),
                "member_count": c.get("num_members", 0),
                "topic": c.get("topic", {}).get("value", ""),
            }
            for c in channels
        ]

    def get_channel_history(
        self,
        channel_id: str,
        limit: int = 100,
        oldest_ts: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetch channel message history."""
        try:
            kwargs: dict[str, Any] = {"channel": channel_id, "limit": limit}
            if oldest_ts:
                kwargs["oldest"] = oldest_ts
            response = self._client.conversations_history(**kwargs)
        except SlackApiError as e:
            raise ConnectionError(f"Slack history fetch failed: {e.response['error']}") from e

        return [self._normalize_message(m) for m in response.get("messages", [])]

    def get_thread_replies(
        self,
        channel_id: str,
        thread_ts: str,
    ) -> list[dict[str, Any]]:
        """Fetch all replies in a thread."""
        try:
            response = self._client.conversations_replies(
                channel=channel_id, ts=thread_ts
            )
        except SlackApiError as e:
            raise ConnectionError(
                f"Slack thread fetch failed: {e.response['error']}"
            ) from e

        return [self._normalize_message(m) for m in response.get("messages", [])]

    def find_user(self, username_or_email: str) -> dict[str, Any] | None:
        """Look up user by username or email."""
        # Try email first
        if "@" in username_or_email:
            try:
                response = self._client.users_lookupByEmail(email=username_or_email)
                return self._normalize_user(response.get("user", {}))
            except SlackApiError as e:
                if e.response.get("error") == "users_not_found":
                    return None
                raise ConnectionError(
                    f"Slack user lookup failed: {e.response['error']}"
                ) from e

        # Otherwise scan users list
        try:
            response = self._client.users_list(limit=200)
        except SlackApiError as e:
            raise ConnectionError(f"Slack users_list failed: {e.response['error']}") from e

        for u in response.get("members", []):
            if u.get("name") == username_or_email or u.get("real_name") == username_or_email:
                return self._normalize_user(u)
        return None

    # ============================================================
    # Write methods (Tier 3)
    # ============================================================

    def post_message(
        self,
        channel_id: str,
        body: str,
        thread_ts: str | None = None,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Post message to channel (or thread if thread_ts set).

        Two-step approval gate per CLAUDE.md default = no comms.
        """
        if not body:
            raise ValueError("post_message requires non-empty body")

        if not approved:
            # Lookup channel name for context in preview
            channel_name = "?"
            try:
                response = self._client.conversations_info(channel=channel_id)
                channel_name = response.get("channel", {}).get("name", "?")
            except SlackApiError:
                pass

            return {
                "preview": True,
                "payload": {
                    "channel_id": channel_id,
                    "channel_name": channel_name,
                    "body": body,
                    "is_thread_reply": bool(thread_ts),
                    "thread_ts": thread_ts,
                },
            }

        try:
            kwargs: dict[str, Any] = {"channel": channel_id, "text": body}
            if thread_ts:
                kwargs["thread_ts"] = thread_ts
            response = self._client.chat_postMessage(**kwargs)
        except SlackApiError as e:
            raise ConnectionError(
                f"Slack post_message failed: {e.response['error']}"
            ) from e

        return {
            "id": response.get("ts", ""),
            "channel": response.get("channel", channel_id),
            "permalink": response.get("permalink"),
            "posted_at": normalize_iso8601(response.get("ts", "")),
        }

    def add_reaction(
        self,
        channel_id: str,
        message_ts: str,
        emoji: str,
        approved: bool = False,
    ) -> dict[str, Any]:
        """Add emoji reaction to a message."""
        # Strip wrapping colons if user passed ":thumbsup:" instead of "thumbsup"
        emoji = emoji.strip(":")

        if not approved:
            return {
                "preview": True,
                "payload": {
                    "channel_id": channel_id,
                    "message_ts": message_ts,
                    "emoji": emoji,
                },
            }

        try:
            self._client.reactions_add(
                channel=channel_id, timestamp=message_ts, name=emoji
            )
        except SlackApiError as e:
            raise ConnectionError(
                f"Slack add_reaction failed: {e.response['error']}"
            ) from e

        return {
            "channel_id": channel_id,
            "message_ts": message_ts,
            "emoji": emoji,
            "ok": True,
        }

    # ============================================================
    # Internal helpers
    # ============================================================

    def _normalize_message(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Convert Slack message → canonical ChatProvider shape."""
        reactions: dict[str, int] = {}
        for r in raw.get("reactions", []) or []:
            reactions[r.get("name", "")] = r.get("count", 0)

        return {
            "id": raw.get("ts", ""),
            "channel": raw.get("channel", ""),
            "user": raw.get("user", "") or raw.get("username", ""),
            "body": raw.get("text", ""),
            "timestamp": normalize_iso8601(raw.get("ts", "")),
            "thread_ts": raw.get("thread_ts"),
            "reactions": reactions,
            "permalink": raw.get("permalink"),
        }

    def _normalize_user(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Convert Slack user → canonical shape."""
        return {
            "id": raw.get("id", ""),
            "name": raw.get("name", ""),
            "real_name": raw.get("real_name", "") or raw.get("profile", {}).get("real_name", ""),
            "email": raw.get("profile", {}).get("email", ""),
            "is_bot": raw.get("is_bot", False),
        }
