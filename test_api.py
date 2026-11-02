# -*- coding: utf-8 -*-
"""
test_api.py —— DeepSeek API 连通性测试

作用：在接入主程序之前，单独验证：
  1. API Key 是否能从环境变量读取
  2. DeepSeek 接口是否能正常访问
  3. 大模型是否能返回回复

如何运行：在 Spyder 中直接点运行按钮（绿色三角）
"""

import os
import sys

# Windows 终端默认 GBK 编码，强制改为 UTF-8，避免中文/符号打印报错
sys.stdout.reconfigure(encoding="utf-8")

# ---------- 第一步：检查 API Key ----------
api_key = os.getenv("DEEPSEEK_API_KEY")

if not api_key:
    print("❌ 没有找到 API Key！")
    print("请检查 Windows 环境变量 DEEPSEEK_API_KEY 是否已设置，")
    print("设置后需要完全重启 Spyder 才能生效。")
    sys.exit(1)  # 缺少密钥，直接退出，不继续调用

print("✅ 第一步通过：API Key 读取成功（不显示内容，保护密钥安全）")

# ---------- 第二步：创建 DeepSeek 客户端 ----------
# DeepSeek 官方接口兼容 OpenAI SDK 格式，只需换成 DeepSeek 的地址
try:
    from openai import OpenAI

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.deepseek.com",  # DeepSeek 官方 API 地址
    )
    print("✅ 第二步通过：客户端创建成功")
except ImportError:
    print("❌ 没有安装 openai 库，请在终端执行：pip install openai")
    sys.exit(1)
except Exception as e:
    print(f"❌ 客户端创建失败：{e}")
    sys.exit(1)

# ---------- 第三步：调用大模型 ----------
print("⏳ 正在调用 DeepSeek 大模型（约需几秒）...\n")

try:
    response = client.chat.completions.create(
        model="deepseek-chat",           # DeepSeek 当前通用对话模型
        messages=[
            # system：设定大模型的角色
            {"role": "system", "content": "你是一个电商客服助手，回答要简洁。"},
            # user：模拟顾客提问
            {"role": "user", "content": "你好，请用一句话介绍你自己。"},
        ],
        max_tokens=100,      # 限制回复长度，节省费用
        timeout=30,          # 超时时间 30 秒，避免程序卡死
    )

    reply = response.choices[0].message.content
    print("✅ 第三步通过：大模型回复如下")
    print("-" * 40)
    print(reply)
    print("-" * 40)
    print("\n🎉 全部测试通过！DeepSeek API 可以正常使用。")

except Exception as e:
    # 常见错误：密钥无效、余额不足、网络超时等
    print(f"❌ 调用失败：{e}")
    print("\n常见原因：")
    print("1. API Key 无效或已过期 → 去 DeepSeek 平台重新生成")
    print("2. 账户余额不足 → 去 DeepSeek 平台充值（测试一次约 0.001 元）")
    print("3. 网络问题 → 检查网络后重试")
