import datetime
import os
import pandas as pd
import requests
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# =================【關鍵分點監控清單】=================
# 格式：[("股票代碼", "股票名稱", "目標分點關鍵字")]
WATCH_LIST = [
    ("2427", "聚亨", "台新"),  # 聚亨 -> 監控台新 (含台新高雄)
    ("6223", "旺矽", "凱基"),  # 旺矽 -> 監控凱基分點
]
# =======================================================


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, data=payload)


def scrape_branch_data():
    results = {}

    with sync_playwright() as p:
        # 啟動 Chrome 並阻擋廣告圖片載入以加速
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        for stk, name, target_branch in WATCH_LIST:
            url = f"https://histock.tw/stock/branch.aspx?no={stk}"
            try:
                print(f"正在載入 {name} ({stk}) 分點頁面...")
                # 關鍵修正：僅等待 HTML 結構載入，不等待廣告封包
                page.goto(url, timeout=20000, wait_until="domcontentloaded")

                # 強制等待分點表格出現 (最多等 5 秒)
                page.wait_for_selector("table", timeout=5000)

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
                err_msg = str(e).split("\n")[0]  # 取得首行簡短錯誤訊息
                print(f"抓取 {stk} 失敗: {err_msg}")
                results[(stk, name, target_branch)] = (False, err_msg)

        browser.close()

    return results


def main():
    today = datetime.date.today().strftime("%Y/%m/%d")
    report_lines = [f"🎯 *指定關鍵分點買賣監控日報 ({today})*\n"]

    scan_results = scrape_branch_data()

    for (stk, name, target_branch), (success, data) in scan_results.items():
        if success:
            if data:
                report_lines.append(f"📌 *【{name} ({stk})】*")
                seen = set()
                for rec in data:
                    if rec not in seen:
                        seen.add(rec)
                        report_lines.append(f"  🏢 分點數據：`{rec}`")
                report_lines.append("")
            else:
                report_lines.append(
                    f"⚪ *【{name} ({stk})】*：分點 `{target_branch}` 今日未入前幾大進出榜\n"
                )
        else:
            report_lines.append(
                f"⚠️ *【{name} ({stk})】*：連線失敗 (`{data}`)\n"
            )

    final_msg = "\n".join(report_lines)
    send_telegram(final_msg)


if __name__ == "__main__":
    main()
