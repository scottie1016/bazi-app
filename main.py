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

def extract_two_cards_html(resp_text: str) -> str:
    """
    精確只提取原網站的「兩張核心大表」：
    1. 八字命盤表 (含基本資訊、四柱主副星藏干與大運)
    2. 無敵律數表 (含格局、三合六合與實律用神統計)
    徹底過濾作者落落長的免責說明、宣傳文章與外站連結
    """
    soup = BeautifulSoup(resp_text, "html.parser")

    # 1. 移除無關全域標籤
    for tag in soup.find_all(["script", "style", "nav", "header", "footer", "form", "iframe", "ins"]):
        tag.decompose()

    # 2. 移除原網站首頁重複大標題
    for a in soup.find_all("a", href="/"):
        if "免費八字命盤" in a.text:
            a.decompose()

    # 3. 移除分享連結、作者宣傳雜文
    for p in soup.find_all(["p", "a", "span", "h2", "h3", "h4"]):
        if p.string and any(k in p.string for k in [
            "分享連結", "初放的資料會慢慢縮減", "心情看板", "數位游牧", 
            "VPN 推薦", "快速學會日本語", "說明", "神煞的說明", 
            "日主強弱的算法", "網站規劃", "粉絲專頁", "其他服務", "凱心健康團隊"
        ]):
            p.decompose()

    # 4. 尋找基本資料文字 (如「坤造、陰女、肖兔、西元 1975 年生」)
    basic_info_list = []
    for p in soup.find_all("p"):
        txt = p.text.strip()
        if any(k in txt for k in ["坤造", "乾造", "陰女", "陽女", "陰男", "陽男", "肖", "西元", "民國"]):
            if "初放的資料" not in txt and "分享連結" not in txt and txt not in basic_info_list:
                basic_info_list.append(txt)

    # 5. 尋找律數格局文字 (如「格局：偏財格 (80%)」、「三合：...」)
    lvshu_info_list = []
    for p in soup.find_all(["p", "div"]):
        txt = p.text.strip()
        if any(k in txt for k in ["格局", "偏財格", "正財格", "三合", "六合", "半合"]):
            if "初放的資料" not in txt and txt not in lvshu_info_list:
                lvshu_info_list.append(txt)

    # 6. 分類表格
    all_tables = soup.find_all("table")
    bazi_tables = []
    lvshu_tables = []

    for t in all_tables:
        t_text = t.text
        if any(k in t_text for k in ["時柱", "日柱", "月柱", "年柱", "主星", "天干", "地支", "藏干", "副星", "大運", "歲"]):
            bazi_tables.append(str(t))
        elif any(k in t_text for k in ["實律", "五常", "五行", "律數", "十神", "取用神", "仇神", "喜神", "忌神", "用神", "病神"]):
            lvshu_tables.append(str(t))
        else:
            if not bazi_tables:
                bazi_tables.append(str(t))
            else:
                lvshu_tables.append(str(t))

    basic_info_html = "<br/>".join(basic_info_list) if basic_info_list else ""
    lvshu_info_html = "<br/>".join(lvshu_info_list) if lvshu_info_list else ""
    bazi_tables_html = "\n".join(bazi_tables)
    lvshu_tables_html = "\n".join(lvshu_tables)

    # 7. 組合雙大表卡片 HTML 與專業典雅排版
    html_output = f"""
    <div class="bazi-two-cards-container">
      <style>
        .bazi-two-cards-container {{
          width: 100% !important;
          max-width: 900px !important;
          margin: 0 auto !important;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang TC", "Microsoft JhengHei", sans-serif;
          color: #2b2520;
          line-height: 1.6;
          box-sizing: border-box;
          text-align: left;
        }}
        .bazi-card {{
          background: #ffffff;
          border: 1px solid #d4ccbd;
          border-radius: 8px;
          padding: 16px 20px;
          margin-bottom: 22px;
          box-shadow: 0 2px 10px rgba(0,0,0,0.04);
          overflow-x: auto;
          -webkit-overflow-scrolling: touch;
        }}
        .bazi-card-header {{
          display: flex;
          justify-content: space-between;
          align-items: center;
          border-bottom: 2px solid #8b2500;
          padding-bottom: 8px;
          margin-bottom: 12px;
        }}
        .bazi-card-title {{
          font-size: 17px;
          font-weight: bold;
          color: #8b2500;
        }}
        .bazi-card-badge {{
          font-size: 12px;
          background: #f5ebe1;
          color: #8b2500;
          padding: 3px 8px;
          border-radius: 4px;
          font-weight: bold;
        }}
        .bazi-info-meta {{
          font-size: 14px;
          color: #4a3e35;
          margin-bottom: 14px;
          background: #faf7f2;
          padding: 9px 14px;
          border-radius: 6px;
          border-left: 3px solid #8b2500;
          font-weight: 500;
          line-height: 1.7;
        }}
        .bazi-card table {{
          width: 100% !important;
          max-width: 100% !important;
          border-collapse: collapse !important;
          margin: 10px 0 16px 0 !important;
          background: #ffffff !important;
          border: 1px solid #c9bfb0 !important;
        }}
        .bazi-card th, .bazi-card td {{
          border: 1px solid #c9bfb0 !important;
          padding: 8px 10px !important;
          text-align: center !important;
          vertical-align: middle !important;
          font-size: 14px !important;
        }}
        .bazi-card th {{
          background-color: #f7f3ea !important;
          color: #5a4228 !important;
          font-weight: bold !important;
        }}
        .bazi-card td {{
          background-color: #ffffff !important;
        }}
        .bazi-card p {{
          margin: 6px 0;
          font-size: 14px;
        }}
        .bazi-card h4 {{
          font-size: 15px;
          color: #5a4228;
          margin: 14px 0 6px 0;
          font-weight: bold;
        }}
      </style>

      <!-- 第一張大表：八字四柱命盤 -->
      <div class="bazi-card">
        <div class="bazi-card-header">
          <div class="bazi-card-title">☯ 八字四柱命盤</div>
          <div class="bazi-card-badge">正宗排盤與大運</div>
        </div>
        {f'<div class="bazi-info-meta">{basic_info_html}</div>' if basic_info_html else ''}
        {bazi_tables_html}
      </div>

      <!-- 第二張大表：無敵律數分析 -->
      <div class="bazi-card">
        <div class="bazi-card-header">
          <div class="bazi-card-title">⚖️ 無敵律數分析</div>
          <div class="bazi-card-badge">五行實律與用神</div>
        </div>
        {f'<div class="bazi-info-meta">{lvshu_info_html}</div>' if lvshu_info_html else ''}
        {lvshu_tables_html}
      </div>
    </div>
    """
    return html_output

@app.get("/")
def home():
    return {
        "status": "online",
        "version": "3.0",
        "service": "Bazi Proxy API (Dual-Card Clean Layout v3.0)",
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
        
        formatted_html = extract_two_cards_html(post_res.text)

        return f"""
        <html>
        <head><meta charset="utf-8"><title>Bazi Proxy Debug v3.0</title></head>
        <body style="font-family:sans-serif; padding:20px; line-height:1.6; max-width:960px; margin:auto; background:#f7f5f0;">
            <h2>✅ Render Proxy 伺服器在線 (版本 v3.0 - 兩大核心卡片專屬呈現)</h2>
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

        # 4. 精確只提取兩張核心大表
        formatted_content = extract_two_cards_html(resp.text)

        return {
            "status": "success",
            "source": "https://myfate.herokuapp.com/",
            "submitted_payload": payload,
            "html": formatted_content
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
