import re
import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import (
    get_clean_envelope,
    get_analyze_envelope,
    create_402_response,
    verify_payment,
    get_clean_price,
    get_analyze_price,
)

app = FastAPI(title="LLM Web Cleaner & Analyzer x402")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["payment-required"],
)

@app.middleware("http")
async def x402_middleware(request: Request, call_next):
    path = request.url.path.rstrip("/")
    
    if request.method == "POST":
        if path == "/clean":
            token = request.headers.get("payment-signature") or request.headers.get("authorization")
            if not token:
                return create_402_response(get_clean_envelope())
            if not await verify_payment(token, "/clean", get_clean_price()):
                return create_402_response(get_clean_envelope())

        elif path == "/analyze":
            token = request.headers.get("payment-signature") or request.headers.get("authorization")
            if not token:
                return create_402_response(get_analyze_envelope())
            if not await verify_payment(token, "/analyze", get_analyze_price()):
                return create_402_response(get_analyze_envelope())

    return await call_next(request)

class URLRequest(BaseModel):
    url: str

class CleanResponse(BaseModel):
    status: str
    title: str
    cleaned_content_markdown: str

class AnalyzeResponse(BaseModel):
    status: str
    title: str
    word_count: int
    sentiment: str
    summary: str
    key_takeaways: list[str]

def fetch_and_clean(url: str):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else "Untitled Page"
    main_content = soup.find("article") or soup.find("main") or soup.body
    text = main_content.get_text(separator="\n", strip=True) if main_content else ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return title, lines

@app.post("/clean", response_model=CleanResponse)
def clean_page(payload: URLRequest):
    title, lines = fetch_and_clean(payload.url)
    cleaned_md = f"# {title}\n\n" + "\n\n".join(lines[:100])
    return CleanResponse(
        status="success",
        title=title,
        cleaned_content_markdown=cleaned_md
    )

@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_page(payload: URLRequest):
    title, lines = fetch_and_clean(payload.url)
    full_text = " ".join(lines)
    words = re.findall(r"\w+", full_text)
    word_count = len(words)

    lower_text = full_text.lower()
    positive_words = ["growth", "increase", "success", "innovative", "bullish", "profit", "gain", "breakthrough", "promising", "positive"]
    negative_words = ["loss", "drop", "crash", "decline", "bearish", "scam", "vulnerability", "risk", "failure", "negative"]

    pos_score = sum(lower_text.count(w) for w in positive_words)
    neg_score = sum(lower_text.count(w) for w in negative_words)

    if pos_score > neg_score:
        sentiment = "positive"
    elif neg_score > pos_score:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    sentences = [s.strip() for s in re.split(r"[.!?]", full_text) if len(s.strip().split()) > 6]
    takeaways = sentences[:3] if sentences else ["No key sentences extracted."]
    summary = " ".join(takeaways[:2])

    return AnalyzeResponse(
        status="success",
        title=title,
        word_count=word_count,
        sentiment=sentiment,
        summary=summary,
        key_takeaways=takeaways
    )

@app.get("/")
def health_check():
    return {
        "status": "ok",
        "service": "x402-llm-cleaner",
        "endpoints": ["/clean", "/analyze"]
    }
