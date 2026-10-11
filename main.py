from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup
import re
import html

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TARGET_URL = "https://myfate.herokuapp.com/"

def extract_exact_payload(soup, year: int, month: int, day: int, hour: int, gender: str):
    """
    100% 動態依照原網站當前 HTML 標籤提取真實的 name 與 value，不再猜測大小寫或欄位名稱
    """
    form = soup.find("form")
    if not form:
        return {}

    payload = {}

    # 1. 抓取所有 Hidden 欄位 (CSRF 等)
    for h in form.find_all("input", type="hidden"):
        if h.get("name"):
            payload[h["name"]] = h.get("value", "")

    # 2. 抓取 Radio 欄位 (曆法 & 性別)
    for r in form.find_all("input", type="radio"):
        name = r.get("name")
        if not name: continue
        val = r.get("value", "")

        parent_text = r.parent.text if r.parent else ""
        if not parent_text and r.get("id"):
            lbl = form.find("label", {"for": r["id"]})
            if lbl: parent_text = lbl.text

        # 曆法：抓取包含「陽」的 radio 真實名稱與值
        if "陽" in parent_text:
            payload[name] = val
        
        # 性別：抓取包含目標性別的 radio 真實名稱與值
        target_gender = "男" if gender in ["男", "乾造", "1"] else "女"
        if target_gender in parent_text:
            payload[name] = val

    # 3. 抓取 Select 下拉選單 (年、月、日、時)
    selects = form.find_all("select")
    for idx, sel in enumerate(selects):
        name = sel.get("name")
        if not name: continue
        options = sel.find_all("option")
        if not options: continue

        is_year = re.search(r"year|年|^y$", name, re.I) or idx == 0
        is_month = re.search(r"month|月|^m$", name, re.I) or idx == 1
        is_day = re.search(r"day|日|^d$", name, re.I) or idx == 2
        is_hour = re.search(r"hour|時|^h$", name, re.I) or idx == 3

        if is_year and not (is_month or is_day or is_hour):
            chosen = None
            for opt in options:
                txt = opt.text.strip()
                val = opt.get("value", txt)
                if str(year) in txt or str(year) in val:
                    chosen = val
                    break
            payload[name] = chosen or (options[0].get("value", options[0].text.strip()))
        elif is_month and not (is_day or is_hour):
            chosen = str(month)
            for opt in options:
                txt = opt.text.strip()
                val = opt.get("value", txt)
                if txt == str(month) or val == str(month):
                    chosen = val
                    break
            payload[name] = chosen
        elif is_day and not is_hour:
            chosen = str(day)
            for opt in options:
                txt = opt.text.strip()
                val = opt.get("value", txt)
                if txt == str(day) or val == str(day):
                    chosen = val
                    break
            payload[name] = chosen
        elif is_hour:
            if 0 <= hour < len(options):
                opt = options[hour]
                payload[name] = opt.get("value", opt.text.strip())
            else:
                payload[name] = options[0].get("value", options[0].text.strip())

    return payload

@app.get("/")
def home():
    return {
        "status": "online",
        "version": "2.5",
        "service": "Bazi Proxy API (Smart DOM Inspection v2.5)",
        "source": "https://myfate.herokuapp.com/",
        "debug_url": "/debug-form"
    }

@app.get("/debug-form", response_class=HTMLResponse)
def debug_form():
    """
    即時線上診斷：顯示原網站真實欄位結構與實測結果
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

        # 動態精確抓取
        exact_p = extract_exact_payload(soup, 1975, 7, 28, 16, "女")
        
        # 測試兩種情況：有 submit 按鈕 與 無 submit 按鈕
        test_cases = [dict(exact_p)]
        p_with_sub = dict(exact_p)
        p_with_sub["submit"] = "命盤分析"
        test_cases.append(p_with_sub)

        test_html = ""
        for i, tc in enumerate(test_cases):
            try:
                r = session.post(action_url, data=tc, headers=headers, timeout=6)
                has_bazi = any(k in r.text for k in ["八字", "主星", "日主", "命造", "律數"])
                color = "green" if (r.status_code == 200 and has_bazi) else "red"
                res_desc = "✅ 成功取得排盤！" if (r.status_code == 200 and has_bazi) else f"HTTP {r.status_code} (長度 {len(r.text)} bytes)"
                test_html += f"<li><b>測試 #{i+1}:</b> <code>{tc}</code><br/>狀態: <b style='color:{color}'>{res_desc}</b></li>"
            except Exception as ex:
                test_html += f"<li>測試 #{i+1}: 錯誤 {str(ex)}</li>"

        # 標籤總覽
        summary_tags = []
        for inp in form.find_all(["input", "select", "button"]):
            summary_tags.append(f"{inp.name.upper()} name='{inp.get('name')}' type='{inp.get('type')}' value='{inp.get('value')}'")
        summary_text = html.escape("\n".join(summary_tags))

        return f"""
        <html>
        <head><meta charset="utf-8"><title>Bazi Proxy Debug v2.5</title></head>
        <body style="font-family:sans-serif; padding:20px; line-height:1.6; max-width:960px; margin:auto;">
            <h2>✅ Render Proxy 伺服器在線 (版本 v2.5 - 智慧動態欄位鏡像)</h2>
            <hr/>
            <h3>🧪 即時實測結果 (1975-07-28 16時 女)：</h3>
            <ul>{test_html}</ul>
            <hr/>
            <h3>🔍 原網站真實表單欄位名稱清單：</h3>
            <pre style="background:#1e1e1e; color:#4ec9b0; padding:15px; border-radius:6px; font-size:13px;">{summary_text}</pre>
            <hr/>
            <p><a href="/api/bazi?year=1975&month=7&day=28&hour=16&gender=女">👉 點此直接執行 API 獲取排盤結果</a></p>
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

        # 2. 自動精確提取表單欄位
        payload = extract_exact_payload(soup, year, month, day, hour, gender)
        
        # 準備嘗試名單 (有/無 submit 按鈕)
        candidates = [dict(payload)]
        p_sub = dict(payload)
        p_sub["submit"] = "命盤分析"
        candidates.append(p_sub)

        success_chart = None
        successful_payload = None
        last_resp_text = ""
        last_status_code = 200

        # 3. 發送請求
        for cand in candidates:
            try:
                resp = session.post(action_url, data=cand, headers=headers, timeout=10)
                resp.encoding = resp.apparent_encoding or "utf-8"
                last_status_code = resp.status_code
                last_resp_text = resp.text

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

        # 4. 回傳結果
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
                "attempted_payload": payload,
                "raw_response_snippet": last_resp_text[:1500]
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
