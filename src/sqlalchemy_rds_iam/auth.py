"""IAM authentication implementation for RDS databases."""

import threading
from typing import Any, Optional, Tuple

import boto3
from cachetools import TTLCache
from mypy_boto3_rds.client import RDSClient
from sqlalchemy.engine import Engine
from sqlalchemy.event import listen


class RDSIAMAuth:
    """Provides IAM authentication for RDS databases.

    This class generates authentication tokens for RDS databases using IAM credentials.
    It supports automatic token generation and renewal.

    Args:
        region_name: Optional AWS region name. If not provided, will be extracted from the endpoint
                    or fall back to the default AWS configuration.
        boto_session: Optional boto3 session to use for AWS API calls.
        cache_timeout: Number of seconds to cache tokens for. Defaults to 600 (10 minutes).
    """

    def __init__(
        self,
        region_name: Optional[str] = None,
        boto_session: Optional[boto3.Session] = None,
        cache_timeout: int = 600,
    ) -> None:
        if cache_timeout < 0:
            raise ValueError("cache_timeout must be 0 or positive")
        self.region_name = region_name
        self.session = boto_session or boto3.Session()
        self.cache_timeout = cache_timeout
        self._rds_client: RDSClient = self.session.client("rds", region_name=self._get_region())
        self._token_cache: TTLCache[Tuple[str, str, int, str], str] = TTLCache(
            maxsize=100, ttl=cache_timeout
        )
        self._cache_lock = threading.Lock()

    def _get_region(self) -> Optional[str]:
        """Get the region to use for RDS authentication.

        Returns:
            The region name to use, falling back to the session's region if none specified.
        """
        return self.region_name or self.session.region_name

    @property
    def rds_client(self) -> RDSClient:
        return self._rds_client

    def register_for_engine(self, engine: Engine) -> None:
        """Register this auth handler with a SQLAlchemy engine.

        This sets up event listeners to provide IAM tokens for new connections.

        Args:
            engine: SQLAlchemy Engine to register with
        """
        listen(engine, "do_connect", self.provide_token)

    def provide_token(self, dialect: Any, conn_rec: Any, cargs: Any, cparams: Any) -> None:
        """Provide IAM token for new connections.

        Uses the region provided during initialization or falls back to boto3's default region."""
        cparams["password"] = self.generate_auth_token(
            user=cparams["user"],
            host=cparams["host"],
            port=cparams["port"],
            region=self.region_name,
        )

    def generate_auth_token(
        self,
        user: str,
        host: str,
        port: int,
        region: Optional[str] = None,
    ) -> str:
        """Generate an IAM authentication token for RDS.

        Args:
            user: Database username
            host: RDS endpoint
            port: Database port
            region: AWS region name

        Returns:
            Authentication token for RDS. Token is cached based on cache_timeout setting
                (defaults to 10 minutes).
        """
        effective_region = region or self._get_region()
        if not effective_region:
            raise ValueError(
                "No region available from initialization, parameters, or boto3 session"
            )

        # Create cache key from input parameters using a tuple instead of a string
        cache_key = (user, host, port, effective_region)

        # TTLCache automatically handles expiration, so we just need to check if the key exists
        with self._cache_lock:
            token = self._token_cache.get(cache_key)
            if token is not None:
                return token

            # Generate new token
            token = self.rds_client.generate_db_auth_token(
                DBHostname=host,
                Port=port,
                DBUsername=user,
                Region=effective_region,
            )

            # Cache the token
            self._token_cache[cache_key] = token
            return token
