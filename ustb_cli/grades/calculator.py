"""以 Decimal 计算，保留每条记录的纳入或排除原因。"""

from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def number(value):
    try:
        result = Decimal(str(value).strip())
        return result if result.is_finite() else None
    except InvalidOperation:
        return None


def calculate(records, repeat="exclude"):
    # 主辅修分开识别；同一课程的多次考试不默认重复计权。
    def key(row):
        return (str(row.get("kcdm") or "").strip(),
                str(row.get("sffx") or "").strip(), str(row.get("xscjlb") or "").strip())

    counts = Counter(key(row) for row in records if row.get("kcdm"))
    included, excluded = [], []
    credits, weighted = Decimal(0), Decimal(0)
    partial = False
    for row in records:
        nature = str(row.get("kcxz") or "").strip()
        score = number(row.get("zzcj"))
        credit = number(row.get("xf"))
        reason, uncertain = None, False
        if nature != "必修":
            reason = "非必修课程" if nature else "课程性质缺失"
            uncertain = not nature
        elif str(row.get("sffx") or "").strip() in ("1", "是") or "辅修" in str(row.get("xscjlb") or ""):
            reason = "辅修课程（默认仅统计主修）"
        elif row.get("kcdm") and counts[key(row)] > 1 and repeat == "exclude":
            reason, uncertain = "同一课程存在多条记录，重修/补考口径待确认", True
        elif score is None or not Decimal(0) <= score <= Decimal(100):
            reason, uncertain = "总评成绩不是有效的百分制数值（等级制/未出分等）", True
        elif credit is None or credit <= 0:
            reason, uncertain = "学分缺失、非数值或不大于 0", True
        detail = {"course_code": row.get("kcdm"), "name": row.get("kcmc") or "未命名课程",
                  "semester": row.get("xnxqmc") or row.get("xnxq"),
                  "nature": nature, "score": row.get("zzcj"), "credits": row.get("xf")}
        if reason:
            excluded.append({**detail, "reason": reason})
            partial |= uncertain
        else:
            contribution = score * credit
            included.append({**detail, "contribution": str(contribution)})
            credits += credit
            weighted += contribution
    average = (weighted / credits).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if credits else None
    return {"rule": "required-numeric-v1", "repeat_policy": repeat,
            "formula": "Σ(成绩 × 学分) / Σ(学分)", "partial": partial,
            "record_count": len(records), "course_count": len(included),
            "total_credits": str(credits), "weighted_sum": str(weighted),
            "average": str(average) if average is not None else None,
            "included": included, "excluded": excluded}
