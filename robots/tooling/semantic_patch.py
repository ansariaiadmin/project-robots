"""Semantic Patch Tool — Pattern-based changes using comby/coccinelle."""

from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class PatchResult:
    """Result of semantic patch application."""
    success: bool
    files_changed: int
    changes: list[dict]
    errors: list[str] = None
    preview: str = ""

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class SemanticPatcher:
    """Applies semantic patches using comby or coccinelle."""

    def __init__(self, config: dict):
        self.config = config
        self.use_comby = self._check_comby()
        self.use_coccinelle = self._check_coccinelle()

    def _check_comby(self) -> bool:
        try:
            subprocess.run(["comby", "-version"], capture_output=True, check=True)
            return True
        except Exception:
            return False

    def _check_coccinelle(self) -> bool:
        try:
            subprocess.run(["spatch", "--version"], capture_output=True, check=True)
            return True
        except Exception:
            return False

    def apply_patch(
        self,
        pattern: str,
        replacement: str,
        file_pattern: str = "*.py",
        directory: Path = None,
        dry_run: bool = False,
        allowed_files: set[str] | None = None,
    ) -> PatchResult:
        """Apply a semantic patch pattern.

        When allowed_files is given, only those project-relative paths are
        touched (builtin engine), so arbitrary rglob replacement is disabled.
        dry_run returns diff previews without writing.
        """
        if allowed_files is not None:
            return self._apply_builtin(
                pattern, replacement, file_pattern, directory,
                dry_run=dry_run, allowed_files=allowed_files,
            )
        if self.use_comby:
            return self._apply_comby(pattern, replacement, file_pattern, directory, dry_run)
        elif self.use_coccinelle:
            return self._apply_coccinelle(pattern, replacement, file_pattern, directory, dry_run)
        else:
            return self._apply_builtin(pattern, replacement, file_pattern, directory, dry_run)

    def _apply_comby(
        self,
        pattern: str,
        replacement: str,
        file_pattern: str,
        directory: Path | None,
        dry_run: bool = False,
    ) -> PatchResult:
        """Apply patch using comby."""
        cwd = directory or Path.cwd()

        try:
            # Dry run first
            result = subprocess.run(
                ["comby", pattern, replacement, file_pattern, "-dry-run"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            if result.returncode != 0:
                return PatchResult(
                    success=False,
                    files_changed=0,
                    changes=[],
                    errors=[result.stderr],
                )

            if dry_run:
                return PatchResult(
                    success=True,
                    files_changed=0,
                    changes=[],
                    preview=result.stdout[:4000],
                    errors=["dry-run preview: comby -in-place not applied"],
                )

            # Apply for real
            result = subprocess.run(
                ["comby", pattern, replacement, file_pattern, "-in-place"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            # Parse output for changed files
            changes = []
            for line in result.stdout.splitlines():
                if "Rewrote" in line or "changed" in line.lower():
                    changes.append({"file": line.strip()})

            return PatchResult(
                success=result.returncode == 0,
                files_changed=len(changes),
                changes=changes,
                errors=[result.stderr] if result.stderr else [],
            )
        except subprocess.TimeoutExpired:
            return PatchResult(success=False, files_changed=0, changes=[], errors=["timeout"])
        except Exception as e:
            return PatchResult(success=False, files_changed=0, changes=[], errors=[str(e)])

    def _apply_coccinelle(
        self,
        pattern: str,
        replacement: str,
        file_pattern: str,
        directory: Path | None,
        dry_run: bool = False,
    ) -> PatchResult:
        """Apply patch using coccinelle (spatch)."""
        cwd = directory or Path.cwd()
        if dry_run:
            return PatchResult(
                success=True,
                files_changed=0,
                changes=[],
                errors=["dry-run preview: spatch --in-place not applied"],
            )
        # Create temporary coccinelle rule file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".cocci", delete=False) as f:
            f.write(f"""
@rule@
expression E;
@@
- {pattern}
+ {replacement}
""")
            rule_file = f.name

        try:
            result = subprocess.run(
                ["spatch", "--sp-file", rule_file, "--dir", str(cwd), "--include", file_pattern, "--in-place"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60,
            )

            changes = []
            for line in result.stdout.splitlines():
                if "diff" in line.lower() or "patch" in line.lower():
                    changes.append({"file": line.strip()})

            return PatchResult(
                success=result.returncode == 0,
                files_changed=len(changes),
                changes=changes,
                errors=[result.stderr] if result.stderr else [],
            )
        except Exception as e:
            return PatchResult(success=False, files_changed=0, changes=[], errors=[str(e)])
        finally:
            Path(rule_file).unlink(missing_ok=True)

    def _apply_builtin(
        self,
        pattern: str,
        replacement: str,
        file_pattern: str,
        directory: Path | None,
        dry_run: bool = False,
        allowed_files: set[str] | None = None,
    ) -> PatchResult:
        """Built-in simple pattern replacement (fallback)."""
        import fnmatch

        from robots.autonomous.guard import preview_unified_diff

        cwd = directory or Path.cwd()
        changes = []
        previews: list[str] = []

        if allowed_files is not None:
            candidates = [
                cwd / rel for rel in sorted(allowed_files)
                if fnmatch.fnmatch(rel, file_pattern)
                or fnmatch.fnmatch(Path(rel).name, file_pattern)
            ]
        else:
            candidates = [p for p in cwd.rglob(file_pattern) if p.is_file()]
        for file_path in candidates:
            if file_path.is_file():
                try:
                    content = file_path.read_text(encoding="utf-8")
                    if pattern in content:
                        new_content = content.replace(pattern, replacement)
                        if new_content != content:
                            rel = file_path.relative_to(cwd).as_posix()
                            previews.append(preview_unified_diff(content, new_content, rel))
                            if not dry_run:
                                file_path.write_text(new_content, encoding="utf-8")
                            changes.append({"file": rel})
                except Exception:
                    pass

        preview = "\n".join(previews)[:8000]
        if dry_run:
            return PatchResult(
                success=True,
                files_changed=0,
                changes=changes,
                preview=preview,
                errors=["dry-run preview: no files written"],
            )
        return PatchResult(
            success=True,
            files_changed=len(changes),
            changes=changes,
            preview=preview,
            errors=["Built-in patcher used; install comby for semantic matching"] if changes else [],
        )

    def apply_decorator_pattern(
        self,
        decorator_name: str,
        file_pattern: str = "*.py",
        directory: Path = None,
        action: str = "add",  # "add", "remove", "replace"
        replacement_decorator: str = None,
    ) -> PatchResult:
        """Apply decorator pattern changes."""
        if action == "add":
            pattern = "def [[name]]([[args]]):\n    [[body]]"
            replacement = f"@{decorator_name}\ndef [[name]]([[args]]):\n    [[body]]"
        elif action == "remove":
            pattern = f"@{decorator_name}\ndef [[name]]([[args]]):\n    [[body]]"
            replacement = "def [[name]]([[args]]):\n    [[body]]"
        elif action == "replace" and replacement_decorator:
            pattern = f"@{decorator_name}\ndef [[name]]([[args]]):\n    [[body]]"
            replacement = f"@{replacement_decorator}\ndef [[name]]([[args]]):\n    [[body]]"
        else:
            return PatchResult(success=False, files_changed=0, changes=[], errors=["Invalid action"])

        return self.apply_patch(pattern, replacement, file_pattern, directory)

    def apply_logging_pattern(
        self,
        file_pattern: str = "*.py",
        directory: Path = None,
        logger_name: str = "logger",
    ) -> PatchResult:
        """Add logging to function entries."""
        pattern = "def [[name]]([[args]]):\n    [[body]]"
        replacement = f"def [[name]]([[args]]):\n    {logger_name}.debug('Entering [[name]]')\n    [[body]]"

        return self.apply_patch(pattern, replacement, file_pattern, directory)


def apply_semantic_patch(
    pattern: str,
    replacement: str,
    file_pattern: str = "*.py",
    directory: Path = None,
    config: dict = None,
    dry_run: bool = False,
    allowed_files: set[str] | None = None,
) -> PatchResult:
    """Convenience function to apply semantic patch."""
    patcher = SemanticPatcher(config or {})
    return patcher.apply_patch(
        pattern, replacement, file_pattern, directory, dry_run, allowed_files
    )
