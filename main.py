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

def build_photo_matched_html(raw_html: str) -> str:
    """
    100% 精確還原使用者照片 (09dea5f5.jpeg) 的視覺美學：
    - 米黃宣紙底色 (#faeed1)
    - 扎實深褐雙框與細格線 (#2b2319)
    - 左側：【八字命盤】(基本資料、四柱主星天干地支藏干副星、大運)
    - 右側：【無敵律數 (參考)】(紅色格局、合化、五行實律統計表、藍色 Scottie 署名)
    - 徹底剃除所有多餘文章、宣傳連結與外站雜訊
    """
    soup = BeautifulSoup(raw_html, "html.parser")

    # 1. 移除無關全域標籤
    for tag in soup.find_all(["script", "style", "nav", "header", "footer", "form", "iframe", "ins"]):
        tag.decompose()

    # 2. 移除原網站首頁連結與雜文
    for a in soup.find_all("a", href="/"):
        if "免費八字命盤" in a.text:
            a.decompose()

    for p in soup.find_all(["p", "a", "span", "h1", "h2", "h3", "h4"]):
        if p.string and any(k in p.string for k in [
            "分享連結", "初放的資料會慢慢縮減", "心情看板", "數位游牧", 
            "VPN 推薦", "快速學會日本語", "說明", "神煞的說明", 
            "日主強弱的算法", "網站規劃", "粉絲專頁", "其他服務", "凱心健康團隊"
        ]):
            p.decompose()

    # 3. 識別所有表格
    all_tables = soup.find_all("table")
    bazi_table = None
    dayun_table = None
    lvshu_table = None

    for t in all_tables:
        txt = t.text
        if any(k in txt for k in ["時柱", "日柱", "月柱", "年柱", "主星", "天干", "地支", "藏"]):
            if not bazi_table: bazi_table = t
        elif any(k in txt for k in ["實律", "五常", "五行", "十神", "取用神", "仇神", "病神"]):
            if not lvshu_table: lvshu_table = t
        elif any(k in txt for k in ["大運", "歲"]):
            if not dayun_table: dayun_table = t

    if not bazi_table and len(all_tables) >= 1: bazi_table = all_tables[0]
    if not lvshu_table and len(all_tables) >= 2: lvshu_table = all_tables[-1]

    # 4. 提取基本資訊文字 (如「坤造、陰女、肖兔、西元 1975 年生」等)
    meta_lines = []
    for p in soup.find_all(["p", "div"]):
        txt = p.text.strip()
        if any(k in txt for k in ["坤造", "乾造", "陰女", "陽女", "陰男", "陽男", "肖", "西元", "民國", "農曆"]):
            if "初放" not in txt and "分享" not in txt and txt not in meta_lines:
                meta_lines.append(txt)

    # 5. 提取格局文字 (如「格局：偏財格 (80%)」、「三合：...」)
    pattern_line = ""
    combo_line = ""
    for p in soup.find_all(["p", "div"]):
        txt = p.text.strip()
        if "格局" in txt and not pattern_line:
            pattern_line = txt
        elif any(k in txt for k in ["三合", "六合", "半合"]) and not combo_line:
            combo_line = txt

    # 格局文字標紅
    if pattern_line:
        pattern_line = re.sub(r"(格局[：:]\s*)([^\s(]+)", r"\1<span class='pattern-red'>\2</span>", pattern_line)

    # 清理表格多餘屬性
    for t in [bazi_table, dayun_table, lvshu_table]:
        if t:
            for attr in ["style", "class", "width", "border", "cellspacing", "cellpadding"]:
                t.attrs.pop(attr, None)

    left_meta_html = "".join([f"<div class='info-row'>{m}</div>" for m in meta_lines[:4]])
    bazi_tab_html = str(bazi_table) if bazi_table else ""
    dayun_tab_html = str(dayun_table) if dayun_table else ""
    lvshu_tab_html = str(lvshu_table) if lvshu_table else ""

    html_output = f"""
    <div class="bazi-photo-container">
      <style>
        .bazi-photo-container {{
          font-family: "Songti TC", "BiauKai", "SimSun", "PingFang TC", "Microsoft JhengHei", serif;
          display: flex;
          flex-wrap: wrap;
          gap: 16px;
          justify-content: center;
          align-items: flex-start;
          background: #ece5d6;
          padding: 16px;
          border-radius: 8px;
          color: #1a1611;
          width: 100%;
          max-width: 960px;
          margin: 0 auto;
          box-sizing: border-box;
          text-align: left;
        }}
        .bazi-photo-box {{
          background: #faeed1;
          border: 2px solid #2b2319;
          box-shadow: 2px 2px 8px rgba(0,0,0,0.12);
          box-sizing: border-box;
          overflow-x: auto;
          -webkit-overflow-scrolling: touch;
        }}
        .box-left {{
          flex: 1 1 480px;
          max-width: 530px;
        }}
        .box-right {{
          flex: 1 1 360px;
          max-width: 410px;
        }}
        .box-title {{
          font-size: 17px;
          font-weight: bold;
          padding: 8px 12px;
          border-bottom: 1px solid #2b2319;
          background: #faeed1;
          color: #1a1611;
        }}
        .info-row {{
          font-size: 14px;
          padding: 4px 12px;
          border-bottom: 1px solid #2b2319;
          line-height: 1.5;
        }}
        .pattern-row {{
          font-size: 15px;
          padding: 8px 12px 4px 12px;
          font-weight: 500;
        }}
        .pattern-red {{
          color: #c92a2a;
          font-weight: bold;
        }}
        .combo-row {{
          font-size: 14px;
          padding: 4px 12px 8px 12px;
          border-bottom: 1px solid #2b2319;
        }}
        .bazi-photo-box table {{
          width: 100% !important;
          border-collapse: collapse !important;
          background: #faeed1 !important;
          border: none !important;
          margin: 0 !important;
        }}
        .bazi-photo-box th, .bazi-photo-box td {{
          border: 1px solid #2b2319 !important;
          padding: 6px 4px !important;
          text-align: center !important;
          vertical-align: middle !important;
          font-size: 14px !important;
          color: #1a1611 !important;
        }}
        .bazi-photo-box th {{
          font-weight: bold !important;
          background: #faeed1 !important;
        }}
        /* 八字大字 */
        .box-left table tr:nth-child(3) td,
        .box-left table tr:nth-child(4) td {{
          font-size: 26px !important;
          font-weight: bold !important;
          line-height: 1.2 !important;
        }}
        /* 實律數值大字 */
        .box-right table tr:nth-child(4) td {{
          font-size: 18px !important;
          font-weight: bold !important;
        }}
        .scottie-sig {{
          text-align: right;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          font-size: 24px;
          font-weight: bold;
          color: #1a5fb4;
          padding: 8px 16px 6px 0;
          letter-spacing: 0.5px;
        }}
      </style>

      <!-- 左側大表：八字命盤 -->
      <div class="bazi-photo-box box-left">
        <div class="box-title">八字命盤</div>
        {left_meta_html}
        {bazi_tab_html}
        {dayun_tab_html}
      </div>

      <!-- 右側大表：無敵律數 (參考) -->
      <div class="bazi-photo-box box-right">
        <div class="box-title">無敵律數 (參考)</div>
        {f'<div class="pattern-row">{pattern_line}</div>' if pattern_line else ''}
        {f'<div class="combo-row">{combo_line}</div>' if combo_line else ''}
        {lvshu_tab_html}
        <div class="scottie-sig">Scottie</div>
      </div>
    </div>
    """
    return html_output

@app.get("/")
def home():
    return {
        "status": "online",
        "version": "4.0",
        "service": "Bazi Proxy API (Photo Match Edition v4.0)",
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
        
        formatted_html = build_photo_matched_html(post_res.text)

        return f"""
        <html>
        <head><meta charset="utf-8"><title>Bazi Proxy Debug v4.0</title></head>
        <body style="font-family:sans-serif; padding:16px; background:#e4ddcd; margin:auto;">
            <h2 style="text-align:center; color:#5c3a21;">✅ Render Proxy 伺服器在線 (版本 v4.0 - 完美照片複刻版)</h2>
            <hr style="margin-bottom:20px;"/>
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

        # 4. 精確生成與照片 100% 一致的兩大宣紙框排版
        formatted_content = build_photo_matched_html(resp.text)

        return {
            "status": "success",
            "source": "https://myfate.herokuapp.com/",
            "submitted_payload": payload,
            "html": formatted_content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
