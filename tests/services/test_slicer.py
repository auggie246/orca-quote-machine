"""Unit tests for slicer service."""

from unittest.mock import patch

from app.models.quote import MaterialType
from app.services.slicer import OrcaSlicerService


class TestOrcaSlicerService:
    """Tests for the OrcaSlicerService class."""

    def test_get_profile_paths(self):
        """Test that get_profile_paths returns dict with required keys."""
        with patch.dict("os.environ", {"PYTEST_CURRENT_TEST": "true"}):
            service = OrcaSlicerService()
            result = service.get_profile_paths(MaterialType.PLA)

            assert isinstance(result, dict)
            assert "machine" in result
            assert "filament" in result
            assert "process" in result

    def test_get_available_materials(self):
        """Test that get_available_materials returns list of strings."""
        service = OrcaSlicerService()
        result = service.get_available_materials()

        assert isinstance(result, list)
        assert len(result) > 0
        assert all(isinstance(material, str) for material in result)

    def test_parse_time_string(self):
        """Test that _parse_time_string converts time strings to minutes."""
        service = OrcaSlicerService()

        # Test normal cases
        assert service._parse_time_string("2h 30m") == 150
        assert service._parse_time_string("1h 0m") == 60
        assert service._parse_time_string("30m") == 30

        # Test fallback
        assert service._parse_time_string("invalid") == 60
