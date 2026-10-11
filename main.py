from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
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
        "service": "Bazi Proxy API",
        "source": "https://myfate.herokuapp.com/",
        "debug_url": "/debug-form"
    }

@app.get("/debug-form", response_class=HTMLResponse)
def debug_form():
    """
    直接回傳 myfate 首頁的原始 <form> HTML，方便立刻查看原網站所有欄位與按鈕名稱
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = requests.get(TARGET_URL, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        form = soup.find("form")
        if form:
            return f"<html><body><h3>原網站 Form 原始碼：</h3><pre>{BeautifulSoup(str(form), 'html.parser').prettify()}</pre></body></html>"
        return "<html><body>未找到 form 標籤</body></html>"
    except Exception as e:
        return f"<html><body>Error: {str(e)}</body></html>"

@app.get("/api/bazi")
def get_bazi(year: int, month: int, day: int, hour: int, gender: str = "女"):
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": TARGET_URL
        }
        
        # 1. 抓取首頁
        home_res = session.get(TARGET_URL, headers=headers, timeout=10)
        soup = BeautifulSoup(home_res.text, "html.parser")
        form = soup.find("form")
        
        action_url = TARGET_URL
        if form and form.get("action"):
            act = form.get("action")
            action_url = act if act.startswith("http") else TARGET_URL.rstrip("/") + "/" + act.lstrip("/")

        # 2. 自動分析表單中所有預設值
        payload = {}
        
        # 加入所有 hidden 輸入
        for h in soup.find_all("input", type="hidden"):
            if h.get("name"):
                payload[h.get("name")] = h.get("value", "")

        # 處理 Year
        year_select = soup.find("select", {"name": "Year"}) or soup.find("select", {"id": "Year"})
        selected_year_val = None
        if year_select:
            for opt in year_select.find_all("option"):
                txt = opt.text.strip()
                val = opt.get("value", txt)
                if f"西元{year}" in txt or f"西元 {year}" in txt or str(year) in txt or val == str(year):
                    selected_year_val = val
                    break
        if not selected_year_val:
            m = year - 1911 if year >= 1912 else 1912 - year
            prefix = "民國" if year >= 1912 else "民前"
            selected_year_val = f"{prefix} {m} (西元{year})"

        # 處理 Month
        month_select = soup.find("select", {"name": "Month"}) or soup.find("select", {"id": "Month"})
        selected_month_val = str(month)
        if month_select:
            for opt in month_select.find_all("option"):
                txt = opt.text.strip()
                val = opt.get("value", txt)
                if txt == str(month) or val == str(month):
                    selected_month_val = val
                    break

        # 處理 Day
        day_select = soup.find("select", {"name": "Day"}) or soup.find("select", {"id": "Day"})
        selected_day_val = str(day)
        if day_select:
            for opt in day_select.find_all("option"):
                txt = opt.text.strip()
                val = opt.get("value", txt)
                if txt == str(day) or val == str(day):
                    selected_day_val = val
                    break

        # 處理 Hour
        hour_select = soup.find("select", {"name": "Hour"}) or soup.find("select", {"id": "Hour"})
        selected_hour_val = None
        if hour_select:
            opts = hour_select.find_all("option")
            if 0 <= hour < len(opts):
                selected_hour_val = opts[hour].get("value", opts[hour].text.strip())
            else:
                for opt in opts:
                    txt = opt.text.strip()
                    if f"{hour}點" in txt or f"{hour}時" in txt or opt.get("value") == str(hour):
                        selected_hour_val = opt.get("value", txt)
                        break

        # 填入標準表單欄位
        payload["Calendar"] = "1" # 陽曆
        payload["Sex"] = "1" if gender in ["男", "乾造"] else "0"
        payload["Year"] = selected_year_val
        payload["Month"] = selected_month_val
        payload["Day"] = selected_day_val
        payload["Hour"] = selected_hour_val
        
        # 尋找提交按鈕 (如果有 name/value)
        submit_btn = soup.find("button", type="submit") or soup.find("input", type="submit")
        if submit_btn and submit_btn.get("name"):
            payload[submit_btn.get("name")] = submit_btn.get("value", "命盤分析")
        else:
            payload["submit"] = "命盤分析"

        # 3. 發送 POST 請求
        resp = session.post(action_url, data=payload, headers=headers, timeout=12)
        
        # 4. 解析傳回的 HTML
        res_soup = BeautifulSoup(resp.text, "html.parser")
        for tag in res_soup.find_all(["script", "style"]):
            tag.decompose()

        chart_div = None
        for table in res_soup.find_all("table"):
            if "八字" in table.text or "主星" in table.text or "日主" in table.text:
                chart_div = table.parent
                break
        if not chart_div:
            chart_div = res_soup.find("div", class_="result-container") or res_soup.find("form") or res_soup.find("body")

        return {
            "status": "success",
            "source": "https://myfate.herokuapp.com/",
            "submitted_payload": payload,
            "html": str(chart_div)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
