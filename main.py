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

def build_myfate_payload(soup, year: int, month: int, day: int, hour: int, gender: str):
    """
    100% 對齊原網站表單定義：
    Calendar: 1 (陽曆), 0 (農曆)
    Sex: 0 (女), 1 (男)
    Year: 根據 (year - 1900) 精確索引取值，徹底解決字串比對失敗退回 1900 的問題
    Month: options[month - 1]
    Day: options[day - 1]
    Hour: options[hour]
    """
    form = soup.find("form")
    if not form:
        return {}

    payload = {}

    # 1. 抓取所有 Hidden 欄位 (CSRF 等)
    for h in form.find_all("input", type="hidden"):
        if h.get("name"):
            payload[h["name"]] = h.get("value", "")

    # 2. 曆法 Calendar (1=陽曆, 0=農曆)
    payload["Calendar"] = "1"

    # 3. 性別 Sex (0=女, 1=男)
    payload["Sex"] = "1" if gender in ["男", "乾造", "1"] else "0"

    # 4. 年份 Year (原網站從 1900 年開始，精確索引為 year - 1900)
    year_sel = form.find("select", {"name": "Year"})
    if year_sel:
        opts = year_sel.find_all("option")
        y_idx = year - 1900
        if 0 <= y_idx < len(opts):
            payload["Year"] = opts[y_idx].get("value") or opts[y_idx].text.strip()
        else:
            for opt in opts:
                if str(year) in opt.text:
                    payload["Year"] = opt.get("value") or opt.text.strip()
                    break

    # 5. 月份 Month
    month_sel = form.find("select", {"name": "Month"})
    if month_sel:
        opts = month_sel.find_all("option")
        m_idx = month - 1
        if 0 <= m_idx < len(opts):
            payload["Month"] = opts[m_idx].get("value") or opts[m_idx].text.strip()
        else:
            payload["Month"] = str(month)

    # 6. 日期 Day
    day_sel = form.find("select", {"name": "Day"})
    if day_sel:
        opts = day_sel.find_all("option")
        d_idx = day - 1
        if 0 <= d_idx < len(opts):
            payload["Day"] = opts[d_idx].get("value") or opts[d_idx].text.strip()
        else:
            payload["Day"] = str(day)

    # 7. 時辰 Hour
    hour_sel = form.find("select", {"name": "Hour"})
    if hour_sel:
        opts = hour_sel.find_all("option")
        if 0 <= hour < len(opts):
            payload["Hour"] = opts[hour].get("value") or opts[hour].text.strip()
        else:
            payload["Hour"] = str(hour)

    return payload

@app.get("/")
def home():
    return {
        "status": "online",
        "version": "2.6",
        "service": "Bazi Proxy API (Fixed Year Index v2.6)",
        "source": "https://myfate.herokuapp.com/",
        "debug_url": "/debug-form"
    }

@app.get("/debug-form", response_class=HTMLResponse)
def debug_form():
    """
    即時線上診斷
    """
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = session.get(TARGET_URL, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        form = soup.find("form")
        
        action_url = TARGET_URL
        if form and form.get("action"):
            act = form.get("action")
            action_url = act if act.startswith("http") else TARGET_URL.rstrip("/") + "/" + act.lstrip("/")

        # 產生 1975-07-28 16時 女 的精確 Payload
        payload = build_myfate_payload(soup, 1975, 7, 28, 16, "女")
        
        # 實測發送
        post_res = session.post(action_url, data=payload, headers=headers, timeout=10)
        post_res.encoding = post_res.apparent_encoding or "utf-8"
        has_table = any(k in post_res.text for k in ["八字", "主星", "日主", "命造", "律數"])
        
        status_color = "green" if (post_res.status_code == 200 and has_table) else "red"
        status_desc = "✅ 成功取得命盤！" if (post_res.status_code == 200 and has_table) else f"HTTP {post_res.status_code} (長度 {len(post_res.text)} bytes)"

        return f"""
        <html>
        <head><meta charset="utf-8"><title>Bazi Proxy Debug v2.6</title></head>
        <body style="font-family:sans-serif; padding:20px; line-height:1.6; max-width:960px; margin:auto;">
            <h2>✅ Render Proxy 伺服器在線 (版本 v2.6)</h2>
            <hr/>
            <h3>🧪 即時實測結果 (1975-07-28 16時 女)：</h3>
            <p><b>送出 Payload：</b> <code>{payload}</code></p>
            <p><b>執行狀態：</b> <b style="color:{status_color}; font-size:16px;">{status_desc}</b></p>
            <hr/>
            <p><a href="/api/bazi?year=1975&month=7&day=28&hour=16&gender=女">👉 點此直接在瀏覽器執行 API 獲取排盤結果</a></p>
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

        # 2. 精確產生對齊 Payload
        payload = build_myfate_payload(soup, year, month, day, hour, gender)

        # 3. 發送請求至 myfate
        resp = session.post(action_url, data=payload, headers=headers, timeout=12)
        resp.encoding = resp.apparent_encoding or "utf-8"

        # 4. 解析命盤內容
        res_soup = BeautifulSoup(resp.text, "html.parser")
        for tag in res_soup.find_all(["script", "style"]):
            tag.decompose()

        chart_div = None
        for table in res_soup.find_all("table"):
            if any(k in table.text for k in ["八字", "主星", "日主", "命造", "律數"]):
                chart_div = table.parent
                break
        if not chart_div:
            chart_div = res_soup.find("div", class_="result-container") or res_soup.find("div", class_="container")

        if chart_div and any(k in chart_div.text for k in ["八字", "主星", "日主", "命造", "律數"]):
            return {
                "status": "success",
                "source": "https://myfate.herokuapp.com/",
                "submitted_payload": payload,
                "html": str(chart_div)
            }
        else:
            return {
                "status": "error",
                "message": f"原網站回應未包含命盤數據 (HTTP {resp.status_code})",
                "submitted_payload": payload,
                "raw_response_snippet": resp.text[:1500]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
