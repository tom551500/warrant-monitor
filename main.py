import datetime
import os
import pandas as pd
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# =================【關鍵分點監控清單】=================
# 格式：("股票代碼", "股票名稱", "目標分點關鍵字", "分點代碼(選填)")
# 只要該分點今天有買進或賣出 1 張以上，就會被完整抓出！
WATCH_LIST = [
    ("2427", "聚亨", "台新-高雄", "9217"),  # 台新高雄券商代碼為 9217
    ("6223", "旺矽", "凱基-台北", "9200"),
]
# =======================================================


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, data=payload)


def get_official_full_broker_data(stk, date_roc, date_ad):
    """直接向證交所/櫃買中心取得『全分點』進出明細 (非前幾大排行榜)"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
    }

    # 免費代理伺服器 (繞過 GitHub Actions 美國 IP 阻擋)
    proxies = {
        "http": "http://103.152.112.162:80",
        "https": "http://103.152.112.162:80",
    }

    # 1. 先查櫃買中心 (TPEx 上櫃) 全分點日報
    tpex_url = f"https://www.tpex.org.tw/www/zh-tw/afterTrading/brokerBS?response=json&date={date_roc}&stk={stk}"
    try:
        res = requests.get(
            tpex_url, headers=headers, timeout=10, proxies=proxies
        )
        if res.status_code == 200:
            data = res.json()
            if "tables" in data and data["tables"]:
                raw_data = data["tables"][0]["data"]
                df = pd.DataFrame(
                    raw_data,
                    columns=[
                        "名次",
                        "分點代碼名稱",
                        "買進張數",
                        "賣出張數",
                        "淨買賣",
                    ],
                )
                return df, "上櫃"
    except Exception:
        pass

    # 2. 若非上櫃，則查證交所 (TWSE 上市) 全分點日報
    twse_url = f"https://www.twse.com.tw/rwd/zh/afterTrading/BSR510?response=json&date={date_ad}&stockNo={stk}"
    try:
        res = requests.get(
            twse_url, headers=headers, timeout=10, proxies=proxies
        )
        if res.status_code == 200:
            data = res.json()
            if "data" in data and data["data"]:
                df = pd.DataFrame(
                    data["data"],
                    columns=[
                        "名次",
                        "分點代碼名稱",
                        "買進張數",
                        "賣出張數",
                        "淨買賣",
                    ],
                )
                return df, "上市"
    except Exception:
        pass

    return None, "未知"


def main():
    today = datetime.date.today()
    roc_year = today.year - 1911
    date_roc = f"{roc_year}/{today.strftime('%m/%d')}"  # 115/09/10
    date_ad = today.strftime("%Y%m%d")  # 20260910

    report_lines = [f"🎯 *全分點精確買賣監控日報 ({date_roc})*\n"]

    for stk, name, target_branch, branch_code in WATCH_LIST:
        df, market_type = get_official_full_broker_data(
            stk, date_roc, date_ad
        )

        if df is not None and not df.empty:
            # 清洗張數欄位
            df["買進張數"] = (
                df["買進張數"].astype(str).str.replace(",", "").astype(float)
            )
            df["賣出張數"] = (
                df["賣出張數"].astype(str).str.replace(",", "").astype(float)
            )
            df["淨買超張數"] = df["買進張數"] - df["賣出張數"]

            # 比對分點名稱或分點代碼 (全方位搜尋)
            matched = df[
                (df["分點代碼名稱"].str.contains(target_branch))
                | (df["分點代碼名稱"].str.contains(branch_code))
            ]

            if not matched.empty:
                report_lines.append(f"📌 *【{name} ({stk}) - {market_type}】*")
                for _, row in matched.iterrows():
                    b_name = row["分點代碼名稱"].strip()
                    buy_cnt = int(row["買進張數"])
                    sell_cnt = int(row["賣出張數"])
                    net_cnt = int(row["淨買超張數"])

                    if net_cnt > 0:
                        status = f"🟢 淨買超 `{net_cnt}` 張"
                    elif net_cnt < 0:
                        status = f"🔴 淨賣超 `{abs(net_cnt)}` 張"
                    else:
                        status = "⚪ 當日買賣平衡 (買賣張數相等)"

                    report_lines.append(f"  🏢 經紀分點：`{b_name}`")
                    report_lines.append(
                        f"  ├ 買進：`{buy_cnt}` 張 | 賣出：`{sell_cnt}` 張"
                    )
                    report_lines.append(f"  └ 結論：{status}\n")
            else:
                report_lines.append(
                    f"⚪ *【{name} ({stk})】*：官方數據顯示，分點 `{target_branch}` 今日**完全無任何買賣紀錄**。\n"
                )
        else:
            report_lines.append(
                f"⚠️ *【{name} ({stk})】*：無法連線至證交所/櫃買中心官方伺服器，或今日非交易日。\n"
            )

    final_msg = "\n".join(report_lines)
    send_telegram(final_msg)


if __name__ == "__main__":
    main()
