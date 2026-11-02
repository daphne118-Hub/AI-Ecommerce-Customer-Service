# -*- coding: utf-8 -*-
"""
tests/test_business.py —— 有状态模拟电商业务测试

A. 纯本地逻辑测试（不花钱）：订单/物流/退款/售后、下单扣库存、状态机、持久化
B. Agent 集成测试（约0.02元）：验证大模型遇到业务/RAG问题会选择正确工具
运行方式：python tests/test_business.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

import business
import tools
from agent import CustomerServiceAgent

results = []


def check(condition, label):
    print(f"{'✅ PASS' if condition else '❌ FAIL'} | {label}")
    results.append(condition)


def local_tests():
    """A. 纯本地逻辑测试"""
    print("\n【A. 本地业务逻辑测试（不调用API）】")
    business.reset_state()  # 保证测试从干净的种子状态开始

    orders = business.list_demo_orders()
    check(len(orders) == 3, "演示订单共3条")

    r = business.query_order("DD20261101001")
    check(r["success"] and r["data"]["total"] == 99, "订单查询：金额99元")
    check(r["data"]["data_source"].startswith("模拟"), "订单结果带模拟数据标记")

    r = business.query_logistics("DD20261101001")
    check(r["success"] and r["data"]["status"] == "运输中", "物流查询：运输中")

    r = business.query_refund("DD20261025003")
    check(r["success"] and r["data"]["status"] == "平台审核中", "退款进度：平台审核中")

    r = business.query_refund("DD20261101001")
    check(r["success"] and "没有退款记录" in r["data"]["status"], "无退款订单：如实说明无记录")

    r = business.query_order("DD99999999")
    check(not r["success"], "不存在的订单：返回失败而非编造")

    # ---- 下单：真实改变系统状态 ----
    check(business.get_stock("蓝牙耳机") == 50, "初始库存50件")
    r = business.place_order("蓝牙耳机", 2)
    check(r["success"] and r["data"]["total"] == 198, "下单2件：金额198元")
    check(r["data"]["remaining_stock"] == 48, "下单后实时库存变为48件")
    check(business.get_stock("蓝牙耳机") == 48, "get_stock 反映扣减后的库存")
    r = tools.check_stock("蓝牙耳机")
    check(r["success"] and r["data"]["stock"] == 48, "工具层库存查询返回实时值")
    r = business.place_order("蓝牙耳机", 999)
    check(not r["success"] and "库存不足" in r["error"], "库存不足：拒绝下单")
    r = business.place_order("不存在的商品", 1)
    check(not r["success"], "不存在的商品：拒绝下单")

    # ---- 售后状态机 ----
    r = business.apply_after_sale("DD20261028002", "杯盖漏水")
    app_id = r["data"]["application_id"]
    check(r["success"] and "等待人工审核" in r["data"]["status"], "售后申请：进入状态机初始态")
    statuses = []
    for _ in range(4):
        statuses.append(business.advance_after_sale(app_id)["data"]["status"])
    check(statuses[-1] == "退款完成", "状态机可推进到退款完成")
    check(len(set(statuses[:3])) == 3, "状态按序流转、不跳步")
    r = business.query_refund("DD20261028002")
    check(r["success"] and r["data"]["status"] == "退款完成", "退款进度查询反映状态机结果")
    check(not business.advance_after_sale("SQ9999")["success"], "不存在的申请单：返回错误")

    # ---- 持久化与重置 ----
    r = business.query_order(orders[-1])
    check(r["success"], "种子订单仍可查询")
    check(len(business.list_demo_orders()) == 4, "下单生成的新订单已持久化到文件")
    business.reset_state()
    check(business.get_stock("蓝牙耳机") == 50, "重置演示数据后库存恢复")
    check(len(business.list_demo_orders()) == 3, "重置后新订单被清除")

    # ---- 工具调度异常兜底 ----
    r = tools.execute_tool("query_logistics", {"order_id": "DD20261101001"})
    check(r["success"], "工具调度：query_logistics 可执行")
    r = tools.execute_tool("不存在的工具", {})
    check(not r["success"], "工具调度：未知工具返回错误不崩溃")
    r = tools.execute_tool("query_order", {"错误参数": "x"})
    check(not r["success"], "工具调度：参数错误被异常兜底")
    r = tools.search_knowledge("背包防水吗")
    check(r["success"] and len(r["data"]["hits"]) > 0, "RAG 工具能召回知识片段")
    r = tools.search_knowledge("支持以旧换新吗")
    check(not r["success"], "RAG 无相关结果：返回拒答信号")
    check(len(tools.TOOL_SPECS) == 12, f"工具总数 12 个（当前 {len(tools.TOOL_SPECS)}）")


def agent_tests():
    """B. Agent 集成测试"""
    print("\n【B. Agent 业务流程集成测试（真实调用DeepSeek）】")
    business.reset_state()
    agent = CustomerServiceAgent("business_test_user")

    cases = [
        ("帮我查一下订单 DD20261101001 的情况",
         "query_order", ["99", "已发货"], "订单查询 → query_order"),
        ("订单 DD20261101001 的快递到哪了？",
         "query_logistics", ["运输中", "华东"], "物流跟踪 → query_logistics"),
        ("订单 DD20261025003 的退款进度怎么样了？",
         "query_refund", ["审核", "129"], "退款进度 → query_refund"),
        ("订单 DD20261028002 的保温杯漏水了，我要申请退货退款",
         "apply_after_sale", ["申请", "提交", "受理"], "售后申请 → apply_after_sale"),
        ("我要买2个蓝牙耳机，帮我下单",
         "place_order", ["订单", "198", "DD"], "模拟下单 → place_order（真实扣库存）"),
        ("帮我查一下订单 DD99999999",
         "query_order", ["无法", "没有", "抱歉", "确认"], "不存在的订单 → 不编造"),
    ]

    for question, expect_tool, expect_words, label in cases:
        reply = agent.run(question)
        tool_ok = expect_tool in agent.last_tool_calls
        words_ok = any(w in reply for w in expect_words)
        print(f"       {'✅' if tool_ok and words_ok else '❌'} {label}")
        print(f"       工具：{agent.last_tool_calls} | 回复：{reply[:80]}")
        check(tool_ok and words_ok, label)
        agent.memory.clear()

    # 下单后库存应真实减少（跨工具一致性）
    stock = business.get_stock("蓝牙耳机")
    check(stock == 48, f"Agent 下单后库存真实减少（当前 {stock} 件）")

    # 开放式问题 → RAG 语义检索
    reply = agent.run("你们店里有用防水面料做的商品吗？")
    rag_used = "search_knowledge" in agent.last_tool_calls
    print(f"       RAG 问题工具：{agent.last_tool_calls} | 回复：{reply[:80]}")
    check(rag_used and "防水" in reply, "开放式问题 → 调用 RAG 检索并依据片段回答")
    agent.memory.clear()

    # 知识库没有的服务 → 拒答
    reply = agent.run("你们支持以旧换新吗？")
    deny = any(w in reply for w in ["无法", "没有", "抱歉", "不支持", "暂时", "确认"])
    print(f"       拒答工具：{agent.last_tool_calls} | 回复：{reply[:80]}")
    check(deny, "知识库无依据 → 拒绝编造、如实说明")

    business.reset_state()  # 测试结束恢复干净状态


def main():
    print("=" * 60)
    print("有状态模拟电商业务流程测试")
    print("=" * 60)
    local_tests()
    agent_tests()
    print("-" * 60)
    print(f"测试结果：{sum(results)}/{len(results)} 通过")


if __name__ == "__main__":
    main()
