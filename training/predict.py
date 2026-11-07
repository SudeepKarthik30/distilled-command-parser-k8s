"""Offline inference harness for batch validation evaluation.

Loads a saved model checkpoint/tokenizer, runs causal generation on test commands,
and writes structured prediction files for evaluation with tools/score.py.
"""

import argparse
import json
import logging
import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("eval-predictor")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate predictions from fine-tuned or base model.")
    parser.add_argument("--model", required=True, help="Path or HuggingFace identifier of the model checkpoint")
    parser.add_argument("--out", required=True, help="Destination filepath for predictions.jsonl")
    parser.add_argument("--data", default="data/validation.jsonl", help="Gold evaluation dataset path")
    parser.add_argument("--max_new", type=int, default=64, help="Maximum generated token count")
    parser.add_argument("--rp", type=float, default=1.0, help="Repetition penalty parameter")
    parser.add_argument("--nr", type=int, default=0, help="No-repeat n-gram size clamp")
    return parser.parse_args()


def run_batch_evaluation():
    args = parse_arguments()
    logger.info(f"Loading tokenizer and model from: {args.model}")

    tokenizer = AutoTokenizer.from_pretrained(args.model)
    tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(args.model).float().eval()

    eval_items = []
    with open(args.data, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            if stripped:
                eval_items.append(json.loads(stripped))

    logger.info(f"Processing {len(eval_items)} validation queries...")
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)

    with open(args.out, "w", encoding="utf-8") as writer:
        for idx, item in enumerate(eval_items, start=1):
            prompt = f"Command: {item['text']}\nJSON:"
            tokenized_input = tokenizer(prompt, return_tensors="pt")

            with torch.no_grad():
                generation_output = model.generate(
                    **tokenized_input,
                    max_new_tokens=args.max_new,
                    do_sample=False,
                    repetition_penalty=args.rp,
                    no_repeat_ngram_size=args.nr,
                    pad_token_id=tokenizer.pad_token_id
                )

            start_token = tokenized_input["input_ids"].shape[1]
            raw_prediction = tokenizer.decode(
                generation_output[0][start_token:],
                skip_special_tokens=True
            ).strip()

            record = {"id": item["id"], "prediction": raw_prediction}
            writer.write(json.dumps(record, ensure_ascii=False) + "\n")

    logger.info(f"Successfully generated {len(eval_items)} predictions -> {args.out}")


if __name__ == "__main__":
    run_batch_evaluation()
