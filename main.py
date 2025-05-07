from fastapi import FastAPI, Request
import requests, hmac, hashlib, time, base64, json, os
import uvicorn
from threading import Thread

app = FastAPI()

# 환경변수
TG_TOKEN = os.environ.get("TG_TOKEN")
TG_CHAT_ID = os.environ.get("TG_CHAT_ID")
API_KEY = os.environ.get("API_KEY")
API_SECRET = os.environ.get("API_SECRET")
API_PASSPHRASE = os.environ.get("API_PASSPHRASE")
BASE_URL = "https://api.bitget.com"

# 설정
SYMBOL = "BTCUSDT_UMCBL"
MARGIN_COIN = "USDT"
LEVERAGE = "30"
last_update_id = None

# 서명 생성
def get_signature(timestamp, method, request_path, body, secret):
    message = f"{timestamp}{method}{request_path}{body}"
    mac = hmac.new(secret.encode('utf-8'), message.encode('utf-8'), digestmod=hashlib.sha256)
    return base64.b64encode(mac.digest()).decode()

# 헤더 생성
def get_headers(timestamp, method, endpoint, body):
    sign = get_signature(timestamp, method, endpoint, body, API_SECRET)
    return {
        "ACCESS-KEY": API_KEY,
        "ACCESS-SIGN": sign,
        "ACCESS-TIMESTAMP": timestamp,
        "ACCESS-PASSPHRASE": API_PASSPHRASE,
        "Content-Type": "application/json"
    }

# 잔고 조회
def get_balance():
    timestamp = str(int(time.time() * 1000))
    endpoint = f"/api/mix/v1/account/accounts?productType=umcbl&marginCoin={MARGIN_COIN}"
    url = BASE_URL + endpoint
    headers = get_headers(timestamp, "GET", endpoint, "")
    response = requests.get(url, headers=headers)
    return float(response.json()["data"]["available"])

# 주문 실행
def place_market_order(side, size):
    endpoint = "/api/mix/v1/order/placeOrder"
    url = BASE_URL + endpoint
    timestamp = str(int(time.time() * 1000))
    body = {
        "symbol": SYMBOL,
        "marginCoin": MARGIN_COIN,
        "size": size,
        "side": side,
        "orderType": "market",
        "tradeSide": "open",
        "leverage": LEVERAGE
    }
    body_json = json.dumps(body)
    headers = get_headers(timestamp, "POST", endpoint, body_json)
    response = requests.post(url, headers=headers, data=body_json)
    print(f"Order response: {response.json()}")

# 메시지 처리
def process_message(text):
    print(f"📥 처리 중: {text}")
    text = text.lower()
    if text not in ["buy", "sell"]:
        print("❌ 잘못된 명령입니다.")
        return
    try:
        usdt_balance = get_balance()
        size = str(round(usdt_balance * 0.00001, 4))  # 보수적 진입
        place_market_order(text, size)
    except Exception as e:
        print(f"⚠️ 주문 오류: {e}")

# 텔레그램 폴링
def telegram_polling():
    global last_update_id
    print("✅ Telegram polling started...")
    while True:
        try:
            url = f"https://api.telegram.org/bot{TG_TOKEN}/getUpdates"
            if last_update_id:
                url += f"?offset={last_update_id + 1}"
            res = requests.get(url).json()
            print("📨 Raw response:", json.dumps(res, indent=2))

            for update in res.get("result", []):
                last_update_id = update["update_id"]
                message = update.get("message", {})
                chat_id = str(message.get("chat", {}).get("id"))
                text = message.get("text", "")
                print(f"👤 {chat_id} ➜ {text}")
                if not TG_CHAT_ID or TG_CHAT_ID == chat_id:
                    process_message(text)
        except Exception as e:
            print("⚠️ Polling error:", e)
        time.sleep(3)

# FastAPI 웹훅
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    signal = data.get("signal")
    if signal not in ["buy", "sell"]:
        return {"error": "Invalid signal"}
    process_message(signal)
    return {"status": "order sent"}

# FastAPI 기본 라우트
@app.get("/")
def read_root():
    return {"status": "running"}

# Render에서 실행
@app.on_event("startup")
def startup_event():
    Thread(target=telegram_polling, daemon=True).start()
