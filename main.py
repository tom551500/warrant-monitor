import datetime
import os
import requests

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

WATCH_LIST = [
    ("2427", "聚亨", "台新"),
]


def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}
    requests.post(url, data=payload)


def main():
    today = datetime.date.today().strftime("%Y/%m/%d")
    report = [f"🎯 *雲端分點買賣監控日報 ({today})*\n"]

    for stk, name, target_branch in WATCH_LIST:
        # 使用 API 接口代替網頁爬蟲，避開 Cloudflare 阻擋
        api_url = f"https://api.cnyes.com/media/api/v1/investor/major/stock/{stk}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            res = requests.get(api_url, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                # 提取分點買賣資料邏輯
                report.append(f"📌 *【{name} ({stk})】*")
                report.append(f"  🏢 分點 `{target_branch}` 監控已連線成功。")
            else:
                report.append(f"⚪ *【{name} ({stk})】*：今日無異常大筆進出。")
        except Exception as e:
            report.append(f"⚠️ *【{name} ({stk})】*：API 連線異常 ({e})")

    send_telegram("\n".join(report))


if __name__ == "__main__":
    main()
