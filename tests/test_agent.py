# -*- coding: utf-8 -*-
"""
tests/test_agent.py —— Agent 工具调用测试

验证目标：
  1. 大模型能根据意图自主选择正确的工具
  2. 工具真实执行（调用轨迹非空）
  3. 回复基于工具返回的真实数据
  4. 转人工请求能正确触发 transfer_to_human
运行方式：python tests/test_agent.py
注意：会真实调用 DeepSeek API（4-5轮，每轮1-3次调用，约0.01元）
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from agent import CustomerServiceAgent


def run_case(agent, question, expect_tool, expect_words, label):
    """执行一个测试用例：检查工具选择 + 回复内容"""
    reply = agent.run(question)
    tool_hit = expect_tool in agent.last_tool_calls
    word_hit = any(w in reply for w in expect_words)
    passed = tool_hit and word_hit
    mark = "✅ PASS" if passed else "❌ FAIL"
    print(f"{mark} | {label}")
    print(f"       调用工具：{agent.last_tool_calls}（期望包含 {expect_tool}）")
    print(f"       回复：{reply[:80]}")
    agent.memory.clear()  # 用例之间不互相污染上下文
    return passed


def main():
    print("=" * 60)
    print("AI 客服 Agent —— 工具调用测试")
    print("=" * 60)

    agent = CustomerServiceAgent("agent_test_user")
    results = []

    # 用例1：库存查询 → 应选择 check_stock
    results.append(run_case(
        agent, "蓝牙耳机现在还有货吗？库存多少？",
        "check_stock", ["50"], "库存查询 → check_stock，返回50件"))

    # 用例2：商品详情 → 应选择 search_product
    results.append(run_case(
        agent, "帮我详细介绍下保温杯",
        "search_product", ["59", "保温"], "商品详情 → search_product，返回59元信息"))

    # 用例3：售后问题 → 应选择 search_faq
    results.append(run_case(
        agent, "你们退款是怎么退的？",
        "search_faq", ["退款", "订单"], "退款咨询 → search_faq，返回FAQ内容"))

    # 用例4：推荐 → 应选择 recommend_product
    results.append(run_case(
        agent, "我预算100元以内，有什么可以推荐的吗？",
        "recommend_product", ["蓝牙耳机", "保温杯"], "商品推荐 → recommend_product"))

    # 用例5：转人工 → 应选择 transfer_to_human
    results.append(run_case(
        agent, "我不想跟机器人说了，给我转人工客服！",
        "transfer_to_human", ["人工", "已受理", "转接"], "转人工请求 → transfer_to_human"))

    # 用例6：不存在的商品 → 工具失败时不编造
    results.append(run_case(
        agent, "你们的苹果手机多少钱？",
        "search_product", ["无法", "没有", "抱歉", "人工"], "查不存在的商品 → 不编造价格"))

    print("-" * 60)
    passed = sum(results)
    print(f"测试结果：{passed}/{len(results)} 通过")


if __name__ == "__main__":
    main()
