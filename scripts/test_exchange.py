import sys, ccxt
sys.path.insert(0, "/app/src")

# Test exchange_public
ex = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'spot'}, 'timeout': 15000})
try:
    t = ex.fetch_ticker("BTC/USDT")
    print(f"BTC: ${t['last']:,.2f} ({t.get('percentage', 0):+.2f}% 24h)")
    print("Exchange: OK")
except Exception as e:
    print(f"Exchange error: {e}")

# Check what the telegram bot sees
from live_server import exchange_public
print(f"exchange_public is None: {exchange_public is None}")
if exchange_public:
    try:
        t2 = exchange_public.fetch_ticker("BTC/USDT")
        print(f"Global exchange BTC: ${t2['last']:,.2f}")
    except Exception as e:
        print(f"Global exchange error: {e}")
