"""Unit tests for TestRailProvider."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from qa_cortex.providers.testrail import TestRailProvider


@pytest.fixture
def valid_config() -> dict:
    return {
        "url": "https://test.testrail.io",
        "username": "test@example.com",
        "api_key": "fake-key",
        "project_id": 1,
        "linked_ticket_field": "custom_jira_id",
    }


@pytest.fixture
def sample_case() -> dict:
    return {
        "id": 42,
        "title": "Sample test case",
        "section_id": 7,
        "type_id": 7,  # Smoke
        "priority_id": 3,  # High
        "custom_preconds": "User logged in",
        "custom_steps_separated": [
            {"content": "Click button", "expected": "Modal opens"},
            {"content": "Fill form", "expected": "Validation passes"},
        ],
        "custom_jira_id": "PROJ-100,PROJ-101",
    }


class TestConfigValidation:
    def test_missing_keys_raises(self) -> None:
        with pytest.raises(ValueError, match="missing required keys"):
            TestRailProvider({"url": "x"})

    def test_valid_config_works(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.testrail.TestRailAPI"):
            provider = TestRailProvider(valid_config)
            assert provider.project_id == 1
            assert provider.linked_ticket_field == "custom_jira_id"


class TestGetTestCase:
    def test_returns_canonical_shape(self, valid_config: dict, sample_case: dict) -> None:
        with patch("qa_cortex.providers.testrail.TestRailAPI") as MockAPI:
            MockAPI.return_value.cases.get_case.return_value = sample_case
            provider = TestRailProvider(valid_config)

            result = provider.get_test_case("42")

            assert result["id"] == "42"
            assert result["title"] == "Sample test case"
            assert result["section"] == "7"
            assert result["type"] == "Smoke"
            assert result["priority"] == "High"
            assert "User logged in" in result["preconditions"]
            assert len(result["steps"]) == 2
            assert result["steps"][0]["step"] == "Click button"
            assert result["steps"][0]["expected"] == "Modal opens"

    def test_extracts_linked_tickets_from_custom_field(
        self, valid_config: dict, sample_case: dict
    ) -> None:
        with patch("qa_cortex.providers.testrail.TestRailAPI") as MockAPI:
            MockAPI.return_value.cases.get_case.return_value = sample_case
            provider = TestRailProvider(valid_config)

            result = provider.get_test_case("42")
            assert "PROJ-100" in result["linked_tickets"]
            assert "PROJ-101" in result["linked_tickets"]

    def test_include_steps_false_skips_steps(
        self, valid_config: dict, sample_case: dict
    ) -> None:
        with patch("qa_cortex.providers.testrail.TestRailAPI") as MockAPI:
            MockAPI.return_value.cases.get_case.return_value = sample_case
            provider = TestRailProvider(valid_config)

            result = provider.get_test_case("42", include_steps=False)
            assert result["steps"] == []

    def test_malformed_id_raises(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.testrail.TestRailAPI"):
            provider = TestRailProvider(valid_config)
            with pytest.raises(ValueError, match="Malformed case_id"):
                provider.get_test_case("not-numeric")


class TestFindCasesByLinkedTicket:
    def test_finds_cases_by_jira_id(self, valid_config: dict, sample_case: dict) -> None:
        with patch("qa_cortex.providers.testrail.TestRailAPI") as MockAPI:
            MockAPI.return_value.cases.get_cases.return_value = [
                sample_case,
                {"id": 99, "title": "Unrelated", "custom_jira_id": "OTHER-1"},
            ]
            provider = TestRailProvider(valid_config)

            result = provider.find_cases_by_linked_ticket("PROJ-100")
            assert len(result) == 1
            assert result[0]["id"] == "42"


class TestCreateTestCase:
    def test_preview_does_not_create(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.testrail.TestRailAPI") as MockAPI:
            provider = TestRailProvider(valid_config)

            result = provider.create_test_case(
                title="New case",
                steps=[{"step": "do x", "expected": "y"}],
                section="5",
                approved=False,
            )

            assert result["preview"] is True
            assert result["payload"]["title"] == "New case"
            MockAPI.return_value.cases.add_case.assert_not_called()

    def test_approved_creates(self, valid_config: dict, sample_case: dict) -> None:
        with patch("qa_cortex.providers.testrail.TestRailAPI") as MockAPI:
            MockAPI.return_value.cases.add_case.return_value = sample_case
            provider = TestRailProvider(valid_config)

            result = provider.create_test_case(
                title="New case",
                steps=[{"step": "do x", "expected": "y"}],
                section="5",
                approved=True,
            )

            MockAPI.return_value.cases.add_case.assert_called_once()
            assert result["title"] == "Sample test case"

    def test_missing_section_raises(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.testrail.TestRailAPI"):
            provider = TestRailProvider(valid_config)
            with pytest.raises(ValueError, match="requires section"):
                provider.create_test_case(title="x", steps=[])


class TestAddResult:
    def test_preview_does_not_post(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.testrail.TestRailAPI") as MockAPI:
            provider = TestRailProvider(valid_config)

            result = provider.add_result(
                case_id="42",
                run_id="100",
                status="passed",
                approved=False,
            )

            assert result["preview"] is True
            MockAPI.return_value.results.add_result_for_case.assert_not_called()

    def test_unknown_status_raises(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.testrail.TestRailAPI"):
            provider = TestRailProvider(valid_config)
            with pytest.raises(ValueError, match="Unknown status"):
                provider.add_result(
                    case_id="1", run_id="1", status="invalid_status_name"
                )

    def test_evidence_urls_appended_to_comment(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.testrail.TestRailAPI") as MockAPI:
            provider = TestRailProvider(valid_config)

            result = provider.add_result(
                case_id="42",
                run_id="100",
                status="failed",
                comment="Bug found",
                evidence_urls=["https://screenshot1.png", "https://video.mp4"],
                approved=False,
            )

            assert "Evidence" in result["payload"]["comment"]
            assert result["payload"]["evidence_count"] == 2


class TestGetRun:
    def test_returns_canonical_shape(self, valid_config: dict) -> None:
        with patch("qa_cortex.providers.testrail.TestRailAPI") as MockAPI:
            MockAPI.return_value.runs.get_run.return_value = {
                "id": 100,
                "name": "Sprint 12 Regression",
                "is_completed": False,
                "passed_count": 25,
                "failed_count": 3,
                "blocked_count": 1,
                "untested_count": 5,
                "url": "https://test.testrail.io/runs/100",
            }
            provider = TestRailProvider(valid_config)

            result = provider.get_run("100")
            assert result["id"] == "100"
            assert result["passed"] == 25
            assert result["failed"] == 3
            assert result["status"] == "active"
