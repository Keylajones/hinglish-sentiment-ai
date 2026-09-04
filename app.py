from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import time
import logging
import torch
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_NAME = "ganeshkharad/gk-hinglish-sentiment"

LABEL_DISPLAY = {
    "LABEL_0": "Negative",
    "LABEL_1": "Neutral",
    "LABEL_2": "Positive",
    "negative": "Negative",
    "neutral":  "Neutral",
    "positive": "Positive",
}

app = FastAPI(
    title="Hinglish Sentiment API",
    description="Sentiment analysis using ganeshkharad/gk-hinglish-sentiment (BERT)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_pipeline = None


def get_pipeline():
    global _pipeline
    if _pipeline is None:
        logger.info(f"Loading model: {MODEL_NAME} ...")
        device = 0 if torch.cuda.is_available() else -1
        tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        model     = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
        _pipeline = pipeline(
            task="text-classification",
            model=model,
            tokenizer=tokenizer,
            top_k=None,
            device=device,
            truncation=True,
            max_length=512,
        )
        logger.info("Model loaded successfully.")
    return _pipeline


def run_inference(text: str, top_k: int = 3):
    raw = get_pipeline()(text)[0]
    results = []
    for item in raw:
        label = LABEL_DISPLAY.get(item["label"], item["label"].capitalize())
        score = round(float(item["score"]), 4)
        results.append({
            "label":          label,
            "score":          score,
            "confidence_pct": round(score * 100, 2),
        })
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


class TextInput(BaseModel):
    text:  str
    top_k: Optional[int] = 3


class BatchInput(BaseModel):
    texts: list[str]
    top_k: Optional[int] = 3


@app.on_event("startup")
async def startup_event():
    get_pipeline()


@app.get("/")
def root():
    return {
        "service":   "Hinglish Sentiment API",
        "model":     MODEL_NAME,
        "endpoints": ["/predict", "/batch", "/health", "/docs"],
    }


@app.get("/health")
def health():
    return {
        "status":       "ok",
        "model_loaded": _pipeline is not None,
        "model_name":   MODEL_NAME,
        "device":       "GPU" if torch.cuda.is_available() else "CPU",
    }


@app.post("/predict")
def predict(payload: TextInput):
    if not payload.text.strip():
        raise HTTPException(status_code=422, detail="Text cannot be empty.")
    t0      = time.perf_counter()
    results = run_inference(payload.text, payload.top_k)
    latency = round((time.perf_counter() - t0) * 1000, 2)
    return {
        "text":       payload.text,
        "prediction": results[0],
        "all_scores": results,
        "latency_ms": latency,
        "model":      MODEL_NAME,
    }


@app.post("/batch")
def batch_predict(payload: BatchInput):
    if not payload.texts:
        raise HTTPException(status_code=422, detail="texts list cannot be empty.")
    if len(payload.texts) > 64:
        raise HTTPException(status_code=422, detail="Maximum 64 texts per batch.")
    t0        = time.perf_counter()
    responses = []
    for text in payload.texts:
        t1      = time.perf_counter()
        results = run_inference(text, payload.top_k)
        lat     = round((time.perf_counter() - t1) * 1000, 2)
        responses.append({
            "text":       text,
            "prediction": results[0],
            "all_scores": results,
            "latency_ms": lat,
            "model":      MODEL_NAME,
        })
    return {
        "results":          responses,
        "total_latency_ms": round((time.perf_counter() - t0) * 1000, 2),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")