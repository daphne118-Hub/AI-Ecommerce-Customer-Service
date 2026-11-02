# -*- coding: utf-8 -*-
"""
tests/test_memory.py —— 对话记忆与滚动摘要测试

用假的 chat 函数替换大模型调用，纯本地验证逻辑（不花钱、不联网）：
  用户隔离 / 长度控制 / 摘要触发 / 摘要失败降级 / 清空
运行方式：python tests/test_memory.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

import config
import llm_client
from memory import memory_manager

results = []


def check(condition, label):
    print(f"{'✅ PASS' if condition else '❌ FAIL'} | {label}")
    results.append(condition)


def main():
    print("=" * 60)
    print("对话记忆与滚动摘要测试（纯本地）")
    print("=" * 60)

    real_chat = llm_client.chat  # 保存原函数，测试结束恢复

    # 1. 用户隔离
    a = memory_manager.get_memory("user_a")
    b = memory_manager.get_memory("user_b")
    a.clear()
    b.clear()
    a.add("user", "我在看蓝牙耳机")
    check(len(b.history) == 0 and len(a.history) == 1,
          "不同用户会话互相隔离")

    # 2. 长度控制：关闭摘要，直接加 30 条
    config.ENABLE_SUMMARY = False
    m = memory_manager.get_memory("trim_test")
    m.clear()
    for i in range(30):
        m.add("user", f"第{i}条消息")
    check(len(m.history) == config.MAX_HISTORY_ROUNDS * 2,
          f"上下文长度被限制为 {config.MAX_HISTORY_ROUNDS * 2} 条")
    check("第29条消息" in m.history[-1]["content"], "保留最新消息、丢弃最旧消息")

    # 3. 摘要触发（用假 chat 模拟模型生成摘要）
    config.ENABLE_SUMMARY = True
    calls = []

    def fake_chat(messages):
        calls.append(messages)
        return "摘要：顾客咨询蓝牙耳机，价格99元，库存50件。"

    llm_client.chat = fake_chat
    m = memory_manager.get_memory("summary_test")
    m.clear()
    for i in range(14):
        m.add("user", f"关于蓝牙耳机的问题{i}")
        m.add("assistant", f"蓝牙耳机99元，回答{i}")

    check(len(calls) >= 1, "历史超阈值时触发了摘要调用")
    check("蓝牙耳机" in m.summary and "99元" in m.summary,
          "摘要作为长期记忆被保存")
    check(len(m.history) < 28, "旧消息被压缩，历史变短")
    check("摘要" in calls[0][0]["content"], "摘要调用使用了专用提示词")

    # 4. 摘要失败降级：chat 返回 None 时不能崩溃，也不能丢历史
    llm_client.chat = lambda messages: None
    m = memory_manager.get_memory("fallback_test")
    m.clear()
    for i in range(18):
        m.add("user", f"消息{i}")
    check(len(m.history) > 0 and m.summary == "",
          "摘要失败时降级为截断，程序不崩溃")

    # 5. 清空同时清空摘要
    m = memory_manager.get_memory("clear_test")
    m.add("user", "测试")
    m.summary = "临时摘要"
    m.clear()
    check(len(m.history) == 0 and m.summary == "", "清空操作同时清除长期记忆")

    llm_client.chat = real_chat
    config.ENABLE_SUMMARY = True
    print("-" * 60)
    print(f"测试结果：{sum(results)}/{len(results)} 通过")


if __name__ == "__main__":
    main()
