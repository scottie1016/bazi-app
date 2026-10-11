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
    form = soup.find("form")
    if not form:
        return {}

    payload = {}

    for h in form.find_all("input", type="hidden"):
        if h.get("name"):
            payload[h["name"]] = h.get("value", "")

    payload["Calendar"] = "1"
    payload["Sex"] = "1" if gender in ["男", "乾造", "1"] else "0"

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

    month_sel = form.find("select", {"name": "Month"})
    if month_sel:
        opts = month_sel.find_all("option")
        m_idx = month - 1
        if 0 <= m_idx < len(opts):
            payload["Month"] = opts[m_idx].get("value") or opts[m_idx].text.strip()
        else:
            payload["Month"] = str(month)

    day_sel = form.find("select", {"name": "Day"})
    if day_sel:
        opts = day_sel.find_all("option")
        d_idx = day - 1
        if 0 <= d_idx < len(opts):
            payload["Day"] = opts[d_idx].get("value") or opts[d_idx].text.strip()
        else:
            payload["Day"] = str(day)

    hour_sel = form.find("select", {"name": "Hour"})
    if hour_sel:
        opts = hour_sel.find_all("option")
        if 0 <= hour < len(opts):
            payload["Hour"] = opts[hour].get("value") or opts[hour].text.strip()
        else:
            payload["Hour"] = str(hour)

    return payload

STYLE_BLOCK = """
<style>
.bazi-result-wrapper {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang TC", "Microsoft JhengHei", sans-serif;
    width: 100%;
    color: #2a2521;
    line-height: 1.6;
}
.bazi-result-wrapper table {
    width: 100%;
    border-collapse: collapse;
    margin: 12px 0 20px 0;
    background: #ffffff;
    border: 1px solid #dcd5ca;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.bazi-result-wrapper th, 
.bazi-result-wrapper td {
    border: 1px solid #dcd5ca;
    padding: 8px 12px;
    text-align: center;
    vertical-align: middle;
    font-size: 14px;
}
.bazi-result-wrapper th {
    background-color: #f7f3eb;
    color: #5c3a21;
    font-weight: bold;
}
.bazi-result-wrapper td {
    background-color: #ffffff;
}
.bazi-result-wrapper h3, 
.bazi-result-wrapper h4 {
    color: #8b2500;
    font-size: 16px;
    font-weight: bold;
    margin: 18px 0 8px 0;
    border-left: 4px solid #8b2500;
    padding-left: 8px;
}
.bazi-result-wrapper p {
    font-size: 14px;
    margin: 6px 0;
}
</style>
"""

@app.get("/")
def home():
    return {
        "status": "online",
        "version": "2.7",
        "service": "Bazi Proxy API (Complete Formatted Layout v2.7)",
        "source": "https://myfate.herokuapp.com/",
        "debug_url": "/debug-form"
    }

@app.get("/debug-form", response_class=HTMLResponse)
def debug_form():
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

        payload = build_myfate_payload(soup, 1975, 7, 28, 16, "女")
        post_res = session.post(action_url, data=payload, headers=headers, timeout=10)
        post_res.encoding = post_res.apparent_encoding or "utf-8"
        
        res_soup = BeautifulSoup(post_res.text, "html.parser")
        for tag in res_soup.find_all(["script", "style", "nav", "header", "footer", "form", "iframe", "ins"]):
            tag.decompose()
        
        container = res_soup.find("div", class_="container") or res_soup.find("body") or res_soup
        formatted_html = f"<div class='bazi-result-wrapper'>{STYLE_BLOCK}{str(container)}</div>"

        return f"""
        <html>
        <head><meta charset="utf-8"><title>Bazi Proxy Debug v2.7</title></head>
        <body style="font-family:sans-serif; padding:20px; line-height:1.6; max-width:960px; margin:auto;">
            <h2>✅ Render Proxy 伺服器在線 (版本 v2.7)</h2>
            <hr/>
            <h3>排盤結果預覽 (1975-07-28 16時 女)：</h3>
            {formatted_html}
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

        # 4. 解析完整排盤結果 (保留所有命盤表格與排版，去除無關廣告與表單)
        res_soup = BeautifulSoup(resp.text, "html.parser")
        
        for tag in res_soup.find_all(["script", "style", "nav", "header", "footer", "form", "iframe", "ins"]):
            tag.decompose()

        # 移除外站廣告或多餘無關宣傳文章
        for elem in res_soup.find_all(True):
            if elem.string and any(k in elem.string for k in ["心情看板", "數位游牧", "VPN 推薦", "快速學會日本語"]):
                elem.decompose()

        # 尋找內容容器 (保留八字命盤、大運、律數等所有結果)
        container = res_soup.find("div", class_="container") or res_soup.find("body") or res_soup

        # 注入美化樣式 (讓表格具備邊框、欄位對齊、典雅風格)
        formatted_content = f"<div class='bazi-result-wrapper'>{STYLE_BLOCK}{str(container)}</div>"

        return {
            "status": "success",
            "source": "https://myfate.herokuapp.com/",
            "submitted_payload": payload,
            "html": formatted_content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
