import os
import json
import base64
import requests
import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="LLM Web Cleaner x402")

CDP_FACILITATOR_URL = "https://api.cdp.coinbase.com/platform/v2/x402/facilitator"
ENDPOINT_URL = "https://x402-llm-cleaner.onrender.com/clean"
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

def get_wallet_address() -> str:
    wallet = os.environ.get("MY_WALLET_ADDRESS")
    if not wallet:
        raise RuntimeError("Missing MY_WALLET_ADDRESS environment variable")
    return wallet

def get_price_amount() -> str:
    return os.environ.get("PRICE_AMOUNT", "5000")

def get_x402_envelope() -> dict:
    return {
        "x402Version": 2,
        "error": "Payment required",
        "resource": {
            "url": ENDPOINT_URL,
            "description": "Extracts core article text from any webpage URL, removes ads and HTML boilerplate, and returns clean Markdown format.\n",
            "mimeType": "application/json"
        },
        "accepts": [
            {
                "scheme": "exact",
                "network": "eip155:8453",
                "amount": get_price_amount(),
                "asset": USDC_BASE_ADDRESS,
                "payTo": get_wallet_address(),
                "maxTimeoutSeconds": 300
            }
        ],
        "extensions": {
            "bazaar": {
                "info": {
                    "input": {
                        "type": "http",
                        "method": "POST",
                        "body": {
                            "url": "https://example.com"
                        },
                        "bodyType": "json"
                    },
                    "output": {
                        "type": "json",
                        "example": {
                            "status": "success",
                            "title": "Example Article Title",
                            "cleaned_content_markdown": "# Title\nThis is the cleaned webpage content ready for LLM processing."
                        }
                    }
                },
                "schema": {
                    "type": "object",
                    "properties": {
                        "input": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "method": {"type": "string"},
                                "body": {"type": "object"},
                                "bodyType": {"type": "string"}
                            },
                            "required": ["type", "method"]
                        },
                        "output": {
                            "type": "object",
                            "properties": {
                                "type": {"type": "string"},
                                "example": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string"},
                                        "title": {"type": "string"},
                                        "cleaned_content_markdown": {"type": "string"}
                                    },
                                    "required": ["status", "title", "cleaned_content_markdown"]
                                }
                            },
                            "required": ["type", "example"]
                        }
                    },
                    "required": ["input", "output"]
                }
            }
        }
    }

def create_402_response() -> JSONResponse:
    envelope = get_x402_envelope()
    encoded = base64.b64encode(json.dumps(envelope).encode("utf-8")).decode("utf-8")
    return JSONResponse(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        content={"error": "Payment required"},
        headers={
            "payment-required": encoded,
            "Access-Control-Expose-Headers": "payment-required"
        }
    )

async def verify_payment(payment_sig: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{CDP_FACILITator_URL}/settle" if False else f"{CDP_FACILITATOR_URL}/settle",
                json={
                    "payment": payment_sig,
                    "resource": ENDPOINT_URL,
                    "network": "eip155:8453",
                    "amount": get_price_amount(),
                    "payTo": get_wallet_address()
                }
            )
            return resp.status_code == 200
    except Exception:
        return False

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
    if request.url.path.rstrip("/") == "/clean" and request.method == "POST":
        payment_token = request.headers.get("payment-signature") or request.headers.get("authorization")

        if not payment_token:
            return create_402_response()

        is_valid = await verify_payment(payment_token)
        if not is_valid:
            return create_402_response()

    return await call_next(request)

class CleanRequest(BaseModel):
    url: str

class CleanResponse(BaseModel):
    status: str
    title: str
    cleaned_content_markdown: str

@app.post("/clean", response_model=CleanResponse)
def clean_page(payload: CleanRequest):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(payload.url, headers=headers, timeout=10)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "svg"]):
        tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else "Untitled Page"
    main_content = soup.find("article") or soup.find("main") or soup.body
    text = main_content.get_text(separator="\n", strip=True) if main_content else ""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    cleaned_md = f"# {title}\n\n" + "\n\n".join(lines[:100])

    return CleanResponse(
        status="success",
        title=title,
        cleaned_content_markdown=cleaned_md
    )

@app.get("/")
def health_check():
    return {"status": "ok", "service": "x402-llm-cleaner"}
