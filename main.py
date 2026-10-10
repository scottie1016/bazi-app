from fastapi import FastAPI, HTTPException, Request
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

def format_year_string(year: int) -> str:
    """
    根據西元年產生 myfate 所需的民國/西元年字串，例如：
    1975 -> '民國 64 (西元1975)' 或 '民國64 (西元1975)'
    1911 -> '民前1 (西元1911)'
    1900 -> '民前12 (西元1900)'
    """
    if year >= 1912:
        m = year - 1911
        return [f"民國 {m} (西元{year})", f"民國{m} (西元{year})", f"民國{m}(西元{year})", str(year)]
    else:
        m = 1912 - year
        return [f"民前 {m} (西元{year})", f"民前{m} (西元{year})", f"民前{m}(西元{year})", str(year)]

def format_hour_string(hour: int) -> list:
    """
    產生時辰文字匹配
    0: 凌晨0點多(早子), 凌晨 0 點多 (早子)
    """
    zhi_names = ["早子", "丑", "丑", "寅", "寅", "卯", "卯", "辰", "辰", "巳", "巳", "午", "午", "未", "未", "申", "申", "酉", "酉", "戌", "戌", "亥", "亥", "夜子"]
    time_descs = [
        "凌晨0點多(早子)", "凌晨1點多(丑)", "凌晨2點多(丑)", "凌晨3點多(寅)", "凌晨4點多(寅)",
        "早上5點多(卯)", "早上6點多(卯)", "早上7點多(辰)", "早上8點多(辰)", "早上9點多(巳)", "早上10點多(巳)",
        "早上11點多(午)", "中午12點多(午)", "下午1點多(未)", "下午2點多(未)", "下午3點多(申)", "下午4點多(申)",
        "下午5點多(酉)", "下午6點多(酉)", "傍晚7點多(戌)", "晚上8點多(戌)", "晚上9點多(亥)", "晚上10點多(亥)",
        "晚上11點多(夜子)"
    ]
    if 0 <= hour <= 23:
        return [time_descs[hour], str(hour)]
    return [str(hour)]

@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Bazi Proxy API (Smart Form Parser)",
        "source": "https://myfate.herokuapp.com/"
    }

@app.get("/api/bazi")
def get_bazi(year: int, month: int, day: int, hour: int, gender: str = "女"):
    """
    自動先取得 myfate 首頁的表單實際 input 名稱與 option 格式，精準填入後提交！
    """
    try:
        session = requests.Session()
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": TARGET_URL
        }
        
        # 1. 先抓取首頁，動態分析表單真實結構
        home_res = session.get(TARGET_URL, headers=headers, timeout=10)
        soup = BeautifulSoup(home_res.text, "html.parser")
        form = soup.find("form")
        
        action_url = TARGET_URL
        if form and form.get("action"):
            act = form.get("action")
            action_url = act if act.startswith("http") else TARGET_URL.rstrip("/") + "/" + act.lstrip("/")
            
        # 2. 自動探測表單中的各個欄位
        payload = {}
        
        # 尋找所有 select 欄位
        selects = soup.find_all("select")
        # 通常依序為: 年, 月, 日, 時 (或檢測 option 內容)
        for sel in selects:
            s_name = sel.get("name")
            if not s_name:
                continue
            opts = sel.find_all("option")
            opt_texts = [o.text.strip() for o in opts]
            opt_values = [o.get("value", o.text.strip()) for o in opts]
            
            # 判斷是否為「年」
            if any("西元" in t or "民國" in t for t in opt_texts):
                year_patterns = format_year_string(year)
                matched_val = None
                for y_pat in year_patterns:
                    for idx, t in enumerate(opt_texts):
                        if y_pat in t or str(year) in t:
                            matched_val = opt_values[idx]
                            break
                    if matched_val is not None:
                        break
                payload[s_name] = matched_val if matched_val is not None else str(year)
                
            # 判斷是否為「月」
            elif any(t in ["1", "01", "12"] for t in opt_texts) and len(opts) <= 13:
                matched_val = None
                for idx, t in enumerate(opt_texts):
                    if t == str(month) or opt_values[idx] == str(month):
                        matched_val = opt_values[idx]
                        break
                payload[s_name] = matched_val if matched_val is not None else str(month)
                
            # 判斷是否為「日」
            elif any(t in ["28", "29", "30", "31"] for t in opt_texts):
                matched_val = None
                for idx, t in enumerate(opt_texts):
                    if t == str(day) or opt_values[idx] == str(day):
                        matched_val = opt_values[idx]
                        break
                payload[s_name] = matched_val if matched_val is not None else str(day)
                
            # 判斷是否為「時」
            elif any("時" in t or "點" in t or "子" in t for t in opt_texts):
                hour_patterns = format_hour_string(hour)
                matched_val = None
                for h_pat in hour_patterns:
                    for idx, t in enumerate(opt_texts):
                        if h_pat in t or f"{hour}點" in t or f"{hour}時" in t:
                            matched_val = opt_values[idx]
                            break
                    if matched_val is not None:
                        break
                payload[s_name] = matched_val if matched_val is not None else str(hour)

        # 尋找 radio / checkbox (曆法, 性別)
        radios = soup.find_all("input", type="radio")
        for r in radios:
            r_name = r.get("name")
            r_val = r.get("value")
            # 曆法: 預設選陽曆
            if r_val in ["0", "solar", "陽曆", "1"]:
                if r_name and r_name not in payload:
                    payload[r_name] = r_val
            # 性別
            if gender in ["男", "乾造"] and r_val in ["1", "male", "男"]:
                payload[r_name] = r_val
            elif gender in ["女", "坤造"] and r_val in ["0", "female", "女"]:
                payload[r_name] = r_val

        # 若某些通用名稱漏掉，加入備用鍵值
        fallback_data = {
            "year": payload.get("year", f"民國{year-1911} (西元{year})"),
            "month": str(month),
            "day": str(day),
            "hour": str(hour),
            "gender": "男" if gender in ["男", "乾造"] else "女",
            "cal": "0"
        }
        for k, v in fallback_data.items():
            if k not in payload:
                payload[k] = v

        # 3. 發送表單請求
        resp = session.post(action_url, data=payload, headers=headers, timeout=12)
        
        # 4. 解析結果
        res_soup = BeautifulSoup(resp.text, "html.parser")
        
        # 檢查是否有特定命盤容器或表格
        # 移除原網站廣告與按鈕
        for tag in res_soup.find_all(["script", "style"]):
            tag.decompose()
            
        # 搜尋包含「八字命盤」或表格的區域
        chart_div = None
        for table in res_soup.find_all("table"):
            if "八字" in table.text or "主星" in table.text or "日主" in table.text:
                chart_div = table.parent
                break
        if not chart_div:
            chart_div = res_soup.find("div", class_="result-container") or res_soup.find("body")

        return {
            "status": "success",
            "source": "https://myfate.herokuapp.com/",
            "submitted_payload": payload,
            "html": str(chart_div)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
