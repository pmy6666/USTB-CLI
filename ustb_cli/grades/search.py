"""课程名称与代码的本地搜索规则。"""

import unicodedata


ALIASES = (
    ("高等数学", "高数"),
    ("线性代数", "线代"),
    ("大学物理", "大物"),
    ("大学英语", "大英"),
    ("概率论与数理统计", "概率统计", "概统"),
)


def normalize(value):
    # 统一大小写、全半角及罗马数字，忽略空白和标点。
    return "".join(c for c in unicodedata.normalize("NFKC", value or "").casefold() if c.isalnum())


def expand_aliases(value):
    for canonical, *aliases in ALIASES:
        for alias in aliases:
            value = value.replace(alias, canonical)
    return value


def matches_course(course, keywords, exact=False):
    fields = [normalize(course[key]) for key in ("name", "course_code")]
    for keyword in keywords:
        query = normalize(keyword)
        if not query:
            raise ValueError("搜索关键词需要包含文字或数字。")
        if exact:
            matched = query in fields
        else:
            matched = (any(query in field for field in fields) or
                       expand_aliases(query) in expand_aliases(fields[0]))
        if not matched:
            return False
    return True
