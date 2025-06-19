#!/usr/bin/env python3
"""
Proof of Concept script to test OrcaSlicer CLI and understand output format.
This script will help us understand what data is available from the slicer.
"""

import os
import subprocess
import sys
import tempfile

# OrcaSlicer CLI path
ORCASLICER_CLI = "/var/lib/flatpak/exports/bin/io.github.softfever.OrcaSlicer"


def test_orcaslicer_info(model_path: str):
    """Test the --info flag to see what information is available."""
    print(f"\n=== Testing --info flag with {model_path} ===")

    try:
        result = subprocess.run(
            [ORCASLICER_CLI, "--info", model_path],
            capture_output=True,
            text=True,
            timeout=60,
        )

        print(f"Return code: {result.returncode}")
        print(f"STDOUT:\n{result.stdout}")
        if result.stderr:
            print(f"STDERR:\n{result.stderr}")

    except subprocess.TimeoutExpired:
        print("Command timed out")
    except subprocess.CalledProcessError as e:
        print(f"Command failed: {e}")
    except FileNotFoundError:
        print(f"OrcaSlicer CLI not found at {ORCASLICER_CLI}")


def test_orcaslicer_slice_export(model_path: str):
    """Test slicing with --export-slicedata to see what files are generated."""
    print(f"\n=== Testing slicing with --export-slicedata for {model_path} ===")

    # Create temporary output directory
    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = os.path.join(temp_dir, "slicedata")
        os.makedirs(output_dir, exist_ok=True)

        try:
            # Try basic slicing with export
            command = [
                ORCASLICER_CLI,
                model_path,
                "--slice",
                "0",  # Slice all plates
                "--export-slicedata",
                output_dir,
                "--debug",
                "3",  # Info level debugging
            ]

            print(f"Running command: {' '.join(command)}")

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minutes timeout
            )

            print(f"Return code: {result.returncode}")
            print(f"STDOUT:\n{result.stdout}")
            if result.stderr:
                print(f"STDERR:\n{result.stderr}")

            # Inspect output directory
            print(f"\n=== Inspecting output directory: {output_dir} ===")
            if os.path.exists(output_dir):
                for root, _dirs, files in os.walk(output_dir):
                    level = root.replace(output_dir, "").count(os.sep)
                    indent = " " * 2 * level
                    print(f"{indent}{os.path.basename(root)}/")
                    subindent = " " * 2 * (level + 1)
                    for file in files:
                        file_path = os.path.join(root, file)
                        file_size = os.path.getsize(file_path)
                        print(f"{subindent}{file} ({file_size} bytes)")

                        # Try to read small files to understand content
                        if file_size < 10000:  # Less than 10KB
                            try:
                                with open(file_path, encoding="utf-8") as f:
                                    content = f.read()
                                    print(f"{subindent}Content preview:")
                                    print(f"{subindent}{content[:500]}...")
                            except (UnicodeDecodeError, Exception):
                                print(f"{subindent}Binary file or unreadable")
            else:
                print("Output directory was not created!")

        except subprocess.TimeoutExpired:
            print("Slicing command timed out")
        except subprocess.CalledProcessError as e:
            print(f"Slicing command failed: {e}")
        except FileNotFoundError:
            print(f"OrcaSlicer CLI not found at {ORCASLICER_CLI}")


def create_test_stl() -> str:
    """Create a simple test STL file if none exists."""
    test_file = "test_cube.stl"
    if not os.path.exists(test_file):
        # Create a simple ASCII STL cube (10x10x10mm)
        stl_content = """solid cube
  facet normal 0.0 0.0 -1.0
    outer loop
      vertex 0.0 0.0 0.0
      vertex 10.0 0.0 0.0
      vertex 10.0 10.0 0.0
    endloop
  endfacet
  facet normal 0.0 0.0 -1.0
    outer loop
      vertex 0.0 0.0 0.0
      vertex 10.0 10.0 0.0
      vertex 0.0 10.0 0.0
    endloop
  endfacet
  facet normal 0.0 0.0 1.0
    outer loop
      vertex 0.0 0.0 10.0
      vertex 10.0 10.0 10.0
      vertex 10.0 0.0 10.0
    endloop
  endfacet
  facet normal 0.0 0.0 1.0
    outer loop
      vertex 0.0 0.0 10.0
      vertex 0.0 10.0 10.0
      vertex 10.0 10.0 10.0
    endloop
  endfacet
endsolid cube"""

        with open(test_file, "w") as f:
            f.write(stl_content)
        print(f"Created test STL file: {test_file}")

    return test_file


def main() -> None:
    print("OrcaSlicer CLI Proof of Concept")
    print("=" * 50)

    # Check if OrcaSlicer CLI exists
    if not os.path.exists(ORCASLICER_CLI):
        print(f"Error: OrcaSlicer CLI not found at {ORCASLICER_CLI}")
        print("Please verify the installation path.")
        sys.exit(1)

    # Create or use test file
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        if not os.path.exists(test_file):
            print(f"Error: File {test_file} not found")
            sys.exit(1)
    else:
        test_file = create_test_stl()

    print(f"Using test file: {test_file}")

    # Test different CLI approaches
    test_orcaslicer_info(test_file)
    test_orcaslicer_slice_export(test_file)

    print("\n" + "=" * 50)
    print("PoC completed. Check the output above to understand:")
    print("1. What information --info provides")
    print("2. What files --export-slicedata creates")
    print("3. Where print time and filament usage might be stored")


if __name__ == "__main__":
    main()
