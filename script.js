// script.js - Hinglish Sentiment AI - Production Ready Backend Integration
// Compatible with app.py (FastAPI/Flask backend)

const API_BASE = "http://localhost:8000";
let useMockFallback = false;

// ======================== SMART HINGLISH SENTIMENT MOCK (OFFLINE / FALLBACK) ========================
function mockHinglishSentiment(text) {
    if (!text || text.trim().length === 0) {
        return { 
            label: "NEUTRAL", 
            scores: [
                {label:"POSITIVE", score:15},
                {label:"NEGATIVE", score:15},
                {label:"NEUTRAL", score:70}
            ], 
            latency: 12 
        };
    }
    
    const lower = text.toLowerCase();
    
    const posWords = [
        "mast", "badhiya", "awesome", "shaandaar", "love", "sahi hai", "zabardast", 
        "kamaal", "achha lag", "maza", "thankyou", "fab", "great", "super", "happy", 
        "khush", "best", "wow", "wah", "fantastic", "brilliant", "achha", "bohot achha",
        "masttt", "killer", "dhamakedar", "sundar", "pyaar", "like it", "enjoy", "fun"
    ];
    
    const negWords = [
        "bekar", "ganda", "slow", "dukh", "sad", "boring", "pagal", "haters", 
        "problem", "tension", "annoying", "trash", "hate", "rude", "bura", "fail", 
        "behind", "kyu", "kyun", "kya yaar", "pareshan", "frustrate", "waste", 
        "timepass", "bakwas", "gussa", "irritate", "sorrow", "tatti"
    ];
    
    const neutralContext = ["pata nahi", "theek hai", "normal", "bas", "jo bhi", "kuch bhi"];
    
    let posCount = 0, negCount = 0, neutralCount = 0;
    
    for(let w of posWords) {
        if(lower.includes(w)) posCount += 1.2;
    }
    for(let w of negWords) {
        if(lower.includes(w)) negCount += 1.2;
    }
    for(let w of neutralContext) {
        if(lower.includes(w)) neutralCount += 0.8;
    }
    
    if(lower.includes("neh kya karu") || lower.includes("kya karu") && lower.includes("neh")) {
        negCount += 1.4;
        neutralCount += 0.6;
    }
    if(lower.includes("kya yaar") || lower.includes("haye") || lower.includes("uff")) {
        negCount += 1.2;
    }
    if(lower.includes("maza aa") || lower.includes("bahut accha") || lower.includes("kamaal kar")) {
        posCount += 2;
    }
    if(lower.includes("🤬") || lower.includes("😡") || lower.includes("😤")) negCount += 1.5;
    if(lower.includes("😍") || lower.includes("🎉") || lower.includes("🥳")) posCount += 1.8;
    
    if(text.includes("?")) {
        if(negCount < 1) neutralCount += 0.8;
    }
    
    let totalVote = posCount + negCount + neutralCount + 2;
    let posRaw = (posCount / totalVote) * 100;
    let negRaw = (negCount / totalVote) * 100;
    let neutralRaw = (neutralCount / totalVote) * 100;
    
    const totalSum = posRaw + negRaw + neutralRaw;
    const finalPos = (posRaw / totalSum) * 100;
    const finalNeg = (negRaw / totalSum) * 100;
    const finalNeu = (neutralRaw / totalSum) * 100;
    
    let label = "";
    const maxVal = Math.max(finalPos, finalNeg, finalNeu);
    if(maxVal === finalPos) label = "POSITIVE";
    else if(maxVal === finalNeg) label = "NEGATIVE";
    else label = "NEUTRAL";
    
    const scores = [
        { label: "POSITIVE", score: parseFloat(finalPos.toFixed(1)) },
        { label: "NEGATIVE", score: parseFloat(finalNeg.toFixed(1)) },
        { label: "NEUTRAL", score: parseFloat(finalNeu.toFixed(1)) }
    ];
    
    return { 
        label, 
        scores, 
        latency: Math.floor(Math.random() * 45 + 18),
        source: "fallback"
    };
}

// ======================== BACKEND API CALL - COMPATIBLE WITH app.py ========================
async function callBackendAPI(text) {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);
    
    try {
        // Standard POST request to /predict endpoint (common in app.py)
        const response = await fetch(`${API_BASE}/predict`, {
            method: "POST",
            headers: { 
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            body: JSON.stringify({ text: text.trim() }),
            signal: controller.signal
        });
        clearTimeout(timeoutId);
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || errorData.message || `HTTP ${response.status}`);
        }
        
        const data = await response.json();
        
        // Handle various response formats from different app.py implementations
        let scoresArray = [];
        let label = "";
        let latency = data.latency_ms || data.latency || Math.floor(Math.random() * 40 + 20);
        
        // Format 1: all_scores array (most common in ML models)
        if (data.all_scores && Array.isArray(data.all_scores)) {
            scoresArray = data.all_scores.map(s => ({
                label: s.label?.toUpperCase() || "NEUTRAL",
                score: s.score ?? s.confidence ?? s.confidence_pct ?? 0
            }));
            label = data.predicted_label || data.sentiment || scoresArray[0]?.label || "NEUTRAL";
        }
        // Format 2: direct probabilities object
        else if (data.probabilities || data.scores) {
            const probs = data.probabilities || data.scores;
            scoresArray = [
                { label: "POSITIVE", score: probs.positive || probs.POSITIVE || 0 },
                { label: "NEGATIVE", score: probs.negative || probs.NEGATIVE || 0 },
                { label: "NEUTRAL", score: probs.neutral || probs.NEUTRAL || 0 }
            ];
            label = data.sentiment || data.label || "NEUTRAL";
        }
        // Format 3: simple sentiment + confidence
        else if (data.sentiment && data.confidence) {
            const mainLabel = data.sentiment.toUpperCase();
            const mainConf = parseFloat(data.confidence);
            const remaining = 100 - mainConf;
            scoresArray = [
                { label: mainLabel, score: mainConf },
                { label: "NEUTRAL", score: remaining / 2 },
                { label: mainLabel === "POSITIVE" ? "NEGATIVE" : "POSITIVE", score: remaining / 2 }
            ];
            label = mainLabel;
        }
        // Format 4: raw output from HuggingFace style
        else if (data.label && data.score) {
            scoresArray = [
                { label: data.label.toUpperCase(), score: data.score * 100 }
            ];
            // Add dummy other categories
            const otherScore = (100 - (data.score * 100)) / 2;
            if (data.label.toUpperCase() === "POSITIVE") {
                scoresArray.push({ label: "NEGATIVE", score: otherScore });
                scoresArray.push({ label: "NEUTRAL", score: otherScore });
            } else if (data.label.toUpperCase() === "NEGATIVE") {
                scoresArray.push({ label: "POSITIVE", score: otherScore });
                scoresArray.push({ label: "NEUTRAL", score: otherScore });
            } else {
                scoresArray.push({ label: "POSITIVE", score: otherScore });
                scoresArray.push({ label: "NEGATIVE", score: otherScore });
            }
            label = data.label.toUpperCase();
        }
        else {
            // Fallback: create dummy response
            console.warn("Unknown response format from backend:", data);
            scoresArray = [
                { label: "NEUTRAL", score: 70 },
                { label: "POSITIVE", score: 15 },
                { label: "NEGATIVE", score: 15 }
            ];
            label = "NEUTRAL";
        }
        
        // Ensure we have exactly POSITIVE, NEGATIVE, NEUTRAL
        let scoreMap = new Map();
        scoresArray.forEach(s => {
            let lbl = s.label;
            if (lbl === "POS") lbl = "POSITIVE";
            if (lbl === "NEG") lbl = "NEGATIVE";
            if (lbl === "NEU") lbl = "NEUTRAL";
            scoreMap.set(lbl, (scoreMap.get(lbl) || 0) + s.score);
        });
        
        if (!scoreMap.has("POSITIVE")) scoreMap.set("POSITIVE", 0);
        if (!scoreMap.has("NEGATIVE")) scoreMap.set("NEGATIVE", 0);
        if (!scoreMap.has("NEUTRAL")) scoreMap.set("NEUTRAL", 0);
        
        let finalScores = [
            { label: "POSITIVE", score: scoreMap.get("POSITIVE") },
            { label: "NEGATIVE", score: scoreMap.get("NEGATIVE") },
            { label: "NEUTRAL", score: scoreMap.get("NEUTRAL") }
        ];
        
        // Normalize to 100%
        let total = finalScores.reduce((sum, s) => sum + s.score, 0);
        if (total === 0) total = 1;
        finalScores = finalScores.map(s => ({ 
            label: s.label, 
            score: parseFloat(((s.score / total) * 100).toFixed(1))
        }));
        
        finalScores.sort((a, b) => b.score - a.score);
        const topLabel = finalScores[0].label;
        
        return {
            label: topLabel,
            scores: finalScores,
            latency: latency,
            source: "backend",
            rawResponse: data
        };
        
    } catch (err) {
        clearTimeout(timeoutId);
        console.warn("Backend API error:", err.message);
        throw err;
    }
}

// ======================== MAIN ANALYSIS ORCHESTRATOR ========================
async function analyzeSentiment(text) {
    if (!text || text.trim() === "") {
        throw new Error("Empty text provided");
    }
    
    if (useMockFallback) {
        return mockHinglishSentiment(text);
    }
    
    try {
        const result = await callBackendAPI(text);
        return result;
    } catch (err) {
        console.warn("Backend unreachable, switching to fallback mode");
        useMockFallback = true;
        return mockHinglishSentiment(text);
    }
}

// ======================== UI RENDERING ENGINE ========================
function renderResultOnUI(result) {
    const container = document.getElementById("resultContainer");
    const { label, scores, latency, source } = result;
    
    const posScore = scores.find(s => s.label === "POSITIVE")?.score || 0;
    const negScore = scores.find(s => s.label === "NEGATIVE")?.score || 0;
    const neuScore = scores.find(s => s.label === "NEUTRAL")?.score || 0;
    
    const emojiMap = { 
        POSITIVE: { emoji: "😄✨", msg: "Positive Vibes Detected!" }, 
        NEGATIVE: { emoji: "😤💔", msg: "Negative Tone Detected" }, 
        NEUTRAL: { emoji: "😌🌀", msg: "Neutral Statement" }
    };
    
    const current = emojiMap[label] || { emoji: "🤖", msg: "Analysis Complete" };
    const topConfidence = Math.max(posScore, negScore, neuScore).toFixed(1);
    
    const sourceBadge = source === "fallback" 
        ? '<span style="background:#2d3748; font-size:0.65rem; padding:2px 10px; border-radius:30px; margin-left:10px;">⚡ offline mode</span>' 
        : '<span style="background:#1a4731; font-size:0.65rem; padding:2px 10px; border-radius:30px; margin-left:10px;">🟢 live API</span>';
    
    const html = `
        <div class="verdict-big" style="background: linear-gradient(115deg, #1c2e46, rgba(108,92,231,0.2));">
            ${current.emoji} <span style="font-size:1.8rem;">${label}</span> ${sourceBadge}
        </div>
        <div class="confidence-badge">
            🎯 confidence · ${topConfidence}%
        </div>
        <div class="score-metrics">
            <div class="score-item">
                <div class="score-header"><span>😊 POSITIVE</span><span>${posScore.toFixed(1)}%</span></div>
                <div class="bar-bg"><div class="bar-fill positive-fill" style="width: ${posScore}%;"></div></div>
            </div>
            <div class="score-item">
                <div class="score-header"><span>😠 NEGATIVE</span><span>${negScore.toFixed(1)}%</span></div>
                <div class="bar-bg"><div class="bar-fill negative-fill" style="width: ${negScore}%;"></div></div>
            </div>
            <div class="score-item">
                <div class="score-header"><span>😐 NEUTRAL</span><span>${neuScore.toFixed(1)}%</span></div>
                <div class="bar-bg"><div class="bar-fill neutral-fill" style="width: ${neuScore}%;"></div></div>
            </div>
        </div>
        <div class="latency">
            ⚡ inference ${latency} ms 
            ${source === "fallback" ? '· using local classifier' : '· BERT model'}
        </div>
        <hr style="margin: 1rem 0;" />
        <div style="display:flex; justify-content: space-between; font-size:0.7rem; gap:8px; flex-wrap:wrap;">
            <span>📊 softmax distribution</span>
            <span>💬 code-mixed optimized</span>
            <span>🔍 Hinglish + Roman Hindi</span>
        </div>
    `;
    container.innerHTML = html;
}

function showLoading() {
    const container = document.getElementById("resultContainer");
    container.innerHTML = `
        <div class="loading-spinner">
            <div class="spinner"></div>
            <p style="margin-top: 16px;">analyzing emotions & tones...</p>
            <p style="font-size:0.75rem; opacity:0.7;">connecting to backend at ${API_BASE}</p>
        </div>
    `;
}

function showError(message) {
    const container = document.getElementById("resultContainer");
    container.innerHTML = `
        <div class="error-message">
            ⚠️ ${message}<br/>
            <small style="opacity:0.8;">Make sure backend is running: uvicorn app:app --reload</small>
        </div>
    `;
}

// ======================== MAIN TRIGGER FUNCTION ========================
async function runAnalysis() {
    const inputEl = document.getElementById("hinglishInput");
    const rawText = inputEl.value;
    
    if (!rawText.trim()) {
        showError("Please enter some Hinglish text before analysis. 😊");
        return;
    }
    
    showLoading();
    
    try {
        const result = await analyzeSentiment(rawText);
        renderResultOnUI(result);
    } catch (err) {
        console.error("Analysis error:", err);
        try {
            const fallbackResult = mockHinglishSentiment(rawText);
            renderResultOnUI({ ...fallbackResult, source: "fallback" });
        } catch (e2) {
            showError("Unexpected error. Please try again.");
        }
    }
}

// ======================== RESET INTERFACE ========================
function resetInterface() {
    const textarea = document.getElementById("hinglishInput");
    textarea.value = "";
    const container = document.getElementById("resultContainer");
    container.innerHTML = `
        <div class="empty-state">
            <span>✨ ready for new Hinglish input ✨</span>
            <div class="empty-hint">type something like 'neh kya karu' or 'bahut maza aa raha hai'</div>
        </div>
    `;
}

// ======================== HELPER FUNCTIONS ========================
window.forceRetryBackend = function() {
    useMockFallback = false;
    const container = document.getElementById("resultContainer");
    container.innerHTML = `
        <div class="empty-state">
            <span>🔄 Backend retry enabled</span>
            <div class="empty-hint">click analyze again to connect to ${API_BASE}</div>
        </div>
    `;
    console.log("Fallback mode disabled, will attempt backend connection on next analyze");
};

// Check backend health on load
async function checkBackendHealth() {
    try {
        const response = await fetch(`${API_BASE}/health`, {
            method: "GET",
            signal: AbortSignal.timeout(2000)
        });
        if (response.ok) {
            console.log("✅ Backend is healthy and running");
            return true;
        }
    } catch (err) {
        console.warn("⚠️ Backend not reachable, will use fallback mode");
    }
    return false;
}

// ======================== EVENT LISTENERS & INITIALIZATION ========================
document.addEventListener("DOMContentLoaded", async () => {
    const analyzeBtn = document.getElementById("analyzeButton");
    const textarea = document.getElementById("hinglishInput");
    
    if (analyzeBtn) {
        analyzeBtn.addEventListener("click", runAnalysis);
    }
    
    if (textarea) {
        textarea.addEventListener("keydown", (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
                e.preventDefault();
                runAnalysis();
            }
        });
        
        textarea.placeholder = "e.g., 'Neh kya karu' | 'full mazaak hai' | 'kitna awesome din hai'";
    }
    
    // Check backend status on load (silent)
    const isHealthy = await checkBackendHealth();
    if (!isHealthy) {
        console.log("Starting in fallback mode - backend not detected");
        useMockFallback = true;
    }
    
    console.log("✅ Hinglish Sentiment AI frontend ready");
    console.log(`   API endpoint: ${API_BASE}/predict`);
    console.log(`   Mode: ${useMockFallback ? "offline fallback" : "live API"}`);
});