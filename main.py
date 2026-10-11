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
  .two-tables-wrapper {
    width: 100% !important;
    max-width: 860px !important;
    margin: 0 auto !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang TC", "Microsoft JhengHei", sans-serif;
    color: #2b2520;
    text-align: left;
    box-sizing: border-box;
  }
  .table-box {
    background: #ffffff;
    border: 1px solid #d4ccbd;
    border-radius: 8px;
    padding: 16px 18px;
    margin-bottom: 22px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
  }
  .table-box-title {
    font-size: 16px;
    font-weight: bold;
    color: #8b2500;
    border-bottom: 2px solid #8b2500;
    padding-bottom: 6px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .table-box table {
    width: 100% !important;
    max-width: 100% !important;
    border-collapse: collapse !important;
    background: #ffffff !important;
    border: 1px solid #c9bfb0 !important;
    margin: 4px 0 !important;
  }
  .table-box th, .table-box td {
    border: 1px solid #c9bfb0 !important;
    padding: 9px 8px !important;
    text-align: center !important;
    vertical-align: middle !important;
    font-size: 14px !important;
  }
  .table-box th {
    background-color: #f7f3ea !important;
    color: #5a4228 !important;
    font-weight: bold !important;
  }
  .table-box td {
    background-color: #ffffff !important;
  }
</style>
"""

def extract_strictly_two_tables(resp_text: str) -> str:
    """
    極簡純淨過濾：僅提取原網站的兩張核心大表 (八字命盤表、無敵律數表)，
    徹底去除所有作者自述、文字段落、廣告與說明！
    """
    soup = BeautifulSoup(resp_text, "html.parser")
    all_tables = soup.find_all("table")

    bazi_table = None
    lvshu_table = None

    for t in all_tables:
        txt = t.text
        # 表一：八字命盤
        if any(k in txt for k in ["時柱", "日柱", "月柱", "年柱", "主星", "天干", "地支", "藏"]):
            if not bazi_table:
                bazi_table = t
        # 表二：無敵律數
        elif any(k in txt for k in ["實律", "五常", "五行", "十神", "取用神", "仇神", "病神"]):
            if not lvshu_table:
                lvshu_table = t

    # 容錯：若關鍵字未精準命中，直接取首尾兩張表
    if not bazi_table and len(all_tables) >= 1:
        bazi_table = all_tables[0]
    if not lvshu_table and len(all_tables) >= 2:
        lvshu_table = all_tables[-1]

    # 清理表格內部可能帶有的不必要樣式屬性
    if bazi_table:
        for attr in ["style", "class", "width"]:
            bazi_table.attrs.pop(attr, None)
    if lvshu_table:
        for attr in ["style", "class", "width"]:
            lvshu_table.attrs.pop(attr, None)

    bazi_html = str(bazi_table) if bazi_table else "<div style='color:#888;'>未找到八字命盤表格</div>"
    lvshu_html = str(lvshu_table) if lvshu_table else "<div style='color:#888;'>未找到無敵律數表格</div>"

    html_output = f"""
    <div class="two-tables-wrapper">
      {STYLE_BLOCK}
      
      <!-- 第一張大表：八字四柱命盤 -->
      <div class="table-box">
        <div class="table-box-title">☯ 八字命盤</div>
        {bazi_html}
      </div>

      <!-- 第二張大表：無敵律數分析 -->
      <div class="table-box">
        <div class="table-box-title">⚖️ 無敵律數</div>
        {lvshu_html}
      </div>
    </div>
    """
    return html_output

@app.get("/")
def home():
    return {
        "status": "online",
        "version": "3.1",
        "service": "Bazi Proxy API (Strict Dual-Table Mode v3.1)",
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
        
        formatted_html = extract_strictly_two_tables(post_res.text)

        return f"""
        <html>
        <head><meta charset="utf-8"><title>Bazi Proxy Debug v3.1</title></head>
        <body style="font-family:sans-serif; padding:20px; line-height:1.6; max-width:960px; margin:auto; background:#f7f5f0;">
            <h2>✅ Render Proxy 伺服器在線 (版本 v3.1 - 極簡雙大表模式)</h2>
            <hr/>
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

        # 4. 極簡提取：僅保留純淨的兩張大表
        formatted_content = extract_strictly_two_tables(resp.text)

        return {
            "status": "success",
            "source": "https://myfate.herokuapp.com/",
            "submitted_payload": payload,
            "html": formatted_content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
