#!/usr/bin/env python3
"""
SHU ICS 課程表爬蟲
從世新大學教務系統撈取課程資料，產出 JSON 檔案
"""

import json
import re
import sys
import time
import urllib.parse
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://ap4.shu.edu.tw/stu1/stu1/sc01021.aspx"

# 預設參數
DEFAULT_YEAR = "115"
DEFAULT_SEMESTER = "1"

# 目標系所代碼
# A07 = 資訊傳播學系, AC1 = 新聞傳播學院
TARGET_DEPTS = ["A07", "AC1"]

# AC1 直接搜尋的課程代碼
AC1_COURSE_CODE = "JCOM-130-02-A1"

# A07 需要額外搜尋的合開課程
A07_EXTRA_COURSES = ["INFO-437-01-A1"]

# 時間表 (固定值)
TIME_SLOTS = [
    {"period": "1", "label": "1", "time": "08:10<br>~<br>09:00"},
    {"period": "2", "label": "2", "time": "09:10<br>~<br>10:00"},
    {"period": "3", "label": "3", "time": "10:10<br>~<br>11:00"},
    {"period": "4", "label": "4", "time": "11:10<br>~<br>12:00"},
    {"period": "5", "label": "5", "time": "12:10<br>~<br>13:00", "isLunch": True},
    {"period": "6", "label": "6", "time": "13:10<br>~<br>14:00"},
    {"period": "7", "label": "7", "time": "14:10<br>~<br>15:00"},
    {"period": "8", "label": "8", "time": "15:10<br>~<br>16:00"},
    {"period": "9", "label": "9", "time": "16:10<br>~<br>17:00"},
    {"period": "10", "label": "10", "time": "17:10<br>~<br>18:00"},
    {"period": "12", "label": "12-14", "time": "19:10<br>~<br>22:00"},
]

DAY_MAP = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "日": 0, "六": 6}


def get_session() -> requests.Session:
    """建立並回傳 requests Session"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://ap4.shu.edu.tw",
        "Referer": BASE_URL,
    })
    return session


def extract_form_fields(soup: BeautifulSoup) -> dict:
    """從 HTML 表單中提取所有欄位"""
    form = soup.find("form", {"id": "Form_SC01021"})
    if not form:
        return {}

    fields = {}
    for inp in form.find_all(["input", "select"]):
        name = inp.get("name")
        if not name:
            continue

        if inp.name == "input":
            input_type = inp.get("type", "text")
            if input_type == "checkbox":
                # Checkbox 只在勾選時傳送
                fields[name] = inp.get("value", "on") if inp.get("checked") else ""
            else:
                fields[name] = inp.get("value", "")
        elif inp.name == "select":
            selected = inp.find("option", selected=True)
            if selected:
                fields[name] = selected.get("value", "")
            else:
                # 如果沒有 selected，取第一個 option
                first_opt = inp.find("option")
                if first_opt:
                    fields[name] = first_opt.get("value", "")

    return fields


def make_post(session: requests.Session, fields: dict, event_target: str = "") -> BeautifulSoup:
    """送出 POST 請求並回傳解析後的 BeautifulSoup"""
    data = fields.copy()
    data["__EVENTTARGET"] = event_target
    data["__EVENTARGUMENT"] = ""

    encoded = urllib.parse.urlencode(data)
    resp = session.post(BASE_URL, data=encoded, timeout=30)
    resp.encoding = "utf-8"
    return BeautifulSoup(resp.text, "html.parser")


def get_department_options(soup: BeautifulSoup) -> list:
    """從頁面中解析系所 dropdown 選項"""
    select = soup.find("select", {"name": "SRH_majr_no"})
    if not select:
        return []

    options = []
    for opt in select.find_all("option"):
        value = opt.get("value", "")
        text = opt.get_text(strip=True)
        if value and text:
            options.append({"value": value, "text": text})
    return options


def search_courses(session: requests.Session, fields: dict, dept_code: str, course_code: str = "") -> tuple:
    """搜尋特定系所的課程"""
    fields["SRH_majr_no"] = dept_code
    fields["SRH_disp_cr_code"] = course_code
    fields["SRH_search_button"] = "搜尋"

    soup = make_post(session, fields, "")

    # 解析課程表格
    courses = parse_course_table(soup)

    # 更新 fields 供後續使用
    new_fields = extract_form_fields(soup)
    return courses, new_fields


def parse_course_table(soup: BeautifulSoup) -> list:
    """解析課程表格"""
    table = soup.find("table", {"id": "GRD_DataGrid"})
    if not table:
        return []

    courses = []
    rows = table.find_all("tr")

    # 跳過表頭 (第一行)
    for row in rows[1:]:
        cells = row.find_all("td")
        if len(cells) < 11:
            continue

        course = parse_course_row(cells)
        if course:
            courses.append(course)

    return courses


def parse_course_row(cells) -> dict:
    """解析單一課程列"""
    try:
        # 表格欄位: 開課系級, 課程簡碼, 授課語言, 學科名稱, 年別, 學分, 選別, 授課老師, 星期, 節次, 教室, 週別, 備註
        class_code = cells[0].get_text(strip=True)
        disp_code = cells[1].get_text(strip=True)
        lang = cells[2].get_text(strip=True)
        full_name_cell = cells[3]
        year = cells[4].get_text(strip=True)
        credits = cells[5].get_text(strip=True)
        required_text = cells[6].get_text(strip=True)
        teacher = cells[7].get_text(strip=True)
        day_text = cells[8].get_text(strip=True)
        period_text = cells[9].get_text(strip=True)
        room = cells[10].get_text(strip=True)

        # 解析課程名稱 (可能包含超連結)
        # HTML 結構: <a href="...">中文名稱</a><br/>English Name
        link_tag = full_name_cell.find("a")
        if link_tag:
            name = link_tag.get_text(strip=True)
        else:
            name = full_name_cell.get_text(strip=True)
            # 移除英文名稱 (如果沒有 <a> 標籤)
            name = re.split(r"\s*[A-Z]", name)[0].strip()
        # 移除多餘空白
        name = re.sub(r"\s+", " ", name)

        # 解析星期
        day = DAY_MAP.get(day_text, 0)

        # 解析節次 (格式: "6,7" 或 "6-8" 或 "6,7,8")
        periods = parse_periods(period_text)

        # 解析選別
        required = required_text == "必"

        # 解析班級資訊
        year_num, class_type, class_name = parse_class_info(class_code, year, cells)

        course = {
            "name": name,
            "teacher": teacher,
            "day": day,
            "periods": periods,
            "room": room,
            "year": year_num,
            "classType": class_type,
            "required": required,
            "className": class_name,
        }

        # 加入課程簡碼 (如有)
        if disp_code:
            course["code"] = disp_code

        return course
    except Exception as e:
        print(f"  解析課程列時發生錯誤: {e}", file=sys.stderr)
        return None


def parse_periods(period_text: str) -> list:
    """解析節次文字為列表"""
    period_text = period_text.strip()
    if not period_text:
        return []

    # 統一分隔符: ~ → -
    period_text = period_text.replace("~", "-")

    # 處理 "6,7" 格式
    if "," in period_text:
        return [p.strip() for p in period_text.split(",")]

    # 處理 "6-8" 格式
    if "-" in period_text:
        parts = period_text.split("-")
        if len(parts) == 2:
            try:
                start = int(parts[0])
                end = int(parts[1])
                return [str(i) for i in range(start, end + 1)]
            except ValueError:
                pass

    # 單一節次
    return [period_text]


def parse_class_info(class_code: str, year: str, cells) -> tuple:
    """解析班級資訊，回傳 (year_num, class_type, class_name)"""
    class_code = class_code.strip()

    # 清理 class_code: 移除代碼前綴 (如 "A07020資傳系二年級" → "資傳系二年級")
    # 常見格式: "A07020資傳系二年級", "資訊傳播學系 二甲"
    clean_code = re.sub(r"^[A-Z0-9]+", "", class_code).strip()

    # 從 class_code 解析班級
    if "甲" in clean_code:
        class_type = "a"
        match = re.search(r"([一二三四五六七八九十]+甲)", clean_code)
        class_name = match.group(1) if match else clean_code
    elif "乙" in clean_code:
        class_type = "b"
        match = re.search(r"([一二三四五六七八九十]+乙)", clean_code)
        class_name = match.group(1) if match else clean_code
    elif "傳播學院" in clean_code or "學院" in clean_code:
        class_type = "common"
        class_name = "傳播學院"
    elif "共同課程" in clean_code:
        class_type = "common"
        class_name = "共同課程"
    elif "二年級" in clean_code:
        class_type = "common"
        class_name = "大二"
    elif "三年級" in clean_code:
        class_type = "common"
        class_name = "大三"
    elif "四年級" in clean_code:
        class_type = "common"
        class_name = "大四"
    else:
        # 嘗試從年別和班別推斷
        class_type = "common"
        class_name = clean_code if clean_code else f"大{year}"

    # 解析年級 (year 欄位可能包含 "1", "2", "半年", "全" 等)
    year_num = ""
    if year:
        # 嘗試直接轉數字
        if year.isdigit():
            year_num = year
        else:
            # 處理中文數字
            cn_to_num = {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5"}
            for cn, num in cn_to_num.items():
                if cn in year:
                    year_num = num
                    break

    # 如果 year_num 還是空，嘗試從 class_name 解析
    if not year_num and class_name:
        for cn, num in {"一": "1", "二": "2", "三": "3", "四": "4", "五": "5"}.items():
            if cn in class_name:
                year_num = num
                break

    return year_num, class_type, class_name


def build_output(dept_name: str, semester_label: str, all_courses: list) -> dict:
    """建立輸出 JSON 結構"""
    return {
        "metadata": {
            "department": dept_name,
            "semester": semester_label,
        },
        "timeSlots": TIME_SLOTS,
        "courses": all_courses,
    }


def setup_session(year: str, semester: str, delay: float = 1.0) -> tuple:
    """建立新的 session 並設定好表單狀態 (學年、學期、學制)"""
    session = get_session()

    # GET 初始頁面
    resp = session.get(BASE_URL, timeout=30)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")
    fields = extract_form_fields(soup)
    time.sleep(delay)

    # POST 學年
    fields["SRH_setyear_SRH"] = year
    soup = make_post(session, fields, "SRH_setyear_SRH")
    fields = extract_form_fields(soup)
    time.sleep(delay)

    # POST 學期
    fields["SRH_setterm_SRH"] = semester
    soup = make_post(session, fields, "SRH_setterm_SRH")
    fields = extract_form_fields(soup)
    time.sleep(delay)

    # POST 學制 (學士班)
    fields["SRH_type_no_SRH"] = "A"
    soup = make_post(session, fields, "SRH_type_no_SRH")
    fields = extract_form_fields(soup)

    return session, fields


def main():
    """主程式"""
    import argparse

    parser = argparse.ArgumentParser(description="SHU ICS 課程表爬蟲")
    parser.add_argument("--year", default=DEFAULT_YEAR, help="學年 (預設: 115)")
    parser.add_argument("--semester", default=DEFAULT_SEMESTER, help="學期 (預設: 1)")
    parser.add_argument("--output", help="輸出檔案路徑")
    parser.add_argument("--delay", type=float, default=1.0, help="請求延遲秒數 (預設: 1.0)")
    args = parser.parse_args()

    year = args.year
    semester = args.semester
    semester_label = f"{year}學年度第{semester}學期"
    semester_file = f"{year}-{semester}"
    output_file = args.output or f"course_{semester_file}.json"

    print(f"=== SHU ICS 課程表爬蟲 ===")
    print(f"學期: {semester_label}")
    print(f"目標系所: {', '.join(TARGET_DEPTS)}")
    print(f"輸出檔案: {output_file}")
    print()

    # 逐系所搜尋課程 (每個系所使用獨立 session)
    print("搜尋課程...")
    all_courses = []
    seen_courses = set()  # 用於去重

    for dept_code in TARGET_DEPTS:
        print(f"\n  搜尋 {dept_code}...")
        print(f"    [1/3] 建立新 session...")
        session, fields = setup_session(year, semester, args.delay)

        # 取得系所選項
        dept_options = get_department_options(soup=BeautifulSoup("", "html.parser"))
        # 從 fields 狀態重新取得
        resp = session.post(BASE_URL, data=urllib.parse.urlencode(fields), timeout=30)
        resp.encoding = "utf-8"
        soup_temp = BeautifulSoup(resp.text, "html.parser")
        dept_options = get_department_options(soup_temp)

        dept_info = next((d for d in dept_options if d["value"] == dept_code), None)
        if not dept_info:
            print(f"    警告: 找不到系所 {dept_code}，跳過")
            continue

        print(f"    [2/3] 搜尋 {dept_info['text']}...")
        # AC1 直接用課程代碼搜尋
        course_code = AC1_COURSE_CODE if dept_code == "AC1" else ""
        courses, fields = search_courses(session, fields, dept_code, course_code)
        print(f"    [3/3] 找到 {len(courses)} 門課程")

        # A07 額外搜尋合開課程 (需用新 session)
        if dept_code == "A07":
            for extra_code in A07_EXTRA_COURSES:
                extra_session, extra_fields = setup_session(year, semester, args.delay)
                extra_courses, _ = search_courses(extra_session, extra_fields, dept_code, extra_code)
                courses.extend(extra_courses)
                print(f"    額外搜尋 {extra_code}: {len(extra_courses)} 門")
                time.sleep(args.delay)

        # 去重 (以 code + day + periods 為 key，合開課程合併教師)
        for course in courses:
            key = (course["code"], course["day"], tuple(course["periods"]))
            if key in seen_courses:
                # 合開課程：合併教師欄位
                for existing in all_courses:
                    if (existing["code"], existing["day"], tuple(existing["periods"])) == key:
                        existing["teacher"] = f"{existing['teacher']} / {course['teacher']}"
                        break
            else:
                seen_courses.add(key)
                all_courses.append(course)

        time.sleep(args.delay)

    print(f"\n合併後共 {len(all_courses)} 門課程")

    # 產出 JSON
    print("\n產出 JSON...")
    output = build_output("資訊傳播學系", semester_label, all_courses)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  已寫入 {output_file}")
    print()
    print("=== 完成 ===")


if __name__ == "__main__":
    main()
