"""中央厨房 BOM 展开：订单行 × BOM 用量合并需求。

鲜仓账面、冻仓账面、当前有效单上的鲜缺分套记账：
- 鲜品：鲜缺只跟鲜仓；「禁替」下冻仓再多也不许抹鲜缺，「允许冻顶」下才许用冻仓减鲜缺。
- 冻品：只跟冻仓。未标记鲜冻：不区分，沿用单一库存。
两种写模型互斥：mode 非法、或禁替下出现冻顶抵扣，都直接抛错，整次失败。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from app.models.models import MODE_ALLOW_FROZEN, MODE_NO_SUBSTITUTE, PREP_MODES

NOTE_FRESH = "鲜品不足"
NOTE_FROZEN = "冻品不足"
NOTE_STOCK = "库存不足"


@dataclass
class NeedLine:
    ingredient_id: int
    ingredient_code: str
    ingredient_name: str
    unit: str
    storage_type: str       # '' 不区分 / fresh 鲜品 / frozen 冻品
    need_qty: float
    stock_qty: float        # 未区分账面快照（未标记时用）
    fresh_stock_qty: float  # 鲜仓账面快照
    frozen_stock_qty: float  # 冻仓账面快照
    fresh_shortage: float   # 鲜缺：只跟鲜仓，独立记账
    frozen_cover: float     # 冻顶抵扣：仅「允许冻顶」时 > 0
    shortage: float         # 最终缺口（缺料贴）
    note: str               # 缺料贴文字：鲜品不足 / 冻品不足 / 库存不足


def explode_and_merge(
    order_lines: list[dict],
    bom_lines: list[dict],
    ingredients: dict[int, dict],
    *,
    mode: str,
) -> list[NeedLine]:
    """order_lines: dish_id, portions; bom_lines: dish_id, ingredient_id, qty_per_portion.

    mode 必须是禁替 / 允许冻顶之一；两套算法互斥，只走其中一套。
    """
    if mode not in PREP_MODES:
        raise ValueError(f"非法备料写模型: {mode!r}")
    need: dict[int, float] = {}
    for ol in order_lines:
        for bl in bom_lines:
            if bl["dish_id"] != ol["dish_id"]:
                continue
            need[bl["ingredient_id"]] = need.get(bl["ingredient_id"], 0.0) + ol["portions"] * bl["qty_per_portion"]
    lines: list[NeedLine] = []
    for iid, qty in sorted(need.items()):
        ing = ingredients[iid]
        st = ing.get("storage_type", "") or ""
        stock = float(ing.get("stock_qty", 0) or 0)
        fresh = float(ing.get("fresh_stock_qty", 0) or 0)
        frozen = float(ing.get("frozen_stock_qty", 0) or 0)
        fresh_shortage = 0.0
        frozen_cover = 0.0
        if st == "fresh":
            # 鲜缺独立记账：只跟鲜仓
            fresh_shortage = max(0.0, qty - fresh)
            if mode == MODE_ALLOW_FROZEN:
                # 打开开关后才许用冻仓减鲜缺
                frozen_cover = min(fresh_shortage, frozen)
            shortage = fresh_shortage - frozen_cover
            note = NOTE_FRESH
        elif st == "frozen":
            shortage = max(0.0, qty - frozen)
            note = NOTE_FROZEN
        else:
            shortage = max(0.0, qty - stock)
            note = NOTE_STOCK
        lines.append(NeedLine(
            ingredient_id=iid,
            ingredient_code=ing["code"],
            ingredient_name=ing["name"],
            unit=ing.get("unit", ""),
            storage_type=st,
            need_qty=round(qty, 3),
            stock_qty=round(stock, 3),
            fresh_stock_qty=round(fresh, 3),
            frozen_stock_qty=round(frozen, 3),
            fresh_shortage=round(fresh_shortage, 3),
            frozen_cover=round(frozen_cover, 3),
            shortage=round(shortage, 3),
            note=note if shortage > 0 else "",
        ))
    # 互斥护栏：禁替模式下一丝冻顶抵扣都不许出现，出现即整次失败
    if mode == MODE_NO_SUBSTITUTE and any(l.frozen_cover > 0 for l in lines):
        raise AssertionError("禁替模式下出现冻顶抵扣")
    return lines


def result_to_dict(lines: list[NeedLine], *, mode: str) -> dict:
    if mode not in PREP_MODES:
        raise ValueError(f"非法备料写模型: {mode!r}")
    return {
        "mode": mode,
        "prep_lines": [asdict(l) for l in lines],
        "shortages": [asdict(l) for l in lines if l.shortage > 0],
        "stats": {
            "ingredient_count": len(lines),
            "shortage_count": sum(1 for l in lines if l.shortage > 0),
            "total_shortage_qty": round(sum(l.shortage for l in lines), 3),
            "fresh_shortage_qty": round(sum(l.fresh_shortage for l in lines), 3),
            "frozen_cover_qty": round(sum(l.frozen_cover for l in lines), 3),
        },
    }
