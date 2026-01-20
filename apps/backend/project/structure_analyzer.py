"""
Project Structure Analyzer
==========================

Analyzes project structure for custom scripts (npm scripts,
Makefile targets, Poetry scripts, shell scripts) and custom
command allowlists.
"""

import json
import re
from pathlib import Path

from .config_parser import ConfigParser
from .models import CustomScripts


class StructureAnalyzer:
    """Analyzes project structure for custom scripts."""

    CUSTOM_ALLOWLIST_FILENAME = ".auto-claude-allowlist"

    def __init__(self, project_dir: Path):
        """
        Initialize structure analyzer.

        Args:
            project_dir: Root directory of the project
        """
        self.project_dir = Path(project_dir).resolve()
        self.parser = ConfigParser(project_dir)
        self.custom_scripts = CustomScripts()
        self.custom_commands = set()
        self.script_commands = set()

    def analyze(self) -> tuple[CustomScripts, set[str], set[str]]:
        """
        Analyze project structure.

        Returns:
            Tuple of (CustomScripts, script_commands, custom_commands)
        """
        self.detect_custom_scripts()
        self.load_custom_allowlist()
        self._load_security_defaults()
        return self.custom_scripts, self.script_commands, self.custom_commands

    def detect_custom_scripts(self) -> None:
        """Detect custom scripts (npm scripts, Makefile targets, etc.)."""
        self._detect_npm_scripts()
        self._detect_makefile_targets()
        self._detect_poetry_scripts()
        self._detect_shell_scripts()

    def _detect_npm_scripts(self) -> None:
        """Detect npm scripts from package.json."""
        pkg = self.parser.read_json("package.json")
        if pkg and "scripts" in pkg:
            self.custom_scripts.npm_scripts = list(pkg["scripts"].keys())

            # Add commands to run these scripts
            for script in self.custom_scripts.npm_scripts:
                self.script_commands.add("npm")
                self.script_commands.add("yarn")
                self.script_commands.add("pnpm")
                self.script_commands.add("bun")

    def _detect_makefile_targets(self) -> None:
        """Detect Makefile targets."""
        if not self.parser.file_exists("Makefile"):
            return

        content = self.parser.read_text("Makefile")
        if not content:
            return

        for line in content.splitlines():
            # Match target definitions like "target:" or "target: deps"
            match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:", line)
            if match:
                target = match.group(1)
                # Skip common internal targets
                if not target.startswith("."):
                    self.custom_scripts.make_targets.append(target)

        if self.custom_scripts.make_targets:
            self.script_commands.add("make")

    def _detect_poetry_scripts(self) -> None:
        """Detect Poetry scripts from pyproject.toml."""
        toml = self.parser.read_toml("pyproject.toml")
        if not toml:
            return

        # Poetry scripts
        if "tool" in toml and "poetry" in toml["tool"]:
            poetry_scripts = toml["tool"]["poetry"].get("scripts", {})
            self.custom_scripts.poetry_scripts = list(poetry_scripts.keys())

        # PEP 621 scripts
        if "project" in toml and "scripts" in toml["project"]:
            self.custom_scripts.poetry_scripts.extend(
                list(toml["project"]["scripts"].keys())
            )

    def _detect_shell_scripts(self) -> None:
        """Detect shell scripts in root directory."""
        for ext in ["*.sh", "*.bash"]:
            for script_path in self.parser.glob_files(ext):
                script_name = script_path.name
                self.custom_scripts.shell_scripts.append(script_name)
                # Allow executing these scripts
                self.script_commands.add(f"./{script_name}")

    def load_custom_allowlist(self) -> None:
        """Load user-defined custom allowlist."""
        content = self.parser.read_text(self.CUSTOM_ALLOWLIST_FILENAME)
        if not content:
            return

        for line in content.splitlines():
            line = line.strip()
            # Skip comments and empty lines
            if line and not line.startswith("#"):
                self.custom_commands.add(line)

    def _load_security_defaults(self) -> None:
        """
        Load pre-approved commands from security_defaults.json.

        This file can be placed in .auto-claude/ directory to provide
        workspace-wide security defaults for multi-repo workspaces.

        Expected format:
        {
            "custom_scripts": {
                "make_targets": ["build", "test", ...],
                "mise_tasks": ["mise run all", ...]
            },
            "validation_commands": {
                "go": {"build": "go build ./...", ...},
                ...
            }
        }
        """
        defaults_path = self.project_dir / ".auto-claude" / "security_defaults.json"
        if not defaults_path.exists():
            return

        try:
            with open(defaults_path, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return

        # Load custom scripts section
        custom_scripts = data.get("custom_scripts", {})

        # Add make targets from defaults
        make_targets = custom_scripts.get("make_targets", [])
        for target in make_targets:
            if target not in self.custom_scripts.make_targets:
                self.custom_scripts.make_targets.append(target)
        if make_targets:
            self.script_commands.add("make")

        # Add mise tasks from defaults
        mise_tasks = custom_scripts.get("mise_tasks", [])
        for task in mise_tasks:
            if task not in self.custom_scripts.mise_tasks:
                self.custom_scripts.mise_tasks.append(task)
        if mise_tasks:
            self.script_commands.add("mise")

        # Load validation commands as custom commands
        validation_commands = data.get("validation_commands", {})
        for _category, commands in validation_commands.items():
            if isinstance(commands, dict):
                for cmd in commands.values():
                    if isinstance(cmd, str):
                        # Extract base command (first word)
                        base_cmd = cmd.split()[0] if cmd else ""
                        if base_cmd:
                            self.custom_commands.add(base_cmd)
