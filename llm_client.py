# -*- coding: utf-8 -*-
"""
llm_client.py —— DeepSeek 大模型调用封装

作用：把"调用大模型"这件事封装成一个函数 chat()
  - 自动检查 API Key
  - 统一处理超时、网络错误、余额不足等异常
  - 调用方只需要传对话历史，拿回复，不用关心细节
被谁调用：main.py、agent.py、app.py
"""

import config
from openai import OpenAI


def create_client():
    """创建 DeepSeek 客户端，密钥缺失时返回 None"""
    if not config.API_KEY:
        return None
    return OpenAI(
        api_key=config.API_KEY,
        base_url=config.BASE_URL,
    )


def chat(messages):
    """
    调用大模型进行对话。

    参数：
        messages: 对话历史列表，格式如
        [
            {"role": "system", "content": "系统提示词"},
            {"role": "user", "content": "顾客问题"},
            {"role": "assistant", "content": "客服回复"},
            ...
        ]

    返回：
        成功 → 模型回复文本（字符串）
        失败 → None（同时打印错误原因，由调用方决定如何提示用户）
    """
    client = create_client()
    if client is None:
        print("错误：未找到 API Key，请设置环境变量 DEEPSEEK_API_KEY")
        return None

    try:
        response = client.chat.completions.create(
            model=config.MODEL_NAME,
            messages=messages,
            max_tokens=config.MAX_TOKENS,
            temperature=config.TEMPERATURE,
            timeout=config.TIMEOUT,
        )
        return response.choices[0].message.content

    except Exception as e:
        # 统一异常出口：网络超时、余额不足、密钥失效等都在这里拦截
        print(f"[调用大模型失败] {e}")
        return None
