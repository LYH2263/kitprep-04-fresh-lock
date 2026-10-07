from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StrictBool
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import STORAGE_TYPES, Ingredient, KitchenSettings

router = APIRouter(prefix="/inventory", tags=["inventory"])

SETTINGS_ID = 1


class MarkerIn(BaseModel):
    code: str
    storage_type: str


class SettingsIn(BaseModel):
    allow_frozen_substitute: StrictBool  # 开关非法（非布尔）→ 422，停在保存前
    markers: list[MarkerIn] = []


def _item(r: Ingredient) -> dict:
    return {"id": r.id, "code": r.code, "name": r.name, "unit": r.unit,
            "storage_type": r.storage_type, "stock_qty": r.stock_qty,
            "fresh_stock_qty": r.fresh_stock_qty, "frozen_stock_qty": r.frozen_stock_qty}


def get_settings_row(db: Session) -> KitchenSettings:
    st = db.get(KitchenSettings, SETTINGS_ID)
    if st is None:
        st = KitchenSettings(id=SETTINGS_ID, allow_frozen_substitute=False)
        db.add(st)
        db.flush()
    return st


def lock_settings_row(db: Session) -> KitchenSettings:
    """带行锁读设置：与备料台生成串行化，同一时刻只许一套禁替/允许替。"""
    st = db.scalar(select(KitchenSettings).where(KitchenSettings.id == SETTINGS_ID).with_for_update())
    if st is None:
        st = KitchenSettings(id=SETTINGS_ID, allow_frozen_substitute=False)
        db.add(st)
        db.flush()
    return st


@router.get("")
def list_inventory(db: Session = Depends(get_db)):
    return [_item(r) for r in db.scalars(select(Ingredient).order_by(Ingredient.id)).all()]


@router.get("/settings")
def read_settings(db: Session = Depends(get_db)):
    st = get_settings_row(db)
    db.commit()
    return {"allow_frozen_substitute": st.allow_frozen_substitute}


@router.put("/settings")
def save_settings(payload: SettingsIn, db: Session = Depends(get_db)):
    # 先校验后落库：标记非法 / 编码对不上 / 编码重复 → 四处都停在保存前
    for m in payload.markers:
        if m.storage_type not in STORAGE_TYPES:
            raise HTTPException(400, f"非法鲜冻标记: {m.storage_type!r}")
    codes = [m.code for m in payload.markers]
    if len(set(codes)) != len(codes):
        raise HTTPException(400, "编码重复")
    ings = {i.code: i for i in db.scalars(select(Ingredient)).all()}
    unknown = [c for c in codes if c not in ings]
    if unknown:
        raise HTTPException(400, f"编码对不上: {', '.join(unknown)}")
    st = lock_settings_row(db)
    st.allow_frozen_substitute = payload.allow_frozen_substitute
    for m in payload.markers:
        ings[m.code].storage_type = m.storage_type
    db.commit()
    return {"allow_frozen_substitute": st.allow_frozen_substitute,
            "items": [_item(r) for r in db.scalars(select(Ingredient).order_by(Ingredient.id)).all()]}
