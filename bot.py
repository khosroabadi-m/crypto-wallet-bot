import requests
import os
import json
from datetime import datetime
import time

# ==================== گرفتن اطلاعات از حافظه مخفی گیت‌هاب ====================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
ETHERSCAN_API_KEY = os.getenv("ETHERSCAN_API_KEY")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
SOLSCAN_API_KEY = os.getenv("SOLSCAN_API_KEY", "")

if not TELEGRAM_TOKEN or not CHAT_ID or not ETHERSCAN_API_KEY:
    raise ValueError("❌ خطا: توکن، آیدی کانال یا کلید اتریوم در Secrets تنظیم نشده است.")

if not SOLSCAN_API_KEY:
    print("⚠️ هشدار: SOLSCAN_API_KEY تنظیم نشده است. توکن‌های سولانا بررسی نمی‌شوند.")

# ==================== آدرس‌های API ====================
TRENDING_METAS_URL = "https://api.dexscreener.com/metas/trending/v1"
META_DETAILS_URL = "https://api.dexscreener.com/metas/meta/v1"
COINGECKO_URL = "https://api.coingecko.com/api/v3/coins/markets"

# ==================== تنظیمات فیلترها ====================
CONFIG = {
    "MIN_LIQUIDITY_DEX": 30000,
    "MIN_VOLUME_DEX": 5000,
    "MIN_VOLUME_CEX": 500000,
    "MIN_CHANGE_24H": 10,
    "MAX_CHANGE_24H": 500,
    "REPORT_COUNT": 5,
    "SUPPORTED_CHAINS": [
        "ethereum", "eth", "bsc", "bnb", "arbitrum", 
        "optimism", "polygon", "base", "linea", 
        "avalanche", "fantom",
        "solana", "sol"
    ]
}

# ==================== توابع ارسال پیام ====================

def send_telegram_message(message):
    """ارسال پیام به کانال تلگرام"""
    print("📤 در حال ارسال پیام به تلگرام...")
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

# ==================== توابع دریافت از DexScreener ====================

def get_trending_metas():
    """دریافت لیست دسته‌بندی‌های داغ از DexScreener"""
    print("🔍 [DEX-۱] دریافت لیست دسته‌بندی‌های داغ از DexScreener...")
    try:
        response = requests.get(TRENDING_METAS_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        print(f"✅ [DEX-۲] تعداد دسته‌بندی‌های دریافت شده: {len(data)}")
        return data
    except Exception as e:
        print(f"❌ [DEX] خطا در دریافت دسته‌بندی‌ها: {e}")
        return []

def get_tokens_from_meta(slug):
    """دریافت لیست توکن‌های یک دسته‌بندی خاص از DexScreener"""
    try:
        url = f"{META_DETAILS_URL}/{slug}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        pairs = data.get("pairs", [])
        print(f"   📊 [DEX] تعداد توکن‌های دسته {slug}: {len(pairs)}")
        return pairs
    except Exception as e:
        print(f"   ⚠️ [DEX] خطا در دریافت توکن‌های دسته {slug}: {e}")
        return []

def is_valid_dex_token(token_info):
    """بررسی کیفیت توکن DEX با فیلترهای مختلف"""
    chain = token_info.get("chain", "").lower()
    
    # ۱. فیلتر شبکه
    if chain not in CONFIG["SUPPORTED_CHAINS"]:
        print(f"   ⏭️ [DEX] شبکه {chain} پشتیبانی نمی‌شود.")
        return False
    
    # ۲. فیلتر نقدینگی
    liquidity = token_info.get("liquidity", 0)
    min_liquidity = CONFIG["MIN_LIQUIDITY_DEX"]
    if chain in ["solana", "sol"]:
        min_liquidity = 10000
    
    if liquidity < min_liquidity:
        print(f"   ⏭️ [DEX] نقدینگی پایین: ${liquidity:,.0f}")
        return False
    
    # ۳. فیلتر حجم معاملات
    volume = token_info.get("volume", 0)
    min_volume = CONFIG["MIN_VOLUME_DEX"]
    if chain in ["solana", "sol"]:
        min_volume = 2000
    
    if volume < min_volume:
        print(f"   ⏭️ [DEX] حجم پایین: ${volume:,.0f}")
        return False
    
    # ۴. فیلتر رشد
    change = token_info.get("change_24h", 0)
    if change < CONFIG["MIN_CHANGE_24H"]:
        print(f"   ⏭️ [DEX] رشد پایین: {change:.2f}%")
        return False
    
    # ۵. جلوگیری از رشدهای غیرعادی
    if change > CONFIG["MAX_CHANGE_24H"]:
        print(f"   ⏭️ [DEX] رشد غیرعادی: {change:.2f}%")
        return False
    
    return True

def get_gainers_from_dex():
    """پیدا کردن ارزهای با رشد بالا از DexScreener"""
    print("="*60)
    print("🚀 [DEX] شروع جستجو در صرافی‌های غیرمتمرکز")
    print("="*60)
    
    metas = get_trending_metas()
    if not metas:
        print("❌ [DEX] هیچ دسته‌بندی داغی پیدا نشد.")
        return []
    
    top_metas = []
    for meta in metas:
        change_24h = meta.get("marketCapChange", {}).get("h24", 0)
        if change_24h >= 3:
            top_metas.append({
                "slug": meta.get("slug"),
                "name": meta.get("name", "نامشخص"),
                "change_24h": change_24h
            })
    
    print(f"📊 [DEX] تعداد دسته‌بندی‌های با رشد +۳٪: {len(top_metas)}")
    
    if not top_metas:
        print("ℹ️ [DEX] هیچ دسته‌بندی با رشد بالا پیدا نشد.")
        return []
    
    print("\n🏆 [DEX] دسته‌بندی‌های برتر:")
    for i, meta in enumerate(top_metas[:5], 1):
        print(f"   {i}. {meta['name']} (رشد دسته: {meta['change_24h']:.2f}%)")
    
    all_gainers = []
    seen_tokens = set()
    filtered_count = 0
    
    for meta in top_metas[:5]:
        slug = meta["slug"]
        print(f"\n🔎 [DEX] بررسی دسته: {meta['name']} ({slug})")
        
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
                
                token_info = {
                    "name": base_token.get("name", "نامشخص"),
                    "symbol": token_symbol,
                    "chain": pair.get("chainId", "ناشناخته"),
                    "price": pair.get("priceUsd", "0"),
                    "change_24h": change_24h,
                    "volume": pair.get("volume", {}).get("h24", 0),
                    "liquidity": pair.get("liquidity", {}).get("usd", 0),
                    "dex_url": pair.get("url", "#"),
                    "contract": token_address,
                    "dex": pair.get("dexId", "نامشخص"),
                    "market_cap": pair.get("marketCap", 0),
                    "meta_name": meta["name"],
                    "source": "DEX"
                }
                
                if is_valid_dex_token(token_info):
                    all_gainers.append(token_info)
                    token_count += 1
                    print(f"   ✅ [DEX] توکن باکیفیت: {token_symbol} (رشد: {change_24h:.2f}%)")
                else:
                    filtered_count += 1
                    
            except Exception as e:
                print(f"   ⚠️ [DEX] خطا در پردازش: {e}")
                continue
        
        print(f"   📊 [DEX] تعداد توکن‌های باکیفیت در این دسته: {token_count}")
    
    print(f"\n📈 [DEX] تعداد کل ارزهای باکیفیت پیدا شده: {len(all_gainers)}")
    print(f"⏭️ [DEX] تعداد ارزهای فیلتر شده: {filtered_count}")
    
    return all_gainers

# ==================== توابع دریافت از CoinGecko ====================

def get_gainers_from_coingecko():
    """دریافت ارزهای با رشد بالا از CoinGecko (صرافی‌های متمرکز)"""
    print("\n" + "="*60)
    print("🚀 [CEX] شروع جستجو در صرافی‌های متمرکز (CoinGecko)")
    print("="*60)
    
    try:
        headers = {}
        if COINGECKO_API_KEY:
            headers["x-cg-pro-api-key"] = COINGECKO_API_KEY
            print("🔑 [CEX] استفاده از کلید API اختصاصی")
        else:
            print("ℹ️ [CEX] بدون کلید API (محدودیت ۱۰-۳۰ درخواست در دقیقه)")
        
        params = {
            "vs_currency": "usd",
            "order": "volume_desc",
            "per_page": 250,
            "page": 1,
            "sparkline": "false",
            "price_change_percentage": "24h"
        }
        
        print("🔍 [CEX-۱] در حال دریافت لیست ارزها از CoinGecko...")
        response = requests.get(COINGECKO_URL, params=params, headers=headers, timeout=15)
        response.raise_for_status()
        data = response.json()
        print(f"✅ [CEX-۲] تعداد ارزهای دریافت شده: {len(data)}")
        
        gainers = []
        filtered_count = 0
        
        for coin in data:
            try:
                change_24h = coin.get("price_change_percentage_24h")
                if change_24h is None:
                    filtered_count += 1
                    continue
                
                volume = coin.get("total_volume") or 0
                market_cap = coin.get("market_cap") or 0
                name = coin.get("name", "نامشخص")
                symbol = coin.get("symbol", "").upper()
                price = coin.get("current_price") or 0
                coin_id = coin.get("id", "")
                
                if change_24h < CONFIG["MIN_CHANGE_24H"]:
                    filtered_count += 1
                    continue
                
                if volume < CONFIG["MIN_VOLUME_CEX"]:
                    filtered_count += 1
                    continue
                
                if change_24h > CONFIG["MAX_CHANGE_24H"]:
                    print(f"   ⏭️ [CEX] رشد غیرعادی: {symbol} ({change_24h:.2f}%)")
                    filtered_count += 1
                    continue
                
                token_info = {
                    "name": name,
                    "symbol": symbol,
                    "chain": "متمرکز (CEX)",
                    "price": str(price),
                    "change_24h": change_24h,
                    "volume": volume,
                    "liquidity": market_cap,
                    "market_cap": market_cap,
                    "dex_url": f"https://www.coingecko.com/en/coins/{coin_id}",
                    "contract": "",
                    "dex": "CoinGecko",
                    "meta_name": "صرافی‌های متمرکز",
                    "source": "CEX"
                }
                gainers.append(token_info)
                print(f"   ✅ [CEX] توکن باکیفیت: {symbol} (رشد: {change_24h:.2f}%)")
                
            except Exception as e:
                print(f"   ⚠️ [CEX] خطا در پردازش: {e}")
                continue
        
        print(f"\n📈 [CEX] تعداد کل ارزهای با رشد +۱۰٪: {len(gainers)}")
        print(f"⏭️ [CEX] تعداد ارزهای فیلتر شده: {filtered_count}")
        
        return gainers
        
    except Exception as e:
        print(f"❌ [CEX] خطا: {e}")
        return []

# ==================== توابع پیدا کردن خریداران اولیه ====================

def get_first_buyers_evm(contract_address, chain_name="ethereum"):
    """پیدا کردن خریداران اولیه با Etherscan API V2"""
    chain_map = {
        "ethereum": 1, "eth": 1, "bsc": 56, "bnb": 56,
        "arbitrum": 42161, "optimism": 10, "polygon": 137,
        "base": 8453, "linea": 59144, "avalanche": 43114,
        "fantom": 250
    }
    
    chain_id_num = chain_map.get(chain_name.lower(), 1)
    
    url = f"https://api.etherscan.io/v2/api?chainid={chain_id_num}&module=account&action=tokentx&contractaddress={contract_address}&sort=asc&apikey={ETHERSCAN_API_KEY}"
    
    print(f"🔗 [EVM] در حال بررسی قرارداد: {contract_address[:10]}...{contract_address[-6:]} در شبکه {chain_name}")
    
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        
        if data.get("status") != "1":
            print(f"⚠️ [EVM] خطای Etherscan: {data.get('message', 'خطای ناشناخته')}")
            return []
        
        transactions = data.get("result", [])
        print(f"📊 [EVM] تعداد کل تراکنش‌های قرارداد: {len(transactions)}")
        
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
        print(f"✅ [EVM] تعداد خریداران اولیه پیدا شده: {len(result)}")
        return result
        
    except Exception as e:
        print(f"❌ [EVM] خطا در Etherscan: {e}")
        return []

def get_first_buyers_solana(contract_address):
    """پیدا کردن خریداران اولیه در شبکه سولانا با Solscan API"""
    if not SOLSCAN_API_KEY:
        print("⚠️ [SOL] کلید Solscan تنظیم نشده است. لطفاً SOLSCAN_API_KEY را به Secrets اضافه کنید.")
        return []
    
    print(f"🔗 [SOL] در حال بررسی قرارداد سولانا: {contract_address[:10]}...{contract_address[-6:]}")
    
    # استفاده از API رسمی Solscan
    url = f"https://public-api.solscan.io/transaction?account={contract_address}&limit=100"
    
    headers = {}
    if SOLSCAN_API_KEY:
        headers["token"] = SOLSCAN_API_KEY
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        
        if response.status_code == 404:
            print("ℹ️ [SOL] قرارداد در Solscan پیدا نشد.")
            return []
        
        data = response.json()
        if not data:
            print("ℹ️ [SOL] اطلاعاتی برای این قرارداد وجود ندارد.")
            return []
        
        print(f"📊 [SOL] تعداد تراکنش‌های پیدا شده: {len(data) if isinstance(data, list) else 0}")
        
        # در اینجا باید خریداران اولیه را استخراج کنیم
        # API عمومی Solscan محدود است و نیاز به بررسی دقیق‌تر دارد
        
        print("ℹ️ [SOL] اطلاعات خریداران اولیه در سولانا نیاز به بررسی دقیق‌تر دارد.")
        return []
        
    except Exception as e:
        print(f"❌ [SOL] خطا در Solscan: {e}")
        return []

def get_first_buyers(contract_address, chain_name):
    """تشخیص شبکه و دریافت خریداران اولیه"""
    if not contract_address or len(contract_address) < 10:
        print(f"⚠️ آدرس قرارداد نامعتبر")
        return []
    
    chain = chain_name.lower()
    
    if chain in ["ethereum", "eth", "bsc", "bnb", "arbitrum", "optimism", "polygon", "base", "linea", "avalanche", "fantom"]:
        return get_first_buyers_evm(contract_address, chain)
    
    elif chain in ["solana", "sol"]:
        return get_first_buyers_solana(contract_address)
    
    else:
        print(f"ℹ️ شبکه {chain} برای جستجوی خریداران پشتیبانی نمی‌شود.")
        return []

# ==================== ساخت پیام گزارش ====================

def format_message(token, buyers=None):
    """ساخت پیام گزارش برای یک توکن - اصلاح شده برای مدیریت انواع داده"""
    source_emoji = "🔄" if token.get("source") == "CEX" else "🦄"
    source_name = "صرافی متمرکز" if token.get("source") == "CEX" else "صرافی غیرمتمرکز"
    
    chain_display = token.get('chain', 'نامشخص')
    if chain_display.lower() in ["solana", "sol"]:
        chain_display = "سولانا 🌟"
    
    # تبدیل قیمت به عدد با مدیریت خطا
    try:
        price = float(token.get('price', 0))
        price_str = f"${price:,.4f}"
    except (ValueError, TypeError):
        price_str = token.get('price', '۰')
    
    # تبدیل سایر مقادیر به عدد
    try:
        change = float(token.get('change_24h', 0))
        change_str = f"{change:.2f}%"
    except (ValueError, TypeError):
        change_str = f"{token.get('change_24h', 0)}%"
    
    try:
        volume = float(token.get('volume', 0))
        volume_str = f"${volume:,.0f}"
    except (ValueError, TypeError):
        volume_str = f"${token.get('volume', 0)}"
    
    try:
        liquidity = float(token.get('liquidity', 0))
        liquidity_str = f"${liquidity:,.0f}"
    except (ValueError, TypeError):
        liquidity_str = f"${token.get('liquidity', 0)}"
    
    message = f"""
{source_emoji} **ارز باکیفیت شناسایی شد!** ({source_name})
▫️ نام: {token.get('name', 'نامشخص')} (${token.get('symbol', 'نامشخص')})
▫️ شبکه: {chain_display}
▫️ دسته‌بندی: {token.get('meta_name', 'نامشخص')}
▫️ صرافی: {token.get('dex', 'نامشخص')}
▫️ قیمت: {price_str}
▫️ رشد ۲۴ ساعته: **{change_str}** ✅
▫️ حجم معاملات: {volume_str}
▫️ نقدینگی/مارکت‌کپ: {liquidity_str}
🔗 [مشاهده در DexScreener]({token.get('dex_url', '#')})
    """
    
    if buyers:
        message += "\n🐋 **کیف‌پول‌های خریدار اولیه (۵ نفر اول):**\n"
        for i, buyer in enumerate(buyers[:5], 1):
            addr = buyer.get("address", "نامشخص")
            short_addr = addr[:6] + "..." + addr[-4:] if len(addr) > 10 else addr
            amount = buyer.get("amount", 0)
            message += f"{i}. `{short_addr}` (مقدار: {amount:.2f} توکن)\n"
    else:
        message += "\n⚠️ خریدار اولیه‌ای پیدا نشد."
    
    return message

# ==================== تابع اصلی ====================

def main():
    """تابع اصلی ربات با دو منبع داده"""
    print("\n" + "="*60)
    print(f"⏳ شروع اسکن جدید در {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)
    
    start_time = time.time()
    
    # ۱. دریافت از DexScreener (صرافی‌های غیرمتمرکز)
    gainers_dex = get_gainers_from_dex()
    
    # ۲. دریافت از CoinGecko (صرافی‌های متمرکز)
    gainers_cex = get_gainers_from_coingecko()
    
    # ۳. ترکیب و حذف تکراری‌ها
    print("\n" + "="*60)
    print("🔄 ترکیب نتایج از دو منبع داده")
    print("="*60)
    
    all_gainers = gainers_dex + gainers_cex
    seen = set()
    unique_gainers = []
    
    for token in all_gainers:
        key = f"{token.get('symbol', '')}-{token.get('chain', '')}"
        if key not in seen:
            seen.add(key)
            unique_gainers.append(token)
    
    # ۴. مرتب‌سازی بر اساس رشد
    unique_gainers.sort(key=lambda x: float(x.get('change_24h', 0)) if x.get('change_24h') is not None else 0, reverse=True)
    
    # ۵. گزارش نهایی
    print(f"\n📊 **خلاصه نهایی:**")
    print(f"   - از صرافی‌های غیرمتمرکز (DEX): {len(gainers_dex)} ارز")
    print(f"   - از صرافی‌های متمرکز (CEX): {len(gainers_cex)} ارز")
    print(f"   - مجموع پس از حذف تکراری‌ها: {len(unique_gainers)} ارز")
    
    if not unique_gainers:
        print("ℹ️ هیچ ارز باکیفیتی با رشد بالا پیدا نشد.")
        return
    
    # نمایش ۵ ارز برتر
    print("\n🏆 ۵ ارز برتر باکیفیت:")
    for i, token in enumerate(unique_gainers[:5], 1):
        change = float(token.get('change_24h', 0)) if token.get('change_24h') is not None else 0
        print(f"   {i}. {token.get('symbol', 'نامشخص')} ({token.get('chain', 'نامشخص')}) - رشد: {change:.2f}% - منبع: {token.get('source', 'نامشخص')}")
    
    # ۶. ارسال گزارش به تلگرام
    report_count = min(CONFIG["REPORT_COUNT"], len(unique_gainers))
    print(f"\n📨 در حال ارسال گزارش برای {report_count} ارز برتر...")
    
    success_count = 0
    for i, token in enumerate(unique_gainers[:report_count], 1):
        print(f"\n--- گزارش {i}: {token.get('symbol', 'نامشخص')} ---")
        
        buyers = None
        contract = token.get("contract", "")
        chain = token.get("chain", "")
        
        # فقط برای توکن‌های DEX با قرارداد معتبر
        if contract and len(contract) > 10 and token.get("source") == "DEX":
            print(f"🔍 در حال جستجوی خریداران اولیه برای {token.get('symbol', 'نامشخص')}...")
            buyers = get_first_buyers(contract, chain)
        else:
            print(f"ℹ️ برای {token.get('symbol', 'نامشخص')} جستجوی خریداران انجام نمی‌شود.")
        
        message = format_message(token, buyers)
        if send_telegram_message(message):
            success_count += 1
            print(f"✅ گزارش {token.get('symbol', 'نامشخص')} با موفقیت ارسال شد.")
        else:
            print(f"❌ ارسال گزارش {token.get('symbol', 'نامشخص')} ناموفق بود.")
        
        if i < report_count:
            time.sleep(2)
    
    # ۷. گزارش نهایی
    elapsed_time = time.time() - start_time
    print("\n" + "="*60)
    print(f"✅ فرآیند اسکن و گزارش‌دهی در {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} به پایان رسید.")
    print(f"⏱️ زمان اجرا: {elapsed_time:.2f} ثانیه")
    print(f"📊 تعداد کل ارزهای باکیفیت پیدا شده: {len(unique_gainers)}")
    print(f"📨 تعداد گزارش‌های ارسال شده: {success_count}")
    print("="*60)

if __name__ == "__main__":
    main()
