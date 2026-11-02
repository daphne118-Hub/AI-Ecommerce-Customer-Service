# -*- coding: utf-8 -*-
"""
business.py —— 有状态的模拟电商业务模块

作用：提供订单、物流、售后、退款、下单的查询与办理能力。
被谁调用：tools.py（作为 Agent 工具的实际执行逻辑）

相比初版的升级（"有状态"是重点）：
  1. 下单会真实校验并扣减库存，生成新订单，库存变化能被 check_stock 立即看到
  2. 售后申请进入状态机：已提交 → 审核通过 → 退款处理中 → 退款完成
  3. 运行时状态持久化到 data/state.json，重启程序后仍在；种子数据保持只读
  4. 结构化字段（库存/订单）与文本检索（RAG）职责分离

重要声明：
  本模块全部数据来自本地 JSON 模拟数据，仅用于演示电商客服业务流程，
  未连接任何真实电商平台，也不代表真实平台数据。
  所有返回结果都带 data_source 标记。
"""

import json
import os
from datetime import date

import knowledge

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
ORDERS_PATH = os.path.join(DATA_DIR, "orders.json")
STATE_PATH = os.path.join(DATA_DIR, "state.json")

# 售后状态机：申请 → 审核 → 退款 → 完成
AFTER_SALE_FLOW = [
    "已提交，等待人工审核",
    "审核通过，待顾客寄回商品",
    "退款处理中",
    "退款完成",
]


# ---------- 运行时状态读写（持久化） ----------

def _default_state():
    return {
        "stock_overrides": {},   # 商品名 → 当前库存（下单扣减后写入）
        "orders": {},            # 下单生成的新订单
        "applications": {},      # 售后申请单（含状态机当前进度）
        "seq": {"order": 1, "application": 1},
    }


def _load_state():
    """加载运行时状态；文件不存在或损坏时返回初始状态"""
    if not os.path.exists(STATE_PATH):
        return _default_state()
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            state = json.load(f)
        # 兼容性兜底：缺字段时补齐
        base = _default_state()
        base.update(state)
        return base
    except (json.JSONDecodeError, OSError):
        return _default_state()


def _save_state(state):
    """保存运行时状态到本地 JSON"""
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        return True
    except OSError:
        return False


def reset_state():
    """重置演示数据（清空下单、售后申请与库存改动），恢复种子状态"""
    if os.path.exists(STATE_PATH):
        os.remove(STATE_PATH)
    return {"success": True, "data": {"message": "演示数据已重置为初始状态"}}


def _demo_note():
    """所有返回都附带的数据来源标记，防止把模拟数据说成真实平台数据"""
    return {"data_source": "模拟演示数据（非真实电商平台）"}


# ---------- 种子订单与实时库存 ----------

def _load_seed_orders():
    """加载只读的种子订单，跳过以 _ 开头的说明字段"""
    try:
        with open(ORDERS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in data.items() if not k.startswith("_")}


def _all_orders():
    """合并：种子订单 + 运行时新增订单（后者可覆盖前者）"""
    orders = _load_seed_orders()
    orders.update(_load_state()["orders"])
    return orders


def _find_order(order_id):
    if not order_id:
        return None
    return _all_orders().get(str(order_id).strip().upper())


def get_stock(product_name):
    """获取商品当前实时库存（优先返回下单扣减后的值）"""
    product = knowledge.search_product(product_name)
    if not product:
        return None
    name = product["name"]
    overrides = _load_state()["stock_overrides"]
    return overrides.get(name, product["stock"])


# ---------- 查询类 ----------

def query_order(order_id):
    """查询订单基本信息：商品、金额、状态、下单时间"""
    order = _find_order(order_id)
    if not order:
        return {"success": False, "error": f"未找到订单 {order_id}，请确认订单号"}
    return {"success": True, "data": {
        "order_id": order["order_id"],
        "status": order["status"],
        "items": order["items"],
        "total": order["total"],
        "created_at": order["created_at"],
        **_demo_note(),
    }}


def query_logistics(order_id):
    """查询订单物流状态"""
    order = _find_order(order_id)
    if not order:
        return {"success": False, "error": f"未找到订单 {order_id}，请确认订单号"}
    return {"success": True, "data": {**order["logistics"], **_demo_note()}}


def query_refund(order_id):
    """查询退款进度（优先返回售后申请状态机中的进度）"""
    order = _find_order(order_id)
    if not order:
        return {"success": False, "error": f"未找到订单 {order_id}，请确认订单号"}

    state = _load_state()
    # 该订单若有售后申请，以状态机进度为准
    for app in state["applications"].values():
        if app["order_id"] == order["order_id"]:
            return {"success": True, "data": {
                "refund_id": app["application_id"],
                "amount": order["total"],
                "reason": app["reason"],
                "status": app["status"],
                "expected_days": "1-3个工作日（模拟）",
                **_demo_note(),
            }}
    if order.get("refund"):
        return {"success": True, "data": {**order["refund"], **_demo_note()}}
    return {"success": True, "data": {
        "status": "该订单当前没有退款记录", **_demo_note()}}


# ---------- 办理类（真实改变状态） ----------

def place_order(product_name, quantity=1, customer="演示顾客"):
    """
    模拟下单：校验商品与库存 → 扣减库存 → 生成订单 → 持久化。
    这是 Agent 从"只查询"升级到"能办事"的关键。
    """
    product = knowledge.search_product(product_name)
    if not product:
        return {"success": False,
                "error": f"未找到商品「{product_name}」，本店只有：{', '.join(knowledge.products.keys())}"}
    try:
        quantity = int(quantity)
    except (ValueError, TypeError):
        return {"success": False, "error": "购买数量必须是整数"}
    if quantity <= 0:
        return {"success": False, "error": "购买数量必须大于 0"}

    name = product["name"]
    state = _load_state()
    current_stock = state["stock_overrides"].get(name, product["stock"])
    if current_stock < quantity:
        return {"success": False,
                "error": f"「{name}」库存不足，当前仅剩 {current_stock} 件"}

    # 扣减库存
    state["stock_overrides"][name] = current_stock - quantity

    # 生成订单号与订单记录
    seq = state["seq"]["order"]
    order_id = f"DD{date.today().strftime('%Y%m%d')}{seq:03d}"
    total = product["price"] * quantity
    order = {
        "order_id": order_id,
        "customer": customer,
        "created_at": date.today().isoformat(),
        "items": [{"name": name, "quantity": quantity, "price": product["price"]}],
        "total": total,
        "status": "待发货",
        "logistics": {
            "company": "模拟速运",
            "tracking_no": "-",
            "status": "待揽收",
            "current_location": "仓库",
            "estimated_delivery": "1-2个工作日内发出",
        },
        "refund": None,
        "after_sale": None,
    }
    state["orders"][order_id] = order
    state["seq"]["order"] = seq + 1
    _save_state(state)

    return {"success": True, "data": {
        "order_id": order_id,
        "product": name,
        "quantity": quantity,
        "total": total,
        "remaining_stock": state["stock_overrides"][name],
        "status": "待发货",
        "notice": "此为演示项目的模拟下单，不会产生真实交易或扣款",
        **_demo_note(),
    }}


def apply_after_sale(order_id, reason, sale_type="退货退款"):
    """提交售后申请，写入状态机初始状态"""
    order = _find_order(order_id)
    if not order:
        return {"success": False, "error": f"未找到订单 {order_id}，请确认订单号"}

    state = _load_state()
    seq = state["seq"]["application"]
    app_id = f"SQ{seq:04d}"
    application = {
        "application_id": app_id,
        "order_id": order["order_id"],
        "type": sale_type,
        "reason": reason,
        "status": AFTER_SALE_FLOW[0],
    }
    state["applications"][app_id] = application
    state["seq"]["application"] = seq + 1
    _save_state(state)

    return {"success": True, "data": {
        **application,
        "next_step": "人工审核（可用 advance_after_sale 推进状态）",
        "notice": "此为演示项目的模拟申请，不会产生真实售后工单",
        **_demo_note(),
    }}


def advance_after_sale(application_id):
    """推进售后状态机：已提交 → 审核通过 → 退款处理中 → 退款完成"""
    state = _load_state()
    app = state["applications"].get(str(application_id).strip().upper())
    if not app:
        return {"success": False,
                "error": f"未找到售后申请 {application_id}，请先提交申请"}

    current = app["status"]
    if current not in AFTER_SALE_FLOW:
        return {"success": False, "error": "售后状态异常"}
    idx = AFTER_SALE_FLOW.index(current)
    if idx >= len(AFTER_SALE_FLOW) - 1:
        return {"success": True, "data": {
            **app, "message": "流程已结束，退款完成", **_demo_note()}}

    app["status"] = AFTER_SALE_FLOW[idx + 1]
    state["applications"][app["application_id"]] = app
    _save_state(state)
    return {"success": True, "data": {
        **app, "message": f"状态已由「{current}」推进到「{app['status']}」",
        **_demo_note()}}


def list_applications():
    """列出所有售后申请（供网页侧边栏展示状态机）"""
    return list(_load_state()["applications"].values())


def list_demo_orders():
    """列出所有可用演示订单号（种子 + 下单生成）"""
    return list(_all_orders().keys())


# ---------- 自测 ----------
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    reset_state()
    print("初始库存：", get_stock("蓝牙耳机"))
    print("下单：", json.dumps(place_order("蓝牙耳机", 2), ensure_ascii=False))
    print("下单后库存：", get_stock("蓝牙耳机"))
    print("库存不足：", json.dumps(place_order("蓝牙耳机", 999), ensure_ascii=False))
    app = apply_after_sale("DD20261028002", "杯盖漏水")
    app_id = app["data"]["application_id"]
    print("售后申请：", json.dumps(app, ensure_ascii=False))
    for _ in range(4):
        print("推进状态：", json.dumps(advance_after_sale(app_id), ensure_ascii=False))
    print("订单数：", len(list_demo_orders()))
    reset_state()
    print("重置后库存：", get_stock("蓝牙耳机"))
