"""Teacher model validation benchmark generator.

Evaluates local Phi-3.5 teacher against data/validation.jsonl using the configured
prompt template, writing results/pred_teacher.jsonl for scoring with tools/score.py.
"""

import json
import logging
import urllib.request
import os

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("teacher-eval")

PROMPT_FILE = "prompts/teacher_prompt.txt"
VALIDATION_DATA = "data/validation.jsonl"
OUTPUT_FILE = "results/pred_teacher.jsonl"
OLLAMA_ENDPOINT = os.environ.get("OLLAMA_URL", "http://localhost:11434")


def generate_teacher_predictions():
    with open(PROMPT_FILE, "r", encoding="utf-8") as pf:
        prompt_template = pf.read()

    os.makedirs(os.path.dirname(OUTPUT_FILE) or ".", exist_ok=True)
    logger.info(f"Querying teacher at {OLLAMA_ENDPOINT} for validation commands...")

    with open(VALIDATION_DATA, "r", encoding="utf-8") as vf, open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        for idx, line in enumerate(vf, 1):
            stripped = line.strip()
            if not stripped:
                continue

            record = json.loads(stripped)
            full_prompt = prompt_template.replace("{command}", record["text"])

            request_body = {
                "model": "phi3.5",
                "prompt": full_prompt,
                "stream": False,
                "options": {
                    "temperature": 0,
                    "seed": 42,
                    "num_predict": 100
                }
            }

            req = urllib.request.Request(
                f"{OLLAMA_ENDPOINT}/api/generate",
                data=json.dumps(request_body).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )

            try:
                with urllib.request.urlopen(req, timeout=300) as response:
                    res_json = json.loads(response.read().decode("utf-8"))
                    pred_text = res_json.get("response", "")
            except Exception as e:
                logger.error(f"Error querying teacher for {record['id']}: {e}")
                pred_text = ""

            out.write(json.dumps({"id": record["id"], "prediction": pred_text}, ensure_ascii=False) + "\n")
            out.flush()

            if idx % 20 == 0:
                logger.info(f"Evaluated {idx} validation items...")

    logger.info(f"Finished generating teacher validation predictions -> {OUTPUT_FILE}")


if __name__ == "__main__":
    generate_teacher_predictions()
