"""Tests for api/routes/health.py"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
import redis
from fastapi import HTTPException

from api.routes.health import health_check
from core.config import settings


@pytest.mark.unit
class TestHealthCheckRedis:
    """Regression tests for the Redis dependency check (issue #62)."""

    @pytest.fixture
    def mock_db_session(self):
        """Create a mock async database session whose execute() succeeds."""
        session = AsyncMock()
        session.execute = AsyncMock(return_value=None)
        return session

    @pytest.mark.asyncio
    async def test_redis_healthy_uses_redis_url(self, mock_db_session):
        """Health check builds the Redis client from settings.redis_url and pings it."""
        mock_client = Mock()
        mock_client.ping.return_value = True

        with patch.object(redis.Redis, "from_url", return_value=mock_client) as mock_from_url:
            result = await health_check(db=mock_db_session)

        mock_from_url.assert_called_once_with(settings.redis_url, decode_responses=True)
        mock_client.ping.assert_called_once_with()
        assert result["dependencies"]["redis"] == "healthy"

    @pytest.mark.asyncio
    async def test_redis_ping_failure_returns_503(self, mock_db_session):
        """A Redis connection error marks Redis unhealthy and raises a 503."""
        mock_client = Mock()
        mock_client.ping.side_effect = redis.exceptions.ConnectionError("connection refused")

        with (
            patch.object(redis.Redis, "from_url", return_value=mock_client) as mock_from_url,
            pytest.raises(HTTPException) as exc_info,
        ):
            await health_check(db=mock_db_session)

        mock_from_url.assert_called_once_with(settings.redis_url, decode_responses=True)
        mock_client.ping.assert_called_once_with()
        assert exc_info.value.status_code == 503
        assert exc_info.value.detail["dependencies"]["redis"] == "unhealthy"
