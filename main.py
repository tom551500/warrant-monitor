import datetime
import os
import pandas as pd
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# =================【關鍵分點監控清單】=================
# 格式：[("股票代碼", "股票名稱", "目標分點關鍵字")]
# 關鍵字支援模糊比對（如填寫 "台新" 或 "台新-高雄" 都搜得到）
WATCH_LIST = [
    ("2427", "聚亨", "台新"),  # 監控 聚亨 的 台新分點 (含台新高雄)
    ("6223", "旺矽", "凱基-台北"),  # 範例：監控 旺矽 的 凱基台北
    # 可在此自由新增更多標的：
    # ("個股代碼", "個股名稱", "分點關鍵字"),
]
# =======================================================


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, data=payload)


def fetch_broker_data(stk, date_roc):
    """向櫃買/證交所 API 讀取分點明細"""
    # 櫃買中心 (上櫃) API
    url_tpex = f"https://www.tpex.org.tw/web/stock/aftertrading/broker_trading/brokerBS_result.php?l=zh-tw&d={date_roc}&stk={stk}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.tpex.org.tw/",
    }

    try:
        res = requests.get(url_tpex, headers=headers, timeout=10)
        if res.status_code == 200 and res.text.strip().startswith("{"):
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
                df["買進張數"] = (
                    df["買進張數"].str.replace(",", "").astype(float)
                )
                df["賣出張數"] = (
                    df["賣出張數"].str.replace(",", "").astype(float)
                )
                df["淨買超張數"] = df["買進張數"] - df["賣出張數"]
                return df
    except Exception as e:
        print(f"抓取 {stk} 失敗: {e}")

    return None


def main():
    today = datetime.date.today()
    roc_year = today.year - 1911
    date_roc = f"{roc_year}/{today.strftime('%m/%d')}"

    report_lines = [f"🎯 *指定關鍵分點買賣監控日報 ({date_roc})*\n"]

    for stk, name, target_branch in WATCH_LIST:
        df = fetch_broker_data(stk, date_roc)

        if df is not None and not df.empty:
            # 使用關鍵字搜尋目標分點（例如: "台新"）
            matched = df[df["分點代碼名稱"].str.contains(target_branch)]

            if not matched.empty:
                report_lines.append(f"📌 *【{name} ({stk})】*")
                for _, row in matched.iterrows():
                    b_name = row["分點代碼名稱"]
                    buy_cnt = int(row["買進張數"])
                    sell_cnt = int(row["賣出張數"])
                    net_cnt = int(row["淨買超張數"])

                    # 判斷買超或賣超圖示
                    signal = "🟢 買超" if net_cnt > 0 else "🔴 賣超"
                    if net_cnt == 0:
                        signal = "⚪ 平衡"

                    report_lines.append(f"  🏢 分點：`{b_name}`")
                    report_lines.append(
                        f"  ├ 買進：`{buy_cnt}` 張 | 賣出：`{sell_cnt}` 張"
                    )
                    report_lines.append(
                        f"  └ 動向：{signal} `{abs(net_cnt)}` 張\n"
                    )
            else:
                report_lines.append(
                    f"⚪ *【{name} ({stk})】*：分點 `{target_branch}` 今日無進出紀錄\n"
                )
        else:
            report_lines.append(
                f"⚠️ *【{name} ({stk})】*：今日查無交易明細（若為上市股票需改接 TWSE 介面）\n"
            )

    final_msg = "\n".join(report_lines)
    send_telegram(final_msg)


if __name__ == "__main__":
    main()
