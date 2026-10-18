"""读取成绩接口自带的课程排名；不推算排名或合并考试记录。"""

from .search import matches_course

def first_present(record, keys):
    """与参考扩展一致，空字符串和 null 跳过，0 保留。"""
    for key in keys:
        value = record.get(key)
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            text = str(value).strip()
            if text:
                return text
    return None


def rank_report(records, keywords=(), exact=False):
    courses = []
    for record in records:
        course = {
            "name": first_present(record, ("kcmc", "KCMC", "courseName", "kcMc")),
            "course_code": first_present(record, ("kcdm", "KCDM", "kch", "KCH", "kcbh")),
            "semester": first_present(record, ("xnxqmc", "xnxq")),
            "score": first_present(record, ("zzcj",)),
            "rank": first_present(record, ("pm", "PM", "rank", "paiming")),
            "total": first_present(record, ("zrs", "ZRS", "total", "totalCount")),
        }
        if matches_course(course, keywords, exact):
            courses.append(course)
    return {
        "source": "/cjgl/grcjcx/grcjcx",
        "course_count": len(courses),
        "queried_count": len(records),
        "ranked_count": sum(item["rank"] is not None for item in courses),
        "incomplete_count": sum(item["rank"] is None or item["total"] is None for item in courses),
        "courses": courses,
    }


def print_rank_report(report, year=None, term=None):
    print("课程成绩排名")
    print(f"学年：{year or '全部'} · 学期：{term or '全部'} · 查询到 {report['course_count']} 条成绩")
    print(f"有排名 {report['ranked_count']} 条 · 排名或总人数未提供 {report['incomplete_count']} 条")
    keywords = report.get("filters", {}).get("search", [])
    if keywords:
        mode = "精确" if report["filters"]["match"] == "exact" else "模糊"
        print(f"搜索（{mode}，全部关键词）：{' / '.join(keywords)} · 从 {report['queried_count']} 条成绩中匹配 {report['course_count']} 条")
    print("口径：直接展示教务接口返回的课程排名和总人数；排名范围以学校为准。")
    if not report["courses"]:
        if keywords:
            print("未找到匹配课程；可缩短关键词，或运行 /ranks 查看全部课程。")
        else:
            print("当前筛选条件下没有成绩记录；可运行 /ranks 查看全部学年。")
    for item in report["courses"]:
        print(f"  {item['name'] or '未命名课程'} [{item['course_code'] or '-'}] · "
              f"{item['semester'] or '-'} · 总评 {item['score'] or '未提供'} · "
              f"排名 {item['rank'] if item['rank'] is not None else '未提供'} · "
              f"总人数 {item['total'] if item['total'] is not None else '未提供'}")
