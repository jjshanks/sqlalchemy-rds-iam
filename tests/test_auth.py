"""Tests for the RDSIAMAuth class."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, event

from sqlalchemy_rds_iam import RDSIAMAuth


def test_rds_iam_auth_initialization() -> None:
    """Test basic initialization of RDSIAMAuth."""
    auth = RDSIAMAuth(region_name="us-west-2")
    assert auth.region_name == "us-west-2"
    assert auth._rds_client is not None
    assert auth.cache_timeout == 600  # default 10 minutes

    auth = RDSIAMAuth(region_name="us-west-2", cache_timeout=300)
    assert auth.cache_timeout == 300


@patch("boto3.Session")
def test_rds_client_lazy_initialization(mock_session: MagicMock) -> None:
    """Test that RDS client is lazily initialized."""
    mock_client = MagicMock()
    mock_session.return_value.client.return_value = mock_client

    auth = RDSIAMAuth(region_name="us-west-2")
    assert auth._rds_client is not None

    # Access the client
    client = auth.rds_client
    assert client == mock_client
    mock_session.return_value.client.assert_called_once_with("rds", region_name="us-west-2")


@patch("boto3.Session")
def test_generate_auth_token(mock_session: MagicMock) -> None:
    """Test generation of authentication token."""
    mock_client = MagicMock()
    mock_client.generate_db_auth_token.return_value = "mock-token"
    mock_session.return_value.client.return_value = mock_client

    auth = RDSIAMAuth(region_name="us-west-2")
    token = auth.generate_auth_token(
        user="test_user",
        host="test-db.xxxxx.us-west-2.rds.amazonaws.com",
        port=5432,
    )

    assert token == "mock-token"
    mock_client.generate_db_auth_token.assert_called_once_with(
        DBHostname="test-db.xxxxx.us-west-2.rds.amazonaws.com",
        Port=5432,
        DBUsername="test_user",
        Region="us-west-2",
    )


@patch("boto3.Session")
def test_token_caching(mock_session: MagicMock) -> None:
    """Test that tokens are properly cached and respect timeout."""
    mock_client = MagicMock()
    mock_client.generate_db_auth_token.return_value = "mock-token"
    mock_session.return_value.client.return_value = mock_client

    # Test with default timeout (600 seconds)
    auth = RDSIAMAuth(region_name="us-west-2")

    # First call should generate token
    token1 = auth.generate_auth_token(
        user="test_user",
        host="test-db.xxxxx.us-west-2.rds.amazonaws.com",
        port=5432,
    )
    assert token1 == "mock-token"
    assert mock_client.generate_db_auth_token.call_count == 1

    # Second call within timeout should return cached token
    token2 = auth.generate_auth_token(
        user="test_user",
        host="test-db.xxxxx.us-west-2.rds.amazonaws.com",
        port=5432,
    )
    assert token2 == "mock-token"
    assert mock_client.generate_db_auth_token.call_count == 1  # No additional calls


@patch("boto3.Session")
def test_cache_behavior_with_different_params(mock_session: MagicMock) -> None:
    """Test cache hits and misses with different parameters."""
    mock_client = MagicMock()
    mock_client.generate_db_auth_token.side_effect = ["token1", "token2", "token3"]
    mock_session.return_value.client.return_value = mock_client

    auth = RDSIAMAuth(region_name="us-west-2")

    # First call - should generate new token
    token1 = auth.generate_auth_token(
        user="user1",
        host="test-db.xxxxx.us-west-2.rds.amazonaws.com",
        port=5432,
    )
    assert token1 == "token1"
    assert mock_client.generate_db_auth_token.call_count == 1

    # Same parameters - should use cache
    token1_cached = auth.generate_auth_token(
        user="user1",
        host="test-db.xxxxx.us-west-2.rds.amazonaws.com",
        port=5432,
    )
    assert token1_cached == "token1"
    assert mock_client.generate_db_auth_token.call_count == 1  # No additional calls

    # Different user - should generate new token
    token2 = auth.generate_auth_token(
        user="user2",
        host="test-db.xxxxx.us-west-2.rds.amazonaws.com",
        port=5432,
    )
    assert token2 == "token2"
    assert mock_client.generate_db_auth_token.call_count == 2

    # Different port - should generate new token
    token3 = auth.generate_auth_token(
        user="user2",
        host="test-db.xxxxx.us-west-2.rds.amazonaws.com",
        port=5433,  # Different port
    )
    assert token3 == "token3"
    assert mock_client.generate_db_auth_token.call_count == 3

    # Repeat call with second user - should use cache
    token2_cached = auth.generate_auth_token(
        user="user2",
        host="test-db.xxxxx.us-west-2.rds.amazonaws.com",
        port=5432,
    )
    assert token2_cached == "token2"
    assert mock_client.generate_db_auth_token.call_count == 3  # No additional calls


@patch("psycopg2.connect")
@patch("boto3.Session")
def test_engine_integration(mock_session: MagicMock, mock_connect: MagicMock) -> None:
    """Test integration with SQLAlchemy engine."""
    auth = RDSIAMAuth(region_name="us-west-2")
    engine = create_engine(
        "postgresql+psycopg2://test_user@test-db.xxxxx.us-west-2.rds.amazonaws.com:5432/test_db",
        _initialize=False,  # Prevent immediate connection attempt
    )

    # Register the auth handler
    auth.register_for_engine(engine)

    # Verify that the event listener was registered
    assert event.contains(engine, "do_connect", auth.provide_token)


def test_invalid_cache_timeout_values() -> None:
    negative_timeout = -1
    with pytest.raises(ValueError):
        RDSIAMAuth(region_name="us-west-2", cache_timeout=negative_timeout)


@patch("boto3.Session")
def test_cache_timeout_zero(mock_session: MagicMock) -> None:
    """Test that setting cache_timeout to 0 disables caching."""
    mock_client = MagicMock()
    mock_client.generate_db_auth_token.side_effect = ["token1", "token2", "token3"]
    mock_session.return_value.client.return_value = mock_client

    # Initialize with cache_timeout=0 to disable caching
    auth = RDSIAMAuth(region_name="us-west-2", cache_timeout=0)

    # First call should generate first token
    token1 = auth.generate_auth_token(
        user="test_user",
        host="test-db.xxxxx.us-west-2.rds.amazonaws.com",
        port=5432,
    )
    assert token1 == "token1"
    assert mock_client.generate_db_auth_token.call_count == 1

    # Second call with same parameters should generate a new token
    # since caching is disabled
    token2 = auth.generate_auth_token(
        user="test_user",
        host="test-db.xxxxx.us-west-2.rds.amazonaws.com",
        port=5432,
    )
    assert token2 == "token2"
    assert mock_client.generate_db_auth_token.call_count == 2

    # Third call should also generate a new token
    token3 = auth.generate_auth_token(
        user="test_user",
        host="test-db.xxxxx.us-west-2.rds.amazonaws.com",
        port=5432,
    )
    assert token3 == "token3"
    assert mock_client.generate_db_auth_token.call_count == 3


@patch("boto3.Session")
def test_region_resolution(mock_session: MagicMock) -> None:
    """Test region resolution logic in _get_region method."""
    # Set up mock session with a default region
    mock_session.return_value.region_name = "us-east-1"

    # Create a mock client that will be returned by session.client()
    mock_client = MagicMock()
    mock_session.return_value.client.return_value = mock_client

    # Case 1: Region provided during initialization
    auth1 = RDSIAMAuth(region_name="us-west-2")
    assert auth1._get_region() == "us-west-2"

    # Case 2: No region provided, falls back to session region
    auth2 = RDSIAMAuth()
    assert auth2._get_region() == "us-east-1"

    # Case 3: No region in initialization or session
    mock_session.return_value.region_name = None
    auth3 = RDSIAMAuth()
    assert auth3._get_region() is None

    # Reset region for the next test
    mock_session.return_value.region_name = "us-east-1"

    # Test region parameter in generate_auth_token takes precedence
    # Reset the mock client to clear any previous calls
    mock_client.reset_mock()

    # Create a new auth instance with the mock client
    auth4 = RDSIAMAuth(region_name="us-west-2")

    # Generate a token with a different region
    auth4.generate_auth_token(
        user="test_user",
        host="test-db.xxxxx.us-west-2.rds.amazonaws.com",
        port=5432,
        region="eu-west-1",  # This should override the initialization region
    )

    # Verify the token was generated with the provided region
    mock_client.generate_db_auth_token.assert_called_once_with(
        DBHostname="test-db.xxxxx.us-west-2.rds.amazonaws.com",
        Port=5432,
        DBUsername="test_user",
        Region="eu-west-1",
    )
