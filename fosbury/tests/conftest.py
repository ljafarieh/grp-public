"""Shared pytest fixtures for the Fosbury test suite."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fosbury.config.settings import Settings

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def stub_settings(tmp_path: Path) -> Settings:
    """Settings with stub_mode=True and temp storage directories."""
    return Settings(
        stub_mode=True,
        log_level="DEBUG",
        sqlite_path=tmp_path / "test.db",
        parquet_dir=tmp_path / "parquet",
        eia_api_key="",
        pjm_api_key="",
        http_retry_max=1,
        http_retry_wait_seconds=0.1,
    )


@pytest.fixture()
def pjm_lmp_raw() -> dict:
    return json.loads((FIXTURE_DIR / "pjm_lmp.json").read_text())


@pytest.fixture()
def pjm_constraints_raw() -> dict:
    return json.loads((FIXTURE_DIR / "pjm_constraints.json").read_text())


@pytest.fixture()
def eia_demand_raw() -> dict:
    return json.loads((FIXTURE_DIR / "eia_demand.json").read_text())


@pytest.fixture()
def va_scc_raw() -> list:
    return json.loads((FIXTURE_DIR / "va_scc.json").read_text())


@pytest.fixture()
def ohio_puco_raw() -> list:
    return json.loads((FIXTURE_DIR / "ohio_puco.json").read_text())


@pytest.fixture()
def pa_puc_raw() -> list:
    return json.loads((FIXTURE_DIR / "pa_puc.json").read_text())


@pytest.fixture()
def ferc_raw() -> list:
    return json.loads((FIXTURE_DIR / "ferc.json").read_text())
