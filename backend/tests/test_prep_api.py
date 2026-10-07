import json

import pytest
from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine
from app.main import app
from app.models.models import PrepRun


@pytest.fixture()
def api():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


def _line(data: dict, code: str) -> dict:
    return next(l for l in data["prep_lines"] if l["ingredient_code"] == code)


def test_generate_defaults_to_no_substitute(api):
    data = api.post("/api/prep/run").json()
    assert data["mode"] == "no_substitute"
    pork = _line(data, "I-PR")  # 鲜8 冻5 需10
    assert pork["fresh_shortage"] == 2.0   # 鲜缺只跟鲜仓
    assert pork["frozen_cover"] == 0.0     # 禁替：冻仓再多也不许抹鲜缺
    assert pork["shortage"] == 2.0


def test_save_then_generate_uses_saved_toggle(api):
    r = api.put("/api/inventory/settings", json={"allow_frozen_substitute": True, "markers": []})
    assert r.status_code == 200
    data = api.post("/api/prep/run").json()
    assert data["mode"] == "allow_frozen"
    pork = _line(data, "I-PR")
    assert pork["fresh_shortage"] == 2.0   # 鲜缺仍独立记账
    assert pork["frozen_cover"] == 2.0     # 打开开关后才许冻顶
    assert pork["shortage"] == 0.0
    # 鸡肉冻仓为 0，仍缺 1
    assert _line(data, "I-CK")["shortage"] == 1.0


def test_illegal_toggle_stops_before_save(api):
    before = api.get("/api/inventory").json()
    r = api.put("/api/inventory/settings", json={"allow_frozen_substitute": "yes", "markers": []})
    assert r.status_code == 422
    assert api.get("/api/inventory/settings").json()["allow_frozen_substitute"] is False
    assert api.get("/api/inventory").json() == before  # 四处都停在保存前


def test_unknown_code_stops_before_save(api):
    before = api.get("/api/inventory").json()
    r = api.put("/api/inventory/settings", json={
        "allow_frozen_substitute": True,
        "markers": [{"code": "I-PR", "storage_type": "frozen"}, {"code": "NOPE", "storage_type": "fresh"}],
    })
    assert r.status_code == 400
    assert api.get("/api/inventory/settings").json()["allow_frozen_substitute"] is False
    assert api.get("/api/inventory").json() == before  # 同批合法标记也不许落


def test_illegal_storage_type_stops_before_save(api):
    before = api.get("/api/inventory").json()
    r = api.put("/api/inventory/settings", json={
        "allow_frozen_substitute": True,
        "markers": [{"code": "I-PR", "storage_type": "chilled"}],
    })
    assert r.status_code == 400
    assert api.get("/api/inventory/settings").json()["allow_frozen_substitute"] is False
    assert api.get("/api/inventory").json() == before


def test_marker_save_then_generate(api):
    r = api.put("/api/inventory/settings", json={
        "allow_frozen_substitute": False,
        "markers": [{"code": "I-ND", "storage_type": "frozen"}],
    })
    assert r.status_code == 200
    data = api.post("/api/prep/run").json()
    noodle = _line(data, "I-ND")  # 改标冻品后只跟冻仓（冻仓 0）
    assert noodle["storage_type"] == "frozen"
    assert noodle["shortage"] == 10.0
    assert noodle["note"] == "冻品不足"


def test_generate_never_deducts_inventory(api):
    before = api.get("/api/inventory").json()
    api.post("/api/prep/run")
    api.post("/api/prep/run")
    assert api.get("/api/inventory").json() == before  # 结存保持点生成之前的数


def test_history_run_keeps_its_mode(api):
    first = api.post("/api/prep/run").json()
    assert first["mode"] == "no_substitute"
    api.put("/api/inventory/settings", json={"allow_frozen_substitute": True, "markers": []})
    second = api.post("/api/prep/run").json()
    assert second["mode"] == "allow_frozen"
    assert api.get("/api/prep/latest").json()["id"] == second["id"]
    # 已按禁替落下的历史单禁止跟着改字
    db = SessionLocal()
    try:
        old = db.get(PrepRun, first["id"])
        assert old.mode == "no_substitute"
        old_data = json.loads(old.result_json)
        assert old_data["mode"] == "no_substitute"
        old_pork = next(l for l in old_data["prep_lines"] if l["ingredient_code"] == "I-PR")
        assert old_pork["frozen_cover"] == 0.0
        assert old_pork["shortage"] == 2.0
    finally:
        db.close()


def test_shortage_notes(api):
    res = api.get("/api/prep/shortages").json()
    by_code = {s["ingredient_code"]: s for s in res["shortages"]}
    assert by_code["I-PR"]["note"] == "鲜品不足"   # 缺鲜只写鲜品不足
    assert by_code["I-ND"]["note"] == "库存不足"   # 未标记不区分
    assert "鲜品不足" not in by_code["I-ND"]["note"]


def test_only_current_effective_order(api):
    assert api.post("/api/prep/run", params={"order_id": 999}).status_code == 409
    data = api.post("/api/prep/run").json()
    assert data["order"]["code"] == "KO-0901"
