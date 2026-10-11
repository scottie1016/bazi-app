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

def generate_candidates(soup, year: int, month: int, day: int, hour: int, gender: str):
    """
    動態產生可能被 myfate 接受的表單組合，自動處理空格、性別代碼(0/1/2)、時辰格式等
    """
    base_payload = {}
    for inp in soup.find_all("input", type="hidden"):
        if inp.get("name"):
            base_payload[inp["name"]] = inp.get("value", "")

    # 年份可能值
    year_options = []
    year_select = soup.find("select", {"name": "Year"}) or soup.find("select", {"id": "Year"})
    if year_select:
        for opt in year_select.find_all("option"):
            txt = opt.text.strip()
            val = opt.get("value") if opt.has_attr("value") else txt
            if f"西元{year}" in txt or f"西元 {year}" in txt or str(year) in txt:
                year_options.append(val)
                year_options.append(txt)
    m = year - 1911 if year >= 1912 else 1912 - year
    prefix = "民國" if year >= 1912 else "民前"
    year_options.extend([f"{prefix}{m} (西元{year})", f"{prefix} {m} (西元{year})", str(year)])
    
    seen_y = set()
    uniq_years = [y for y in year_options if y and not (y in seen_y or seen_y.add(y))]

    # 時辰可能值
    hour_options = []
    hour_select = soup.find("select", {"name": "Hour"}) or soup.find("select", {"id": "Hour"})
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

    # 性別可能代碼 (女常見為 0, 2, 1; 男常見為 1, 0)
    is_male = gender in ["男", "乾造", "1"]
    sex_options = ["1", "0", "男"] if is_male else ["0", "2", "1", "女"]

    # 組合候選
    candidates = []
    for y in uniq_years[:2]:
        for h in uniq_hours[:2]:
            for s in sex_options[:3]:
                for with_submit in [False, True]:
                    p = dict(base_payload)
                    p["Calendar"] = "1"
                    p["Sex"] = s
                    p["Year"] = y
                    p["Month"] = str(month)
                    p["Day"] = str(day)
                    p["Hour"] = h
                    if with_submit:
                        p["submit"] = "命盤分析"
                    candidates.append(p)
    return candidates

@app.get("/")
def home():
    return {
        "status": "online",
        "version": "2.2",
        "service": "Bazi Proxy API (Resilient Auto-Fallback)",
        "source": "https://myfate.herokuapp.com/",
        "debug_url": "/debug-form"
    }

@app.get("/debug-form", response_class=HTMLResponse)
def debug_form():
    """
    除錯診斷頁面：可看到原網站真實表單，並自動實測各組 Payload 回應
    """
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = session.get(TARGET_URL, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        form = soup.find("form")
        form_html = form.prettify() if form else "未找到 form 標籤"

        action_url = TARGET_URL
        if form and form.get("action"):
            act = form.get("action")
            action_url = act if act.startswith("http") else TARGET_URL.rstrip("/") + "/" + act.lstrip("/")

        # 自動實測前 6 組候選
        candidates = generate_candidates(soup, 1975, 7, 28, 16, "女")
        test_results_html = ""
        for i, cand in enumerate(candidates[:6]):
            try:
                r = session.post(action_url, data=cand, headers=headers, timeout=6)
                has_table = "table" in r.text or "八字" in r.text or "主星" in r.text
                status_color = "green" if (r.status_code == 200 and has_table) else "red"
                test_results_html += f"""
                <li style="margin-bottom:8px;">
                    <b>組合 #{i+1}:</b> <code>{cand}</code><br/>
                    狀態: <span style="color:{status_color}; font-weight:bold;">HTTP {r.status_code}</span> | 
                    是否含排盤: <b>{'✅ 是' if has_table else '❌ 否'}</b> | 回應長度: {len(r.text)} bytes
                </li>
                """
            except Exception as e:
                test_results_html += f"<li>組合 #{i+1}: 錯誤 - {str(e)}</li>"

        return f"""
        <html>
        <head><meta charset="utf-8"><title>Bazi Proxy Debug Form v2.2</title></head>
        <body style="font-family:sans-serif; padding:20px; line-height:1.6; max-width:960px; margin:auto;">
            <h2>✅ Render Proxy 伺服器在線 (版本 v2.2 - 自動重試與彈性容錯)</h2>
            <p>目標來源：<a href="{TARGET_URL}" target="_blank">{TARGET_URL}</a></p>
            <hr/>
            <h3>🧪 即時診斷測試 (1975-07-28 16時 女)：</h3>
            <ul>{test_results_html}</ul>
            <hr/>
            <h3>原網站 Form 標籤與欄位：</h3>
            <pre style="background:#f4f4f4; padding:15px; border-radius:6px; overflow:auto; max-height:400px; font-size:12px;">{form_html}</pre>
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

        # 2. 取得候選 Payload 組合
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
