"""Unit tests for ReportFormatter component.

Tests the formatter's ability to create well-structured
markdown reports from legislation summaries.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from deepeval.test_case import LLMTestCase

from evals.metrics.report_formatting import (
    ReportFormattingMetric,
    SectionPresenceMetric,
    MarkdownSyntaxMetric,
    create_report_formatting_metric,
)
from utils.schemas import ChainData, WriterOutput, LegislationItem


class TestReportFormatter:
    """Test suite for ReportFormatter component."""

    @pytest.fixture(autouse=True)
    def setup(self, sample_writer_output: dict[str, Any]):
        self.summary = sample_writer_output

    def test_formatter_initialization(self):
        """Test that formatter can be imported."""
        from pipelines.node.report_formatter import report_formatter_chain

        assert report_formatter_chain is not None

    def test_report_formatter_with_valid_input(
        self, sample_writer_output: dict[str, Any]
    ):
        """Test report formatter with valid inputs."""
        from pipelines.node.report_formatter import report_formatter

        inputs: ChainData = {
            "city": "Toronto",
            "topic": "Economy & Housing",
            "legislation_summary": WriterOutput(
                items=[LegislationItem(**item) for item in sample_writer_output["items"]]
            ),
        }

        result = report_formatter(inputs)

        assert "markdown_report" in result
        assert isinstance(result["markdown_report"], str)
        assert len(result["markdown_report"]) > 0

    def test_report_formatter_without_summary(self):
        """Test report formatter handles missing summary gracefully."""
        from pipelines.node.report_formatter import report_formatter

        inputs: ChainData = {
            "legislation_summary": None,
        }

        result = report_formatter(inputs)

        assert "markdown_report" in result
        assert result["markdown_report"] == ""

    def test_report_includes_required_sections(self):
        """Test that report includes topic header and item structure."""
        from pipelines.node.report_formatter import report_formatter

        inputs: ChainData = {
            "city": "Toronto",
            "topic": "Economy & Housing",
            "legislation_summary": WriterOutput(
                items=[
                    LegislationItem(
                        header="Test legislation headline",
                        description="This is a test description of legislation.",
                    )
                ]
            ),
        }

        result = report_formatter(inputs)
        report = result["markdown_report"]

        assert "## ECONOMY & HOUSING" in report
        assert "**Test legislation headline**" in report
        assert "Toronto" in report
        assert "This is a test description" in report


class TestReportFormattingMetric:
    """Test suite for report formatting evaluation metric."""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.metric = ReportFormattingMetric

    def test_well_formatted_report(self):
        """Test metric scores high for well-formatted report."""
        test_case = LLMTestCase(
            input="Generate report for Toronto legislation",
            actual_output="""## ECONOMY & HOUSING

**Climate Action Initiative passed 38-7**
Toronto

City Council passed Bill 1 establishing a 65% GHG reduction target by 2030. The bill mandates building retrofits.

**Affordable Housing Strategy requires 20% affordable units**
Toronto

Bill 2 passed 42-3, requiring 20% affordable units in large developments.
""",
        )

        self.metric.measure(test_case)
        assert self.metric.score >= 0.75

    def test_poorly_formatted_report(self):
        """Test metric detects poorly formatted reports."""
        test_case = LLMTestCase(
            input="Generate report",
            actual_output="""Some random text that isn't really a report
No headers or structure here
Just some bullet points
- Point 1
- Point 2""",
        )

        self.metric.measure(test_case)
        assert self.metric.score < 0.5

    def test_missing_sections(self):
        """Test metric detects missing required sections."""
        test_case = LLMTestCase(
            input="Generate report",
            actual_output="""Just some content without proper section headers or item structure.""",
        )

        self.metric.measure(test_case)
        assert self.metric.score < 0.8


class TestSectionPresenceMetric:
    """Test suite for required section presence validation."""

    def test_all_sections_present(self):
        """Test detection of all required sections."""
        metric = SectionPresenceMetric(
            required_sections=[
                "## TOPIC HEADER",
                "**Item Header**",
            ]
        )

        test_case = LLMTestCase(
            input="Generate report",
            actual_output="""## ECONOMY & HOUSING

**Climate Action Initiative passed 38-7**
Toronto

City Council passed Bill 1 establishing a 65% GHG reduction target.
""",
        )

        metric.measure(test_case)
        assert metric.score >= 1.0

    def test_missing_sections(self):
        """Test detection of missing sections."""
        metric = SectionPresenceMetric(
            required_sections=["## TOPIC HEADER", "**Item Header**"]
        )

        test_case = LLMTestCase(
            input="Generate report",
            actual_output="""Some text without proper topic headers or bold item headers.""",
        )

        metric.measure(test_case)
        assert metric.score < 1.0

    def test_custom_required_sections(self):
        """Test custom required sections."""
        metric = SectionPresenceMetric(
            required_sections=[
                "## TOPIC HEADER",
                "**Item Header**",
            ]
        )

        test_case = LLMTestCase(
            input="Generate report",
            actual_output="""## TRANSPORTATION

**New bus routes approved for downtown**
Toronto

Three new bus routes will serve the downtown core starting March 1.
""",
        )

        metric.measure(test_case)
        assert metric.score >= 1.0


class TestMarkdownSyntaxMetric:
    """Test suite for markdown syntax validation."""

    def test_valid_markdown_syntax(self):
        """Test detection of valid markdown syntax."""
        metric = MarkdownSyntaxMetric(threshold=0.9)

        test_case = LLMTestCase(
            input="Generate report",
            actual_output="""## ECONOMY & HOUSING

**Council passes eviction package**
Toronto

The Council voted 48-18 to extend tenant protections.

**Albany advances FAB cap reform**
New York State

A-1234 heard in committee 12-4.

---

## TRANSPORTATION

**New subway line approved**
Toronto

The TTC approved the Ontario Line expansion.
""",
        )

        metric.measure(test_case)
        assert metric.score >= 0.9

    def test_broken_markdown_syntax(self):
        """Test detection of broken markdown."""
        metric = MarkdownSyntaxMetric(threshold=0.9)

        test_case = LLMTestCase(
            input="Generate report",
            actual_output="""#Title (missing space)

##Section (missing space)

-Bullet (missing space)
*[text(no closing bracket)""",
        )

        metric.measure(test_case)
        assert metric.score < 0.5


class TestReportFormatterIntegration:
    """Integration tests for report formatter."""

    def test_full_report_generation(self, sample_writer_output: dict[str, Any]):
        """Test complete report generation workflow."""
        from pipelines.node.report_formatter import report_formatter

        inputs: ChainData = {
            "city": "Toronto",
            "topic": "Economy & Housing",
            "legislation_summary": WriterOutput(
                items=[LegislationItem(**item) for item in sample_writer_output["items"]]
            ),
        }

        result = report_formatter(inputs)
        report = result["markdown_report"]

        assert isinstance(report, str)
        assert len(report) > 100
        assert report.startswith("##")


class TestReportFormatterEdgeCases:
    """Edge case tests for report formatter."""

    def test_empty_items(self):
        """Test handling of empty items list."""
        from pipelines.node.report_formatter import report_formatter

        inputs: ChainData = {
            "city": "Toronto",
            "topic": "Economy",
            "legislation_summary": None,
        }

        result = report_formatter(inputs)
        assert "markdown_report" in result
        assert result["markdown_report"] == ""

    def test_single_item(self):
        """Test handling of a single legislation item."""
        from pipelines.node.report_formatter import report_formatter

        inputs: ChainData = {
            "city": "Toronto",
            "topic": "Housing",
            "legislation_summary": WriterOutput(
                items=[
                    LegislationItem(
                        header="New housing bill passed",
                        description="The council approved a new housing bill.",
                    )
                ]
            ),
        }

        result = report_formatter(inputs)
        assert "## HOUSING" in result["markdown_report"]
        assert "**New housing bill passed**" in result["markdown_report"]

    def test_special_characters_in_header(self):
        """Test handling of special characters in headers."""
        from pipelines.node.report_formatter import report_formatter

        inputs: ChainData = {
            "city": "Toronto",
            "topic": "Economy",
            "legislation_summary": WriterOutput(
                items=[
                    LegislationItem(
                        header="Test: Special Chars & More (#1)",
                        description="Description with special chars.",
                    )
                ]
            ),
        }

        result = report_formatter(inputs)
        assert "**Test: Special Chars & More (#1)**" in result["markdown_report"]


def run_report_formatter_evaluation() -> dict[str, Any]:
    """Run full evaluation suite for report formatter.

    Returns:
        Dictionary with evaluation results
    """
    from deepeval import evaluate

    test_cases = [
        LLMTestCase(
            input="Generate markdown report for Toronto legislation",
            actual_output="""## ECONOMY & HOUSING

**Climate Action Initiative passed 38-7**
Toronto

City Council passed Bill 1 establishing a 65% GHG reduction target by 2030. The bill mandates building retrofits and allocates $50M for renewable energy.

**Affordable Housing Strategy requires 20% affordable units**
Toronto

Bill 2 passed 42-3, requiring 20% affordable units in large developments. It establishes a $100M housing trust.
""",
        ),
        LLMTestCase(
            input="Generate report",
            actual_output="""Random text without proper structure
No headers or formatting
Just plain text""",
        ),
    ]

    metrics = create_report_formatting_metric(
        threshold=0.75,
        strict_sections=True,
        check_syntax=True,
    )

    results = evaluate(test_cases=test_cases, metrics=metrics)
    return results


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
