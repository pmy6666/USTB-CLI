"""只读成绩接口；复用认证客户端的会话和重定向校验。"""

import json
import re
from urllib.parse import urlsplit

from ..auth.client import AuthClient, BYYT


class GradesError(Exception):
    pass


class SessionExpired(GradesError):
    pass


def validate_year(year):
    if not re.fullmatch(r"[0-9]{4}-[0-9]{4}", year) or int(year[5:]) != int(year[:4]) + 1:
        raise GradesError("学年格式应为连续两年，例如 2023-2024。")
    return year


def filter_records(records, year=None, term=None):
    if year is None and term is None:
        return records
    selected = []
    for row in records:
        # 实际响应：xnxq=2023-20241，xnxqmc=2023-2024-1。
        semester = None
        for field in ("xnxq", "xnxqmc"):
            semester = re.fullmatch(r"([0-9]{4}-[0-9]{4})-?([123])", str(row.get(field) or "").strip())
            if semester:
                break
        if semester is None:
            raise GradesError("部分成绩缺少可识别的学年学期，无法可靠筛选；请先运行不带筛选的 /grades。")
        if (year is None or semester[1] == year) and (term is None or semester[2] == term):
            selected.append(row)
    return selected


class GradesClient:
    def __init__(self, auth=None):
        self.auth = auth or AuthClient()

    def post(self, path, **kwargs):
        response = self.auth.request("POST", BYYT + path, **kwargs)
        if response.status_code in (401, 403) or urlsplit(response.url).path.startswith(
                ("/authentication/", "/oauth/", "/idp/")):
            raise SessionExpired("未登录或会话已失效，请先运行 /login 或 cli.exe auth login。")
        response.raise_for_status()
        try:
            result = response.json()
        except ValueError:
            raise GradesError("成绩接口未返回 JSON，请检查登录状态或稍后重试。") from None
        if not isinstance(result, dict):
            raise GradesError("成绩接口响应格式异常。")
        code = result.get("code")
        if str(code) in ("401", "403"):
            raise SessionExpired("教务会话已失效，请重新登录。")
        if code is not None and str(code) not in ("0", "200"):
            raise GradesError("教务接口返回业务错误，未进行计算。")
        return result

    def fetch(self, year=None, term=None):
        if year is not None:
            validate_year(year)
        me = self.post("/user/me", data={})
        me = me.get("data", me)
        if not isinstance(me, dict) or not any(me.get(k) for k in ("yhdm", "username", "userName")):
            raise SessionExpired("未取得登录用户信息，请重新登录。")
        records, seen_pages, total = [], set(), None
        for page in range(1, 1001):
            result = self.post("/cjgl/grcjcx/grcjcx", json={
                # 学校接口单独传 xn 会返回空列表；统一查全，再按响应字段筛选。
                "xn": None, "xq": None, "kcmc": None, "cxbj": "-1",
                "pylx": me.get("pylx") or "1", "current": page, "pageSize": 500,
                "xscjlb": None, "sffx": None, "yhdm": me.get("yhdm") or None,
            })
            content = result.get("content")
            if not isinstance(content, dict) or not isinstance(content.get("list"), list):
                raise GradesError("成绩分页格式异常，未进行计算。")
            rows = content["list"]
            raw_total = content.get("total")
            if isinstance(raw_total, bool) or not str(raw_total).isdigit():
                raise GradesError("成绩分页缺少有效总条数，无法确认数据完整性。")
            current_total = int(raw_total)
            if total is not None and current_total != total:
                raise GradesError("查询期间成绩总条数发生变化，请重新查询。")
            total = current_total
            if any(not isinstance(row, dict) for row in rows):
                raise GradesError("成绩记录格式异常。")
            signature = json.dumps(rows, sort_keys=True, ensure_ascii=False)
            if rows and signature in seen_pages:
                raise GradesError("成绩接口返回了重复页，未进行计算。")
            seen_pages.add(signature)
            records.extend(rows)
            if len(records) == total:
                return filter_records(records, year, term)
            if not rows or len(records) > total:
                raise GradesError("成绩分页数量与总条数不符，请重试。")
        raise GradesError("成绩分页超过查询上限，未进行计算。")
