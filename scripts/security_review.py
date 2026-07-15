"""Run deterministic repository security checks for the release gate."""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

SECRET_PATTERNS = {
    "supabase_secret": re.compile(r"sb_secret_[A-Za-z0-9_-]{20,}"),
    "jwt": re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}"),
    "credentialed_postgres_url": re.compile(r"postgres(?:ql)?://[^\s:@]+:[^\s@]+@[^\s]+"),
}
FRONTEND_FORBIDDEN = (
    "SUPABASE_SECRET_KEY",
    "SUPABASE_SERVICE_ROLE_KEY",
    "SUPABASE_DB_URL",
    "postgresql://",
    "dangerouslySetInnerHTML",
)
KNOWLEDGE_TABLES = (
    "embedding_models",
    "corpus_versions",
    "wiki_pages",
    "document_chunks",
    "entity_aliases",
    "source_attributions",
    "sync_runs",
)


@dataclass(frozen=True, slots=True)
class SecurityFinding:
    check: str
    passed: bool
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {"check": self.check, "passed": self.passed, "detail": self.detail}


def _review_files() -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        check=True,
        capture_output=True,
    )
    return tuple(Path(value.decode()) for value in result.stdout.split(b"\0") if value)


def _text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def run_review() -> tuple[SecurityFinding, ...]:
    """Check repository secrets, browser boundaries, RLS declarations, and private buckets."""
    files = _review_files()
    secret_hits: list[str] = []
    for path in files:
        content = _text(path)
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                secret_hits.append(f"{path.as_posix()}:{name}")
    frontend_hits: list[str] = []
    for path in files:
        if not path.as_posix().startswith("apps/web/"):
            continue
        content = _text(path)
        for marker in FRONTEND_FORBIDDEN:
            if marker in content:
                frontend_hits.append(f"{path.as_posix()}:{marker}")

    migrations = "\n".join(
        _text(path) for path in files if path.as_posix().startswith("supabase/migrations/")
    ).casefold()
    missing_rls = [
        table
        for table in KNOWLEDGE_TABLES
        if f"alter table knowledge.{table} enable row level security" not in migrations
    ]
    grants_safe = all(
        marker in migrations
        for marker in (
            "revoke all privileges on all tables in schema knowledge from anon, authenticated",
            "revoke all on function public.hybrid_search_dst",
            "revoke all on function public.activate_corpus_version",
            "revoke all on function public.rollback_corpus_version",
        )
    )
    private_buckets = all(
        re.search(rf"'{re.escape(bucket)}',\s*'{re.escape(bucket)}',\s*false", migrations)
        for bucket in (
            "dst-wiki-raw",
            "dst-corpus-snapshots",
            "dst-evaluation-reports",
        )
    )
    return (
        SecurityFinding(
            "repository_secret_scan",
            not secret_hits,
            "no credential patterns in tracked or unignored files"
            if not secret_hits
            else ", ".join(secret_hits),
        ),
        SecurityFinding(
            "frontend_secret_and_raw_html_scan",
            not frontend_hits,
            "frontend contains only the public FastAPI base URL"
            if not frontend_hits
            else ", ".join(frontend_hits),
        ),
        SecurityFinding(
            "knowledge_rls",
            not missing_rls,
            "all knowledge tables enable RLS"
            if not missing_rls
            else f"missing RLS: {', '.join(missing_rls)}",
        ),
        SecurityFinding(
            "grants_and_rpc_review",
            grants_safe,
            "anon/authenticated table and privileged RPC access is revoked",
        ),
        SecurityFinding(
            "private_storage_buckets",
            private_buckets,
            "all corpus and report buckets are private",
        ),
    )


def main() -> int:
    findings = run_review()
    passed = all(finding.passed for finding in findings)
    print(
        json.dumps(
            {"passed": passed, "findings": [finding.to_dict() for finding in findings]},
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
