import os
import json
import base64
import httpx
from fastapi.responses import JSONResponse

CDP_FACILITATOR_URL = "https://api.cdp.coinbase.com/platform/v2/x402/facilitator"
BASE_URL = "https://x402-llm-cleaner.onrender.com"
USDC_BASE_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

def get_wallet_address() -> str:
    wallet = os.environ.get("MY_WALLET_ADDRESS")
    if not wallet:
        raise RuntimeError("Missing MY_WALLET_ADDRESS environment variable")
    return wallet

def get_clean_price() -> str:
    return os.environ.get("PRICE_AMOUNT", "5000")

def get_analyze_price() -> str:
    return os.environ.get("ANALYZE_PRICE_AMOUNT", "20000")

def get_clean_envelope() -> dict:
    return {
        "x402Version": 2,
        "error": "Payment required",
        "resource": {
            "url": f"{BASE_URL}/clean",
            "description": "Extracts core article text from any webpage URL, removes ads and HTML boilerplate, and returns clean Markdown format.\n",
            "mimeType": "application/json"
        },
        "accepts": [
            {
                "scheme": "exact",
                "network": "eip155:8453",
                "amount": get_clean_price(),
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
                        "body": {"url": "https://example.com"},
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

def get_analyze_envelope() -> dict:
    return {
        "x402Version": 2,
        "error": "Payment required",
        "resource": {
            "url": f"{BASE_URL}/analyze",
            "description": "Analyzes article content: extracts key takeaways, evaluates market and semantic sentiment, counts words, and generates executive summaries for autonomous agents.\n",
            "mimeType": "application/json"
        },
        "accepts": [
            {
                "scheme": "exact",
                "network": "eip155:8453",
                "amount": get_analyze_price(),
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
                        "body": {"url": "https://example.com"},
                        "bodyType": "json"
                    },
                    "output": {
                        "type": "json",
                        "example": {
                            "status": "success",
                            "title": "Tech Breakthrough Article",
                            "word_count": 450,
                            "sentiment": "positive",
                            "summary": "Key summary highlighting the core innovations and outcomes.",
                            "key_takeaways": [
                                "Advancement in autonomous AI workflows",
                                "Reduction in operational compute costs"
                            ]
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
                                        "word_count": {"type": "integer"},
                                        "sentiment": {"type": "string"},
                                        "summary": {"type": "string"},
                                        "key_takeaways": {
                                            "type": "array",
                                            "items": {"type": "string"}
                                        }
                                    },
                                    "required": ["status", "title", "word_count", "sentiment", "summary", "key_takeaways"]
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

def create_402_response(envelope: dict) -> JSONResponse:
    encoded = base64.b64encode(json.dumps(envelope).encode("utf-8")).decode("utf-8")
    return JSONResponse(
        status_code=402,
        content={"error": "Payment required"},
        headers={
            "payment-required": encoded,
            "Access-Control-Expose-Headers": "payment-required"
        }
    )

async def verify_payment(payment_sig: str, endpoint_path: str, required_amount: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{CDP_FACILITATOR_URL}/settle",
                json={
                    "payment": payment_sig,
                    "resource": f"{BASE_URL}{endpoint_path}",
                    "network": "eip155:8453",
                    "amount": required_amount,
                    "payTo": get_wallet_address()
                }
            )
            return resp.status_code == 200
    except Exception:
        return False
