from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup

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
        "version": "2.1",
        "service": "Bazi Proxy API",
        "source": "https://myfate.herokuapp.com/",
        "debug_url": "/debug-form"
    }

@app.get("/debug-form", response_class=HTMLResponse)
def debug_form():
    """在瀏覽器呈現 myfate 原網站的表單欄位與當前連線狀態"""
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = session.get(TARGET_URL, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        form = soup.find("form")
        form_html = form.prettify() if form else "未找到 form 標籤"
        
        return f"""
        <html>
        <head><meta charset="utf-8"><title>Bazi Proxy Debug Form</title></head>
        <body style="font-family:sans-serif; padding:20px; line-height:1.6;">
            <h2>✅ Render Proxy 伺服器在線 (版本 v2.1)</h2>
            <p>目標來源：<a href="{TARGET_URL}" target="_blank">{TARGET_URL}</a></p>
            <hr/>
            <h3>原網站 Form 標籤與欄位：</h3>
            <pre style="background:#f4f4f4; padding:15px; border-radius:6px; overflow:auto; max-height:500px;">{form_html}</pre>
            <hr/>
            <p><a href="/api/bazi?year=1975&month=7&day=28&hour=16&gender=女">👉 點此直接測試 1975-07-28 16時 女 (API)</a></p>
        </body>
        </html>
        """
    except Exception as e:
        return f"<html><body><h3>連線失敗：</h3><pre>{str(e)}</pre></body></html>"

@app.get("/api/bazi")
def get_bazi(year: int, month: int, day: int, hour: int, gender: str = "女"):
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": TARGET_URL,
            "Origin": TARGET_URL.rstrip("/")
        }
        
        # 1. 抓取首頁解析原始表單
        home_res = session.get(TARGET_URL, headers=headers, timeout=12)
        soup = BeautifulSoup(home_res.text, "html.parser")
        form = soup.find("form")
        
        action_url = TARGET_URL
        if form and form.get("action"):
            act = form.get("action")
            action_url = act if act.startswith("http") else TARGET_URL.rstrip("/") + "/" + act.lstrip("/")

        payload = {}
        
        # 抓取所有 hidden 欄位 (包含 CSRF 或 session token)
        for h in soup.find_all("input", type="hidden"):
            if h.get("name"):
                payload[h.get("name")] = h.get("value", "")

        # 曆法 Calendar (預設 陽曆)
        cal_val = "1"
        for r in soup.find_all("input", {"type": "radio", "name": "Calendar"}):
            parent_text = r.parent.text if r.parent else ""
            if "陽" in parent_text or r.get("value") == "1":
                cal_val = r.get("value", "1")
                break
        payload["Calendar"] = cal_val

        # 性別 Sex
        target_sex_name = "男" if gender in ["男", "乾造", "1"] else "女"
        sex_val = "1" if target_sex_name == "男" else "0"
        for r in soup.find_all("input", {"type": "radio", "name": "Sex"}):
            parent_text = r.parent.text if r.parent else ""
            if target_sex_name in parent_text:
                sex_val = r.get("value", sex_val)
                break
        payload["Sex"] = sex_val

        # 年份 Year (動態精確比對原網站 option)
        year_select = soup.find("select", {"name": "Year"}) or soup.find("select", {"id": "Year"})
        selected_year_val = None
        if year_select:
            for opt in year_select.find_all("option"):
                txt = opt.text.strip()
                val = opt.get("value") if opt.has_attr("value") else txt
                if f"西元{year}" in txt or f"西元 {year}" in txt or f"({year})" in txt or txt == str(year) or val == str(year):
                    selected_year_val = val
                    break
        if not selected_year_val:
            m = year - 1911 if year >= 1912 else 1912 - year
            prefix = "民國" if year >= 1912 else "民前"
            selected_year_val = f"{prefix}{m} (西元{year})"
        payload["Year"] = selected_year_val

        # 月份 Month
        month_select = soup.find("select", {"name": "Month"}) or soup.find("select", {"id": "Month"})
        selected_month_val = str(month)
        if month_select:
            for opt in month_select.find_all("option"):
                txt = opt.text.strip()
                val = opt.get("value") if opt.has_attr("value") else txt
                if txt == str(month) or val == str(month):
                    selected_month_val = val
                    break
        payload["Month"] = selected_month_val

        # 日期 Day
        day_select = soup.find("select", {"name": "Day"}) or soup.find("select", {"id": "Day"})
        selected_day_val = str(day)
        if day_select:
            for opt in day_select.find_all("option"):
                txt = opt.text.strip()
                val = opt.get("value") if opt.has_attr("value") else txt
                if txt == str(day) or val == str(day):
                    selected_day_val = val
                    break
        payload["Day"] = selected_day_val

        # 時辰 Hour
        hour_select = soup.find("select", {"name": "Hour"}) or soup.find("select", {"id": "Hour"})
        selected_hour_val = str(hour)
        if hour_select:
            opts = hour_select.find_all("option")
            if 0 <= hour < len(opts):
                selected_hour_val = opts[hour].get("value") if opts[hour].has_attr("value") else opts[hour].text.strip()
            else:
                for opt in opts:
                    txt = opt.text.strip()
                    val = opt.get("value") if opt.has_attr("value") else txt
                    if f"{hour}點" in txt or val == str(hour):
                        selected_hour_val = val
                        break
        payload["Hour"] = selected_hour_val
        
        # 提交按鈕：僅在帶有 name 屬性時附帶
        submit_btn = soup.find("button", type="submit") or soup.find("input", type="submit")
        if submit_btn and submit_btn.get("name"):
            payload[submit_btn.get("name")] = submit_btn.get("value", "命盤分析")

        # 2. 發送 POST 請求
        resp = session.post(action_url, data=payload, headers=headers, timeout=12)
        resp.encoding = resp.apparent_encoding or "utf-8"
        
        res_soup = BeautifulSoup(resp.text, "html.parser")
        for tag in res_soup.find_all(["script", "style"]):
            tag.decompose()

        # 檢查是否有八字命盤表格
        chart_div = None
        for table in res_soup.find_all("table"):
            if any(k in table.text for k in ["八字", "主星", "日主", "命造", "律數"]):
                chart_div = table.parent
                break

        # 若原網站仍回傳日期錯誤提示
        if "請檢查日期" in resp.text:
            return {
                "status": "error",
                "message": "原網站提示：請檢查日期是否輸入正確！",
                "submitted_payload": payload,
                "raw_response_snippet": resp.text[:1500]
            }

        if not chart_div:
            chart_div = res_soup.find("div", class_="result-container") or res_soup.find("div", class_="container")

        return {
            "status": "success",
            "source": "https://myfate.herokuapp.com/",
            "submitted_payload": payload,
            "html": str(chart_div) if chart_div else resp.text
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
