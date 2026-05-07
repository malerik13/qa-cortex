"""Unit tests for ConfluenceProvider."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from qa_cortex.providers.confluence import ConfluenceProvider


@pytest.fixture
def valid_config() -> dict:
    return {
        "url": "https://test.atlassian.net/wiki",
        "email": "test@example.com",
        "api_token": "fake-token",
    }


@pytest.fixture
def sample_page() -> dict:
    return {
        "id": "12345",
        "title": "Sample Doc",
        "space": {"key": "PROJ"},
        "body": {"view": {"value": "<p>Hello <b>world</b></p>"}},
        "version": {
            "when": "2026-05-01T10:00:00.000Z",
            "by": {"displayName": "Alice"},
        },
        "metadata": {"labels": {"results": [{"name": "important"}]}},
    }


class TestConfigValidation:
    def test_missing_keys_raises(self) -> None:
        with pytest.raises(ValueError, match="missing required keys"):
            ConfluenceProvider({"url": "x"})

    def test_valid_config_works(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.confluence.Confluence"):
            ConfluenceProvider(valid_config)


class TestSearch:
    def test_returns_normalized_results(self, valid_config: dict, sample_page: dict) -> None:
        with patch("qa_cortex.providers.confluence.Confluence") as MockClient:
            MockClient.return_value.cql.return_value = {"results": [sample_page]}
            provider = ConfluenceProvider(valid_config)

            results = provider.search("hello")
            assert len(results) == 1
            assert results[0]["title"] == "Sample Doc"
            assert results[0]["space"] == "PROJ"

    def test_cql_pass_through(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.confluence.Confluence") as MockClient:
            MockClient.return_value.cql.return_value = {"results": []}
            provider = ConfluenceProvider(valid_config)

            provider.search('type=page AND space="PROJ"')
            args, _ = MockClient.return_value.cql.call_args
            assert "type=page" in args[0]


class TestGetPage:
    def test_returns_canonical_with_body(
        self, valid_config: dict, sample_page: dict
    ) -> None:
        with patch("qa_cortex.providers.confluence.Confluence") as MockClient:
            MockClient.return_value.get_page_by_id.return_value = sample_page
            provider = ConfluenceProvider(valid_config)

            result = provider.get_page("12345")
            assert result["id"] == "12345"
            assert result["title"] == "Sample Doc"
            # Body converted to markdown (or fallback HTML strip)
            assert "Hello" in result["body_markdown"]
            assert "world" in result["body_markdown"]
            assert result["author"] == "Alice"
            assert "important" in result["labels"]

    def test_404_raises_lookup_error(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.confluence.Confluence") as MockClient:
            MockClient.return_value.get_page_by_id.side_effect = Exception("404 not found")
            provider = ConfluenceProvider(valid_config)

            with pytest.raises(LookupError):
                provider.get_page("999")


class TestListSpaces:
    def test_returns_canonical_shapes(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.confluence.Confluence") as MockClient:
            MockClient.return_value.get_all_spaces.return_value = {
                "results": [
                    {
                        "key": "PROJ",
                        "name": "Project Space",
                        "description": {"plain": {"value": "Main project docs"}},
                    },
                    {"key": "ENG", "name": "Engineering"},
                ]
            }
            provider = ConfluenceProvider(valid_config)

            spaces = provider.list_spaces()
            assert len(spaces) == 2
            assert spaces[0]["key"] == "PROJ"
            assert spaces[0]["description"] == "Main project docs"
            assert spaces[1]["key"] == "ENG"


class TestHTMLToMarkdown:
    def test_strips_html_in_fallback(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.confluence.Confluence"):
            provider = ConfluenceProvider(valid_config)
            # Force fallback by patching markdownify import
            with patch.dict("sys.modules", {"markdownify": None}):
                result = provider._html_to_markdown("<p>Hello <b>world</b></p>")
                assert "Hello" in result
                assert "world" in result
                assert "<p>" not in result  # tag stripped
