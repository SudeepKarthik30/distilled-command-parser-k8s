"""Dataset cleaning and validation pipeline for teacher-generated distillation data.

Filters invalid JSON, unsupported intents, hallucinated slot spans, and duplicate queries.
Outputs verified train.jsonl with sha256 checksum and dataset breakdown counts.
"""

import argparse
import glob
import hashlib
import json
import logging
import os
import sys
from typing import Dict, Any, List, Set, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cleaner")

ALLOWED_INTENTS = {
    "alarm_set", "alarm_query", "calendar_set", "calendar_query",
    "calendar_remove", "weather_query", "datetime_query", "recommendation_events"
}
REQUIRED_SLOT_KEYS = {"intent", "date", "time", "place"}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Clean raw teacher model annotations.")
    parser.add_argument("--shards", default="results/teacher", help="Directory containing shard-*.jsonl files")
    parser.add_argument("--out-dir", default="results/clean", help="Target output directory for cleaned datasets")
    parser.add_argument("--upload", action="store_true", help="Upload artifacts to SeaweedFS object store")
    return parser.parse_args()


def load_shard_records(shard_directory: str) -> List[Dict[str, Any]]:
    records = []
    pattern = os.path.join(shard_directory, "shard-*.jsonl")
    for filepath in sorted(glob.glob(pattern)):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped:
                    records.append(json.loads(stripped))
    records.sort(key=lambda item: item["id"])
    return records


def validate_and_filter(records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    stats = {
        "input": len(records),
        "bad_json": 0,
        "bad_keys": 0,
        "bad_intent": 0,
        "bad_slot": 0,
        "duplicates": 0,
        "kept": 0
    }
    cleaned_items: List[Dict[str, Any]] = []
    seen_prompts: Set[str] = set()

    for item in records:
        raw_text = item.get("text", "")
        # 1. Parse teacher JSON
        try:
            parsed = json.loads(item["teacher_raw"])
        except Exception:
            stats["bad_json"] += 1
            continue

        # 2. Check exact keys
        if not isinstance(parsed, dict) or set(parsed.keys()) != REQUIRED_SLOT_KEYS:
            stats["bad_keys"] += 1
            continue

        # 3. Check intent domain
        if parsed["intent"] not in ALLOWED_INTENTS:
            stats["bad_intent"] += 1
            continue

        # 4. Check slot ground truth in query text
        slot_valid = True
        for slot in ("date", "time", "place"):
            val = parsed[slot]
            if val is not None:
                if not isinstance(val, str) or val not in raw_text:
                    slot_valid = False
                    break
        if not slot_valid:
            stats["bad_slot"] += 1
            continue

        # 5. Check duplicate queries
        if raw_text in seen_prompts:
            stats["duplicates"] += 1
            continue

        seen_prompts.add(raw_text)
        cleaned_items.append(item)
        stats["kept"] += 1

    total_accounted = sum(stats[k] for k in ("bad_json", "bad_keys", "bad_intent", "bad_slot", "duplicates", "kept"))
    assert total_accounted == stats["input"], f"Audit failure: {total_accounted} != {stats['input']}"
    return cleaned_items, stats


def write_outputs(output_dir: str, cleaned_records: List[Dict[str, Any]], stats: Dict[str, int]) -> str:
    os.makedirs(output_dir, exist_ok=True)
    target_path = os.path.join(output_dir, "train.jsonl")

    with open(target_path, "w", encoding="utf-8") as out:
        for r in cleaned_records:
            entry = {"id": r["id"], "text": r["text"], "teacher_raw": r["teacher_raw"]}
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")

    with open(target_path, "rb") as f:
        file_sha256 = hashlib.sha256(f.read()).hexdigest()

    checksum_file = os.path.join(output_dir, "train.sha256")
    with open(checksum_file, "w", encoding="utf-8") as cs:
        cs.write(f"{file_sha256}  train.jsonl\n")

    stats_file = os.path.join(output_dir, "counts.json")
    with open(stats_file, "w", encoding="utf-8") as cf:
        json.dump(stats, cf, indent=2)

    logger.info("Summary Statistics:\n" + json.dumps(stats, indent=2))
    logger.info(f"Dataset SHA-256: {file_sha256}")
    return file_sha256


def upload_to_s3(output_dir: str, shard_dir: str):
    import boto3
    endpoint = os.environ.get("S3_ENDPOINT", "http://localhost:8333")
    s3_client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.environ["S3_ACCESS_KEY"],
        aws_secret_access_key=os.environ["S3_SECRET_KEY"],
        region_name="us-east-1"
    )
    for fname in ("train.jsonl", "train.sha256"):
        src = os.path.join(output_dir, fname)
        s3_client.upload_file(src, "datasets", f"v1/{fname}")
    for shard_path in sorted(glob.glob(f"{shard_dir}/shard-*.jsonl")):
        bname = os.path.basename(shard_path)
        s3_client.upload_file(shard_path, "datasets", f"teacher/{bname}")
    logger.info("Uploaded verified datasets and shards to S3.")


def main():
    args = parse_arguments()
    records = load_shard_records(args.shards)
    logger.info(f"Loaded {len(records)} raw entries from {args.shards}")
    cleaned, stats = validate_and_filter(records)
    write_outputs(args.out_dir, cleaned, stats)

    if args.upload:
        upload_to_s3(args.out_dir, args.shards)


if __name__ == "__main__":
    main()
