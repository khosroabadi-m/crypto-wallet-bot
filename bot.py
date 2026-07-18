import requests
import os
from datetime import datetime

# --- گرفتن اطلاعات از حافظه مخفی گیت‌هاب ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")

if not TELEGRAM_TOKEN or not CHAT_ID or not ETHERSCAN_API_KEY:
    raise ValueError("خطا: توکن، آیدی کانال یا کلید اتریوم در Secrets تنظیم نشده است.")

TRENDING_URL = "https://api.dexscreener.com/latest/dex/tokens/trending"

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ پیام با موفقیت به کانال ارسال شد.")
    except Exception as e:
        print(f"❌ خطا در ارسال پیام: {e}")

def get_gainer_tokens():
    try:
        response = requests.get(TRENDING_URL, timeout=10)
        data = response.json()
        gainers = []
        
        for token in data.get("tokens", []):
            price_change = token.get("priceChange", {})
            change_24h = price_change.get("h24", 0)
            
            if change_24h >= 20:
                gainers.append({
                    "name": token.get("baseToken", {}).get("name", "نامشخص"),
                    "symbol": token.get("baseToken", {}).get("symbol", "نمادنامشخص"),
                    "chain": token.get("chainId", "ناشناخته"),
                    "price": token.get("priceUsd", "۰"),
                    "change_24h": change_24h,
                    "volume": token.get("volume", {}).get("h24", 0),
                    "liquidity": token.get("liquidity", {}).get("usd", 0),
                    "dex_url": token.get("url", "#"),
                    "contract": token.get("baseToken", {}).get("address", "")
                })
        return gainers
    except Exception as e:
        print(f"❌ خطا در دریافت لیست ارزها: {e}")
        return []

def get_first_buyers(contract_address):
    if not contract_address or len(contract_address) < 10:
        return []
    
    url = f"https://api.etherscan.io/api?module=account&action=tokentx&contractaddress={contract_address}&sort=asc&apikey={ETHERSCAN_API_KEY}"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("status") != "1":
            return []
        
        transactions = data.get("result", [])
        buyers = {}
        for tx in transactions:
            from_addr = tx.get("from")
            value = float(tx.get("value", 0)) / (10 ** 18)
            if value > 0 and from_addr not in buyers:
                buyers[from_addr] = {
                    "amount": value,
                    "timestamp": tx.get("timeStamp")
                }
                if len(buyers) >= 5:
                    break
        
        result = [{"address": addr, **data} for addr, data in buyers.items()]
        return sorted(result, key=lambda x: x["timestamp"])
    
    except Exception as e:
        print(f"❌ خطا در دریافت خریداران: {e}")
        return []

def main():
    print(f"⏳ اسکن جدید در {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} شروع شد...")
    
    gainers = get_gainer_tokens()
    print(f"🔍 تعداد ارزهای بالای ۲۰٪: {len(gainers)}")
    
    if not gainers:
        print("ℹ️ هیچ ارزی پیدا نشد.")
        return
    
    token = gainers[0]
    
    message = f"""
🚀 **ارز داغ جدید شناسایی شد!**
▫️ نام: {token['name']} (${token['symbol']})
▫️ شبکه: {token['chain']}
▫️ قیمت: ${token['price']}
▫️ رشد ۲۴ ساعته: **{token['change_24h']}%** ✅
▫️ حجم معاملات: ${token['volume']:,.0f}
▫️ نقدینگی: ${token['liquidity']:,.0f}
🔗 [مشاهده در DexScreener]({token['dex_url']})
    """
    
    contract = token.get("contract")
    if contract and len(contract) > 10:
        buyers = get_first_buyers(contract)
        if buyers:
            message += "\n🐋 **کیف‌پول‌های خریدار اولیه:**\n"
            for i, buyer in enumerate(buyers[:5], 1):
                addr = buyer["address"]
                short_addr = addr[:6] + "..." + addr[-4:]
                message += f"{i}. `{short_addr}` (مقدار: {buyer['amount']:.2f} توکن)\n"
        else:
            message += "\n⚠️ خریدار اولیه‌ای پیدا نشد."
    else:
        message += "\n⚠️ آدرس قرارداد در دسترس نیست."
    
    send_telegram_message(message)
    print("✅ گزارش نهایی به کانال ارسال شد.")

if __name__ == "__main__":
    main()
