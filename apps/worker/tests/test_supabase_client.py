"""Tests for vigil/supabase_client.py — module-level Supabase client creation."""

import importlib
from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.unit
def test_client_created_with_settings():
    """create_client is called with settings.supabase_url and settings.supabase_service_role_key."""
    mock_client = MagicMock()

    with patch("supabase.create_client", return_value=mock_client) as mock_create:
        import vigil.supabase_client

        importlib.reload(vigil.supabase_client)

        mock_create.assert_called_once()
        args = mock_create.call_args[0]
        # Should use the values from settings (set via env vars in conftest)
        assert len(args) == 2
        assert isinstance(args[0], str)  # supabase_url
        assert isinstance(args[1], str)  # supabase_service_role_key


@pytest.mark.unit
def test_uses_service_role_key():
    """The second argument to create_client should come from supabase_service_role_key."""
    mock_client = MagicMock()

    with patch("supabase.create_client", return_value=mock_client) as mock_create:
        import vigil.supabase_client

        importlib.reload(vigil.supabase_client)

        args = mock_create.call_args[0]
        # The conftest sets VIGIL_SUPABASE_SERVICE_ROLE_KEY=test-key
        assert args[1] == "test-key"


@pytest.mark.unit
def test_client_is_module_level():
    """vigil.supabase_client exposes a `supabase` attribute at module level."""
    mock_client = MagicMock()

    with patch("supabase.create_client", return_value=mock_client):
        import vigil.supabase_client

        importlib.reload(vigil.supabase_client)

        assert hasattr(vigil.supabase_client, "supabase")
        assert vigil.supabase_client.supabase is mock_client
