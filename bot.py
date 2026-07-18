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

# آدرس‌های API
TRENDING_METAS_URL = "https://api.dexscreener.com/metas/trending/v1"
META_DETAILS_URL = "https://api.dexscreener.com/metas/meta/v1"

# ==================== تنظیمات فیلترها (قابل تغییر) ====================
CONFIG = {
    "MIN_LIQUIDITY": 50000,      # حداقل نقدینگی ۵۰,۰۰۰ دلار
    "MIN_VOLUME": 10000,         # حداقل حجم ۱۰,۰۰۰ دلار
    "MAX_AGE_HOURS": 168,        # حداکثر سن توکن (۷ روز)
    "MIN_CHANGE_24H": 10,        # حداقل رشد ۱۰٪
    "MIN_TX_COUNT": 10,          # حداقل تعداد تراکنش‌ها
    "SUPPORTED_CHAINS": ["ethereum", "eth", "bsc", "bnb", "arbitrum", "polygon", "base", "linea"]
}

# ==================== توابع کمکی ====================

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

def is_valid_token(token_info):
    """
    بررسی کیفیت یک توکن با فیلترهای مختلف
    برگرداندن True یعنی توکن باکیفیت است
    """
    chain = token_info.get("chain", "").lower()
    
    # ۱. فیلتر شبکه (فقط شبکه‌های معتبر)
    if chain not in CONFIG["SUPPORTED_CHAINS"]:
        print(f"   ⏭️ شبکه {chain} پشتیبانی نمی‌شود.")
        return False
    
    # ۲. فیلتر نقدینگی
    liquidity = token_info.get("liquidity", 0)
    if liquidity < CONFIG["MIN_LIQUIDITY"]:
        print(f"   ⏭️ نقدینگی پایین: ${liquidity:,.0f} (حداقل {CONFIG['MIN_LIQUIDITY']:,})")
        return False
    
    # ۳. فیلتر حجم معاملات
    volume = token_info.get("volume", 0)
    if volume < CONFIG["MIN_VOLUME"]:
        print(f"   ⏭️ حجم پایین: ${volume:,.0f} (حداقل {CONFIG['MIN_VOLUME']:,})")
        return False
    
    # ۴. فیلتر رشد
    change = token_info.get("change_24h", 0)
    if change < CONFIG["MIN_CHANGE_24H"]:
        print(f"   ⏭️ رشد پایین: {change:.2f}% (حداقل {CONFIG['MIN_CHANGE_24H']}%)")
        return False
    
    # ۵. فیلتر تعداد تراکنش‌ها (اگر موجود باشد)
    tx_count = token_info.get("tx_count", 0)
    if tx_count > 0 and tx_count < CONFIG["MIN_TX_COUNT"]:
        print(f"   ⏭️ تعداد تراکنش‌ها کم: {tx_count} (حداقل {CONFIG['MIN_TX_COUNT']})")
        return False
    
    # ۶. جلوگیری از رشدهای غیرعادی (احتمالاً خطا)
    if change > 10000:  # رشد بیش از ۱۰۰۰۰٪ احتمالاً خطا است
        print(f"   ⏭️ رشد غیرعادی: {change:.2f}% (احتمالاً خطای داده)")
        return False
    
    return True

# ==================== توابع دریافت داده ====================

def get_trending_metas():
    """دریافت لیست دسته‌بندی‌های داغ"""
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
    """دریافت لیست توکن‌های یک دسته‌بندی خاص"""
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

# ==================== توابع پیدا کردن خریداران ====================

def get_first_buyers_evm(contract_address, chain_name="ethereum"):
    """پیدا کردن خریداران اولیه با Etherscan API V2"""
    chain_map = {
        "ethereum": 1, "eth": 1, "bsc": 56, "bnb": 56,
        "arbitrum": 42161, "optimism": 10, "polygon": 137,
        "base": 8453, "linea": 59144
    }
    
    chain_id_num = chain_map.get(chain_name.lower(), 1)
    
    url = f"https://api.etherscan.io/v2/api?chainid={chain_id_num}&module=account&action=tokentx&contractaddress={contract_address}&sort=asc&apikey={ETHERSCAN_API_KEY}"
    
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
                decimals = int(tx.get("tokenDecimal", 18))
                value = float(tx.get("value", 0)) / (10 ** decimals)
                if value > 0 and from_addr not in buyers:
                    buyers[from_addr] = {
                        "amount": value,
                        "timestamp": tx.get("timeStamp"),
                        "hash": tx.get("hash")
                    }
                    if len(buyers) >= 5:
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

def get_first_buyers(contract_address, chain_name):
    """تشخیص شبکه و دریافت خریداران اولیه"""
    if not contract_address or len(contract_address) < 10:
        return []
    
    print(f"🔗 در حال بررسی قرارداد: {contract_address[:10]}...{contract_address[-6:]} در شبکه {chain_name}")
    
    chain = chain_name.lower()
    
    if chain in ["ethereum", "eth", "bsc", "bnb", "arbitrum", "optimism", "polygon", "base", "linea"]:
        return get_first_buyers_evm(contract_address, chain)
    else:
        print(f"ℹ️ شبکه {chain} پشتیبانی نمی‌شود.")
        return []

# ==================== تابع اصلی ====================

def get_gainer_tokens():
    """پیدا کردن ارزهای با رشد بالا با فیلترهای کیفیت"""
    print("="*60)
    print("🚀 شروع فرآیند جستجوی ارزهای با رشد بالا")
    print("="*60)
    
    metas = get_trending_metas()
    if not metas:
        print("❌ هیچ دسته‌بندی داغی پیدا نشد.")
        return []
    
    # فیلتر دسته‌بندی‌ها بر اساس رشد ۲۴ ساعته
    top_metas = []
    for meta in metas:
        change_24h = meta.get("marketCapChange", {}).get("h24", 0)
        if change_24h >= 5:
            top_metas.append({
                "slug": meta.get("slug"),
                "name": meta.get("name", "نامشخص"),
                "change_24h": change_24h
            })
    
    print(f"📊 [۳] تعداد دسته‌بندی‌های با رشد +۵٪: {len(top_metas)}")
    
    if not top_metas:
        print("ℹ️ هیچ دسته‌بندی با رشد بالای ۵٪ پیدا نشد.")
        return []
    
    print("\n🏆 دسته‌بندی‌های برتر:")
    for i, meta in enumerate(top_metas[:5], 1):
        print(f"   {i}. {meta['name']} (رشد: {meta['change_24h']:.2f}%)")
    
    # دریافت توکن‌های هر دسته
    all_gainers = []
    seen_tokens = set()
    filtered_count = 0
    
    for meta in top_metas[:5]:
        slug = meta["slug"]
        print(f"\n🔎 [۴] بررسی دسته: {meta['name']} ({slug})")
        
        pairs = get_tokens_from_meta(slug)
        token_count = 0
        
        for pair in pairs:
            try:
                base_token = pair.get("baseToken", {})
                token_symbol = base_token.get("symbol", "نامشخص")
                token_address = base_token.get("address", "")
                
                token_key = f"{pair.get('chainId', '')}-{token_address}"
                if token_key in seen_tokens:
                    continue
                seen_tokens.add(token_key)
                
                price_change = pair.get("priceChange", {})
                change_24h = price_change.get("h24", 0)
                
                # ساخت اطلاعات توکن برای بررسی
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
                    "meta_name": meta["name"],
                    "tx_count": len(pair.get("txns", {}).get("h24", {}))  # تعداد تراکنش‌ها
                }
                
                # اعمال فیلترهای کیفیت
                if is_valid_token(token_info):
                    all_gainers.append(token_info)
                    token_count += 1
                    print(f"   ✅ توکن باکیفیت: {token_symbol} (رشد: {change_24h:.2f}%)")
                else:
                    filtered_count += 1
                    
            except Exception as e:
                print(f"   ⚠️ خطا در پردازش یک توکن: {e}")
                continue
        
        print(f"   📊 تعداد توکن‌های باکیفیت در این دسته: {token_count}")
    
    # مرتب‌سازی بر اساس بیشترین رشد
    all_gainers.sort(key=lambda x: x["change_24h"], reverse=True)
    
    print(f"\n📈 [نهایی] تعداد کل ارزهای با رشد +۱۰٪ پیدا شده: {len(all_gainers)}")
    print(f"⏭️ تعداد ارزهای فیلتر شده (بی‌کیفیت): {filtered_count}")
    
    if all_gainers:
        print("\n🏆 ۵ ارز برتر باکیفیت:")
        for i, token in enumerate(all_gainers[:5], 1):
            print(f"   {i}. {token['symbol']} ({token['chain']}) - رشد: {token['change_24h']:.2f}% - نقدینگی: ${token['liquidity']:,.0f}")
    
    return all_gainers

def format_message(token, buyers=None):
    """ساخت پیام گزارش"""
    message = f"""
🚀 **ارز باکیفیت شناسایی شد!**
▫️ نام: {token['name']} (${token['symbol']})
▫️ شبکه: {token['chain']}
▫️ دسته‌بندی: {token.get('meta_name', 'نامشخص')}
▫️ صرافی: {token.get('dex', 'نامشخص')}
▫️ قیمت: ${token['price']}
▫️ رشد ۲۴ ساعته: **{token['change_24h']:.2f}%** ✅
▫️ حجم معاملات: ${token['volume']:,.0f}
▫️ نقدینگی: ${token['liquidity']:,.0f} (حداقل {CONFIG['MIN_LIQUIDITY']:,}$)
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
        message += "\n⚠️ خریدار اولیه‌ای پیدا نشد."
    
    message += f"\n\n📋 **فیلترهای اعمال شده:**\n• حداقل نقدینگی: ${CONFIG['MIN_LIQUIDITY']:,}\n• حداقل رشد: {CONFIG['MIN_CHANGE_24H']}%"
    
    return message

def main():
    """تابع اصلی"""
    print("\n" + "="*60)
    print(f"⏳ شروع اسکن جدید در {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    start_time = time.time()
    
    gainers = get_gainer_tokens()
    
    if not gainers:
        print("ℹ️ هیچ ارز باکیفیتی با رشد بالا پیدا نشد.")
        return
    
    report_count = min(3, len(gainers))  # فقط ۳ ارز برتر باکیفیت
    print(f"\n📨 در حال ارسال گزارش برای {report_count} ارز برتر باکیفیت...")
    
    success_count = 0
    for i, token in enumerate(gainers[:report_count], 1):
        print(f"\n--- گزارش {i}: {token['symbol']} ---")
        
        buyers = None
        contract = token.get("contract")
        chain = token.get("chain", "")
        
        if contract and len(contract) > 10 and chain.lower() in ["ethereum", "eth", "bsc", "bnb", "arbitrum", "optimism", "polygon", "base", "linea"]:
            print(f"🔍 در حال جستجوی خریداران اولیه...")
            buyers = get_first_buyers(contract, chain)
        else:
            print(f"⚠️ شبکه {chain} برای جستجوی خریداران پشتیبانی نمی‌شود.")
        
        message = format_message(token, buyers)
        if send_telegram_message(message):
            success_count += 1
            print(f"✅ گزارش {token['symbol']} با موفقیت ارسال شد.")
        else:
            print(f"❌ ارسال گزارش {token['symbol']} ناموفق بود.")
        
        if i < report_count:
            time.sleep(2)
    
    elapsed_time = time.time() - start_time
    print("\n" + "="*60)
    print(f"✅ فرآیند اسکن و گزارش‌دهی در {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} به پایان رسید.")
    print(f"⏱️ زمان اجرا: {elapsed_time:.2f} ثانیه")
    print(f"📊 تعداد کل ارزهای باکیفیت پیدا شده: {len(gainers)}")
    print(f"📨 تعداد گزارش‌های ارسال شده: {success_count}")
    print("="*60)

if __name__ == "__main__":
    main()
