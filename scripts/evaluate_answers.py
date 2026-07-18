"""Evaluate saved grounded-answer observations for citations, faithfulness, and abstention."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.config import Settings
from src.evaluation import (
    DEFAULT_RELEASE_DATASET,
    AnswerEvaluator,
    ReleaseDataset,
    load_answer_observations,
)
from src.operations import SupabaseEvaluationReportRepository


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_RELEASE_DATASET)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--upload", action="store_true")
    return parser.parse_args()


def main() -> int:
    """Score only explicitly recorded answers and optionally persist the report privately."""
    args = parse_args()
    report = AnswerEvaluator().evaluate(
        ReleaseDataset.load(args.dataset),
        load_answer_observations(args.observations),
    )
    rendered = json.dumps(report.to_dict(), ensure_ascii=False, indent=2)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    if args.upload:
        settings = Settings()
        api_key = settings.supabase_admin_api_key
        if settings.supabase_url is None or api_key is None:
            raise SystemExit("SUPABASE_URL and a backend secret/service-role key are required")
        with SupabaseEvaluationReportRepository(
            base_url=str(settings.supabase_url),
            api_key=api_key.get_secret_value(),
            bucket=settings.supabase_eval_bucket,
        ) as storage:
            path = storage.upload_json("answers", f"{rendered}\n".encode())
        print(json.dumps({"storage_path": path}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
