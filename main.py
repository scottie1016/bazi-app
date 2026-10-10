from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
from bs4 import BeautifulSoup

app = FastAPI()

# 允許跨域請求 (讓你的 GitHub Pages 能夠直接呼叫)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

TARGET_URL = "https://myfate.herokuapp.com/"

@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Bazi Proxy API",
        "source": "https://myfate.herokuapp.com/",
        "usage": "/api/bazi?year=1975&month=10&day=16&hour=0&gender=男"
    }

@app.get("/api/bazi")
def get_bazi(year: int, month: int, day: int, hour: int, gender: str = "女"):
    """
    轉發請求到 myfate.herokuapp.com 並抓取純淨命盤結果
    """
    try:
        # 對應 myfate 的表單參數
        payload = {
            "cal": "0",         # 0=陽曆, 1=農曆
            "gender": gender,   # 男 或 女
            "year": str(year),
            "month": str(month),
            "day": str(day),
            "hour": str(hour)
        }
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        # 發送 POST 請求
        response = requests.post(TARGET_URL, data=payload, headers=headers, timeout=12)
        
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="原網站服務暫時無法連線")
            
        soup = BeautifulSoup(response.text, "html.parser")
        
        # 擷取主要的命盤容器 (若有特定 class 或 table)
        result_div = soup.find("div", class_="result-container") or soup.find("table") or soup.find("body")
        
        return {
            "status": "success",
            "source": "https://myfate.herokuapp.com/",
            "attribution": "數據與演算法來源：myfate.herokuapp.com",
            "html": str(result_div)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
