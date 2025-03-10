"""Test configuration and fixtures for sqlalchemy-rds-iam."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from sqlalchemy_rds_iam import RDSIAMAuth


@pytest.fixture
def mock_rds_endpoint() -> str:
    """Return a mock RDS endpoint for testing."""
    return "test-db.xxxxx.region.rds.amazonaws.com"


@pytest.fixture
def mock_engine(mock_rds_endpoint: str) -> Engine:
    """Create a SQLAlchemy engine with mock IAM authentication."""
    return create_engine(
        f"postgresql+psycopg2://test_user@{mock_rds_endpoint}:5432/test_db",
        connect_args={"auth_plugin": RDSIAMAuth()},
    )
