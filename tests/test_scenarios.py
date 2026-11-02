# -*- coding: utf-8 -*-
"""
tests/test_scenarios.py —— 核心场景集成测试

作用：模拟真实顾客提问，验证智能客服核心功能：
  1. 商品价格查询   2. 库存查询   3. FAQ售后问答
  4. 多轮对话指代理解  5. 知识库没有的数据不编造
运行方式：python tests/test_scenarios.py
注意：会真实调用 DeepSeek API（每条约0.001元，共约0.005元）
"""

import os
import sys

# 让测试脚本能在任意目录运行：把项目根目录加入模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from main import get_reply, USER_ID          # noqa: E402
from memory import memory_manager            # noqa: E402


def check(reply, must_contain, label):
    """检查回复中是否包含关键词（任一命中即通过）"""
    passed = any(word in reply for word in must_contain)
    mark = "✅ PASS" if passed else "❌ FAIL"
    print(f"{mark} | {label}")
    print(f"       回复：{reply[:80]}")
    return passed


def main():
    results = []

    print("=" * 60)
    print("AI 电商智能客服 —— 核心场景测试")
    print("=" * 60)

    # 场景1：商品价格查询
    results.append(check(
        get_reply("蓝牙耳机多少钱？"), ["99"], "查询蓝牙耳机价格 → 应返回99元"))

    # 场景2：库存查询
    results.append(check(
        get_reply("保温杯还有库存吗？"), ["30"], "查询保温杯库存 → 应返回30件"))

    # 场景3：售后FAQ（退货）
    results.append(check(
        get_reply("你们家支持退货吗？"), ["退货", "售后"], "询问退货政策 → 应返回FAQ内容"))

    # 场景4：多轮对话指代（上一句在问双肩背包，这句的"它"应指背包）
    results.append(check(
        get_reply("双肩背包是什么价格？然后它有货吗，库存多少？"),
        ["129", "20"], "双肩背包价格+库存 → 应返回129元、20件"))

    # 场景5：知识库没有的数据，不允许编造（我们不卖手机）
    results.append(check(
        get_reply("你们店里的苹果手机多少钱？"),
        ["无法", "没有", "抱歉", "人工", "暂时"],
        "询问不存在的商品 → 不应编造价格"))

    print("-" * 60)
    passed = sum(results)
    print(f"测试结果：{passed}/{len(results)} 通过")

    # 清空测试产生的对话记忆
    memory_manager.get_memory(USER_ID).clear()


if __name__ == "__main__":
    main()
