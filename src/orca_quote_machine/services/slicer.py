"""OrcaSlicer integration service."""

import asyncio
import os
import tempfile
from pathlib import Path

# Import enhanced Rust functions
from orca_quote_machine._rust_core import SlicingResult, parse_slicer_output
from orca_quote_machine.core.config import Settings, get_settings
from orca_quote_machine.models.quote import MaterialType


class SlicerError(Exception):
    """Custom exception for slicer-related errors."""

    pass


class OrcaSlicerService:
    """Service for interacting with OrcaSlicer CLI."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.cli_path = self.settings.orcaslicer_cli_path
        self.profiles_dir = self.settings.slicer_profiles.base_dir  # type: ignore[union-attr]
        self.filament_profiles_dir = self.profiles_dir / "filament"

    def _get_filament_profile_path(self, material_name: str) -> Path:
        """
        Gets the path to a filament profile using a hybrid strategy.
        1. Checks for an explicit override in settings (e.g., `filament_pla`).
        2. Falls back to a file-based convention (`material_name.ini`).
        3. Raises a clear error if no profile is found.
        """
        profile_config = self.settings.slicer_profiles
        material_lower = material_name.lower()

        # 1. Check for an explicit override in settings (for official materials)
        config_key = f"filament_{material_lower}"
        if hasattr(profile_config, config_key):
            profile_filename = getattr(profile_config, config_key)
            profile_path = self.filament_profiles_dir / profile_filename
            # The Pydantic validator already checked this at startup, so we can trust it exists.
            return profile_path  # type: ignore[no-any-return]

        # 2. Fallback to file-based convention for custom materials.
        # Convention: material name 'TPU' maps to `tpu.json`.
        conventional_filename = f"{material_lower}.json"
        profile_path = self.filament_profiles_dir / conventional_filename
        if profile_path.exists():
            return profile_path

        # 3. If no profile is found by any method, fail clearly.
        raise SlicerError(
            f"No profile found for material '{material_name}'. "
            f"Looked for config override '{config_key}' and conventional file '{conventional_filename}'."
        )

    def get_profile_paths(
        self, material: MaterialType | str | None = None
    ) -> dict[str, str]:
        """
        Resolves full paths for machine, process, and the correct filament profile.
        Accepts an enum member or a raw string for the material.
        """
        # Default to PLA if no material is provided.
        material_name = getattr(material, "value", material) or MaterialType.PLA.value

        profile_config = self.settings.slicer_profiles
        filament_profile_path = self._get_filament_profile_path(material_name)

        profiles = {
            "machine": self.profiles_dir / "machine" / profile_config.machine,  # type: ignore[union-attr]
            "filament": filament_profile_path,
            "process": self.profiles_dir / "process" / profile_config.process,  # type: ignore[union-attr]
        }

        return {k: str(v.resolve()) for k, v in profiles.items()}

    def get_available_materials(self) -> list[str]:
        """
        Discovers all available materials for populating UI elements.
        Combines official materials from the enum with custom materials
        found as .json files in the filament profile directory.
        """
        # 1. Start with official materials from the enum
        official_materials = {m.value for m in MaterialType}

        # 2. Scan the filesystem for all .json files
        discovered_materials = set()
        if self.filament_profiles_dir.is_dir():
            for f in self.filament_profiles_dir.glob("*.json"):
                # Convert 'generic_tpu.json' -> 'generic_tpu'
                material_name = f.stem.upper()  # Convert to uppercase for consistency
                discovered_materials.add(material_name)

        # 3. Combine, ensuring original casing is preferred, and sort.
        all_materials = sorted(official_materials.union(discovered_materials))
        return all_materials

    async def slice_model(
        self, model_path: str, material: MaterialType | None = None
    ) -> SlicingResult:
        """
        Slice a 3D model and extract print information.

        Args:
            model_path: Path to the 3D model file
            material: Material type to use for slicing

        Returns:
            SlicingResult with print time and filament usage

        Raises:
            SlicerError: If slicing fails
        """
        if not os.path.exists(model_path):
            raise SlicerError(f"Model file not found: {model_path}")

        profiles = self.get_profile_paths(material)

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "output"
            output_dir.mkdir(exist_ok=True)

            # Build command
            command = [
                self.cli_path,
                model_path,
                "--slice",
                "0",  # Slice all plates
                "--load-settings",
                f"{profiles['machine']};{profiles['process']}",
                "--load-filaments",
                profiles["filament"],
                "--export-slicedata",
                str(output_dir),
                "--outputdir",
                str(output_dir),
                "--debug",
                "1",  # Minimal logging
            ]

            try:
                # Run slicer process
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=temp_dir,
                )

                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=self.settings.slicer_timeout
                )

                if process.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Unknown slicer error"
                    raise SlicerError(f"Slicer failed: {error_msg}")

                # Parse results using Rust implementation
                return await parse_slicer_output(str(output_dir))

            except TimeoutError as e:
                raise SlicerError("Slicing operation timed out") from e
            except Exception as e:
                raise SlicerError(f"Slicing failed: {str(e)}") from e
