"""Unit tests for the regulatory transformer and PDF parser."""

from __future__ import annotations

import pytest

from fosbury.core.exceptions import TransformationError
from fosbury.core.models import GridEvent, GridEventDataset
from fosbury.pipelines.pdf_parser import extract_delay_days, scan_text
from fosbury.transformers.regulatory import RegulatoryTransformer


# ---------------------------------------------------------------------------
# PDF parser tests
# ---------------------------------------------------------------------------


class TestExtractDelayDays:
    def test_days(self) -> None:
        assert extract_delay_days("extended by 90 days") == 90

    def test_weeks(self) -> None:
        assert extract_delay_days("pushed back 12 weeks") == 84

    def test_months(self) -> None:
        assert extract_delay_days("delayed 14 months") == 420

    def test_years(self) -> None:
        assert extract_delay_days("a 2-year restudy period") == 730

    def test_no_match(self) -> None:
        assert extract_delay_days("no delay information here") == 0

    def test_prefers_years_over_days(self) -> None:
        # "2-year" appears before "90 days" in pattern priority
        result = extract_delay_days("2-year delay and separately 90 days notice")
        assert result == 730


class TestScanText:
    def test_finds_keywords(self) -> None:
        text = "The transformer procurement backlog is now 52 weeks."
        result = scan_text(text)
        assert result.has_signal
        assert "transformer procurement" in result.keywords_matched
        assert result.metric_delta == 364  # 52 weeks * 7

    def test_no_signal(self) -> None:
        result = scan_text("The weather was nice today.")
        assert not result.has_signal
        assert result.metric_delta == 0

    def test_multiple_keywords(self) -> None:
        text = "A formal protest was filed regarding cost-shifting to ratepayers."
        result = scan_text(text)
        assert len(result.keywords_matched) >= 2

    def test_case_insensitive(self) -> None:
        result = scan_text("PROTEST FILED AGAINST RATEPAYER COST-SHIFTING")
        assert result.has_signal


# ---------------------------------------------------------------------------
# RegulatoryTransformer tests
# ---------------------------------------------------------------------------


def _sample_event(**overrides) -> dict:
    base = {
        "event_id": "test_001",
        "iso_region": "PJM",
        "state_jurisdiction": "VA",
        "entity_target": "Dominion Energy",
        "data_type": "REGULATORY_PROTEST",
        "raw_text_blob": "Protest filed regarding transformer procurement delays.",
        "metric_delta": 180,
        "keywords_matched": ["protest", "transformer procurement"],
        "source_url": "https://scc.virginia.gov/test.pdf",
        "scraped_at": "2026-06-19T15:00:00",
    }
    base.update(overrides)
    return base


class TestRegulatoryTransformer:
    def test_happy_path(self) -> None:
        raw = [_sample_event()]
        result = RegulatoryTransformer("va_scc").transform(raw)
        assert isinstance(result, GridEventDataset)
        assert result.row_count == 1
        assert result.records[0].entity_target == "Dominion Energy"

    def test_deduplicates_same_event_id(self) -> None:
        raw = [_sample_event(), _sample_event()]
        result = RegulatoryTransformer("va_scc").transform(raw)
        assert result.row_count == 1

    def test_autogenerates_missing_event_id(self) -> None:
        raw = [_sample_event(event_id="")]
        result = RegulatoryTransformer("va_scc").transform(raw)
        assert result.row_count == 1
        assert result.records[0].event_id != ""

    def test_skips_invalid_data_type(self) -> None:
        raw = [_sample_event(data_type="INVALID_TYPE")]
        with pytest.raises(TransformationError):
            RegulatoryTransformer("va_scc").transform(raw)

    def test_raises_on_non_list(self) -> None:
        with pytest.raises(TransformationError, match="expected list"):
            RegulatoryTransformer("va_scc").transform({"items": []})

    def test_multiple_sources(self, va_scc_raw, ohio_puco_raw, pa_puc_raw, ferc_raw) -> None:
        for source_key, raw in [
            ("va_scc", va_scc_raw),
            ("ohio_puco", ohio_puco_raw),
            ("pa_puc", pa_puc_raw),
            ("ferc", ferc_raw),
        ]:
            result = RegulatoryTransformer(source_key).transform(raw)
            assert result.row_count > 0, f"{source_key} produced zero records"

    def test_text_blob_truncated(self) -> None:
        long_text = "x" * 5000
        raw = [_sample_event(raw_text_blob=long_text)]
        result = RegulatoryTransformer("va_scc").transform(raw)
        assert len(result.records[0].raw_text_blob) <= 2000
