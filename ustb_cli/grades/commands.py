"""成绩业务的命令入口。"""

from datetime import datetime, timezone
import argparse
import json
import sys

import requests

from ..auth.client import AuthError
from ..auth.session import load_session
from .calculator import calculate
from .client import GradesClient, GradesError, SessionExpired, validate_year
from .ranking import print_rank_report, rank_report
from .search import normalize


def year_argument(value):
    try:
        return validate_year(value)
    except GradesError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def search_argument(value):
    if not normalize(value):
        raise argparse.ArgumentTypeError("搜索关键词需要包含文字或数字。")
    return value


def register_commands(subparsers):
    grades = subparsers.add_parser("grades", help="查询并计算主修必修课加权均分")
    grades.set_defaults(handler=run_grades)
    grades.add_argument("--year", type=year_argument, help="按学年筛选，例如 2025-2026")
    grades.add_argument("--term", choices=("1", "2", "3"), help="按学期筛选")
    grades.add_argument("--repeat", choices=("exclude", "all"), default="exclude",
                        help="同课多条记录：默认排除待核对，all 按全部考试记录计算")
    grades.add_argument("--json", action="store_true", help="输出 JSON，十进制数值以字符串表示")
    ranks = subparsers.add_parser("ranks", help="查询每门课程的成绩排名与总人数")
    ranks.set_defaults(handler=run_ranks)
    ranks.add_argument("keywords", nargs="*", type=search_argument, metavar="关键词",
                       help="按课程名称或代码搜索，支持高数/线代等简称；多个关键词须全部匹配")
    ranks.add_argument("--exact", action="store_true", help="按完整课程名称或代码匹配，不扩展简称")
    ranks.add_argument("--year", type=year_argument, help="按学年筛选，例如 2025-2026")
    ranks.add_argument("--term", choices=("1", "2", "3"), help="按学期筛选")
    ranks.add_argument("--json", action="store_true", help="输出 JSON，缺失排名或总人数为 null")


def run_grades(args):
    return run_query(args, ranking=False)


def run_ranks(args):
    return run_query(args, ranking=True)


def run_query(args, ranking):
    try:
        cookies = load_session(args.state_dir / "session.bin")
        if not cookies:
            raise SessionExpired("未找到本地会话，请先运行 /login 或 cli.exe auth login。")
        client = GradesClient()
        client.auth.session.cookies.update(cookies)
        records = client.fetch(args.year, args.term)
        report = (rank_report(records, args.keywords, args.exact) if ranking
                  else calculate(records, args.repeat))
        report["fetched_at"] = datetime.now(timezone.utc).isoformat()
        report["filters"] = {"year": args.year, "term": args.term}
        if ranking and args.keywords:
            report["filters"].update(search=args.keywords, match="exact" if args.exact else "fuzzy")
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        elif ranking:
            print_rank_report(report, args.year, args.term)
        else:
            print("主修必修课加权成绩" + ("（部分结果，有待核对项）" if report["partial"] else ""))
            print(f"学年：{args.year or '全部'} · 学期：{args.term or '全部'} · 查询到 {len(records)} 条成绩")
            if not records:
                print("当前筛选条件下没有成绩记录；可运行 /grades 查看全部学年。")
            print("公式：" + report["formula"])
            print(f"纳入 {report['course_count']} 门 · 总学分 {report['total_credits']} · 加权总分 {report['weighted_sum']}")
            print("加权均分：" + (report["average"] if report["average"] is not None else "无可计算课程"))
            print("口径：数值不及格计入；等级成绩不换算；" +
                  ("同课多条记录全部计入。" if args.repeat == "all" else "同课多条记录排除待核对。"))
            for item in report["included"]:
                print(f"  {item['name']} [{item['course_code'] or '-'}] · {item['semester'] or '-'} · "
                      f"{item['score']} × {item['credits']} = {item['contribution']}")
            if report["excluded"]:
                print(f"排除/待核对 {len(report['excluded'])} 条：")
                for item in report["excluded"]:
                    print(f"  {item['name']} [{item['course_code'] or '-'}] · {item['semester'] or '-'}：{item['reason']}")
        return 0
    except SessionExpired as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n已取消成绩查询。", file=sys.stderr)
        return 130
    except requests.RequestException:
        print("成绩查询网络请求失败，请检查网络后重试。", file=sys.stderr)
        return 2
    except (GradesError, AuthError, OSError, ValueError) as exc:
        print(f"成绩查询失败：{exc}", file=sys.stderr)
        return 2
