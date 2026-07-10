from app.ai.client import AIClient, AIResponse
from app.ai.code_fixer import CodeFixer, CodePatch
from app.ai.prompts import (
    ANALYZE_DEPENDENCY_PROMPT,
    CHECK_BREAKING_CHANGES_PROMPT,
    GENERATE_MIGRATION_PROMPT,
    SUGGEST_ALTERNATIVE_PROMPT,
)

__all__ = [
    "AIClient",
    "AIResponse",
    "CodeFixer",
    "CodePatch",
    "ANALYZE_DEPENDENCY_PROMPT",
    "CHECK_BREAKING_CHANGES_PROMPT",
    "GENERATE_MIGRATION_PROMPT",
    "SUGGEST_ALTERNATIVE_PROMPT",
]
