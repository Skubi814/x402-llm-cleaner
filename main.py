import os
import requests
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from markdownify import markdownify as md
from readability import Document

app = FastAPI(title="LLM-Friendly Text Cleaner API (x402)")

X402_PRICE_USDC = os.environ.get("X402_PRICE_USDC", "0.001")
MY_WALLET_ADDRESS = os.environ.get("MY_WALLET_ADDRESS")

@app.get("/")
def read_root():
    return {"status": "online", "message": "x402 LLM Cleaner API is running"}

@app.post("/clean")
async def clean_page(request: Request, response: Response):
    x402_tx_header = request.headers.get("X-402-Payment-Proof")
    
    if not x402_tx_header:
        custom_headers = {
            "X-402-Version": "2",
            "X-402-Amount": X402_PRICE_USDC,
            "X-402-Asset": "USDC",
            "X-402-Network": "base",
            "X-402-Destination": MY_WALLET_ADDRESS if MY_WALLET_ADDRESS else "0x0000000000000000000000000000000000000000"
        }
        return JSONResponse(
            status_code=402,
            content={
                "message": "Payment Required. Please pay via x402 protocol.",
                "x402Version": 2
            },
            headers=custom_headers
        )

    try:
        body = await request.json()
        url_to_clean = body.get("url")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body.")
    
    if not url_to_clean:
        raise HTTPException(status_code=400, detail="Missing 'url' parameter in JSON body.")

    try:
        html_response = requests.get(url_to_clean, timeout=10, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
        html_content = html_response.text

        doc = Document(html_content)
        clean_html = doc.summary()
        title = doc.title()

        markdown_text = md(clean_html, strip=['a', 'img'])

        return {
            "status": "success",
            "title": title,
            "cleaned_content_markdown": markdown_text.strip()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing the webpage: {str(e)}")
