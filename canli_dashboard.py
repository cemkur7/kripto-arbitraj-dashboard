import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import smtplib
from email.message import EmailMessage
import os

st.set_page_config(page_title="Canlı Kripto Arbitraj", layout="wide")
st.title("\U0001F4C8 Canlı Kripto Arbitraj Takibi")

coins = [
    "BTC", "ETH", "USDT", "XRP", "BNB", "SOL", "DOGE", "ADA", "TRX",
    "LINK", "AVAX", "DOT", "MATIC", "SHIB", "LTC", "NEAR", "PEPE", "ARB", "OP"
]

borsalar = {
    "Binance": lambda c: f"https://api.binance.com/api/v3/ticker/price?symbol={c}USDT",
    "KuCoin": lambda c: f"https://api.kucoin.com/api/v1/market/orderbook/level1?symbol={c}-USDT",
    "MEXC": lambda c: f"https://api.mexc.com/api/v3/ticker/price?symbol={c}USDT",
    "Gate.io": lambda c: f"https://api.gateio.ws/api/v4/spot/tickers?currency_pair={c}_USDT",
    "OKX": lambda c: f"https://www.okx.com/api/v5/market/ticker?instId={c}-USDT",
}

komisyonlar = {
    "Binance": 0.001,
    "KuCoin": 0.001,
    "MEXC": 0.001,
    "Gate.io": 0.001,
    "OKX": 0.001
}

transfer_ucretleri = {
    "BTC": 10, "ETH": 5, "SOL": 0.2, "AVAX": 0.2, "XRP": 0.1, "DOGE": 1,
    "USDT": 1, "ADA": 1, "TRX": 1, "LINK": 1, "DOT": 1, "MATIC": 1, "SHIB": 1,
    "LTC": 1, "NEAR": 1, "PEPE": 1, "ARB": 1, "OP": 1, "BNB": 1, "XRP": 1
}

fiyat_gecmisi = {}

@st.cache_data(ttl=60)
def get_prices(coin):
    prices = {}
    for borsa, url_func in borsalar.items():
        try:
            url = url_func(coin)
            r = requests.get(url, timeout=10).json()
            if borsa == "Binance":
                prices[borsa] = float(r['price'])
            elif borsa == "KuCoin":
                prices[borsa] = float(r['data']['price'])
            elif borsa == "MEXC":
                prices[borsa] = float(r['price'])
            elif borsa == "Gate.io":
                prices[borsa] = float(r[0]['last'])
            elif borsa == "OKX":
                prices[borsa] = float(r['data'][0]['last'])
        except:
            prices[borsa] = None
    return prices

selected_coins = st.multiselect("Takip Edilecek Coinler", coins, default=["BTC", "ETH", "SOL"])
min_kar_filtre = st.slider("Minimum Kar % Filtresi", min_value=0.0, max_value=5.0, value=0.0, step=0.01)

all_data = []
zaman = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for coin in selected_coins:
    row = {"Coin": coin}
    prices = get_prices(coin)
    row.update(prices)
    try:
        max_borsa = max(prices, key=lambda x: prices[x] if prices[x] else 0)
        min_borsa = min(prices, key=lambda x: prices[x] if prices[x] else float('inf'))
        if prices[max_borsa] and prices[min_borsa]:
            fark = prices[max_borsa] - prices[min_borsa]
            oran = (fark / prices[min_borsa]) * 100
            al_komisyon = prices[min_borsa] * komisyonlar[min_borsa]
            sat_komisyon = prices[max_borsa] * komisyonlar[max_borsa]
            transfer = transfer_ucretleri.get(coin, 1)
            net_kar = fark - al_komisyon - sat_komisyon - transfer
            if oran >= min_kar_filtre:
                row["Al"] = f"{min_borsa} ({prices[min_borsa]:.2f})"
                row["Sat"] = f"{max_borsa} ({prices[max_borsa]:.2f})"
                row["Kar %"] = round(oran, 2)
                row["Net Kâr"] = round(net_kar, 2)
                row["Zaman"] = zaman

                if coin not in fiyat_gecmisi:
                    fiyat_gecmisi[coin] = []
                fiyat_gecmisi[coin].append(prices[min_borsa])
                if len(fiyat_gecmisi[coin]) > 5:
                    fiyat_gecmisi[coin] = fiyat_gecmisi[coin][-5:]
            else:
                row["Al"] = row["Sat"] = row["Kar %"] = row["Net Kâr"] = row["Zaman"] = "-"
        else:
            row["Al"] = row["Sat"] = row["Kar %"] = row["Net Kâr"] = row["Zaman"] = "-"
    except:
        row["Al"] = row["Sat"] = row["Kar %"] = row["Net Kâr"] = row["Zaman"] = "-"

    all_data.append(row)

renkli_df = pd.DataFrame(all_data)

csv = renkli_df.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 CSV Olarak İndir",
    data=csv,
    file_name="arbitraj_verileri.csv",
    mime='text/csv'
)

def kar_renklendir(val):
    if val == "-":
        return ""
    try:
        v = float(val)
        if v > 0:
            return "background-color: #d4edda; color: #155724"
        elif v < 0:
            return "background-color: #f8d7da; color: #721c24"
    except:
        return ""
    return ""

st.dataframe(
    renkli_df.style.applymap(kar_renklendir, subset=["Kar %", "Net Kâr"]),
    use_container_width=True
)

st.subheader("📈 Coin Fiyat Trendleri (Son 5 Güncelleme)")
for coin in selected_coins:
    if coin in fiyat_gecmisi and len(fiyat_gecmisi[coin]) >= 2:
        st.line_chart(pd.DataFrame(fiyat_gecmisi[coin], columns=[coin]))

# Günlük özet e-posta gönderimi (örnek)
def send_summary_email():
    summary = renkli_df.sort_values("Net Kâr", ascending=False).head(3).to_string(index=False)
    content = f"En kârlı ilk 3 fırsat ({zaman}):\n\n{summary}"

    try:
        sender = os.environ.get("EMAIL_USER")
        password = os.environ.get("EMAIL_PASS")
        receiver = os.environ.get("EMAIL_TO")

        msg = EmailMessage()
        msg.set_content(content)
        msg["Subject"] = "Günlük Arbitraj Özeti"
        msg["From"] = sender
        msg["To"] = receiver

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)

        st.success("📧 Günlük özet e-posta başarıyla gönderildi!")
    except:
        st.warning("E-posta gönderilemedi. Ortam değişkenlerini kontrol edin.")

if st.button("📨 Günlük Özet Mail Gönder"):
    send_summary_email()

st.caption(f"Veriler 60 saniyede bir otomatik olarak güncellenir. Son güncelleme: {zaman}")
