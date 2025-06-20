"""Tests for configuration settings.

Focus: Test our custom validation logic, not Pydantic's built-in validation.
Pydantic already handles type validation, required fields, and env var parsing.
"""

import os
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings, SlicerProfileSettings, get_settings


class TestCustomValidationLogic:
    """Tests for our custom validation logic that extends Pydantic."""

    def test_extension_normalization(self):
        """Test our custom extension normalization logic."""
        settings = Settings(
            secret_key="test-secret-key",
            allowed_extensions=["STL", "obj", ".step", "STP"],  # Mixed formats
            _env_file=None,  # Don't load .env to isolate test
        )

        # Test OUR normalization logic - should all be lowercase with dots
        assert settings.allowed_extensions == [".stl", ".obj", ".step", ".stp"]

    def test_extension_normalization_edge_cases(self):
        """Test extension normalization with edge cases."""
        settings = Settings(
            secret_key="test-secret-key",
            allowed_extensions=["3MF", ".GCODE", "step"],
            _env_file=None,
        )

        # All should be normalized to lowercase with leading dots
        assert settings.allowed_extensions == [".3mf", ".gcode", ".step"]

    def test_slicer_profiles_auto_initialization(self):
        """Test our custom slicer profiles initialization logic."""
        settings = Settings(
            secret_key="test-secret-key",
            slicer_profiles=None,  # Explicitly set to None
            _env_file=None,
        )

        # Test OUR initialization logic - should auto-create SlicerProfileSettings
        assert settings.slicer_profiles is not None
        assert isinstance(settings.slicer_profiles, SlicerProfileSettings)

    @patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "test_file.py::test_name"})
    def test_profile_validation_skipped_in_tests(self):
        """Test our custom environment-based validation skipping logic."""
        # This tests OUR conditional logic for skipping validation in test environments
        # Should not raise ValidationError even with nonexistent profile paths
        slicer_settings = SlicerProfileSettings(
            base_dir=Path("nonexistent_directory"),
            machine="missing_machine.json",
            process="missing_process.json",
        )

        # Should succeed because our logic skips validation in test environment
        assert slicer_settings is not None
        assert slicer_settings.base_dir == Path("nonexistent_directory")

    @patch.dict(os.environ, {"SKIP_PROFILE_VALIDATION": "true"})
    def test_profile_validation_skipped_when_flag_set(self):
        """Test our validation skipping with explicit environment flag."""
        # Test another path of OUR conditional logic
        slicer_settings = SlicerProfileSettings(
            base_dir=Path("another_nonexistent_directory")
        )

        # Should succeed because of our SKIP_PROFILE_VALIDATION logic
        assert slicer_settings is not None

    def test_profile_validation_runs_in_production_like_environment(self):
        """Test that our validation logic runs when not in test environment."""
        # Clear test environment variables to simulate production
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValueError, match="profile not found"),
        ):
            SlicerProfileSettings(base_dir=Path("definitely_nonexistent_directory"))


class TestConfigurationBehavior:
    """Tests for configuration behavior and integration logic."""

    def test_settings_with_minimal_required_config(self):
        """Test that Settings can be created with minimal required config."""
        settings = Settings(
            secret_key="test-secret-key",
            _env_file=None,  # Don't load .env to test true defaults
        )

        # Should succeed and have reasonable defaults
        assert settings.secret_key == "test-secret-key"
        assert settings.app_name == "OrcaSlicer Quotation Machine"
        assert settings.debug is False
        assert isinstance(settings.slicer_profiles, SlicerProfileSettings)

    def test_secret_key_is_required(self):
        """Test that SECRET_KEY is truly required (Pydantic's validation)."""
        # This is a minimal test of Pydantic's required field validation
        # We trust Pydantic for most validation, but SECRET_KEY is critical

        # Clear SECRET_KEY from environment to ensure it's required
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValidationError, match="secret_key"),
        ):
            Settings(_env_file=None)

    def test_get_settings_caching_behavior(self):
        """Test our caching function behavior."""
        # Set required field
        with patch.dict(os.environ, {"SECRET_KEY": "test-key"}):
            # Clear cache first
            get_settings.cache_clear()

            settings1 = get_settings()
            settings2 = get_settings()

            # Should be the same instance due to @lru_cache
            assert settings1 is settings2

    def test_nested_env_var_parsing(self):
        """Test that nested environment variables work correctly."""
        env_vars = {
            "SECRET_KEY": "test-secret-key",
            "SLICER_PROFILES__BASE_DIR": "custom/profiles/path",
            "SLICER_PROFILES__MACHINE": "custom_machine.json",
        }

        with patch.dict(os.environ, env_vars):
            settings = Settings(_env_file=None)

            # Test that nested env vars are parsed correctly
            assert str(settings.slicer_profiles.base_dir) == "custom/profiles/path"
            assert settings.slicer_profiles.machine == "custom_machine.json"


class TestSlicerProfileSettings:
    """Tests specifically for SlicerProfileSettings custom logic."""

    def test_profile_path_construction(self):
        """Test that profile paths are constructed correctly."""
        with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "true"}):
            slicer_settings = SlicerProfileSettings(
                base_dir=Path("/custom/path"),
                machine="my_machine.json",
                filament_pla="my_pla.json",
            )

            # Test that our path logic works correctly
            assert slicer_settings.base_dir == Path("/custom/path")
            assert slicer_settings.machine == "my_machine.json"
            assert slicer_settings.filament_pla == "my_pla.json"

    def test_default_profile_names(self):
        """Test that default profile filenames are sensible."""
        with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "true"}):
            slicer_settings = SlicerProfileSettings()

            # Test our updated default choices that match actual files
            assert slicer_settings.machine == "RatRig V-Core 3 400 0.5 nozzle.json"
            assert slicer_settings.process == "0.25mm RatRig 0.5mm nozzle - slower.json"
            assert slicer_settings.filament_pla == "Alt Tab PLA+.json"
            assert slicer_settings.filament_petg == "Polymaker PETG PEI.json"
            assert slicer_settings.filament_asa == "fusrock ASA G11.json"
