# -*- coding: utf-8 -*-
"""
tests/test_app_ui.py —— 网页界面交互测试

验证目标（回归测试）：点击快捷按钮后，本轮提问和回答必须立刻显示，
不能出现"显示上一条回复"的延迟渲染问题。
运行方式：python tests/test_app_ui.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from streamlit.testing.v1 import AppTest

APP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app.py")


def main():
    print("=" * 60)
    print("网页界面交互测试（模拟真实点击）")
    print("=" * 60)

    # 启动虚拟页面
    at = AppTest.from_file(APP_PATH, default_timeout=90)
    at.run()
    if at.exception:
        print(f"❌ 页面启动异常：{at.exception}")
        return

    buttons = [b.label for b in at.button]
    print(f"页面按钮：{buttons}")

    # 点击第一个快捷提问按钮（索引2：0=清空, 1=转人工, 2=蓝牙耳机多少钱）
    target_index = buttons.index("蓝牙耳机多少钱")
    at.button[target_index].click().run()

    if at.exception:
        print(f"❌ 点击后页面异常：{at.exception}")
        return

    # 检查页面上渲染出的文本
    texts = [m.value for m in at.markdown]
    has_question = any("蓝牙耳机多少钱" in t for t in texts)
    has_answer = any("99" in t for t in texts)

    print(f"{'✅ PASS' if has_question else '❌ FAIL'} | 点击后立刻显示本轮提问")
    print(f"{'✅ PASS' if has_answer else '❌ FAIL'} | 点击后立刻显示本轮回答（含99元）")
    print("-" * 60)
    print("渲染出的回答示例：")
    for t in texts:
        if "99" in t:
            print(f"       {t[:100]}")

    print("-" * 60)
    print("✅ 测试通过：按钮点击后无需二次点击" if has_question and has_answer
          else "❌ 测试失败：仍存在渲染延迟")


if __name__ == "__main__":
    main()
