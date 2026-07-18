import requests
import os
import json
from datetime import datetime
import time

# --- گرفتن اطلاعات از حافظه مخفی گیت‌هاب ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")

if not TELEGRAM_TOKEN or not CHAT_ID or not ETHERSCAN_API_KEY:
    raise ValueError("خطا: توکن، آیدی کانال یا کلید اتریوم در Secrets تنظیم نشده است.")

# آدرس‌های API جدید
TRENDING_METAS_URL = "https://api.dexscreener.com/metas/trending/v1"
META_DETAILS_URL = "https://api.dexscreener.com/metas/meta/v1"

def send_telegram_message(message):
    """ارسال پیام به کانال تلگرام"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        print("✅ پیام با موفقیت به کانال ارسال شد.")
        return True
    except Exception as e:
        print(f"❌ خطا در ارسال پیام: {e}")
        return False

def get_trending_metas():
    """
    دریافت لیست دسته‌بندی‌های داغ از API ترندینگ
    """
    print("🔍 [۱] دریافت لیست دسته‌بندی‌های داغ...")
    try:
        response = requests.get(TRENDING_METAS_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"✅ [۲] تعداد دسته‌بندی‌های دریافت شده: {len(data)}")
        return data
    except Exception as e:
        print(f"❌ خطا در دریافت دسته‌بندی‌ها: {e}")
        return []

def get_tokens_from_meta(slug):
    """
    دریافت لیست توکن‌های یک دسته‌بندی خاص
    """
    try:
        url = f"{META_DETAILS_URL}/{slug}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        pairs = data.get("pairs", [])
        print(f"   📊 تعداد توکن‌های دسته {slug}: {len(pairs)}")
        return pairs
    except Exception as e:
        print(f"   ⚠️ خطا در دریافت توکن‌های دسته {slug}: {e}")
        return []

def get_gainer_tokens():
    """
    پیدا کردن ارزهای با رشد بالا با استفاده از API ترندینگ
    """
    print("="*60)
    print("🚀 شروع فرآیند جستجوی ارزهای با رشد بالا")
    print("="*60)
    
    # دریافت دسته‌بندی‌های داغ
    metas = get_trending_metas()
    if not metas:
        print("❌ هیچ دسته‌بندی داغی پیدا نشد.")
        return []
    
    # فیلتر دسته‌بندی‌ها بر اساس رشد ۲۴ ساعته
    top_metas = []
    for meta in metas:
        change_24h = meta.get("marketCapChange", {}).get("h24", 0)
        if change_24h >= 5:  # فقط دسته‌هایی با رشد بالای ۵٪
            top_metas.append({
                "slug": meta.get("slug"),
                "name": meta.get("name", "نامشخص"),
                "change_24h": change_24h,
                "market_cap": meta.get("marketCap", 0),
                "volume": meta.get("volume", 0),
                "token_count": meta.get("tokenCount", 0)
            })
    
    print(f"📊 [۳] تعداد دسته‌بندی‌های با رشد +۵٪: {len(top_metas)}")
    
    if not top_metas:
        print("ℹ️ هیچ دسته‌بندی با رشد بالای ۵٪ پیدا نشد.")
        return []
    
    # نمایش دسته‌بندی‌های برتر
    print("\n🏆 دسته‌بندی‌های برتر:")
    for i, meta in enumerate(top_metas[:5], 1):
        print(f"   {i}. {meta['name']} (رشد: {meta['change_24h']:.2f}%)")
    
    # دریافت توکن‌های هر دسته
    all_gainers = []
    seen_tokens = set()  # برای جلوگیری از تکراری‌ها
    
    for meta in top_metas[:5]:  # فقط ۵ دسته برتر
        slug = meta["slug"]
        print(f"\n🔎 [۴] بررسی دسته: {meta['name']} ({slug})")
        
        pairs = get_tokens_from_meta(slug)
        token_count = 0
        
        for pair in pairs:
            try:
                # استخراج اطلاعات
                base_token = pair.get("baseToken", {})
                token_symbol = base_token.get("symbol", "نامشخص")
                token_address = base_token.get("address", "")
                
                # کلید یکتا برای جلوگیری از تکراری‌ها
                token_key = f"{pair.get('chainId', '')}-{token_address}"
                if token_key in seen_tokens:
                    continue
                seen_tokens.add(token_key)
                
                price_change = pair.get("priceChange", {})
                change_24h = price_change.get("h24", 0)
                
                # فیلتر توکن‌های با رشد بالا
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
                        "contract": token_address,
                        "dex": pair.get("dexId", "نامشخص"),
                        "market_cap": pair.get("marketCap", 0),
                        "meta_name": meta["name"]  # ذخیره نام دسته‌بندی
                    }
                    all_gainers.append(token_info)
                    token_count += 1
                    print(f"   ✅ توکن پیدا شد: {token_symbol} (رشد: {change_24h:.2f}%)")
                    
            except Exception as e:
                print(f"   ⚠️ خطا در پردازش یک توکن: {e}")
                continue
        
        print(f"   📊 تعداد کل توکن‌های با رشد +۱۰٪ در این دسته: {token_count}")
    
    # مرتب‌سازی بر اساس بیشترین رشد
    all_gainers.sort(key=lambda x: x["change_24h"], reverse=True)
    
    print(f"\n📈 [نهایی] تعداد کل ارزهای با رشد +۱۰٪ پیدا شده: {len(all_gainers)}")
    
    if all_gainers:
        print("\n🏆 ۵ ارز برتر:")
        for i, token in enumerate(all_gainers[:5], 1):
            print(f"   {i}. {token['symbol']} ({token['chain']}) - رشد: {token['change_24h']:.2f}%")
    
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

def format_message(token, buyers=None):
    """ساخت پیام گزارش برای یک توکن"""
    message = f"""
🚀 **ارز داغ جدید شناسایی شد!**
▫️ نام: {token['name']} (${token['symbol']})
▫️ شبکه: {token['chain']}
▫️ دسته‌بندی: {token.get('meta_name', 'نامشخص')}
▫️ صرافی: {token.get('dex', 'نامشخص')}
▫️ قیمت: ${token['price']}
▫️ رشد ۲۴ ساعته: **{token['change_24h']:.2f}%** ✅
▫️ حجم معاملات ۲۴h: ${token['volume']:,.0f}
▫️ نقدینگی: ${token['liquidity']:,.0f}
▫️ مارکت‌کپ: ${token.get('market_cap', 0):,.0f}
🔗 [مشاهده در DexScreener]({token['dex_url']})
    """
    
    if buyers:
        message += "\n🐋 **کیف‌پول‌های خریدار اولیه (۵ نفر اول):**\n"
        for i, buyer in enumerate(buyers[:5], 1):
            addr = buyer["address"]
            short_addr = addr[:6] + "..." + addr[-4:]
            message += f"{i}. `{short_addr}` (مقدار: {buyer['amount']:.2f} توکن)\n"
    else:
        message += "\n⚠️ خریدار اولیه‌ای پیدا نشد (ممکن است توکن جدید باشد)."
    
    return message

def main():
    """تابع اصلی ربات"""
    print("\n" + "="*60)
    print(f"⏳ شروع اسکن جدید در {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    start_time = time.time()
    
    # دریافت ارزهای با رشد بالا
    gainers = get_gainer_tokens()
    
    if not gainers:
        print("ℹ️ هیچ ارزی با رشد بالا پیدا نشد.")
        return
    
    # تعداد ارزهای قابل گزارش
    report_count = min(5, len(gainers))  # حداکثر ۵ ارز
    print(f"\n📨 در حال ارسال گزارش برای {report_count} ارز برتر...")
    
    success_count = 0
    for i, token in enumerate(gainers[:report_count], 1):
        print(f"\n--- گزارش {i}: {token['symbol']} ---")
        
        # جستجوی خریداران اولیه
        buyers = None
        contract = token.get("contract")
        if contract and len(contract) > 10:
            print(f"🔍 در حال جستجوی خریداران اولیه برای {token['symbol']}...")
            buyers = get_first_buyers(contract)
        else:
            print(f"⚠️ آدرس قرارداد برای {token['symbol']} در دسترس نیست.")
        
        # ساخت و ارسال پیام
        message = format_message(token, buyers)
        if send_telegram_message(message):
            success_count += 1
            print(f"✅ گزارش {token['symbol']} با موفقیت ارسال شد.")
        else:
            print(f"❌ ارسال گزارش {token['symbol']} ناموفق بود.")
        
        # تاخیر بین پیام‌ها برای جلوگیری از اسپم
        if i < report_count:
            time.sleep(2)
    
    # گزارش نهایی
    elapsed_time = time.time() - start_time
    print("\n" + "="*60)
    print(f"✅ فرآیند اسکن و گزارش‌دهی در {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} به پایان رسید.")
    print(f"⏱️ زمان اجرا: {elapsed_time:.2f} ثانیه")
    print(f"📊 تعداد کل ارزهای پیدا شده: {len(gainers)}")
    print(f"📨 تعداد گزارش‌های ارسال شده: {success_count}")
    print("="*60)

if __name__ == "__main__":
    main()
