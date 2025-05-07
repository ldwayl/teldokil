
from fastapi import FastAPI, Request
import requests, hmac, hashlib, time, base64, json, os

app = FastAPI()

API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")
API_PASSPHRASE = os.environ.get("API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"

SYMBOL = "BTCUSDT_UMCBL"
MARGIN_COIN = "USDT"
LEVERAGE = "30"

def get_signature(timestamp, method, request_path, body, secret):
    message = f"{timestamp}{method}{request_path}{body}"
    mac = hmac.new(secret.encode('utf-8'), message.encode('utf-8'), digestmod=hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

def get_headers(timestamp, method, request_path, body):
    sign = get_signature(timestamp, method, request_path, body, API_SECRET)
    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }

def get_balance():
    endpoint = "/api/mix/v1/account/accounts"
    url = BASE_URL + endpoint + f"?productType=umcbl&marginCoin={MARGIN_COIN}"
    timestamp = str(int(time.time() * 1000))
    headers = get_headers(timestamp, "GET", endpoint + f"?productType=umcbl&marginCoin={MARGIN_COIN}", "")
    response = requests.get(url, headers=headers)
    return float(response.json()["data"]["available"])

def place_market_order(side: str, size: str):
    endpoint = "/api/mix/v1/order/placeOrder"
    url = BASE_URL + endpoint
    timestamp = str(int(time.time() * 1000))

    body = {
        "symbol": SYMBOL,
        "marginCoin": MARGIN_COIN,
        "side": "open_long" if side == "buy" else "open_short",
        "orderType": "market",
        "size": size,
        "leverage": LEVERAGE
    }

    body_json = json.dumps(body)
    headers = get_headers(timestamp, "POST", endpoint, body_json)
    response = requests.post(url, headers=headers, data=body_json)
    print(response.json())

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    signal = data.get("signal")
    if signal not in ["buy", "sell"]:
        return {"error": "Invalid signal"}
    
    try:
        usdt_balance = get_balance()
        # 예시로 1000USDT당 0.01BTC 매수 비율 가정, 실전은 코인 가격 반영 필요
        size = str(round(usdt_balance * 0.00001, 4))  # 보수적 진입
        place_market_order(signal, size)
    except Exception as e:
        return {"error": str(e)}

    return {"status": "order executed", "side": signal}
