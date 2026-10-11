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

def generate_candidates(soup, year: int, month: int, day: int, hour: int, gender: str):
    """
    精確產生目標日期的表單組合，絕對排除無關年份 (如 1900)，並涵蓋 submit 按鈕
    """
    base_payload = {}
    for inp in soup.find_all("input", type="hidden"):
        if inp.get("name"):
            base_payload[inp["name"]] = inp.get("value", "")

    # 1. 年份：精確鎖定目標年份
    m = year - 1911 if year >= 1912 else 1912 - year
    prefix = "民國" if year >= 1912 else "民前"

    raw_years = []
    year_select = soup.find("select", {"name": re.compile(r"year", re.I)}) or soup.find("select", {"id": re.compile(r"year", re.I)})
    if year_select:
        for opt in year_select.find_all("option"):
            txt = opt.text.strip()
            val = opt.get("value", txt)
            if str(year) in txt or str(year) in val or (str(m) in txt and prefix in txt):
                raw_years.append(val)
                raw_years.append(txt)

    # 備選加入標準格式 (含空格與無空格)
    raw_years.extend([
        f"{prefix} {m} (西元{year})",
        f"{prefix}{m} (西元{year})",
        str(year)
    ])
    
    # 嚴格過濾：必須包含目標年份或民國年號，絕對不允許 1900 等無關年份
    seen_y = set()
    uniq_years = []
    for y in raw_years:
        if y and (str(year) in y or str(m) in y) and not (y in seen_y or seen_y.add(y)):
            uniq_years.append(y)

    # 2. 時辰：精確提取該時辰
    hour_options = []
    hour_select = soup.find("select", {"name": re.compile(r"hour", re.I)}) or soup.find("select", {"id": re.compile(r"hour", re.I)})
    if hour_select:
        opts = hour_select.find_all("option")
        if 0 <= hour < len(opts):
            opt = opts[hour]
            if opt.has_attr("value"):
                hour_options.append(opt["value"])
            hour_options.append(opt.text.strip())
    hour_options.extend([str(hour)])
    seen_h = set()
    uniq_hours = [h for h in hour_options if h and not (h in seen_h or seen_h.add(h))]

    # 3. 性別：0, 1, 2, 中文
    is_male = gender in ["男", "乾造", "1"]
    sex_options = ["1", "0", "男"] if is_male else ["0", "1", "2", "女"]

    # 4. 曆法：1 (陽曆), 0
    cal_options = ["1", "0"]

    # 5. 組合候選名單 (涵蓋有/無 submit 按鈕)
    candidates = []
    for y in uniq_years[:2]:
        for h in uniq_hours[:2]:
            for s in sex_options[:2]:
                for cal in cal_options:
                    for with_sub in [True, False]:
                        p = dict(base_payload)
                        p["Calendar"] = cal
                        p["Sex"] = s
                        p["Year"] = y
                        p["Month"] = str(month)
                        p["Day"] = str(day)
                        p["Hour"] = h
                        if with_sub:
                            p["submit"] = "命盤分析"
                        candidates.append(p)

    return candidates

@app.get("/")
def home():
    return {
        "status": "online",
        "version": "2.4",
        "service": "Bazi Proxy API (Targeted Match v2.4)",
        "source": "https://myfate.herokuapp.com/",
        "debug_url": "/debug-form"
    }

@app.get("/debug-form", response_class=HTMLResponse)
def debug_form():
    """
    即時線上診斷頁面
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

        # 實測 1975-07-28 16時 女
        candidates = generate_candidates(soup, 1975, 7, 28, 16, "女")
        test_results_html = ""
        success_found = False

        for i, cand in enumerate(candidates[:10]):
            try:
                r = session.post(action_url, data=cand, headers=headers, timeout=6)
                has_table = any(k in r.text for k in ["八字", "主星", "日主", "命造", "律數"])
                if r.status_code == 200 and has_table:
                    status_text = "✅ 成功 (HTTP 200 包含命盤！)"
                    status_color = "green"
                    success_found = True
                else:
                    status_text = f"HTTP {r.status_code} (無命盤)"
                    status_color = "red"
                
                test_results_html += f"""
                <li style="margin-bottom:8px; font-size:13px;">
                    <b>組合 #{i+1}:</b> <code>{cand}</code><br/>
                    結果: <span style="color:{status_color}; font-weight:bold;">{status_text}</span> | 長度: {len(r.text)} bytes
                </li>
                """
                if success_found:
                    break
            except Exception as e:
                test_results_html += f"<li>組合 #{i+1}: 錯誤 - {str(e)}</li>"

        return f"""
        <html>
        <head><meta charset="utf-8"><title>Bazi Proxy Debug Form v2.4</title></head>
        <body style="font-family:sans-serif; padding:20px; line-height:1.6; max-width:960px; margin:auto;">
            <h2>✅ Render Proxy 伺服器在線 (版本 v2.4)</h2>
            <p>目標來源：<a href="{TARGET_URL}" target="_blank">{TARGET_URL}</a></p>
            <hr/>
            <h3>🧪 即時診斷測試 (1975-07-28 16時 女)：</h3>
            <ul>{test_results_html}</ul>
            <hr/>
            <p><a href="/api/bazi?year=1975&month=7&day=28&hour=16&gender=女">👉 點此直接在瀏覽器執行 API 獲取命盤</a></p>
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

        # 2. 取得候選 Payload 組合 (已嚴格鎖定目標年份)
        candidates = generate_candidates(soup, year, month, day, hour, gender)
        
        success_chart = None
        successful_payload = None
        last_resp_text = ""
        last_status_code = 200

        # 3. 自動嘗試最佳組合直到獲取排盤結果
        for cand in candidates:
            try:
                resp = session.post(action_url, data=cand, headers=headers, timeout=10)
                resp.encoding = resp.apparent_encoding or "utf-8"
                last_status_code = resp.status_code
                last_resp_text = resp.text

                # 判斷是否成功取得命盤內容 (HTTP 200 且含有八字特徵)
                if resp.status_code == 200 and any(k in resp.text for k in ["八字", "主星", "日主", "命造", "律數"]):
                    res_soup = BeautifulSoup(resp.text, "html.parser")
                    for tag in res_soup.find_all(["script", "style"]):
                        tag.decompose()

                    for table in res_soup.find_all("table"):
                        if any(k in table.text for k in ["八字", "主星", "日主", "命造", "律數"]):
                            success_chart = table.parent
                            break
                    if not success_chart:
                        success_chart = res_soup.find("div", class_="result-container") or res_soup.find("div", class_="container")
                    
                    if success_chart:
                        successful_payload = cand
                        break
            except Exception:
                continue

        # 4. 回傳處理結果
        if success_chart:
            return {
                "status": "success",
                "source": "https://myfate.herokuapp.com/",
                "submitted_payload": successful_payload,
                "html": str(success_chart)
            }
        else:
            return {
                "status": "error",
                "message": f"原網站回應未包含命盤數據 (HTTP {last_status_code})",
                "attempted_candidates": len(candidates),
                "raw_response_snippet": last_resp_text[:1500]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
