"""Training pipeline for distilling natural language command parsing into Pythia-70M.

Reads verified teacher outputs, prepares input tokens with masking, and trains via PyTorch AdamW.
Saves model checkpoints, tokenizer configs, version metadata, and SHA-256 manifests.
"""

import argparse
import csv
import hashlib
import json
import logging
import os
import random
from typing import List, Tuple, Dict, Any

import numpy as np
import torch
import yaml
import transformers
from transformers import AutoModelForCausalLM, AutoTokenizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("trainer")


def parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fine-tune student model on distilled dataset.")
    parser.add_argument("--config", default="training/config.yaml", help="Path to YAML training configuration")
    parser.add_argument("--subset", type=int, default=0, help="Train on small subset of examples (for testing)")
    return parser.parse_args()


def set_reproducibility(seed: int):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


class DistillationDataset:
    """Encodes training prompts and target JSON with sequence length limits and prompt masking."""

    def __init__(self, tokenizer: AutoTokenizer, max_len: int):
        self.tokenizer = tokenizer
        self.max_len = max_len

    def encode_example(self, record: Dict[str, Any]) -> Tuple[List[int], List[int]]:
        prompt_ids = self.tokenizer(f"Command: {record['text']}\nJSON:")["input_ids"]
        target_ids = self.tokenizer(" " + record["teacher_raw"])["input_ids"] + [self.tokenizer.eos_token_id]

        full_input_ids = (prompt_ids + target_ids)[:self.max_len]
        # Mask prompt tokens (-100) so loss is only calculated on the generated JSON output
        labels = ([-100] * len(prompt_ids) + target_ids)[:self.max_len]
        return full_input_ids, labels

    def collate_batch(self, batch_items: List[Tuple[List[int], List[int]]]) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        max_batch_len = max(len(ids) for ids, _ in batch_items)
        batch_size = len(batch_items)

        padded_inputs = torch.full((batch_size, max_batch_len), self.tokenizer.pad_token_id, dtype=torch.long)
        padded_labels = torch.full((batch_size, max_batch_len), -100, dtype=torch.long)
        attention_mask = torch.zeros((batch_size, max_batch_len), dtype=torch.long)

        for idx, (inp_ids, lbl_ids) in enumerate(batch_items):
            seq_len = len(inp_ids)
            padded_inputs[idx, :seq_len] = torch.tensor(inp_ids, dtype=torch.long)
            padded_labels[idx, :len(lbl_ids)] = torch.tensor(lbl_ids, dtype=torch.long)
            attention_mask[idx, :seq_len] = 1

        return padded_inputs, attention_mask, padded_labels


def main():
    args = parse_cli_args()
    with open(args.config, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    seed_val = int(cfg.get("seed", 1007))
    set_reproducibility(seed_val)

    sample_limit = args.subset or cfg.get("n_train", 1500)
    raw_lines = [line.strip() for line in open(cfg["train_file"], encoding="utf-8") if line.strip()]
    records = [json.loads(line) for line in raw_lines][:sample_limit]

    logger.info(f"Loaded {len(records)} training records (subset={args.subset})")

    base_model_id = cfg["base_model"]
    if os.path.exists("v1") and os.path.exists("v1/model.safetensors"):
        logger.info("Initializing from local base model weights in './v1'")
        tokenizer = AutoTokenizer.from_pretrained("v1")
        tokenizer.pad_token = tokenizer.eos_token
        student_model = AutoModelForCausalLM.from_pretrained("v1").float()
    else:
        tokenizer = AutoTokenizer.from_pretrained(base_model_id)
        tokenizer.pad_token = tokenizer.eos_token
        student_model = AutoModelForCausalLM.from_pretrained(base_model_id).float()

    dataset_encoder = DistillationDataset(tokenizer, max_len=cfg["max_len"])
    encoded_data = [dataset_encoder.encode_example(r) for r in records]

    optimizer = torch.optim.AdamW(student_model.parameters(), lr=float(cfg["learning_rate"]))
    generator = torch.Generator().manual_seed(seed_val)

    output_dir = "models/subset-test" if args.subset else cfg["output_dir"]
    loss_csv_file = "training/loss_subset.csv" if args.subset else cfg["loss_csv"]
    loss_history = []

    batch_sz = int(cfg["batch_size"])
    num_epochs = int(cfg["epochs"])

    logger.info(f"Starting fine-tuning: {num_epochs} epochs, batch_size={batch_sz}, lr={cfg['learning_rate']}")
    student_model.train()

    for epoch in range(1, num_epochs + 1):
        permuted_indices = torch.randperm(len(encoded_data), generator=generator).tolist()
        epoch_loss_total = 0.0
        batch_count = 0

        for start_idx in range(0, len(permuted_indices), batch_sz):
            chunk = [encoded_data[i] for i in permuted_indices[start_idx:start_idx + batch_sz]]
            b_ids, b_mask, b_labels = dataset_encoder.collate_batch(chunk)

            outputs = student_model(input_ids=b_ids, attention_mask=b_mask, labels=b_labels)
            loss = outputs.loss

            loss.backward()
            optimizer.step()
            optimizer.zero_grad()

            epoch_loss_total += loss.item()
            batch_count += 1

        avg_epoch_loss = epoch_loss_total / max(1, batch_count)
        loss_history.append((epoch, round(avg_epoch_loss, 6)))
        logger.info(f"Epoch {epoch}/{num_epochs} - Training Loss: {avg_epoch_loss:.4f}")

    os.makedirs(os.path.dirname(loss_csv_file) or ".", exist_ok=True)
    with open(loss_csv_file, "w", newline="", encoding="utf-8") as f:
        csv_writer = csv.writer(f)
        csv_writer.writerow(["epoch", "train_loss"])
        csv_writer.writerows(loss_history)

    os.makedirs(output_dir, exist_ok=True)
    student_model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)

    metadata = {
        "version": cfg.get("version", "v1"),
        "base_model": base_model_id,
        "seed": seed_val,
        "n_train": len(encoded_data),
        "epochs": num_epochs,
        "learning_rate": cfg["learning_rate"],
        "torch": torch.__version__,
        "transformers": transformers.__version__
    }
    with open(os.path.join(output_dir, "version.json"), "w", encoding="utf-8") as vf:
        json.dump(metadata, vf, indent=2)

    manifest_path = os.path.join(output_dir, "model.sha256")
    with open(manifest_path, "w", encoding="utf-8") as mf:
        for fname in sorted(os.listdir(output_dir)):
            if fname != "model.sha256":
                item_path = os.path.join(output_dir, fname)
                if os.path.isfile(item_path):
                    with open(item_path, "rb") as bf:
                        digest = hashlib.sha256(bf.read()).hexdigest()
                    mf.write(f"{digest}  {fname}\n")

    logger.info(f"Model and artifacts successfully preserved in {output_dir}")


if __name__ == "__main__":
    main()
