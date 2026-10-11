<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>八字命盤排盤系統</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background-color: #f7f5f0;
      color: #2a2521;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang TC", "Microsoft JhengHei", sans-serif;
      padding: 16px;
      display: flex;
      flex-direction: column;
      align-items: center;
      min-height: 100vh;
    }
    .container {
      width: 100%;
      max-width: 960px;
    }
    .header-card {
      background: #fff;
      border: 1px solid #dcd5ca;
      border-radius: 8px;
      padding: 16px 20px;
      margin-bottom: 16px;
      box-shadow: 0 2px 6px rgba(0,0,0,0.04);
    }
    .header-top {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      border-bottom: 1px solid #eee;
      padding-bottom: 8px;
    }
    .app-title {
      font-size: 17px;
      font-weight: bold;
      color: #8b2500;
    }
    .server-status {
      font-size: 13px;
      color: #666;
      display: flex;
      align-items: center;
      gap: 6px;
    }
    .server-status.online { color: #2e7d32; font-weight: bold; }
    .server-status.waking { color: #e65100; font-weight: bold; }
    .form-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 14px;
      align-items: center;
    }
    .form-item {
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 14px;
    }
    .form-item label { color: #555; font-weight: 500; }
    .form-item input, .form-item select {
      padding: 5px 8px;
      border: 1px solid #ccc;
      border-radius: 4px;
      font-size: 14px;
      background: #fff;
      outline: none;
    }
    .btn-calc {
      background: #8b2500;
      color: #fff;
      border: none;
      padding: 6px 18px;
      border-radius: 4px;
      font-size: 14px;
      font-weight: bold;
      cursor: pointer;
      margin-left: auto;
      transition: background 0.15s;
    }
    .btn-calc:hover { background: #aa2d00; }

    /* 結果呈現區 */
    .result-container {
      background: #ece5d6;
      border: 1px solid #dcd5ca;
      border-radius: 8px;
      padding: 12px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.06);
      min-height: 400px;
      display: block;
      text-align: left;
      overflow-x: auto;
    }
    #chartContent { width: 100%; }
    .loading-spinner {
      font-size: 15px;
      color: #666;
      display: none;
      text-align: center;
      line-height: 1.8;
      padding: 40px 0;
    }
    .loading-spinner.active { display: block; }

    .footer {
      text-align: center;
      font-size: 13px;
      color: #777;
      margin-top: 20px;
      padding-top: 12px;
      border-top: 1px solid #e0dacf;
      width: 100%;
    }
    .footer a { color: #8b2500; text-decoration: none; font-weight: 500; }
  </style>
</head>
<body>

<div class="container">
  <!-- 控制面板 -->
  <div class="header-card">
    <div class="header-top">
      <div class="app-title">☯ 專業八字命盤排盤系統</div>
      <div class="server-status" id="serverStatus">
        <span id="statusDot">●</span> <span id="statusText">伺服器狀態檢測中...</span>
      </div>
    </div>
    <div class="form-grid">
      <div class="form-item">
        <label>姓名：</label>
        <input type="text" id="userName" placeholder="請輸入姓名" value="Scottie" style="width: 86px;">
      </div>
      <div class="form-item">
        <label>性別：</label>
        <select id="userGender">
          <option value="男">男 (乾造)</option>
          <option value="女" selected>女 (坤造)</option>
        </select>
      </div>
      <div class="form-item">
        <label>年份：</label>
        <select id="inputYear" style="width: 175px;"></select>
      </div>
      <div class="form-item">
        <select id="inputMonth" style="width: 62px;"></select> 月
      </div>
      <div class="form-item">
        <select id="inputDay" style="width: 62px;"></select> 日
      </div>
      <div class="form-item">
        <label>時辰：</label>
        <select id="inputHour">
          <option value="0">凌晨0點多 (早子 00:00-00:59)</option>
          <option value="1">凌晨1點多 (丑時 01:00-01:59)</option>
          <option value="2">凌晨2點多 (丑時 02:00-02:59)</option>
          <option value="3">凌晨3點多 (寅時 03:00-03:59)</option>
          <option value="4">凌晨4點多 (寅時 04:00-04:59)</option>
          <option value="5">早上5點多 (卯時 05:00-05:59)</option>
          <option value="6">早上6點多 (卯時 06:00-06:59)</option>
          <option value="7">早上7點多 (辰時 07:00-07:59)</option>
          <option value="8">早上8點多 (辰時 08:00-08:59)</option>
          <option value="9">早上9點多 (巳時 09:00-09:59)</option>
          <option value="10">早上10點多 (巳時 10:00-10:59)</option>
          <option value="11">早上11點多 (午時 11:00-11:59)</option>
          <option value="12">中午12點多 (午時 12:00-12:59)</option>
          <option value="13">下午1點多 (未時 13:00-13:59)</option>
          <option value="14">下午2點多 (未時 14:00-14:59)</option>
          <option value="15">下午3點多 (申時 15:00-15:59)</option>
          <option value="16" selected>下午4點多 (申時 16:00-16:59)</option>
          <option value="17">下午5點多 (酉時 17:00-17:59)</option>
          <option value="18">下午6點多 (酉時 18:00-18:59)</option>
          <option value="19">傍晚7點多 (戌時 19:00-19:59)</option>
          <option value="20">晚上8點多 (戌時 20:00-20:59)</option>
          <option value="21">晚上9點多 (亥時 21:00-21:59)</option>
          <option value="22">晚上10點多 (亥時 22:00-22:59)</option>
          <option value="23">晚上11點多 (夜子 23:00-23:59)</option>
        </select>
      </div>
      <button class="btn-calc" onclick="fetchBaziData()">⚡ 排盤更新</button>
    </div>
  </div>

  <!-- 命盤呈現區域 -->
  <div class="result-container" id="resultContainer">
    <div class="loading-spinner" id="loadingSpinner">
      <div style="font-size:24px; margin-bottom:8px;">⏳</div>
      <div>正在連線後端同步計算排盤中...</div>
    </div>
    <div id="chartContent"></div>
  </div>

  <div class="footer">
    資料來源聲明：本排盤系統之演算法與實律數據運算自 <a href="https://myfate.herokuapp.com/" target="_blank" rel="noopener noreferrer">myfate.herokuapp.com</a> 官方伺服器。
  </div>
</div>

<script>
  const RENDER_BASE = "https://bazi-app-e7uy.onrender.com";
  const PROXY_API_URL = `${RENDER_BASE}/api/bazi`;

  function initOptions() {
    const ySel = document.getElementById("inputYear");
    for (let y = 1900; y <= 2050; y++) {
      let opt = document.createElement("option");
      opt.value = y;
      let label = (y >= 1912) ? `民國 ${y - 1911} (西元${y}) 年` : `民前 ${1912 - y} (西元${y}) 年`;
      opt.textContent = label;
      if (y === 1975) opt.selected = true;
      ySel.appendChild(opt);
    }
    const mSel = document.getElementById("inputMonth");
    for (let m = 1; m <= 12; m++) {
      let opt = document.createElement("option");
      opt.value = m; opt.textContent = m;
      if (m === 7) opt.selected = true;
      mSel.appendChild(opt);
    }
    const dSel = document.getElementById("inputDay");
    for (let d = 1; d <= 31; d++) {
      let opt = document.createElement("option");
      opt.value = d; opt.textContent = d;
      if (d === 28) opt.selected = true;
      dSel.appendChild(opt);
    }
  }

  async function checkServerStatus() {
    const statusBox = document.getElementById("serverStatus");
    const statusText = document.getElementById("statusText");
    statusBox.className = "server-status waking";
    statusText.textContent = "伺服器連線中...";

    try {
      const res = await fetch(`${RENDER_BASE}/`, { method: "GET" });
      if (res.ok) {
        statusBox.className = "server-status online";
        statusText.textContent = "● 後端伺服器在線";
      } else {
        statusText.textContent = `伺服器回應異常 (${res.status})`;
      }
    } catch (e) {
      statusText.textContent = "伺服器喚醒中，請稍候...";
    }
  }

  async function fetchBaziData() {
    const name = document.getElementById("userName").value.trim() || "無名氏";
    const gender = document.getElementById("userGender").value;
    const year = document.getElementById("inputYear").value;
    const month = document.getElementById("inputMonth").value;
    const day = document.getElementById("inputDay").value;
    const hour = document.getElementById("inputHour").value;

    const spinner = document.getElementById("loadingSpinner");
    const content = document.getElementById("chartContent");

    spinner.classList.add("active");
    content.innerHTML = "";

    const requestUrl = `${PROXY_API_URL}?year=${year}&month=${month}&day=${day}&hour=${hour}&gender=${encodeURIComponent(gender)}&name=${encodeURIComponent(name)}`;

    try {
      const res = await fetch(requestUrl);
      if (!res.ok) {
        throw new Error(`伺服器回應錯誤 HTTP ${res.status}: ${res.statusText}`);
      }
      const data = await res.json();
      spinner.classList.remove("active");

      if (data.html) {
        content.innerHTML = data.html;
      } else {
        content.innerHTML = `<div style="color:red; text-align:center;">獲取命盤失敗，請稍後重試。</div>`;
      }
    } catch (err) {
      spinner.classList.remove("active");
      content.innerHTML = `<div style="color:#c62828; text-align:center; padding:20px;">⚠️ 連線失敗：${err.message}</div>`;
    }
  }

  initOptions();
  checkServerStatus();
</script>

</body>
</html>
