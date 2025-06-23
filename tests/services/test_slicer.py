"""Unit tests for slicer service."""

from unittest.mock import patch

from orca_quote_machine.models.quote import MaterialType
from orca_quote_machine.services.slicer import OrcaSlicerService


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

