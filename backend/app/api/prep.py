import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.api.inventory import lock_settings_row
from app.database import get_db
from app.models.models import (
    MODE_ALLOW_FROZEN,
    MODE_NO_SUBSTITUTE,
    BomLine,
    Ingredient,
    KitchenOrder,
    OrderLine,
    PrepRun,
)
from app.services.bom_engine import explode_and_merge, result_to_dict

router = APIRouter(prefix="/prep", tags=["prep"])


def current_effective_order(db: Session) -> KitchenOrder:
    """当前有效单：最新的 open 订单。"""
    order = db.scalars(
        select(KitchenOrder).where(KitchenOrder.status == "open").order_by(KitchenOrder.id.desc())
    ).first()
    if not order:
        raise HTTPException(409, "没有当前有效单")
    return order


def _check_effective(order_id: int | None, order: KitchenOrder) -> None:
    if order_id is not None and order_id != order.id:
        raise HTTPException(409, "只能出当前有效单")


def _generate(db: Session, order: KitchenOrder) -> PrepRun:
    # 同一事务内：锁设置行 → 读开关 → 按保存当下的标记与账面出单 → 落新单。
    # 行锁使库存页保存与备料台生成串行化，一单只落在同一套禁替/允许替上。
    settings = lock_settings_row(db)
    allow = settings.allow_frozen_substitute
    if not isinstance(allow, bool):
        db.rollback()
        raise HTTPException(409, "开关状态非法")
    mode = MODE_ALLOW_FROZEN if allow else MODE_NO_SUBSTITUTE
    ols = [{"dish_id": l.dish_id, "portions": l.portions}
           for l in db.scalars(select(OrderLine).where(OrderLine.order_id == order.id)).all()]
    bom = [{"dish_id": b.dish_id, "ingredient_id": b.ingredient_id, "qty_per_portion": b.qty_per_portion}
           for b in db.scalars(select(BomLine)).all()]
    ings = {i.id: {"code": i.code, "name": i.name, "unit": i.unit,
                   "storage_type": i.storage_type, "stock_qty": i.stock_qty,
                   "fresh_stock_qty": i.fresh_stock_qty, "frozen_stock_qty": i.frozen_stock_qty}
            for i in db.scalars(select(Ingredient)).all()}
    try:
        result = result_to_dict(explode_and_merge(ols, bom, ings, mode=mode), mode=mode)
    except (ValueError, AssertionError) as exc:
        # 两套写模型互斥：非法或越界即整次失败，鲜仓/冻仓/当前单/缺料贴全部退回
        db.rollback()
        raise HTTPException(409, f"生成失败，已全部退回: {exc}")
    result["order"] = {"id": order.id, "code": order.code, "outlet": order.outlet}
    # 只落备料单快照，绝不扣库存结存
    run = PrepRun(order_id=order.id, created_at=datetime.utcnow(), mode=mode,
                  result_json=json.dumps(result, ensure_ascii=False))
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def _run_payload(run: PrepRun) -> dict:
    return {"id": run.id, **json.loads(run.result_json)}


@router.post("/run")
def run_prep(order_id: int | None = None, db: Session = Depends(get_db)):
    order = current_effective_order(db)
    _check_effective(order_id, order)
    return _run_payload(_generate(db, order))


@router.get("/latest")
def latest(order_id: int | None = None, db: Session = Depends(get_db)):
    order = current_effective_order(db)
    _check_effective(order_id, order)
    run = db.scalars(select(PrepRun).where(PrepRun.order_id == order.id).order_by(PrepRun.id.desc())).first()
    if not run:
        run = _generate(db, order)
    return _run_payload(run)


@router.get("/shortages")
def shortages(order_id: int | None = None, db: Session = Depends(get_db)):
    data = latest(order_id=order_id, db=db)
    return {"order_id": data["order"]["id"], "mode": data.get("mode"),
            "shortages": data.get("shortages", []), "stats": data.get("stats", {})}
