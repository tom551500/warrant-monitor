import datetime
import os
import pandas as pd
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

# =================【關鍵分點監控清單】=================
# 格式：[("股票代碼", "股票名稱", "目標分點關鍵字")]
WATCH_LIST = [
    ("2427", "聚亨", "台新"),  # 聚亨 (上市) -> 監控台新/台新高雄
    ("6223", "旺矽", "凱基"),  # 旺矽 (上櫃) -> 監控凱基分點
]
# =======================================================


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, data=payload)


def get_branch_info(stk, target_branch):
    """從 HiStock 嗨投資抓取上市/上櫃個股當日分點明細，繞過官網 IP 封鎖"""
    url = f"https://histock.tw/stock/branch.aspx?no={stk}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code == 200:
            # 讀取 HTML 中所有表格
            tables = pd.read_html(res.text)
            results = []

            for df in tables:
                df.columns = [str(c) for c in df.columns]

                for idx, row in df.iterrows():
                    row_vals = [str(val) for val in row.values]
                    row_text = " ".join(row_vals)

                    # 若該列包含目標分點關鍵字 (如: 台新)
                    if target_branch in row_text:
                        results.append(row_vals)

            return results
    except Exception as e:
        print(f"抓取 {stk} 失敗: {e}")
    return None


def main():
    today = datetime.date.today().strftime("%Y/%m/%d")
    report_lines = [f"🎯 *指定關鍵分點買賣監控日報 ({today})*\n"]

    for stk, name, target_branch in WATCH_LIST:
        records = get_branch_info(stk, target_branch)

        if records:
            report_lines.append(f"📌 *【{name} ({stk})】*")
            seen = set()
            for rec in records:
                clean_rec = [
                    x for x in rec if x != "nan" and x != "None" and x.strip()
                ]
                rec_str = " | ".join(clean_rec)
                if rec_str not in seen:
                    seen.add(rec_str)
                    report_lines.append(f"  🏢 找到分點數據：`{rec_str}`")
            report_lines.append("")
        elif records == []:
            report_lines.append(
                f"⚪ *【{name} ({stk})】*：分點 `{target_branch}` 今日未入前幾大進出榜\n"
            )
        else:
            report_lines.append(f"⚠️ *【{name} ({stk})】*：連線數據讀取失敗\n")

    final_msg = "\n".join(report_lines)
    send_telegram(final_msg)


if __name__ == "__main__":
    main()
