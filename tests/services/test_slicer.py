"""Integration tests for OrcaSlicer service."""

import builtins
import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_mock import MockerFixture

from app.models.quote import MaterialType, SlicingResult
from app.services.slicer import OrcaSlicerService, SlicerError


class TestOrcaSlicerService:
    """Tests for the OrcaSlicerService class."""

    def test_init(self) -> None:
        """Test OrcaSlicerService initialization."""
        service = OrcaSlicerService()

        assert service.settings is not None
        assert service.cli_path is not None
        assert service.profiles_dir is not None

    def test_get_profile_paths_default(self) -> None:
        """Test getting profile paths with default material."""
        service = OrcaSlicerService()

        with patch.object(service, 'profiles_dir') as mock_profiles_dir:
            # Mock the profile files exist
            mock_profiles_dir.__truediv__.return_value.exists.return_value = True

            profiles = service.get_profile_paths()

            assert "printer" in profiles
            assert "filament" in profiles
            assert "process" in profiles

            # Should default to PLA
            assert "pla.ini" in profiles["filament"]

    def test_get_profile_paths_specific_material(self) -> None:
        """Test getting profile paths with specific material."""
        service = OrcaSlicerService()

        with patch.object(service, 'profiles_dir') as mock_profiles_dir:
            mock_profiles_dir.__truediv__.return_value.exists.return_value = True

            profiles = service.get_profile_paths(MaterialType.PETG)

            assert "petg.ini" in profiles["filament"]

    def test_get_profile_paths_missing_file(self) -> None:
        """Test error when profile file is missing."""
        service = OrcaSlicerService()

        with patch.object(service, 'profiles_dir') as mock_profiles_dir:
            # Mock that one file doesn't exist
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            mock_profiles_dir.__truediv__.return_value = mock_path

            with pytest.raises(SlicerError, match="Profile not found"):
                service.get_profile_paths()

    @pytest.mark.asyncio
    async def test_slice_model_file_not_found(self) -> None:
        """Test slicing fails when model file doesn't exist."""
        service = OrcaSlicerService()

        with pytest.raises(SlicerError, match="Model file not found"):
            await service.slice_model("/nonexistent/file.stl")

    @pytest.mark.asyncio
    async def test_slice_model_success(self, mocker: MockerFixture) -> None:
        """Test successful model slicing."""
        service = OrcaSlicerService()

        # Mock file exists
        mocker.patch("os.path.exists", return_value=True)

        # Mock profile paths
        mock_profiles = {
            "printer": "/path/to/printer.ini",
            "filament": "/path/to/pla.ini",
            "process": "/path/to/process.ini"
        }
        mocker.patch.object(service, "get_profile_paths", return_value=mock_profiles)

        # Mock subprocess execution
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate = AsyncMock(return_value=(b"Success", b""))

        mocker.patch("asyncio.create_subprocess_exec", return_value=mock_process)
        mocker.patch("asyncio.wait_for", return_value=(b"Success", b""))

        # Mock result parsing
        mock_result = SlicingResult(
            print_time_minutes=120,
            filament_weight_grams=25.5
        )
        mocker.patch.object(service, "_parse_slice_results", return_value=mock_result)

        result = await service.slice_model("/path/to/test.stl", MaterialType.PLA)

        assert isinstance(result, SlicingResult)
        assert result.print_time_minutes == 120
        assert result.filament_weight_grams == 25.5

    @pytest.mark.asyncio
    async def test_slice_model_cli_failure(self, mocker: MockerFixture) -> None:
        """Test slicing fails when CLI returns error."""
        service = OrcaSlicerService()

        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(service, "get_profile_paths", return_value={})

        # Mock failed subprocess
        mock_process = AsyncMock()
        mock_process.returncode = 1  # Non-zero return code
        mock_process.communicate = AsyncMock(return_value=(b"", b"Slicing error"))

        mocker.patch("asyncio.create_subprocess_exec", return_value=mock_process)
        mocker.patch("asyncio.wait_for", return_value=(b"", b"Slicing error"))

        with pytest.raises(SlicerError, match="Slicer failed"):
            await service.slice_model("/path/to/test.stl")

    @pytest.mark.asyncio
    async def test_slice_model_timeout(self, mocker: MockerFixture) -> None:
        """Test slicing fails on timeout."""
        service = OrcaSlicerService()

        mocker.patch("os.path.exists", return_value=True)
        mocker.patch.object(service, "get_profile_paths", return_value={})
        mocker.patch("asyncio.create_subprocess_exec")

        # Mock timeout
        mocker.patch("asyncio.wait_for", side_effect=builtins.TimeoutError())

        with pytest.raises(SlicerError, match="timed out"):
            await service.slice_model("/path/to/test.stl")

    @pytest.mark.asyncio
    async def test_parse_gcode_metadata_success(self) -> None:
        """Test parsing G-code metadata successfully."""
        service = OrcaSlicerService()

        # Create temporary G-code file with metadata
        gcode_content = """
; Sliced at: ...
; estimated printing time (normal mode): 2h 30m
; filament used [mm]: 5000.5
; filament used [g]: 25.5
G28 ; home
G1 X10 Y10
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.gcode', delete=False) as f:
            f.write(gcode_content)
            f.flush()

            try:
                result = await service._parse_gcode_metadata(Path(f.name))
                print_time, filament_weight = result

                assert print_time == 150  # 2h 30m = 150 minutes
                assert filament_weight == 25.5

            finally:
                os.unlink(f.name)

    @pytest.mark.asyncio
    async def test_parse_gcode_metadata_no_metadata(self) -> None:
        """Test parsing G-code file without metadata."""
        service = OrcaSlicerService()

        # Create G-code file without metadata
        gcode_content = """
G28 ; home
G1 X10 Y10
M104 S200
"""

        with tempfile.NamedTemporaryFile(mode='w', suffix='.gcode', delete=False) as f:
            f.write(gcode_content)
            f.flush()

            try:
                result = await service._parse_gcode_metadata(Path(f.name))
                print_time, filament_weight = result

                # Should return fallback values
                assert print_time == 60  # 1 hour default
                assert filament_weight == 20.0  # 20g default

            finally:
                os.unlink(f.name)

    def test_parse_time_string_hours_and_minutes(self) -> None:
        """Test parsing time string with hours and minutes."""
        service = OrcaSlicerService()

        result = service._parse_time_string("2h 30m")
        assert result == 150  # 2*60 + 30

        result = service._parse_time_string("1h 0m")
        assert result == 60

        result = service._parse_time_string("0h 45m")
        assert result == 45

    def test_parse_time_string_minutes_only(self) -> None:
        """Test parsing time string with minutes only."""
        service = OrcaSlicerService()

        result = service._parse_time_string("90m")
        assert result == 90

        result = service._parse_time_string("30")
        assert result == 30

    def test_parse_time_string_invalid(self) -> None:
        """Test parsing invalid time string."""
        service = OrcaSlicerService()

        result = service._parse_time_string("invalid")
        assert result == 60  # Default fallback

        result = service._parse_time_string("")
        assert result == 60

    @pytest.mark.asyncio
    async def test_parse_slice_results_no_gcode(self) -> None:
        """Test parsing results when no G-code files found."""
        service = OrcaSlicerService()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            with pytest.raises(SlicerError, match="No G-code output found"):
                await service._parse_slice_results(output_dir, "")

    @pytest.mark.asyncio
    async def test_parse_slice_results_with_json(self, mocker: MockerFixture) -> None:
        """Test parsing results with JSON metadata file."""
        service = OrcaSlicerService()

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            # Create dummy G-code file
            gcode_file = output_dir / "output.gcode"
            gcode_file.write_text("G28\n")

            # Create JSON metadata file
            json_file = output_dir / "metadata.json"
            json_file.write_text('{"print_time_minutes": 180, "filament_grams": 35.2}')

            # Mock G-code parsing to return different values
            mocker.patch.object(
                service,
                "_parse_gcode_metadata",
                return_value=(120, 25.0)
            )

            result = await service._parse_slice_results(output_dir, "")

            # Should prefer JSON values over G-code values
            assert result.print_time_minutes == 180
            assert result.filament_weight_grams == 35.2
