# SHU ICS 課程表爬蟲計畫

## 專案概述

世新大學資訊傳播學系（ICS）開課系統自動化爬蟲，從學校教務系統撈取課程資料並產出 JSON，
供前端課表系統使用。

- **目標網站**: https://ap4.shu.edu.tw/stu1/stu1/sc01021.aspx
- **目標學期**: 115學年度第1學期 (115-1)
- **爬蟲範圍**: 資傳系 (INFO) + 新聞傳播學院 (AC1)
- **技術棧**: Python + requests + BeautifulSoup
- **更新方式**: GitHub Actions 定時排程 (每日自動爬取)

---

## 網站分析

### 技術架構
- ASP.NET WebForms 頁面，使用 `__VIEWSTATE` 和 `__EVENTVALIDATION` 機制
- 表單 POST 觸發 postback，動態載入系所 dropdown

### 關鍵表單欄位
| 欄位名稱 | 說明 | 值 |
|---------|------|-----|
| `SRH_setyear_SRH` | 學年 | 115 |
| `SRH_setterm_SRH` | 學期 | 1=第一學期, 2=第二學期 |
| `SRH_type_no_SRH` | 學制 | A=學士班, C=進修, M=碩士... |
| `SRH_majr_no` | 系所 | A07=資傳系, AC1=新聞傳播學院 |
| `SRH_grade` | 年級 | 1-7 |
| `SRH_class_no` | 班別 | 0=不分班, 1=甲, 2=乙... |
| `SRH_teach_name` | 教師姓名 | 文字輸入 |
| `SRH_cr_sql_1~14` | 節次 | checkbox |
| `SRH_day_of_wk_SRH` | 星期 | 0=日, 1=一, ..., 6=六 |
| `SRH_full_name` | 課程名稱 | 文字輸入 |
| `SRH_disp_cr_code` | 課程代碼 | 直接搜尋特定課程 (如 INFO-437-01-A1) |

### 回傳表格欄位
開課系級 | 課程簡碼 | 授課語言 | 學科名稱 | 年別 | 學分 | 選別 | 授課老師 | 星期 | 節次 | 教室 | 週別 | 備註

---

## 爬蟲流程

```
1. GET /sc01021.aspx
   └→ 解析 HTML 取得 __VIEWSTATE, __EVENTVALIDATION, __VIEWSTATEGENERATOR

2. POST 選擇學年 (SRH_setyear_SRH=115)
   └→ 觸發 postback

3. POST 選擇學期 (SRH_setterm_SRH=1)
   └→ 觸發 postback

4. POST 選擇學制 (SRH_type_no_SRH=A)
   └→ 觸發系所 dropdown 動態載入

5. 逐系所搜尋課程:
   - A07 (資傳系): 一般搜尋 + 額外搜尋合開課程
   - AC1 (傳播學院): 用 SRH_disp_cr_code 直接搜尋特定課程

6. 合併去重 + 合開課程教師合併 → 產出 JSON
```

---

## JSON 格式規範

### 輸出格式 (course_115-1.json)
```json
{
  "metadata": {
    "department": "資訊傳播學系",
    "semester": "115學年度第1學期"
  },
  "timeSlots": [
    { "period": "1", "label": "1", "time": "08:10<br>~<br>09:00" },
    { "period": "2", "label": "2", "time": "09:10<br>~<br>10:00" },
    { "period": "3", "label": "3", "time": "10:10<br>~<br>11:00" },
    { "period": "4", "label": "4", "time": "11:10<br>~<br>12:00" },
    { "period": "5", "label": "5", "time": "12:10<br>~<br>13:00", "isLunch": true },
    { "period": "6", "label": "6", "time": "13:10<br>~<br>14:00" },
    { "period": "7", "label": "7", "time": "14:10<br>~<br>15:00" },
    { "period": "8", "label": "8", "time": "15:10<br>~<br>16:00" },
    { "period": "9", "label": "9", "time": "16:10<br>~<br>17:00" },
    { "period": "10", "label": "10", "time": "17:10<br>~<br>18:00" },
    { "period": "12", "label": "12-14", "time": "19:10<br>~<br>22:00" }
  ],
  "courses": [
    {
      "code": "INFO-238-01-A1",
      "name": "資訊傳播專題(一)",
      "teacher": "莊道明",
      "day": 1,
      "periods": ["3", "4"],
      "room": "CB205",
      "year": "2",
      "classType": "a",
      "required": true,
      "className": "二甲"
    }
  ]
}
```

### 欄位轉換規則
| 原始欄位 | 目標欄位 | 轉換邏輯 |
|---------|----------|----------|
| 學科名稱 | name | 直接取用 |
| 授課老師 | teacher | 直接取用 |
| 星期 | day | 中文轉數字：一→1, 二→2, 三→3, 四→4, 五→5 |
| 節次 | periods | "6,7" → ["6","7"]；"6-8" → ["6","7","8"] |
| 教室 | room | 直接取用 |
| 年別 | year | 直接取用 |
| 課程簡碼 | code | 直接取用（114-1 留空 ""） |
| 選別 | required | "必"→true, "選"→false |
| 開課系級 | className | 解析班別：資傳一甲→"資傳一甲", 傳播學院→"傳播學院" |
| 課程簡碼前綴 | classType | 以 INFO 開頭→"a"/"b"（依班別）, 其他→"common" |

### 合開課程處理
- 同一課程代碼 (code) + 同一天 + 同一節次 → 合併為一筆
- 教師欄位用 " / " 連接 (如 "江信昱 / 郭冠麟")

### 格式統一說明 (2026-07-15 更新)
所有學期的 JSON 檔案格式已統一：
- **timeSlots.time**: `08:10<br>~<br>09:00` 格式
- **timeSlots key**: period, label, time 順序
- **className**: 保留 "資傳" 前綴 (如 "資傳一甲", "資傳二年級")
- **code 欄位**: 所有檔案都有 (114-1 留空 "")
- **note 欄位**: 保留 (如 114-1 的 "note": "學號尾數1、2、3")
- **合開教師**: 統一使用 " / " 格式

---

## 已知重要坑 (必讀)

### 1. Session 狀態衝突
**問題**: ASP.NET server 會記住搜尋狀態，在同一 session 中搜尋第二個系所會失敗（返回空表格）。

**症狀**: 
- 搜尋 A07 後再搜尋 AC1 → AC1 返回 0 門課程
- 搜尋 AC1 後再搜尋 A07 → A07 返回 0 門課程

**解決方案**: 每個系所使用獨立的 `requests.Session()`，透過 `setup_session()` 建立乾淨的表單狀態。

### 2. 課程代碼搜尋需要新 Session
**問題**: 用 `SRH_disp_cr_code` 直接搜尋特定課程時，如果 session 已有搜尋紀錄，會返回 0 結果。

**症狀**: 
- 先搜尋 A07，再用 `SRH_disp_cr_code=INFO-437-01-A1` 搜尋 → 0 結果
- 直接搜尋 `INFO-437-01-A1` → 2 結果

**解決方案**: 額外搜尋合開課程時，建立新的 session。

### 3. 頁面分頁限制
**問題**: A07 搜尋結果限制 10 筆，某些課程（如 INFO-437-01-A1）不在第一頁。

**解決方案**: 用 `SRH_disp_cr_code` 直接搜尋特定課程代碼。

### 4. 課程代碼格式變動
**問題**: 115-1 學期課程代碼從 `INFO-XXX` 改為 `JCOM-XXX` 格式（傳播學院課程）。

**說明**: 這是學校系統變動，非爬蟲問題。

---

## 檔案結構

```
ics-course-table/
├── .github/
│   └── workflows/
│       └── scrape.yml          # GitHub Actions 排程
├── scrape.py                   # 爬蟲主程式
├── convert_json.py             # JSON 格式轉換腳本
├── requirements.txt            # Python 依賴
├── PLAN.md                     # 本規劃文件
├── config.json                 # 學期設定
├── course_115-1.json           # 115-1 課程資料 (產出)
├── course_114-2.json           # 114-2 課程資料
├── course_114-1.json           # 114-1 課程資料
├── index.html                  # 前端課表系統
├── manifest.json               # PWA 設定
├── service-worker.js           # PWA 快取
└── ... (icon 檔案)
```

---

## 當前狀態 (115-1 學期)

### 已完成
- [x] 爬蟲主程式 `scrape.py` 正常運作
- [x] A07 (資傳系) 搜尋正常
- [x] AC1 (傳播學院) 用 `SRH_disp_cr_code` 搜尋特定課程
- [x] 合開課程教師欄位合併 (江信昱 / 郭冠麟)
- [x] GitHub Actions 定時排程設定
- [x] 前端 `index.html` 正常顯示
- [x] JSON 格式統一 (114-1, 114-2, 115-1)
- [x] className 統一加上 "資傳" 前綴

### 當前課程列表 (115-1)
| 課程代碼 | 課程名稱 | 教師 |
|---------|---------|------|
| INFO-115-01-A1 | 資訊傳播概論 | 莊道明 |
| INFO-116-01-A1 | 資訊行銷 | 江信昱 |
| INFO-118-01-A1 | 探索資訊傳播 | 黃昭謀 |
| INFO-119-01-A1 | 0 AI藝術創作與攝影 | 陳俊廷 |
| INFO-231-01-A1 | 社群經營 | 黃昭謀 |
| INFO-233-01-A1 | 分類學原理與應用 | 阮明淑 |
| INFO-234-01-A1 | 資訊檢索與創意寫作 | 阮明淑 |
| INFO-242-01-A1 | 生成式AI的內容核實 | 江信昱 / 郭冠麟 |
| INFO-244-01-A1 | 0剪輯技巧與敘事 | 陳中宇 |
| INFO-437-01-A1 | 資訊傳播專題（四） | 江信昱 / 郭冠麟 |
| JCOM-130-02-A1 | 0數位影像製作實務 | 陳怡君 |

---

## GitHub Actions 設定

### 排程策略
- **定時執行**: 每日凌晨 6:00 UTC+8 (22:00 UTC)
- **手動觸發**: 支援 `workflow_dispatch` 手動執行

### 工作流程
```yaml
name: Scrape Course Data
on:
  schedule:
    - cron: '0 22 * * *'   # 每日 06:00 UTC+8
  workflow_dispatch:         # 手動觸發

jobs:
  scrape:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python scrape.py
      - uses: stefanzweifel/git-auto-commit-action@v5
        with:
          commit_message: 'chore: update course data [automated]'
```

---

## 依賴

```
requests>=2.28.0
beautifulsoup4>=4.12.0
```

---

## 使用方式

### 本地執行
```bash
pip install -r requirements.txt
python scrape.py --year 115 --semester 1 --delay 1.5
```

### 參數說明
- `--year`: 學年 (預設: 115)
- `--semester`: 學期 (預設: 1)
- `--output`: 輸出檔案路徑 (預設: course_{year}-{semester}.json)
- `--delay`: 請求延遲秒數 (預設: 1.0)

### 測試前端
```bash
python -m http.server 8080
# 瀏覽器開啟 http://localhost:8080
```

---

## 維護指南

### 新增學期
1. 更新 `config.json` 加入新學期
2. 修改 `scrape.py` 中的 `TARGET_DEPTS` 和相關設定
3. 執行爬蟲產出新 JSON

### 新增課程搜尋
1. 在 `A07_EXTRA_COURSES` 或 `AC1_COURSE_CODE` 加入課程代碼
2. 確認搜尋邏輯正確

### 排錯
1. 檢查 ViewState/EventValidation 是否正確解析
2. 確認 session 是否獨立（避免狀態衝突）
3. 查看爬蟲輸出的 debug 資訊
