from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import re

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TARGET_URL = "https://myfate.herokuapp.com/"

@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Bazi Proxy API (Targeted Exact Field Parser)",
        "source": "https://myfate.herokuapp.com/"
    }

@app.get("/api/bazi")
def get_bazi(year: int, month: int, day: int, hour: int, gender: str = "女"):
    """
    精確比對 myfate.herokuapp.com 表單標籤:
    - action: "/"
    - Calendar: 1 (陽曆) 或 0 (農曆)
    - Sex: 1 (男) 或 0 (女)
    - Year: 匹配 <select name="Year"> 的 option 值
    - Month: 匹配 <select name="Month"> 的 option 值
    - Day: 匹配 <select name="Day"> 的 option 值
    - Hour: 匹配 <select name="Hour"> 的 option 值
    """
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": TARGET_URL
        }
        
        # 1. 抓取首頁提取真實下拉選項的值 (精確保證 100% 吻合)
        home_res = session.get(TARGET_URL, headers=headers, timeout=10)
        soup = BeautifulSoup(home_res.text, "html.parser")
        
        # 2. 取得 Year 的 option 值
        year_select = soup.find("select", {"name": "Year"}) or soup.find("select", {"id": "Year"})
        selected_year_val = None
        if year_select:
            for opt in year_select.find_all("option"):
                txt = opt.text.strip()
                val = opt.get("value", txt)
                # 比對西元或民國
                if f"西元{year}" in txt or f"西元 {year}" in txt or str(year) in txt or val == str(year):
                    selected_year_val = val
                    break
        if not selected_year_val:
            # 備用計算格式
            m = year - 1911 if year >= 1912 else 1912 - year
            prefix = "民國" if year >= 1912 else "民前"
            selected_year_val = f"{prefix} {m} (西元{year})"

        # 3. 取得 Month 的 option 值
        month_select = soup.find("select", {"name": "Month"}) or soup.find("select", {"id": "Month"})
        selected_month_val = str(month)
        if month_select:
            for opt in month_select.find_all("option"):
                txt = opt.text.strip()
                val = opt.get("value", txt)
                if txt == str(month) or val == str(month):
                    selected_month_val = val
                    break

        # 4. 取得 Day 的 option 值
        day_select = soup.find("select", {"name": "Day"}) or soup.find("select", {"id": "Day"})
        selected_day_val = str(day)
        if day_select:
            for opt in day_select.find_all("option"):
                txt = opt.text.strip()
                val = opt.get("value", txt)
                if txt == str(day) or val == str(day):
                    selected_day_val = val
                    break

        # 5. 取得 Hour 的 option 值
        hour_select = soup.find("select", {"name": "Hour"}) or soup.find("select", {"id": "Hour"})
        selected_hour_val = None
        if hour_select:
            opts = hour_select.find_all("option")
            # 依時辰索引直接取第 hour 個 option
            if 0 <= hour < len(opts):
                selected_hour_val = opts[hour].get("value", opts[hour].text.strip())
            else:
                for opt in opts:
                    txt = opt.text.strip()
                    if f"{hour}點" in txt or f"{hour}時" in txt or opt.get("value") == str(hour):
                        selected_hour_val = opt.get("value", txt)
                        break

        # 6. 精確組裝 POST 表單 Payload
        payload = {
            "Calendar": "1",  # 1 = 陽曆
            "Sex": "1" if gender in ["男", "乾造"] else "0", # 1 = 男, 0 = 女
            "Year": selected_year_val,
            "Month": selected_month_val,
            "Day": selected_day_val,
            "Hour": selected_hour_val
        }

        # 7. POST 回原網站首頁 action="/"
        resp = session.post(TARGET_URL, data=payload, headers=headers, timeout=12)
        
        # 8. 解析傳回的 HTML
        res_soup = BeautifulSoup(resp.text, "html.parser")
        for tag in res_soup.find_all(["script", "style"]):
            tag.decompose()

        # 尋找命盤表格或結果
        chart_div = None
        for table in res_soup.find_all("table"):
            if "八字" in table.text or "主星" in table.text or "日主" in table.text:
                chart_div = table.parent
                break
        if not chart_div:
            # 若包含 error 提示或無結果
            chart_div = res_soup.find("div", class_="result-container") or res_soup.find("form") or res_soup.find("body")

        return {
            "status": "success",
            "source": "https://myfate.herokuapp.com/",
            "submitted_payload": payload,
            "html": str(chart_div)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
