import os
import json
import logging
import threading
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

import boto3
import torch
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from transformers import AutoTokenizer, AutoModelForCausalLM

# Set thread parallelism for PyTorch inference
torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "1")))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("command-parser")

MODEL_URI = os.environ.get("MODEL_URI", "s3://models/models/v1/")
MODEL_VERSION = os.environ.get("MODEL_VERSION", "v1")
S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "")
MAX_NEW_TOKENS = int(os.environ.get("MAX_NEW_TOKENS", "64"))
FAULT_INJECT = os.environ.get("FAULT_INJECT", "0")
POD_HOSTNAME = os.environ.get("HOSTNAME", "local")
LOCAL_CACHE_DIR = "/tmp/model"

SUPPORTED_INTENTS = {
    "alarm_set", "alarm_query", "calendar_set", "calendar_query",
    "calendar_remove", "weather_query", "datetime_query", "recommendation_events"
}
EXPECTED_SLOTS = {"intent", "date", "time", "place"}


class CommandRequest(BaseModel):
    text: str = Field(default="", description="Command query string to parse")


class ModelManager:
    """Manages downloading, caching, and serving inference for the command parser model."""

    def __init__(self):
        self.tokenizer = None
        self.model = None
        self._is_ready = False

    def is_ready(self) -> bool:
        return self._is_ready and self.model is not None

    def fetch_and_load(self):
        try:
            if MODEL_URI.startswith("file://"):
                local_path = MODEL_URI.removeprefix("file://")
                logger.info(f"Loading local weights from {local_path}")
                self.tokenizer = AutoTokenizer.from_pretrained(local_path)
                self.tokenizer.pad_token = self.tokenizer.eos_token
                self.model = AutoModelForCausalLM.from_pretrained(local_path).float().eval()
                self._is_ready = True
                return

            bucket, _, prefix = MODEL_URI.removeprefix("s3://").partition("/")
            s3_client = boto3.client(
                "s3",
                endpoint_url=S3_ENDPOINT or None,
                aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
                aws_secret_access_key=os.environ.get("S3_SECRET_KEY")
            )
            os.makedirs(LOCAL_CACHE_DIR, exist_ok=True)
            logger.info(f"Fetching weights: bucket={bucket}, prefix={prefix}, endpoint={S3_ENDPOINT}")

            contents = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix).get("Contents", [])
            download_count = 0
            for obj in contents:
                fname = obj["Key"].split("/")[-1]
                if fname:
                    target_file = os.path.join(LOCAL_CACHE_DIR, fname)
                    s3_client.download_file(bucket, obj["Key"], target_file)
                    download_count += 1
            logger.info(f"Successfully downloaded {download_count} files to {LOCAL_CACHE_DIR}")

            self.tokenizer = AutoTokenizer.from_pretrained(LOCAL_CACHE_DIR)
            self.tokenizer.pad_token = self.tokenizer.eos_token
            self.model = AutoModelForCausalLM.from_pretrained(LOCAL_CACHE_DIR).float().eval()
            self._is_ready = True
            logger.info("Model and tokenizer successfully initialized into memory.")
        except Exception as exc:
            logger.error(f"Failed to load model: {exc}", exc_info=True)
            self._is_ready = False

    def predict(self, text: str) -> str:
        prompt = f"Command: {text}\nJSON:"
        inputs = self.tokenizer(prompt, return_tensors="pt")
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=MAX_NEW_TOKENS,
                do_sample=False,
                no_repeat_ngram_size=8,
                pad_token_id=self.tokenizer.pad_token_id
            )
        start_idx = inputs["input_ids"].shape[1]
        decoded = self.tokenizer.decode(outputs[0][start_idx:], skip_special_tokens=True)
        return decoded.strip()


model_manager = ModelManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Asynchronously load model weights on startup
    init_thread = threading.Thread(target=model_manager.fetch_and_load, daemon=True)
    init_thread.start()
    yield


app = FastAPI(title="Command Parser Service", version="1.0.0", lifespan=lifespan)


def validate_schema(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    if set(data.keys()) != EXPECTED_SLOTS:
        return False
    if data["intent"] not in SUPPORTED_INTENTS:
        return False
    return all(data[slot] is None or isinstance(data[slot], str) for slot in ("date", "time", "place"))


@app.get("/healthz")
async def health_check():
    return {"status": "ok"}


@app.get("/readyz")
async def readiness_check():
    if not model_manager.is_ready():
        return JSONResponse(status_code=503, content={"status": "loading"})
    return {"status": "ready"}


@app.post("/parse")
async def parse_command(payload: CommandRequest):
    response_headers = {
        "X-Model-Version": MODEL_VERSION,
        "X-Served-By": POD_HOSTNAME
    }

    if not model_manager.is_ready():
        return JSONResponse(
            status_code=503,
            content={"error": "model_not_ready"},
            headers=response_headers
        )

    output_text = model_manager.predict(payload.text)
    if FAULT_INJECT == "1":
        output_text = "not json"

    try:
        parsed_json = json.loads(output_text)
    except Exception:
        parsed_json = None

    if not validate_schema(parsed_json):
        return JSONResponse(
            status_code=500,
            content={"error": "invalid_model_output"},
            headers=response_headers
        )

    return JSONResponse(status_code=200, content=parsed_json, headers=response_headers)
