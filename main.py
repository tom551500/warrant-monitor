import datetime
import os
import re
import pandas as pd
import requests
from playwright.sync_api import sync_playwright

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# =================【關鍵分點監控清單】=================
# 格式：[("股票代碼", "股票名稱", ["主關鍵字", "備用關鍵字"])]
WATCH_LIST = [
    ("2427", "聚亨", ["台新-高雄", "台新高雄", "台新"]),
    ("6223", "旺矽", ["凱基-台北", "凱基台北", "凱基"]),
]
# =======================================================


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, data=payload)


def parse_branch_row(line, keywords):
    """從網頁文字行中萃取分點名稱與買賣張數"""
    for kw in keywords:
        if kw in line:
            # 尋找行內的數字 (包含正負數)
            numbers = re.findall(r"-?\d+(?:,\d+)*", line)
            if numbers:
                clean_nums = [int(n.replace(",", "")) for n in numbers]
                return kw, clean_nums
    return None, None


def scrape_broker_data():
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

        for stk, name, keywords in WATCH_LIST:
            url = f"https://www.wantgoo.com/stock/{stk}/major-investors/broker-yield"
            try:
                print(f"正在分析 {name} ({stk}) 地緣分點...")
                page.goto(url, timeout=30000, wait_until="load")
                page.wait_for_timeout(6000)  # 等待 AJAX 籌碼數據完全載入

                html_content = page.content()
                found_match = False
                matched_details = []

                # 1. 優先嘗試 Pandas 表格解析
                try:
                    dfs = pd.read_html(html_content)
                    for df in dfs:
                        df_str = df.astype(str)
                        for _, row in df_str.iterrows():
                            row_text = " ".join(row.values)
                            for kw in keywords:
                                if kw in row_text:
                                    clean_row = [
                                        v.strip()
                                        for v in row.values
                                        if v != "nan"
                                        and v != "None"
                                        and v.strip()
                                    ]
                                    matched_details.append(
                                        " | ".join(clean_row)
                                    )
                                    found_match = True
                                    break
                except Exception:
                    pass

                # 2. 備用文字行深度萃取
                if not found_match:
                    lines = page.inner_text("body").split("\n")
                    for line in lines:
                        for kw in keywords:
                            if kw in line and len(line.strip()) > 3:
                                matched_details.append(line.strip())
                                found_match = True
                                break

                results[(stk, name, keywords[0])] = (True, matched_details)

            except Exception as e:
                err_brief = str(e).split("\n")[0][:40]
                results[(stk, name, keywords[0])] = (
                    False,
                    f"連線失敗: {err_brief}",
                )

        browser.close()

    return results


def main():
    today = datetime.date.today().strftime("%Y/%m/%d")
    report_lines = [f"🎯 *地緣關鍵分點監控日報 ({today})*\n"]

    scan_results = scrape_broker_data()

    for (stk, name, target_kw), (success, data) in scan_results.items():
        if success:
            if data:
                report_lines.append(f"📌 *【{name} ({stk})】*")
                seen = set()
                for item in data:
                    if item not in seen:
                        seen.add(item)
                        report_lines.append(f"  🏢 地緣分點明細：`{item}`")
                report_lines.append("")
            else:
                report_lines.append(
                    f"⚪ *【{name} ({stk})】*：地緣分點 `{target_kw}` 今日未入前幾大進出榜\n"
                )
        else:
            report_lines.append(f"⚠️ *【{name} ({stk})】*：{data}\n")

    final_msg = "\n".join(report_lines)
    send_telegram(final_msg)


if __name__ == "__main__":
    main()
