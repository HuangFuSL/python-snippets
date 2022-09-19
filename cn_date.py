'''
公历农历转换

作者：HuangFuSL

依赖包：pythonnet

输入格式：
2022 - 输出2022年的所有农历日期
202202 - 输出2022年2月的所有农历日期
20220202 - 输出2022年2月2日的农历日期
其他 - 输出当天的农历日期

输出格式
2022-12-28 十一月初六
'''

import datetime
import itertools
import sys
from typing import Any, List

try:
    import clr

    clr.AddReference("System.Globalization")
    from System import DateTime  # type: ignore
    from System.Globalization import ChineseLunisolarCalendar  # type: ignore
except ImportError:
    sys.exit(-1)


class InvalidInput(Exception):

    def __init__(self, *args) -> None:
        super().__init__(*args)

    def __str__(self) -> str:
        return 'Invalid Input'


CALENDAR = ChineseLunisolarCalendar()
NUMBER_LOOKUP = [
    '初', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二'
]
TEN_LOOKUP = '初十廿三'


def build_result(cn_month: int, cn_day: int) -> str:
    ''' 数字转文本 '''
    if cn_day % 10:
        day = TEN_LOOKUP[cn_day // 10] + NUMBER_LOOKUP[cn_day % 10]
    else:
        day = TEN_LOOKUP[cn_day // 10] + '十'
        if day[0] == '十':
            day = NUMBER_LOOKUP[0] + '十'

    if cn_month != 1:
        month = NUMBER_LOOKUP[cn_month] + '月'
    else:
        month = '正月'

    return month + day


def convert(date: DateTime) -> str:
    ''' 调用C#函数库 '''
    cn_year = CALENDAR.GetYear(date)
    cn_month = CALENDAR.GetMonth(date)
    cn_day = CALENDAR.GetDayOfMonth(date)
    leap_month = CALENDAR.GetLeapMonth(cn_year)
    true_month = cn_month if cn_month < leap_month else cn_month - 1
    return ('闰' if cn_month == leap_month else '') + build_result(true_month, cn_day)


def get_day_iter(y: int, m: int):
    ''' 获取月份天数 '''
    lookup = [0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    days_total = lookup[m] + 1
    if m == 2 and (y % 4 == 0 and y % 100 != 0 or y % 400 == 0):
        days_total += 1
    yield from range(1, days_total)


if __name__ == "__main__":
    def to_list(_): return [int(_)]
    date_str = input().strip()

    try:
        if len(date_str) == 8:
            y, m, d = map(to_list, [date_str[:4], date_str[4:6], date_str[6:]])
        elif len(date_str) == 6:
            y, m = map(to_list, [date_str[:4], date_str[4:]])
            d = None
        elif len(date_str) == 4:
            y = to_list(date_str[:4])
            m, d = range(1, 13), None
        else:
            raise InvalidInput()
    except InvalidInput:
        y, m, d = map(to_list, [datetime.date.today().timetuple()[:3]])

    for a, b in itertools.product(y, m):
        for c in d if d is not None else get_day_iter(a, b):
            print(f'{datetime.date(a, b, c):%Y-%m-%d} {convert(DateTime(a, b, c))}')
