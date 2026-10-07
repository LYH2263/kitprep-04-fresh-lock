import pytest

from app.models.models import MODE_ALLOW_FROZEN, MODE_NO_SUBSTITUTE
from app.services.bom_engine import explode_and_merge

def test_explode_merge():
    order_lines = [{"dish_id": 1, "portions": 10}, {"dish_id": 2, "portions": 5}]
    bom = [
        {"dish_id": 1, "ingredient_id": 1, "qty_per_portion": 0.2},
        {"dish_id": 1, "ingredient_id": 2, "qty_per_portion": 0.1},
        {"dish_id": 2, "ingredient_id": 1, "qty_per_portion": 0.3},
    ]
    ings = {
        1: {"code": "A", "name": "肉", "unit": "kg", "stock_qty": 1.0},
        2: {"code": "B", "name": "米", "unit": "kg", "stock_qty": 5.0},
    }
    lines = explode_and_merge(order_lines, bom, ings, mode=MODE_NO_SUBSTITUTE)
    by_id = {l.ingredient_id: l for l in lines}
    assert by_id[1].need_qty == 3.5  # 10*0.2 + 5*0.3
    assert by_id[1].shortage == 2.5
    assert by_id[2].need_qty == 1.0
    assert by_id[2].shortage == 0.0

def test_no_negative_shortage():
    order_lines = [{"dish_id": 1, "portions": 1}]
    bom = [{"dish_id": 1, "ingredient_id": 1, "qty_per_portion": 1.0}]
    ings = {1: {"code": "A", "name": "油", "unit": "L", "stock_qty": 10.0}}
    lines = explode_and_merge(order_lines, bom, ings, mode=MODE_NO_SUBSTITUTE)
    assert lines[0].shortage == 0.0

def _fresh_ing(fresh: float, frozen: float) -> dict:
    return {"code": "F", "name": "鲜肉", "unit": "kg", "storage_type": "fresh",
            "stock_qty": 0.0, "fresh_stock_qty": fresh, "frozen_stock_qty": frozen}

def test_fresh_shortage_ignores_frozen_when_no_substitute():
    """禁替：鲜缺只跟鲜仓，冻仓再多也不许把鲜缺抹成 0。"""
    order_lines = [{"dish_id": 1, "portions": 10}]
    bom = [{"dish_id": 1, "ingredient_id": 1, "qty_per_portion": 1.0}]
    ings = {1: _fresh_ing(fresh=4.0, frozen=100.0)}
    (line,) = explode_and_merge(order_lines, bom, ings, mode=MODE_NO_SUBSTITUTE)
    assert line.fresh_shortage == 6.0   # 鲜缺独立记账
    assert line.frozen_cover == 0.0     # 禁替下一丝冻顶都不许
    assert line.shortage == 6.0
    assert line.note == "鲜品不足"

def test_frozen_may_cover_fresh_only_when_allowed():
    """允许冻顶：冻仓可减鲜缺，但最多减到鲜缺为止。"""
    order_lines = [{"dish_id": 1, "portions": 10}]
    bom = [{"dish_id": 1, "ingredient_id": 1, "qty_per_portion": 1.0}]
    ings = {1: _fresh_ing(fresh=4.0, frozen=100.0)}
    (line,) = explode_and_merge(order_lines, bom, ings, mode=MODE_ALLOW_FROZEN)
    assert line.fresh_shortage == 6.0   # 鲜缺仍按鲜仓记账
    assert line.frozen_cover == 6.0
    assert line.shortage == 0.0
    assert line.note == ""              # 无缺口不上缺料贴

def test_frozen_cover_capped_by_frozen_stock():
    order_lines = [{"dish_id": 1, "portions": 10}]
    bom = [{"dish_id": 1, "ingredient_id": 1, "qty_per_portion": 1.0}]
    ings = {1: _fresh_ing(fresh=4.0, frozen=2.0)}
    (line,) = explode_and_merge(order_lines, bom, ings, mode=MODE_ALLOW_FROZEN)
    assert line.fresh_shortage == 6.0
    assert line.frozen_cover == 2.0
    assert line.shortage == 4.0
    assert line.note == "鲜品不足"

def test_frozen_item_only_counts_frozen_warehouse():
    """冻品只跟冻仓，鲜仓不反向顶。"""
    order_lines = [{"dish_id": 1, "portions": 10}]
    bom = [{"dish_id": 1, "ingredient_id": 1, "qty_per_portion": 1.0}]
    ings = {1: {"code": "Z", "name": "冻虾", "unit": "kg", "storage_type": "frozen",
                "stock_qty": 0.0, "fresh_stock_qty": 100.0, "frozen_stock_qty": 3.0}}
    for mode in (MODE_NO_SUBSTITUTE, MODE_ALLOW_FROZEN):
        (line,) = explode_and_merge(order_lines, bom, ings, mode=mode)
        assert line.shortage == 7.0
        assert line.fresh_shortage == 0.0
        assert line.frozen_cover == 0.0
        assert line.note == "冻品不足"

def test_unmarked_ingredient_not_distinguished():
    """没标过鲜冻则不区分，沿用单一库存。"""
    order_lines = [{"dish_id": 1, "portions": 10}]
    bom = [{"dish_id": 1, "ingredient_id": 1, "qty_per_portion": 1.0}]
    ings = {1: {"code": "U", "name": "大米", "unit": "kg", "storage_type": "",
                "stock_qty": 4.0, "fresh_stock_qty": 0.0, "frozen_stock_qty": 100.0}}
    for mode in (MODE_NO_SUBSTITUTE, MODE_ALLOW_FROZEN):
        (line,) = explode_and_merge(order_lines, bom, ings, mode=mode)
        assert line.shortage == 6.0
        assert line.frozen_cover == 0.0
        assert line.note == "库存不足"

def test_illegal_mode_fails():
    """两套写模型互斥：非法模式直接失败，不许各算一遍再合成。"""
    with pytest.raises(ValueError):
        explode_and_merge([], [], {}, mode="merge_both")
    with pytest.raises(ValueError):
        explode_and_merge([], [], {}, mode="")
