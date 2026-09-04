import json
import time
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, field

BASE = "http://localhost:8000"

# ── ANSI colors ───────────────────────────────────────────────────────────────
USE_COLOR = sys.platform != "win32" or "ANSICON" in __import__("os").environ
GREEN  = "\033[92m" if USE_COLOR else ""
RED    = "\033[91m" if USE_COLOR else ""
YELLOW = "\033[93m" if USE_COLOR else ""
CYAN   = "\033[96m" if USE_COLOR else ""
BOLD   = "\033[1m"  if USE_COLOR else ""
RESET  = "\033[0m"  if USE_COLOR else ""

PASS_TAG = f"{GREEN}PASS{RESET}"
FAIL_TAG = f"{RED}FAIL{RESET}"
SKIP_TAG = f"{YELLOW}SKIP{RESET}"


# ── Result tracker ────────────────────────────────────────────────────────────
@dataclass
class Results:
    passed:  int  = 0
    failed:  int  = 0
    skipped: int  = 0
    errors:  list = field(default_factory=list)

    def ok(self, name: str):
        self.passed += 1
        print(f"  [{PASS_TAG}] {name}")

    def fail(self, name: str, reason: str):
        self.failed += 1
        self.errors.append((name, reason))
        print(f"  [{FAIL_TAG}] {name}")
        print(f"         {RED}{reason}{RESET}")

    def skip(self, name: str, reason: str = ""):
        self.skipped += 1
        print(f"  [{SKIP_TAG}] {name}" + (f"  — {reason}" if reason else ""))

    def summary(self) -> bool:
        total = self.passed + self.failed + self.skipped
        color = GREEN if self.failed == 0 else RED
        print(f"\n{BOLD}{'─'*56}{RESET}")
        print(f"{BOLD}Results:{RESET}  "
              f"{color}{self.passed} passed{RESET}  |  "
              f"{RED}{self.failed} failed{RESET}  |  "
              f"{YELLOW}{self.skipped} skipped{RESET}  |  {total} total")
        if self.errors:
            print(f"\n{BOLD}Failures:{RESET}")
            for name, reason in self.errors:
                print(f"  {RED}✗{RESET} {name}")
                print(f"    {reason}")
        print(f"{'─'*56}")
        return self.failed == 0


R = Results()


def check(name: str, condition: bool, reason: str = "assertion failed"):
    if condition:
        R.ok(name)
    else:
        R.fail(name, reason)


def section(title: str):
    print(f"\n{BOLD}{CYAN}── {title} {'─' * (50 - len(title))}{RESET}")


# ── HTTP helpers ──────────────────────────────────────────────────────────────
def get(path: str, timeout: int = 10) -> tuple[dict, int]:
    req = urllib.request.Request(BASE + path, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read()), resp.status


def post(path: str, body: dict, timeout: int = 30) -> tuple[dict, int]:
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read()), resp.status


def post_raw(path: str, body: dict, timeout: int = 10) -> tuple[dict, int]:
    """POST that returns (body, status) even on HTTP 4xx/5xx."""
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read()), resp.status
    except urllib.error.HTTPError as e:
        return json.loads(e.read()), e.code


# ── Test data ─────────────────────────────────────────────────────────────────
POSITIVE = [
    "yaar aaj ka din ekdum mast tha, sab kuch perfect gaya!",
    "kya baat hai yaar, zabardast performance!",
    "omg itna cute hai yeh, I'm literally obsessed",
    "bahut achha laga sach mein, dil khush ho gaya",
]

NEGATIVE = [
    "isko dekh ke bahut gussa aata hai, seriously kuch samajh nahi aata",
    "bhai ye movie toh bilkul bakwaas thi, time waste kar diya",
    "ye kaam bilkul bekar hai, mujhe pasand nahi aaya",
    "kitna bura hua, sab kuch kharaab ho gaya",
]

NEUTRAL = [
    "theek hai, chal jaata hai, kuch khaas nahi tha",
    "kal meeting hai office mein",
    "aaj mausam theek hai",
]

VALID_LABELS = {"Positive", "Negative", "Neutral"}


# ═════════════════════════════════════════════════════════════════════════════
# 1. Health & connectivity
# ═════════════════════════════════════════════════════════════════════════════
def test_health():
    section("Health & connectivity")
    try:
        data, status = get("/health")
    except urllib.error.URLError as e:
        R.fail("server reachable", str(e))
        print(f"\n  {RED}Cannot connect to {BASE}{RESET}")
        print(f"  Make sure 'python app.py' is running first.\n")
        sys.exit(1)

    check("GET /health → 200",        status == 200,                f"got {status}")
    check("field: status == 'ok'",    data.get("status") == "ok",   f"got '{data.get('status')}'")
    check("field: model_loaded True", data.get("model_loaded") is True,
          "model not loaded — wait for startup to finish")
    check("field: model_name set",    bool(data.get("model_name")), "missing or empty")
    check("field: device present",    "device" in data,             str(list(data.keys())))


# ═════════════════════════════════════════════════════════════════════════════
# 2. Root endpoint
# ═════════════════════════════════════════════════════════════════════════════
def test_root():
    section("Root endpoint")
    data, status = get("/")
    check("GET / → 200",           status == 200,       f"got {status}")
    check("field: service",        "service" in data,   str(data))
    check("field: endpoints list", "endpoints" in data, str(data))


# ═════════════════════════════════════════════════════════════════════════════
# 3. /predict — response schema
# ═════════════════════════════════════════════════════════════════════════════
def test_predict_schema():
    section("/predict — response schema")
    text = "yaar aaj ka din ekdum mast tha!"
    data, status = post("/predict", {"text": text})

    check("status 200",              status == 200,        f"got {status}")
    check("field: text",             "text" in data,       str(list(data.keys())))
    check("field: prediction",       "prediction" in data, str(list(data.keys())))
    check("field: all_scores",       "all_scores" in data, str(list(data.keys())))
    check("field: latency_ms",       "latency_ms" in data, str(list(data.keys())))
    check("field: model",            "model" in data,      str(list(data.keys())))
    check("text echoed correctly",   data.get("text") == text,
          f"expected '{text}', got '{data.get('text')}'")

    pred = data.get("prediction", {})
    check("prediction.label present",
          "label" in pred, str(pred))
    check("prediction.label is valid",
          pred.get("label") in VALID_LABELS,
          f"got '{pred.get('label')}'")
    check("prediction.score is float 0–1",
          isinstance(pred.get("score"), float) and 0.0 <= pred["score"] <= 1.0,
          f"got {pred.get('score')}")
    check("prediction.confidence_pct is float 0–100",
          isinstance(pred.get("confidence_pct"), float) and 0.0 <= pred["confidence_pct"] <= 100.0,
          f"got {pred.get('confidence_pct')}")

    scores = data.get("all_scores", [])
    check("all_scores is a list",
          isinstance(scores, list), type(scores).__name__)
    check("all_scores has 1–3 entries",
          1 <= len(scores) <= 3, f"got {len(scores)}")
    check("all_scores sorted descending",
          all(scores[i]["score"] >= scores[i+1]["score"]
              for i in range(len(scores) - 1)),
          "scores not in descending order")

    check("latency_ms is positive",
          isinstance(data.get("latency_ms"), (int, float)) and data["latency_ms"] > 0,
          f"got {data.get('latency_ms')}")


# ═════════════════════════════════════════════════════════════════════════════
# 4. /predict — sentiment accuracy
# ═════════════════════════════════════════════════════════════════════════════
def test_predict_accuracy():
    section("/predict — sentiment accuracy")

    def label_of(text: str) -> str:
        d, _ = post("/predict", {"text": text})
        return d["prediction"]["label"]

    correct_pos = sum(1 for t in POSITIVE if label_of(t) == "Positive")
    correct_neg = sum(1 for t in NEGATIVE if label_of(t) == "Negative")
    threshold   = 0.75

    check(
        f"positive accuracy {correct_pos}/{len(POSITIVE)} ≥ {int(threshold*100)}%",
        correct_pos >= len(POSITIVE) * threshold,
        f"only {correct_pos}/{len(POSITIVE)} classified Positive"
    )
    check(
        f"negative accuracy {correct_neg}/{len(NEGATIVE)} ≥ {int(threshold*100)}%",
        correct_neg >= len(NEGATIVE) * threshold,
        f"only {correct_neg}/{len(NEGATIVE)} classified Negative"
    )

    for t in NEUTRAL:
        lbl = label_of(t)
        check(f"neutral returns a valid label  [{lbl}]",
              lbl in VALID_LABELS, f"got '{lbl}'")


# ═════════════════════════════════════════════════════════════════════════════
# 5. /predict — edge cases
# ═════════════════════════════════════════════════════════════════════════════
def test_predict_edge_cases():
    section("/predict — edge cases")

    # Empty string → 422
    _, status = post_raw("/predict", {"text": ""})
    check("empty string → 422", status == 422, f"got {status}")

    # Whitespace only → 422
    _, status = post_raw("/predict", {"text": "   "})
    check("whitespace-only → 422", status == 422, f"got {status}")

    # Missing 'text' key → 422
    _, status = post_raw("/predict", {})
    check("missing 'text' key → 422", status == 422, f"got {status}")

    # Pure English
    data, status = post("/predict", {"text": "I absolutely love this!"})
    check("pure English accepted",
          status == 200 and data["prediction"]["label"] in VALID_LABELS,
          f"status={status}")

    # Pure Hindi (Devanagari)
    data, status = post("/predict", {"text": "आज का दिन बहुत अच्छा था"})
    check("pure Hindi (Devanagari) accepted",
          status == 200 and data["prediction"]["label"] in VALID_LABELS,
          f"status={status}")

    # Single word
    data, status = post("/predict", {"text": "mast"})
    check("single word accepted",
          status == 200 and data["prediction"]["label"] in VALID_LABELS,
          f"status={status}")

    # Numbers and symbols
    data, status = post("/predict", {"text": "100% mast tha yaar!!!"})
    check("numbers + symbols accepted",
          status == 200 and data["prediction"]["label"] in VALID_LABELS,
          f"status={status}")

    # Long text (near 512-token truncation limit)
    long_text = "yaar aaj ka din mast tha aur sab khush the. " * 60
    data, status = post("/predict", {"text": long_text})
    check("very long text accepted (truncated to 512 tokens)",
          status == 200 and data["prediction"]["label"] in VALID_LABELS,
          f"status={status}")

    # top_k=1
    data, status = post("/predict", {"text": "bahut achha tha!", "top_k": 1})
    check("top_k=1 → exactly 1 score returned",
          status == 200 and len(data.get("all_scores", [])) == 1,
          f"got {len(data.get('all_scores', []))} scores")

    # top_k=2
    data, status = post("/predict", {"text": "bahut achha tha!", "top_k": 2})
    check("top_k=2 → exactly 2 scores returned",
          status == 200 and len(data.get("all_scores", [])) == 2,
          f"got {len(data.get('all_scores', []))} scores")


# ═════════════════════════════════════════════════════════════════════════════
# 6. /batch endpoint
# ═════════════════════════════════════════════════════════════════════════════
def test_batch():
    section("/batch endpoint")
    texts = POSITIVE[:2] + NEGATIVE[:2] + NEUTRAL[:1]
    data, status = post("/batch", {"texts": texts})

    check("status 200",
          status == 200, f"got {status}")
    check("field: results",
          "results" in data, str(list(data.keys())))
    check("field: total_latency_ms",
          "total_latency_ms" in data, str(list(data.keys())))
    check(f"result count matches input ({len(texts)})",
          len(data.get("results", [])) == len(texts),
          f"sent {len(texts)}, got {len(data.get('results', []))}")

    for i, r in enumerate(data.get("results", [])):
        lbl = r.get("prediction", {}).get("label")
        check(f"  result[{i}] label is valid  [{lbl}]",
              lbl in VALID_LABELS, f"got '{lbl}'")
        check(f"  result[{i}] has latency_ms",
              "latency_ms" in r, str(list(r.keys())))

    # Empty texts list → 422
    _, status = post_raw("/batch", {"texts": []})
    check("empty texts list → 422", status == 422, f"got {status}")

    # Over limit (65 texts) → 422
    _, status = post_raw("/batch", {"texts": ["test"] * 65})
    check("65 texts → 422 (max is 64)", status == 422, f"got {status}")

    # Exactly 64 texts → 200
    data, status = post("/batch", {"texts": ["yaar mast hai"] * 64})
    check("exactly 64 texts → 200",
          status == 200 and len(data.get("results", [])) == 64,
          f"status={status}, results={len(data.get('results', []))}")


# ═════════════════════════════════════════════════════════════════════════════
# 7. Latency benchmark
# ═════════════════════════════════════════════════════════════════════════════
def test_latency():
    section("Latency benchmark")
    text  = "yaar aaj ka din ekdum mast tha!"
    times = []

    for i in range(5):
        t0 = time.perf_counter()
        post("/predict", {"text": text})
        ms = (time.perf_counter() - t0) * 1000
        times.append(ms)

    avg = sum(times) / len(times)
    mn  = min(times)
    mx  = max(times)
    p95 = sorted(times)[int(len(times) * 0.95)]

    check(f"avg latency < 5000 ms  (got {avg:.0f} ms)",
          avg < 5000,
          f"{avg:.0f} ms — consider GPU for faster inference")

    print(f"         min={mn:.0f} ms  avg={avg:.0f} ms  "
          f"max={mx:.0f} ms  p95={p95:.0f} ms")


# ═════════════════════════════════════════════════════════════════════════════
# 8. CORS headers
# ═════════════════════════════════════════════════════════════════════════════
def test_cors():
    section("CORS headers")
    try:
        req = urllib.request.Request(
            BASE + "/health",
            headers={"Origin": "http://localhost:5500"},
            method="GET"
        )
        with urllib.request.urlopen(req) as resp:
            hdrs = {k.lower(): v for k, v in resp.headers.items()}
            check("Access-Control-Allow-Origin present",
                  "access-control-allow-origin" in hdrs,
                  "CORS header missing — browser fetch() from HTML will be blocked")
    except Exception as e:
        R.skip("CORS check", str(e))


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print(f"\n{BOLD}Hinglish Sentiment API — Test Suite{RESET}")
    print(f"Target: {CYAN}{BASE}{RESET}")

    test_health()             # exits if server unreachable
    test_root()
    test_predict_schema()
    test_predict_accuracy()
    test_predict_edge_cases()
    test_batch()
    test_latency()
    test_cors()

    success = R.summary()
    sys.exit(0 if success else 1)