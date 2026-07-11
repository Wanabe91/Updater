from __future__ import annotations

import json
import logging
from pathlib import Path

from app.ai.client import AIClient, extract_json
from app.ai.prompts import GENERATE_MIGRATION_PROMPT

logger = logging.getLogger(__name__)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[-1].strip() == "```":
        lines = lines[1:-1]
    else:
        lines = lines[1:]
    return "\n".join(lines)


class CodePatch:
    def __init__(
        self,
        file_path: Path,
        old_code: str,
        new_code: str,
        description: str = "",
    ) -> None:
        self.file_path = file_path
        self.old_code = old_code
        self.new_code = new_code
        self.description = description

    def to_dict(self) -> dict:
        return {
            "file_path": str(self.file_path),
            "old_code": self.old_code,
            "new_code": self.new_code,
            "description": self.description,
        }


class CodeFixer:
    def __init__(self, ai_client: AIClient) -> None:
        self.ai_client = ai_client

    def fix_imports(
        self,
        file_path: Path,
        old_package: str,
        new_package: str,
        source: str | None = None,
    ) -> CodePatch | None:
        if source is None:
            source = file_path.read_text(encoding="utf-8")
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a code migration assistant. "
                    "Replace all imports from the old package "
                    "with the new package. "
                    "Return ONLY the complete modified file "
                    "content, nothing else."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Replace all imports from '{old_package}' "
                    f"with '{new_package}' "
                    f"in the following file:\n\n{source}"
                ),
            },
        ]
        response = self.ai_client.chat(messages, temperature=0.0)
        if not response.success:
            logger.error("fix_imports failed for %s: %s", file_path, response.error)
            return None

        new_source = _strip_code_fences(response.content)
        if source.endswith("\n") and not new_source.endswith("\n"):
            new_source += "\n"
        if new_source.strip() == source.strip():
            logger.info("No import changes needed in %s", file_path)
            return None

        return CodePatch(
            file_path=file_path,
            old_code=source,
            new_code=new_source,
            description=f"Replace imports: {old_package} -> {new_package}",
        )

    def fix_api_usage(
        self,
        file_path: Path,
        old_package: str,
        old_version: str,
        new_package: str,
        new_version: str,
        source: str | None = None,
    ) -> list[CodePatch]:
        if source is None:
            source = file_path.read_text(encoding="utf-8")

        if old_package not in source and new_package not in source:
            return []

        prompt = GENERATE_MIGRATION_PROMPT.format(
            old_package=old_package,
            old_version=old_version,
            new_package=new_package,
            new_version=new_version,
            old_code=source,
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a code migration expert. "
                    "Respond only in valid JSON."
                ),
            },
            {"role": "user", "content": prompt},
        ]
        response = self.ai_client.chat(messages, temperature=0.2)
        if not response.success:
            logger.error("fix_api_usage failed for %s: %s", file_path, response.error)
            return []

        try:
            result = json.loads(extract_json(response.content))
        except ValueError:
            logger.warning(
                "Failed to parse JSON from fix_api_usage for %s",
                file_path,
            )
            return []

        migrated_code = result.get("migrated_code", "")
        if not migrated_code or migrated_code.strip() == source.strip():
            return []

        breaking = result.get("breaking_changes", "")
        if isinstance(breaking, list):
            breaking = "; ".join(str(item) for item in breaking)

        return [
            CodePatch(
                file_path=file_path,
                old_code=source,
                new_code=migrated_code,
                description=breaking,
            )
        ]

    def generate_patches(
        self,
        project_path: Path,
        old_package: str,
        new_package: str,
        old_version: str = "",
        new_version: str = "",
    ) -> list[CodePatch]:
        patches: list[CodePatch] = []
        supported_ext = {
            ".py", ".js", ".ts", ".jsx", ".tsx",
            ".go", ".rs", ".java",
        }

        for file_path in project_path.rglob("*"):
            if file_path.suffix not in supported_ext:
                continue
            rel = file_path.relative_to(project_path).parts
            if any(part.startswith(".") for part in rel):
                continue
            if file_path.name.endswith(".min.js") or file_path.name.endswith(".min.ts"):
                continue

            try:
                source = file_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, PermissionError):
                continue

            if old_package not in source:
                continue

            import_patch = self.fix_imports(
                file_path, old_package, new_package, source=source
            )
            current_source = source
            if import_patch is not None:
                patches.append(import_patch)
                current_source = import_patch.new_code

            api_patches = self.fix_api_usage(
                file_path,
                old_package,
                old_version,
                new_package,
                new_version,
                source=current_source,
            )
            patches.extend(api_patches)

        return patches
