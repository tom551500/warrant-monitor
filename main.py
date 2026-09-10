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


def scrape_wantgoo_data():
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

        for stk, name, target_branch in WATCH_LIST:
            url = f"https://www.wantgoo.com/stock/{stk}/major-investors/broker-yield"
            try:
                print(f"正在載入 {name} ({stk}) 玩股網頁面...")
                page.goto(url, timeout=30000, wait_until="load")

                # 緩衝 5 秒，給予 JavaScript 足夠時間完成數據渲染
                page.wait_for_timeout(5000)

                html_content = page.content()
                matched_records = []

                # 1. 嘗試由 Pandas 解析 HTML 表格
                try:
                    dfs = pd.read_html(html_content)
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
                except Exception:
                    pass

                # 2. 若未抓到表格，直接自網頁全文萃取包含目標分點的文字行
                if not matched_records:
                    lines = page.inner_text("body").split("\n")
                    for line in lines:
                        if target_branch in line and len(line.strip()) > 2:
                            matched_records.append(line.strip())

                results[(stk, name, target_branch)] = (True, matched_records)

            except Exception as e:
                err_brief = str(e).split("\n")[0][:50]
                results[(stk, name, target_branch)] = (
                    False,
                    f"連線失敗: {err_brief}",
                )

        browser.close()

    return results


def main():
    today = datetime.date.today().strftime("%Y/%m/%d")
    report_lines = [f"🎯 *指定關鍵分點買賣監控日報 ({today})*\n"]

    scan_results = scrape_wantgoo_data()

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
            report_lines.append(f"⚠️ *【{name} ({stk})】*：{data}\n")

    final_msg = "\n".join(report_lines)
    send_telegram(final_msg)


if __name__ == "__main__":
    main()
