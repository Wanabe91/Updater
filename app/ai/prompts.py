from __future__ import annotations

ANALYZE_DEPENDENCY_PROMPT = """
Analyze the following dependency and provide:
1. Whether it's outdated
2. Security concerns
3. Better alternatives if they exist
4. Migration complexity (low/medium/high)

Package: {package}
Version: {version}
Ecosystem: {ecosystem}
"""

SUGGEST_ALTERNATIVE_PROMPT = """
Suggest better alternatives for the following dependency.
Consider: maintenance status, performance, features, community size.

Current package: {package}
Version: {version}
Ecosystem: {ecosystem}

Respond in JSON format:
{{
    "alternatives": [
        {{
            "name": "package-name",
            "version": "x.y.z",
            "reason": "why it's better",
            "migration_complexity": "low|medium|high",
            "confidence": 0.0-1.0
        }}
    ]
}}
"""

GENERATE_MIGRATION_PROMPT = """
Generate code migration steps for replacing
{old_package} ({old_version}) with {new_package} ({new_version}).

Old API usage:
{old_code}

Provide:
1. Import changes
2. API changes
3. Complete migrated code
4. Notes on breaking changes

Respond in JSON format:
{{
    "imports": {{"old": "...", "new": "..."}},
    "api_changes": [...],
    "migrated_code": "...",
    "breaking_changes": [...]
}}
"""

CHECK_BREAKING_CHANGES_PROMPT = """
Check if upgrading {package} from {old_version} to {new_version} introduces breaking changes.

Respond in JSON format:
{{
    "has_breaking_changes": true/false,
    "severity": "none|low|medium|high|critical",
    "changes": [...],
    "migration_notes": "..."
}}
"""
