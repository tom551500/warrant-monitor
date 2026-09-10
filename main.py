import datetime
import os
import pandas as pd
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
MARKET_MAKERS = ["9800", "1480", "9200", "5850", "8880", "7000"]


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}

    res = requests.post(url, data=payload)
    print(f"Telegram 推播狀態碼: {res.status_code}")

    if res.status_code != 200:
        print(f"❌ Telegram 發送失敗，回應內容: {res.text}")
    else:
        print("✅ Telegram 訊息發送成功！")


def main():
    # 自動轉為民國年格式 (例如: 115/09/08)
    today = datetime.date.today()
    roc_year = today.year - 1911
    date_roc = f"{roc_year}/{today.strftime('%m/%d')}"

    target_warrants = ["030001", "030002"]
    report_lines = [f"📊 *權證主力籌碼測試日報 ({date_roc})*\n"]

    for stk in target_warrants:
        url = f"https://www.tpex.org.tw/web/stock/aftertrading/broker_trading/brokerBS_result.php?l=zh-tw&d={date_roc}&stk={stk}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            res = requests.get(url, headers=headers, timeout=10)
            if res.status_code == 200 and res.text.startswith("{"):
                data = res.json()
                if "aaData" in data and data["aaData"]:
                    df = pd.DataFrame(
                        data["aaData"],
                        columns=[
                            "名次",
                            "分點代碼名稱",
                            "買進張數",
                            "賣出張數",
                            "淨買賣",
                        ],
                    )
                    df["分點代碼"] = df["分點代碼名稱"].str.extract(
                        r"(\d{4})"
                    )
                    df["買進張數"] = (
                        df["買進張數"].str.replace(",", "").astype(float)
                    )
                    df["賣出張數"] = (
                        df["賣出張數"].str.replace(",", "").astype(float)
                    )
                    df["淨買超張數"] = df["買進張數"] - df["賣出張數"]

                    clean_df = df[~df["分點代碼"].isin(MARKET_MAKERS)]
                    top_buy = clean_df.sort_values(
                        by="淨買超張數", ascending=False
                    ).head(1)

                    if not top_buy.empty:
                        row = top_buy.iloc[0]
                        report_lines.append(
                            f"🔹 *權證 {stk}*"
                            f"\n  └ 買超第一：{row['分點代碼名稱']}"
                            f"\n  └ 淨買超：`{int(row['淨買超張數'])}` 張\n"
                        )
        except Exception as e:
            print(f"抓取 {stk} 失敗: {e}")

    final_msg = (
        "\n".join(report_lines)
        if len(report_lines) > 1
        else f"⚠️ 權證系統測試中 ({date_roc})：今日查無資料或為非交易日。"
    )

    send_telegram(final_msg)


if __name__ == "__main__":
    main()
