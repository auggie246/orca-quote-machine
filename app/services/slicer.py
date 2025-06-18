"""OrcaSlicer integration service."""

import asyncio
import json
import os
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple

from app.core.config import get_settings
from app.models.quote import MaterialType, SlicingResult


class SlicerError(Exception):
    """Custom exception for slicer-related errors."""
    pass


class OrcaSlicerService:
    """Service for interacting with OrcaSlicer CLI."""
    
    def __init__(self):
        self.settings = get_settings()
        self.cli_path = self.settings.orcaslicer_cli_path
        self.profiles_dir = Path(self.settings.slicer_profiles_dir)
    
    def get_profile_paths(self, material: Optional[MaterialType] = None) -> Dict[str, str]:
        """Get paths to slicer profile files."""
        material = material or MaterialType.PLA
        
        profiles = {
            "machine": self.profiles_dir / "machine" / "default_machine.ini",
            "filament": self.profiles_dir / "filament" / f"{material.value.lower()}.ini",
            "process": self.profiles_dir / "process" / "standard_0.2mm.ini",
        }
        
        # Verify all profiles exist
        for profile_type, path in profiles.items():
            if not path.exists():
                raise SlicerError(f"Profile not found: {profile_type} at {path}")
        
        return {k: str(v) for k, v in profiles.items()}
    
    async def slice_model(self, 
                         model_path: str, 
                         material: Optional[MaterialType] = None) -> SlicingResult:
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
            output_dir.mkdir()
            
            # Build command
            command = [
                self.cli_path,
                model_path,
                "--slice", "0",  # Slice all plates
                "--load-settings", f"{profiles['machine']};{profiles['process']}",
                "--load-filaments", profiles['filament'],
                "--export-slicedata", str(output_dir),
                "--outputdir", str(output_dir),
                "--debug", "1",  # Minimal logging
            ]
            
            try:
                # Run slicer process
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=temp_dir
                )
                
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=self.settings.slicer_timeout
                )
                
                if process.returncode != 0:
                    error_msg = stderr.decode() if stderr else "Unknown slicer error"
                    raise SlicerError(f"Slicer failed: {error_msg}")
                
                # Parse results
                return await self._parse_slice_results(output_dir, stdout.decode())
                
            except asyncio.TimeoutError:
                raise SlicerError("Slicing operation timed out")
            except Exception as e:
                raise SlicerError(f"Slicing failed: {str(e)}")
    
    async def _parse_slice_results(self, output_dir: Path, stdout: str) -> SlicingResult:
        """
        Parse slicing results from output directory and stdout.
        
        This method will be updated once we understand the exact output format
        from our PoC testing.
        """
        # TODO: Implement actual parsing based on PoC results
        # For now, return placeholder values
        
        # Look for common output files
        gcode_files = list(output_dir.glob("*.gcode"))
        json_files = list(output_dir.glob("*.json"))
        
        if not gcode_files:
            raise SlicerError("No G-code output found")
        
        # Parse G-code comments for print info (common location)
        gcode_path = gcode_files[0]
        print_time_minutes, filament_grams = await self._parse_gcode_metadata(gcode_path)
        
        # Try to parse from JSON files if available
        if json_files:
            json_data = await self._parse_json_metadata(json_files[0])
            if json_data:
                print_time_minutes = json_data.get("print_time_minutes", print_time_minutes)
                filament_grams = json_data.get("filament_grams", filament_grams)
        
        return SlicingResult(
            print_time_minutes=print_time_minutes,
            filament_weight_grams=filament_grams,
            layer_count=None  # TODO: Extract from results
        )
    
    async def _parse_gcode_metadata(self, gcode_path: Path) -> Tuple[int, float]:
        """Parse print time and filament usage from G-code comments."""
        print_time_minutes = 0
        filament_grams = 0.0
        
        try:
            with open(gcode_path, 'r', encoding='utf-8') as f:
                # Read first 100 lines where metadata is typically located
                for i, line in enumerate(f):
                    if i > 100:
                        break
                    
                    line = line.strip()
                    
                    # Common G-code comment patterns for print time
                    if "; estimated printing time" in line.lower():
                        # Parse time formats like "1h 30m", "90m", etc.
                        time_str = line.split(":")[-1].strip()
                        print_time_minutes = self._parse_time_string(time_str)
                    
                    # Common patterns for filament usage
                    elif "; filament used" in line.lower() or "; material volume" in line.lower():
                        # Parse weight/volume information
                        if "g" in line or "gram" in line:
                            import re
                            match = re.search(r'(\d+\.?\d*)\s*g', line)
                            if match:
                                filament_grams = float(match.group(1))
        
        except Exception as e:
            # Fallback values if parsing fails
            print(f"Warning: Could not parse G-code metadata: {e}")
            print_time_minutes = 60  # 1 hour default
            filament_grams = 20.0   # 20g default
        
        return print_time_minutes, filament_grams
    
    async def _parse_json_metadata(self, json_path: Path) -> Optional[Dict]:
        """Parse metadata from JSON output files."""
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data
        except Exception:
            return None
    
    def _parse_time_string(self, time_str: str) -> int:
        """Parse time string to minutes."""
        import re
        
        # Remove common prefixes and clean up
        time_str = re.sub(r'(estimated|printing|time|:)', '', time_str, flags=re.IGNORECASE)
        time_str = time_str.strip()
        
        minutes = 0
        
        # Parse "1h 30m" format
        hour_match = re.search(r'(\d+)h', time_str)
        minute_match = re.search(r'(\d+)m', time_str)
        
        if hour_match:
            minutes += int(hour_match.group(1)) * 60
        if minute_match:
            minutes += int(minute_match.group(1))
        
        # Parse "90m" format (minutes only)
        if not hour_match and not minute_match:
            minute_only = re.search(r'(\d+)', time_str)
            if minute_only:
                minutes = int(minute_only.group(1))
        
        return minutes or 60  # Default to 1 hour if parsing fails