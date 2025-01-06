#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def run_command(cmd, cwd=None):
    """Run a shell command and check for errors."""
    try:
        subprocess.run(cmd, check=True, cwd=cwd, shell=True)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        print(f"Error: {e}")
        sys.exit(1)


def get_package_name(package_dir):
    """Get the package name from package.json."""
    package_json = package_dir / "package.json"
    if not package_json.exists():
        return None
    with open(package_json) as f:
        return json.load(f).get("name")


def add_packages_to_root(base_path, jupyterlite_path):
    """Add packages to the root package.json using file: protocol."""
    base_path = Path(base_path)
    if not base_path.exists():
        print(f"Warning: Path {base_path} does not exist")
        return

    # Build the packages first
    print(f"Building packages in {base_path}...")
    run_command("jlpm", cwd=str(base_path))
    run_command("jlpm run build", cwd=str(base_path))

    # Get relative path from jupyterlite to base_path
    rel_path = os.path.relpath(base_path, jupyterlite_path)

    # Read root package.json
    root_package_json = Path(jupyterlite_path) / "package.json"
    with open(root_package_json) as f:
        root_package = json.load(f)

    # Initialize or get dependencies
    dependencies = root_package.get("dependencies", {})
    resolutions = root_package.get("resolutions", {})

    # Process each package
    for item in base_path.iterdir():
        if item.is_dir():
            package_name = get_package_name(item)
            if not package_name:
                continue

            if package_name.startswith("@jupyterlab") or package_name.startswith(
                "@jupyter-notebook"
            ):
                print(f"Adding package: {package_name}")
                package_path = f"file:{rel_path}/{item.name}"
                dependencies[package_name] = package_path
                resolutions[package_name] = package_path

    # Update root package.json
    root_package["dependencies"] = dependencies
    root_package["resolutions"] = resolutions

    with open(root_package_json, "w") as f:
        json.dump(root_package, f, indent=2)


def build_jupyterlite(jupyterlite_path):
    """Build the JupyterLite project."""
    run_command("rm -rf .doit.db", cwd=str(jupyterlite_path))
    run_command("jlpm", cwd=str(jupyterlite_path))
    run_command("jlpm deduplicate", cwd=str(jupyterlite_path))
    run_command("jlpm run build", cwd=str(jupyterlite_path))
    run_command("jlpm run pack:app", cwd=str(jupyterlite_path))

    jupyterlite_core_path = Path(jupyterlite_path) / "py" / "jupyterlite-core"
    run_command("hatch build", cwd=str(jupyterlite_core_path))


def main():
    parser = argparse.ArgumentParser(
        description="Build JupyterLite with local package links"
    )
    parser.add_argument(
        "--jupyterlab-path",
        default="./jupyterlab/packages",
        help="Path to JupyterLab packages (default: %(default)s)",
    )
    parser.add_argument(
        "--notebook-path",
        default="./notebook/packages",
        help="Path to Notebook packages (default: %(default)s)",
    )
    parser.add_argument(
        "--jupyterlite-path",
        default="./jupyterlite",
        help="Path to JupyterLite repository (default: %(default)s)",
    )

    args = parser.parse_args()

    # Convert to absolute paths
    jupyterlab_path = str(Path(args.jupyterlab_path).resolve())
    notebook_path = str(Path(args.notebook_path).resolve())
    jupyterlite_path = str(Path(args.jupyterlite_path).resolve())

    # Store current directory to restore later
    original_dir = os.getcwd()

    try:
        # Change to jupyterlite directory
        os.chdir(jupyterlite_path)

        # Install dependencies
        run_command("python -m pip install -r requirements-build.txt")
        run_command("jlpm")

        # Add packages to root package.json
        print("\nAdding JupyterLab packages...")
        add_packages_to_root(jupyterlab_path, jupyterlite_path)

        print("\nAdding Notebook packages...")
        add_packages_to_root(notebook_path, jupyterlite_path)

        print("\nBuilding JupyterLite...")
        build_jupyterlite(jupyterlite_path)

    finally:
        # Restore original directory
        os.chdir(original_dir)

    print("Done.")


if __name__ == "__main__":
    main()
