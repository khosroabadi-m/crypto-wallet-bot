import requests
import os
import json
from datetime import datetime

# --- گرفتن اطلاعات از حافظه مخفی گیت‌هاب ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")

if not TELEGRAM_TOKEN or not CHAT_ID or not ETHERSCAN_API_KEY:
    raise ValueError("خطا: توکن، آیدی کانال یا کلید اتریوم در Secrets تنظیم نشده است.")

# آدرس‌های جدید و معتبر DexScreener API
DEXSCREENER_SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"
DEXSCREENER_TRENDING_URL = "https://api.dexscreener.com/metas/trending/v1"

def send_telegram_message(message):
    """ارسال پیام به کانال تلگرام"""
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
        return True
    except Exception as e:
        print(f"❌ خطا در ارسال پیام: {e}")
        return False

def get_gainer_tokens():
    """
    دریافت ارزهای با رشد بالا با استفاده از API جستجوی DexScreener
    این تابع لاگ‌های کاملی برای نمایش در گیت‌هاب تولید می‌کند
    """
    print("🔍 [۱] شروع فرآیند جستجوی ارزها...")
    
    # لیست عبارات جستجو برای پوشش بازار بیشتر
    search_queries = ["USDC", "WETH", "SOL"]
    all_gainers = []
    seen_tokens = set()  # برای جلوگیری از گزارش تکراری
    
    for query in search_queries:
        print(f"🔎 [۲] جستجو برای عبارت: '{query}'")
        try:
            url = f"{DEXSCREENER_SEARCH_URL}?q={query}"
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            
            # بررسی ساختار داده برگشتی
            if not data or "pairs" not in data:
                print(f"⚠️ [۳] پاسخ API برای '{query}' بدون جفت‌ارز بود.")
                continue
            
            pairs = data.get("pairs", [])
            print(f"📊 [۴] تعداد جفت‌ارزهای دریافت شده برای '{query}': {len(pairs)}")
            
            # پردازش هر جفت‌ارز
            for pair in pairs:
                try:
                    # استخراج اطلاعات با مدیریت خطا
                    base_token = pair.get("baseToken", {})
                    token_symbol = base_token.get("symbol", "نامشخص")
                    
                    # کلید یکتا برای جلوگیری از تکراری‌ها
                    token_key = f"{pair.get('chainId', '')}-{base_token.get('address', '')}"
                    if token_key in seen_tokens:
                        continue
                    seen_tokens.add(token_key)
                    
                    price_change = pair.get("priceChange", {})
                    change_24h = price_change.get("h24", 0)
                    
                    # فیلتر بر اساس رشد ۲۴ ساعته
                    if change_24h >= 10:  # عدد ۱۰ برای رشد ۱۰٪
                        token_info = {
                            "name": base_token.get("name", "نامشخص"),
                            "symbol": token_symbol,
                            "chain": pair.get("chainId", "ناشناخته"),
                            "price": pair.get("priceUsd", "۰"),
                            "change_24h": change_24h,
                            "volume": pair.get("volume", {}).get("h24", 0),
                            "liquidity": pair.get("liquidity", {}).get("usd", 0),
                            "dex_url": pair.get("url", "#"),
                            "contract": base_token.get("address", ""),
                            "dex": pair.get("dexId", "نامشخص"),
                            "market_cap": pair.get("marketCap", 0)
                        }
                        all_gainers.append(token_info)
                        print(f"✅ [۵] توکن با رشد بالا پیدا شد: {token_symbol} ({change_24h}%)")
                        
                except Exception as e:
                    print(f"⚠️ خطا در پردازش یک جفت‌ارز: {e}")
                    continue
                    
        except requests.exceptions.RequestException as e:
            print(f"❌ [خطا] در جستجوی '{query}': {e}")
        except json.JSONDecodeError as e:
            print(f"❌ [خطا] پاسخ JSON نامعتبر برای '{query}': {e}")
    
    # مرتب‌سازی بر اساس بیشترین رشد
    all_gainers.sort(key=lambda x: x["change_24h"], reverse=True)
    
    print(f"📈 [نهایی] تعداد کل ارزهای با رشد +۱۰٪ پیدا شده: {len(all_gainers)}")
    if all_gainers:
        print("🏆 برترین ارز:")
        top = all_gainers[0]
        print(f"   - {top['symbol']} با رشد {top['change_24h']}% در شبکه {top['chain']}")
    
    return all_gainers

def get_first_buyers(contract_address):
    """پیدا کردن خریداران اولیه با Etherscan API"""
    if not contract_address or len(contract_address) < 10:
        print(f"⚠️ آدرس قرارداد نامعتبر: {contract_address}")
        return []
    
    print(f"🔗 در حال بررسی قرارداد: {contract_address[:10]}...{contract_address[-6:]}")
    
    url = f"https://api.etherscan.io/api?module=account&action=tokentx&contractaddress={contract_address}&sort=asc&apikey={ETHERSCAN_API_KEY}"
    
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        
        if data.get("status") != "1":
            print(f"⚠️ خطای Etherscan: {data.get('message', 'خطای ناشناخته')}")
            return []
        
        transactions = data.get("result", [])
        print(f"📊 تعداد کل تراکنش‌های قرارداد: {len(transactions)}")
        
        buyers = {}
        for tx in transactions:
            try:
                from_addr = tx.get("from")
                # تبدیل مقدار توکن با ۱۸ رقم اعشار (فرض پیش‌فرض)
                value = float(tx.get("value", 0)) / (10 ** 18)
                if value > 0 and from_addr not in buyers:
                    buyers[from_addr] = {
                        "amount": value,
                        "timestamp": tx.get("timeStamp"),
                        "hash": tx.get("hash")
                    }
                    if len(buyers) >= 5:  # ۵ خریدار اول
                        break
            except (ValueError, TypeError):
                continue
        
        result = [{"address": addr, **data} for addr, data in buyers.items()]
        result.sort(key=lambda x: x["timestamp"])
        print(f"✅ تعداد خریداران اولیه پیدا شده: {len(result)}")
        return result
        
    except Exception as e:
        print(f"❌ خطا در Etherscan: {e}")
        return []

def main():
    """تابع اصلی ربات"""
    print("="*60)
    print(f"⏳ شروع اسکن جدید در {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    # دریافت ارزهای با رشد بالا
    gainers = get_gainer_tokens()
    
    if not gainers:
        print("ℹ️ هیچ ارزی با رشد بالای ۱۰٪ پیدا نشد.")
        return
    
    # گزارش ۳ ارز برتر (قابل تنظیم)
    report_count = min(3, len(gainers))
    print(f"📨 در حال ارسال گزارش برای {report_count} ارز برتر...")
    
    for i, token in enumerate(gainers[:report_count], 1):
        print(f"\n--- گزارش {i}: {token['symbol']} ---")
        
        # ساخت پیام کامل
        message = f"""
🚀 **ارز داغ جدید شناسایی شد!**
▫️ نام: {token['name']} (${token['symbol']})
▫️ شبکه: {token['chain']}
▫️ صرافی: {token.get('dex', 'نامشخص')}
▫️ قیمت: ${token['price']}
▫️ رشد ۲۴ ساعته: **{token['change_24h']:.2f}%** ✅
▫️ حجم معاملات ۲۴h: ${token['volume']:,.0f}
▫️ نقدینگی: ${token['liquidity']:,.0f}
▫️ مارکت‌کپ: ${token.get('market_cap', 0):,.0f}
🔗 [مشاهده در DexScreener]({token['dex_url']})
        """
        
        # جستجوی خریداران اولیه
        contract = token.get("contract")
        if contract and len(contract) > 10:
            print(f"🔍 در حال جستجوی خریداران اولیه برای {token['symbol']}...")
            buyers = get_first_buyers(contract)
            
            if buyers:
                message += "\n🐋 **کیف‌پول‌های خریدار اولیه (۵ نفر اول):**\n"
                for j, buyer in enumerate(buyers[:5], 1):
                    addr = buyer["address"]
                    short_addr = addr[:6] + "..." + addr[-4:]
                    message += f"{j}. `{short_addr}` (مقدار: {buyer['amount']:.2f} توکن)\n"
            else:
                message += "\n⚠️ خریدار اولیه‌ای پیدا نشد (ممکن است توکن جدید باشد)."
        else:
            message += "\n⚠️ آدرس قرارداد در دسترس نیست یا معتبر نمی‌باشد."
        
        # ارسال به تلگرام
        success = send_telegram_message(message)
        if success:
            print(f"✅ گزارش {token['symbol']} با موفقیت به کانال ارسال شد.")
        else:
            print(f"❌ ارسال گزارش {token['symbol']} ناموفق بود.")
    
    print("\n" + "="*60)
    print(f"✅ فرآیند اسکن و گزارش‌دهی در {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} به پایان رسید.")
    print("="*60)

if __name__ == "__main__":
    main()
