"""Parallel teacher labeling worker.

Dispatches partitioned command subsets to local/remote Ollama Phi-3.5 instance.
Writes verbatim raw outputs to per-shard JSON Lines files for subsequent verification.
"""

import json
import logging
import os
import sys
from typing import Dict, Any, List, Set
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [Shard %(thread)d] %(message)s")
logger = logging.getLogger("shard-worker")


def get_worker_configuration() -> Dict[str, Any]:
    if "SHARD_INDEX" not in os.environ or "SHARD_COUNT" not in os.environ:
        logger.error("Environment variables SHARD_INDEX and SHARD_COUNT are required.")
        sys.exit(1)

    return {
        "shard_index": int(os.environ["SHARD_INDEX"]),
        "shard_count": int(os.environ["SHARD_COUNT"]),
        "ollama_url": os.environ.get("OLLAMA_URL", "http://localhost:11434"),
        "command_pool": os.environ.get("POOL", "data/commands_pool.jsonl"),
        "prompt_template": os.environ.get("PROMPT", "prompts/teacher_prompt.txt"),
        "output_directory": os.environ.get("OUT_DIR", "results/teacher"),
        "sample_limit": int(os.environ.get("LIMIT", "0"))
    }


class TeacherDistillationWorker:
    def __init__(self, config: Dict[str, Any]):
        self.cfg = config
        self.session = requests.Session()
        os.makedirs(self.cfg["output_directory"], exist_ok=True)
        self.destination_file = os.path.join(
            self.cfg["output_directory"],
            f"shard-{self.cfg['shard_index']}.jsonl"
        )
        with open(self.cfg["prompt_template"], "r", encoding="utf-8") as f:
            self.prompt_scaffold = f.read().rstrip("\n")

    def get_processed_ids(self) -> Set[str]:
        completed_ids = set()
        if os.path.exists(self.destination_file):
            with open(self.destination_file, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped:
                        try:
                            completed_ids.add(json.loads(stripped)["id"])
                        except Exception:
                            pass
        return completed_ids

    def load_partitioned_commands(self) -> List[Dict[str, Any]]:
        with open(self.cfg["command_pool"], "r", encoding="utf-8") as f:
            all_lines = [line.strip() for line in f if line.strip()]

        # Modulo sharding across commands
        partition = [
            json.loads(line)
            for idx, line in enumerate(all_lines)
            if idx % self.cfg["shard_count"] == self.cfg["shard_index"]
        ]

        if self.cfg["sample_limit"] > 0:
            partition = partition[:self.cfg["sample_limit"]]

        return partition

    def request_teacher_inference(self, prompt: str) -> str:
        payload = {
            "model": "phi3.5",
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "seed": 42,
                "num_predict": 80,
                "stop": ["\n\n", "Command:"]
            }
        }
        resp = self.session.post(
            f"{self.cfg['ollama_url']}/api/generate",
            json=payload,
            timeout=600
        )
        resp.raise_for_status()
        return resp.json()["response"]

    def execute(self):
        commands = self.load_partitioned_commands()
        completed = self.get_processed_ids()
        total_items = len(commands)

        logger.info(
            f"Initialized worker {self.cfg['shard_index']}/{self.cfg['shard_count']}. "
            f"Total partition items: {total_items}, already done: {len(completed)}"
        )

        with open(self.destination_file, "a", encoding="utf-8") as writer:
            for count, item in enumerate(commands, start=1):
                item_id = item["id"]
                if item_id in completed:
                    continue

                formatted_prompt = self.prompt_scaffold.replace("{command}", item["text"])
                raw_response = self.request_teacher_inference(formatted_prompt)

                record = {
                    "id": item_id,
                    "text": item["text"],
                    "teacher_raw": raw_response
                }
                writer.write(json.dumps(record, ensure_ascii=False) + "\n")
                writer.flush()
                completed.add(item_id)

                if count % 25 == 0 or count == total_items:
                    logger.info(f"Progress: [{count}/{total_items}] completed ({item_id})")


def main():
    config = get_worker_configuration()
    worker = TeacherDistillationWorker(config)
    worker.execute()


if __name__ == "__main__":
    main()
