"""Unit tests for all three transformers."""

from __future__ import annotations

from decimal import Decimal

import pytest

from fosbury.core.exceptions import TransformationError
from fosbury.core.models import ConstraintDataset, DemandDataset, LmpDataset
from fosbury.transformers.constraints import ConstraintsTransformer
from fosbury.transformers.eia_demand import EiaDemandTransformer
from fosbury.transformers.lmp import LmpTransformer


# ---------------------------------------------------------------------------
# LmpTransformer
# ---------------------------------------------------------------------------


class TestLmpTransformer:
    def test_happy_path(self, pjm_lmp_raw: dict) -> None:
        result = LmpTransformer().transform(pjm_lmp_raw)
        assert isinstance(result, LmpDataset)
        assert result.row_count == 3
        assert result.records[0].pnode_name == "AEP GEN HUB"
        assert result.records[0].lmp_total == Decimal("28.0")

    def test_skips_null_price_rows(self) -> None:
        raw = {
            "items": [
                {
                    "datetime_beginning_utc": "2026-06-18T00:00:00",
                    "pnode_id": 1,
                    "pnode_name": "HUB",
                    "total_lmp_rt": None,  # should be skipped
                },
                {
                    "datetime_beginning_utc": "2026-06-18T00:05:00",
                    "pnode_id": 1,
                    "pnode_name": "HUB",
                    "total_lmp_rt": 25.0,
                },
            ]
        }
        result = LmpTransformer().transform(raw)
        assert result.row_count == 1

    def test_raises_on_wrong_type(self) -> None:
        with pytest.raises(TransformationError, match="Expected dict"):
            LmpTransformer().transform([1, 2, 3])

    def test_raises_when_no_items_key(self) -> None:
        with pytest.raises(TransformationError, match="'items' list"):
            LmpTransformer().transform({"data": []})

    def test_raises_when_all_rows_invalid(self) -> None:
        raw = {"items": [{"total_lmp_rt": None}, {"total_lmp_rt": None}]}
        with pytest.raises(TransformationError, match="zero records"):
            LmpTransformer().transform(raw)

    def test_lmp_components_parsed(self, pjm_lmp_raw: dict) -> None:
        result = LmpTransformer().transform(pjm_lmp_raw)
        r = result.records[0]
        assert r.lmp_congestion == Decimal("-1.25")
        assert r.lmp_energy == Decimal("28.5")


# ---------------------------------------------------------------------------
# ConstraintsTransformer
# ---------------------------------------------------------------------------


class TestConstraintsTransformer:
    def test_happy_path(self, pjm_constraints_raw: dict) -> None:
        result = ConstraintsTransformer().transform(pjm_constraints_raw)
        assert isinstance(result, ConstraintDataset)
        assert result.row_count == 2

    def test_pct_loading_computed(self, pjm_constraints_raw: dict) -> None:
        result = ConstraintsTransformer().transform(pjm_constraints_raw)
        r = result.records[0]
        assert r.pct_loading is not None
        expected = Decimal("1820.5") / Decimal("2000.0") * 100
        assert abs(r.pct_loading - expected) < Decimal("0.01")

    def test_raises_on_empty_results(self) -> None:
        raw = {"items": [{"shadow_price": None}]}
        with pytest.raises(TransformationError, match="zero records"):
            ConstraintsTransformer().transform(raw)

    def test_raises_on_bad_structure(self) -> None:
        with pytest.raises(TransformationError):
            ConstraintsTransformer().transform("not a dict")


# ---------------------------------------------------------------------------
# EiaDemandTransformer
# ---------------------------------------------------------------------------


class TestEiaDemandTransformer:
    def test_happy_path(self, eia_demand_raw: dict) -> None:
        result = EiaDemandTransformer().transform(eia_demand_raw)
        assert isinstance(result, DemandDataset)
        assert result.row_count == 3

    def test_respondent_parsed(self, eia_demand_raw: dict) -> None:
        result = EiaDemandTransformer().transform(eia_demand_raw)
        assert result.records[0].respondent == "PJM"
        assert result.records[0].value_mwh == Decimal("112500")

    def test_skips_null_values(self) -> None:
        raw = {
            "response": {
                "data": [
                    {
                        "period": "2026-06-18T00",
                        "respondent": "PJM",
                        "respondent-name": "PJM LLC",
                        "type-name": "Demand",
                        "value": None,
                    },
                    {
                        "period": "2026-06-18T01",
                        "respondent": "PJM",
                        "respondent-name": "PJM LLC",
                        "type-name": "Demand",
                        "value": 100000,
                    },
                ]
            }
        }
        result = EiaDemandTransformer().transform(raw)
        assert result.row_count == 1

    def test_raises_on_bad_structure(self) -> None:
        with pytest.raises(TransformationError):
            EiaDemandTransformer().transform({"response": {"not_data": []}})
