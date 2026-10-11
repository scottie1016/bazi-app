from fastapi import FastAPI, HTTPException
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
    width: 100% !important;
    text-align: left !important;
    color: #2a2521;
    line-height: 1.6;
    padding: 0 !important;
    margin: 0 !important;
    box-sizing: border-box !important;
}
.bazi-result-wrapper .container,
.bazi-result-wrapper .row,
.bazi-result-wrapper [class*="col-"] {
    width: 100% !important;
    max-width: 100% !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
    padding-left: 0 !important;
    padding-right: 0 !important;
    box-sizing: border-box !important;
}
.bazi-result-wrapper table {
    width: 100% !important;
    max-width: 100% !important;
    border-collapse: collapse !important;
    margin: 12px 0 20px 0 !important;
    background: #ffffff !important;
    border: 1px solid #dcd5ca !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.bazi-result-wrapper th, 
.bazi-result-wrapper td {
    border: 1px solid #dcd5ca !important;
    padding: 8px 6px !important;
    text-align: center !important;
    vertical-align: middle !important;
    font-size: 13.5px !important;
}
.bazi-result-wrapper th {
    background-color: #f7f3eb !important;
    color: #5c3a21 !important;
    font-weight: bold !important;
}
.bazi-result-wrapper td {
    background-color: #ffffff !important;
}
.bazi-result-wrapper h3, 
.bazi-result-wrapper h4 {
    color: #8b2500 !important;
    font-size: 16px !important;
    font-weight: bold !important;
    margin: 18px 0 8px 0 !important;
    border-left: 4px solid #8b2500 !important;
    padding-left: 8px !important;
    text-align: left !important;
}
.bazi-result-wrapper p {
    font-size: 14px !important;
    margin: 6px 0 !important;
    text-align: left !important;
}
</style>
"""

def extract_clean_bazi_html(resp_text: str) -> str:
    res_soup = BeautifulSoup(resp_text, "html.parser")
    
    # 1. 移除無關全域標籤
    for tag in res_soup.find_all(["script", "style", "nav", "header", "footer", "form", "iframe", "ins"]):
        tag.decompose()

    # 2. 移除原網站首頁重複大標題
    for a in res_soup.find_all("a", href="/"):
        if "免費八字命盤" in a.text:
            a.decompose()

    # 3. 移除分享連結、作者宣傳雜文
    for p in res_soup.find_all(["p", "a", "span", "h2", "h3"]):
        if p.string and any(k in p.string for k in ["分享連結", "初放的資料會慢慢縮減", "心情看板", "數位游牧", "VPN 推薦", "快速學會日本語"]):
            p.decompose()

    # 4. 抓取包含所有排盤表格的區塊
    results = []
    for c in res_soup.find_all("div", class_="container"):
        if c.find("table") or any(k in c.text for k in ["八字", "主星", "日主", "命造", "律數", "坤造", "乾造"]):
            results.append(str(c))

    if not results:
        for t in res_soup.find_all("table"):
            results.append(str(t.parent if t.parent else t))

    if not results:
        body = res_soup.find("body")
        results = [str(body)] if body else [str(res_soup)]

    full_inner_html = "\n".join(results)
    return f"<div class='bazi-result-wrapper'>{STYLE_BLOCK}{full_inner_html}</div>"

@app.get("/")
def home():
    return {
        "status": "online",
        "version": "2.9",
        "service": "Bazi Proxy API (Fixed Alignment & Full Chart v2.9)",
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
        post_res = session.post(action_url, data=payload, headers=headers, timeout=12)
        post_res.encoding = post_res.apparent_encoding or "utf-8"
        
        formatted_html = extract_clean_bazi_html(post_res.text)

        return f"""
        <html>
        <head><meta charset="utf-8"><title>Bazi Proxy Debug v2.9</title></head>
        <body style="font-family:sans-serif; padding:20px; line-height:1.6; max-width:960px; margin:auto;">
            <h2>✅ Render Proxy 伺服器在線 (版本 v2.9 - 左側對齊與完整命盤)</h2>
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

        # 4. 解析完整排盤結果
        formatted_content = extract_clean_bazi_html(resp.text)

        return {
            "status": "success",
            "source": "https://myfate.herokuapp.com/",
            "submitted_payload": payload,
            "html": formatted_content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
