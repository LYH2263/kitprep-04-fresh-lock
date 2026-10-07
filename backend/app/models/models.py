from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

# 原料鲜冻标记：'' 不区分 / fresh 鲜品 / frozen 冻品
STORAGE_TYPES = ("", "fresh", "frozen")

# 备料单写模型（互斥）：禁替 / 允许冻顶鲜
MODE_NO_SUBSTITUTE = "no_substitute"
MODE_ALLOW_FROZEN = "allow_frozen"
PREP_MODES = (MODE_NO_SUBSTITUTE, MODE_ALLOW_FROZEN)

class Dish(Base):
    __tablename__ = "dishes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    portion_unit: Mapped[str] = mapped_column(String(16), default="份")

class Ingredient(Base):
    __tablename__ = "ingredients"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    unit: Mapped[str] = mapped_column(String(16), default="kg")
    stock_qty: Mapped[float] = mapped_column(Float, default=0.0)
    storage_type: Mapped[str] = mapped_column(String(8), default="")  # '' 不区分 / fresh / frozen
    fresh_stock_qty: Mapped[float] = mapped_column(Float, default=0.0)   # 鲜仓账面
    frozen_stock_qty: Mapped[float] = mapped_column(Float, default=0.0)  # 冻仓账面

class BomLine(Base):
    __tablename__ = "bom_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.id"))
    ingredient_id: Mapped[int] = mapped_column(ForeignKey("ingredients.id"))
    qty_per_portion: Mapped[float] = mapped_column(Float)

class KitchenOrder(Base):
    __tablename__ = "kitchen_orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    outlet: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32), default="open")

class OrderLine(Base):
    __tablename__ = "order_lines"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("kitchen_orders.id"))
    dish_id: Mapped[int] = mapped_column(ForeignKey("dishes.id"))
    portions: Mapped[int] = mapped_column(Integer)

class PrepRun(Base):
    __tablename__ = "prep_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("kitchen_orders.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    mode: Mapped[str] = mapped_column(String(16), default=MODE_NO_SUBSTITUTE)  # 生成当下的写模型快照
    result_json: Mapped[str] = mapped_column(Text, default="{}")

class KitchenSettings(Base):
    """单行全局设置（id 恒为 1）：「允许冻顶鲜」开关。"""
    __tablename__ = "kitchen_settings"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    allow_frozen_substitute: Mapped[bool] = mapped_column(Boolean, default=False)
