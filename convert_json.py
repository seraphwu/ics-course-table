#!/usr/bin/env python3
"""
轉換 course JSON 檔案格式，統一為 114-2/115-1 格式
"""

import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 統一的 timeSlots（使用 114-2/115-1 的時間）
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

# className 映射：簡短 → 完整
CLASS_NAME_MAP = {
    "一甲": "資傳一甲",
    "一乙": "資傳一乙",
    "二甲": "資傳二甲",
    "二乙": "資傳二乙",
    "三甲": "資傳三甲",
    "三乙": "資傳三乙",
    "四甲": "資傳四甲",
    "四乙": "資傳四乙",
    "大一": "資傳一年級",
    "大二": "資傳二年級",
    "大三": "資傳三年級",
    "大四": "資傳四年級",
}


def convert_114_1(data):
    """轉換 course_114-1.json"""
    # 1. 替換 timeSlots
    data["timeSlots"] = TIME_SLOTS

    # 2. 轉換 courses
    for course in data["courses"]:
        # 新增 code 欄位（留空）
        if "code" not in course:
            course["code"] = ""

        # 修正合開教師格式：/ → " / "
        if "/" in course["teacher"] and " / " not in course["teacher"]:
            course["teacher"] = course["teacher"].replace("/", " / ")

    return data


def convert_classname(data):
    """轉換 className：加上 "資傳" 前綴"""
    for course in data["courses"]:
        cn = course.get("className", "")
        if cn in CLASS_NAME_MAP:
            course["className"] = CLASS_NAME_MAP[cn]
    return data


def convert_file(filename, converter):
    """轉換單一檔案"""
    print(f"轉換 {filename}...")
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    data = converter(data)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  完成 ({len(data['courses'])} 門課程)")


def main():
    convert_file("course_114-1.json", convert_114_1)
    convert_file("course_114-2.json", convert_classname)
    convert_file("course_115-1.json", convert_classname)
    print("\n全部轉換完成！")


if __name__ == "__main__":
    main()
