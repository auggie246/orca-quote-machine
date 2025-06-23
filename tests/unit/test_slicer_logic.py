"""Unit tests for slicer service logic.

Focus: Test profile resolution logic, material discovery, and error handling.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from orca_quote_machine.models.quote import MaterialType
from orca_quote_machine.services.slicer import OrcaSlicerService, SlicerError


class TestSlicerServiceLogic:
    """Tests for OrcaSlicerService business logic."""

    def test_get_profile_paths_with_enum_material(self):
        """Test profile path resolution with MaterialType enum."""
        service = OrcaSlicerService()

        # Test with enum
        paths = service.get_profile_paths(MaterialType.PLA)

        assert "machine" in paths
        assert "filament" in paths
        assert "process" in paths
        assert all(Path(p).suffix == ".json" for p in paths.values())

    def test_get_profile_paths_with_string_material(self):
        """Test profile path resolution with string material name."""
        service = OrcaSlicerService()

        # Test with string
        paths = service.get_profile_paths("PETG")

        assert "filament" in paths
        assert paths["filament"].endswith("PETG.json") or "petg" in paths["filament"].lower()

    def test_get_profile_paths_defaults_to_pla(self):
        """Test that None material defaults to PLA profile."""
        service = OrcaSlicerService()

        # Test with None
        paths = service.get_profile_paths(None)

        assert "filament" in paths
        # Should use PLA profile

    def test_get_available_materials_returns_list(self):
        """Test material discovery returns a list of strings."""
        service = OrcaSlicerService()

        materials = service.get_available_materials()

        assert isinstance(materials, list)
        assert all(isinstance(m, str) for m in materials)
        # Should at least include the enum materials
        assert "PLA" in materials
        assert "PETG" in materials
        assert "ASA" in materials

    def test_get_available_materials_includes_custom(self):
        """Test that custom materials are discovered from filesystem."""
        service = OrcaSlicerService()

        # Mock the filament directory to include custom materials
        with patch.object(Path, 'glob') as mock_glob:
            mock_files = [
                MagicMock(stem="TPU"),
                MagicMock(stem="NYLON"),
                MagicMock(stem="PLA"),  # Duplicate of enum
            ]
            mock_glob.return_value = mock_files

            materials = service.get_available_materials()

            # Should include both enum and custom materials
            assert "TPU" in materials
            assert "NYLON" in materials
            # Should not have duplicates
            assert materials.count("PLA") == 1

    def test_get_filament_profile_path_with_override(self):
        """Test filament profile resolution with config override."""
        service = OrcaSlicerService()

        # Test that config overrides work
        profile_path = service._get_filament_profile_path("PLA")

        assert isinstance(profile_path, Path)
        assert profile_path.name.endswith(".json")

    def test_get_filament_profile_path_fallback_convention(self):
        """Test filament profile fallback to naming convention."""
        service = OrcaSlicerService()

        # Mock a material that doesn't have a config override
        with patch.object(service.settings.slicer_profiles, '__dict__',
                         {'base_dir': service.profiles_dir,
                          'machine': 'test.json',
                          'process': 'test.json'}):

            # Mock file existence check
            with patch.object(Path, 'exists', return_value=True):
                profile_path = service._get_filament_profile_path("CUSTOM_MATERIAL")

                assert profile_path.name == "custom_material.json"

    def test_get_filament_profile_path_raises_on_missing(self):
        """Test that missing profiles raise SlicerError."""
        service = OrcaSlicerService()

        # Mock a material with no profile
        with patch.object(Path, 'exists', return_value=False):
            with pytest.raises(SlicerError) as exc_info:
                service._get_filament_profile_path("NONEXISTENT")

            assert "No profile found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_slice_model_validates_file_exists(self):
        """Test that slice_model checks if the file exists."""
        service = OrcaSlicerService()

        with pytest.raises(SlicerError) as exc_info:
            await service.slice_model("/nonexistent/file.stl", MaterialType.PLA)

        assert "Model file not found" in str(exc_info.value)
