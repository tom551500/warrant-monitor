import datetime
import os
import re
import pandas as pd
import requests
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# =================【關鍵分點監控清單】=================
# 格式：[("股票代碼", "股票名稱", "目標分點關鍵字", "市場類別上市/上櫃")]
# 只要該分點今天有買進或賣出 1 張以上，就能完整捕捉！
WATCH_LIST = [
    ("2427", "聚亨", "台新", "上市"),  # 聚亨 (2427) -> 監控台新/台新高雄
    ("6223", "旺矽", "凱基", "上櫃"),  # 旺矽 (6223) -> 監控凱基分點
]
# =======================================================


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, data=payload)


def fetch_official_full_data():
    results = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="zh-TW",
        )
        page = context.new_page()

        for stk, name, target_branch, market in WATCH_LIST:
            try:
                print(f"正在向官方查詢 {name} ({stk}) 全分點資料...")

                if market == "上市":
                    # 證交所官方 BSR510 全分點查詢
                    url = f"https://www.twse.com.tw/zh/trading/historical/bsr510.html"
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)

                    # 輸入股票代碼並查詢
                    page.fill("input[name='stkNo']", stk)
                    page.click("button.submit", timeout=5000)
                    page.wait_for_timeout(4000)

                else:
                    # 櫃買中心官方 brokerBS 全分點查詢
                    url = f"https://www.tpex.org.tw/web/stock/aftertrading/broker_trading/brokerBS.php?l=zh-tw"
                    page.goto(url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)

                    page.fill("input[name='stk_code']", stk)
                    page.click("button.btn-submit", timeout=5000)
                    page.wait_for_timeout(4000)

                html_content = page.content()
                dfs = pd.read_html(html_content)

                matched_records = []
                for df in dfs:
                    df_str = df.astype(str)
                    for _, row in df_str.iterrows():
                        row_text = " ".join(row.values)
                        if target_branch in row_text:
                            clean_row = [
                                v.strip()
                                for v in row.values
                                if v != "nan" and v != "None" and v.strip()
                            ]
                            matched_records.append(" | ".join(clean_row))

                results[(stk, name, target_branch)] = (True, matched_records)

            except Exception as e:
                err_brief = str(e).split("\n")[0][:40]
                results[(stk, name, target_branch)] = (
                    False,
                    f"官方頁面載入失敗: {err_brief}",
                )

        browser.close()

    return results


def main():
    today = datetime.date.today().strftime("%Y/%m/%d")
    report_lines = [f"🎯 *全分點官方買賣監控日報 ({today})*\n"]

    scan_results = fetch_official_full_data()

    for (stk, name, target_branch), (success, data) in scan_results.items():
        if success:
            if data:
                report_lines.append(f"📌 *【{name} ({stk})】*")
                seen = set()
                for rec in data:
                    if rec not in seen:
                        seen.add(rec)
                        report_lines.append(f"  🏢 經紀分點進出：`{rec}`")
                report_lines.append("")
            else:
                report_lines.append(
                    f"⚪ *【{name} ({stk})】*：官方全分點明細顯示，分點 `{target_branch}` 今日**完全無買賣紀錄**（連 1 張都沒有）。\n"
                )
        else:
            report_lines.append(f"⚠️ *【{name} ({stk})】*：{data}\n")

    final_msg = "\n".join(report_lines)
    send_telegram(final_msg)


if __name__ == "__main__":
    main()
