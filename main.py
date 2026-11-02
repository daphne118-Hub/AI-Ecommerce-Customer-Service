# -*- coding: utf-8 -*-
"""
main.py —— AI 电商智能客服主程序（命令行版）

作用：多轮对话入口。流程：
  顾客输入 → 拼接（系统提示词 + 知识库 + 对话历史）→ 调用 DeepSeek → 输出回复
运行方式：在 Spyder 中直接点运行（绿色三角）

版本说明：
  v1 关键词匹配版（已由本版升级替代，逻辑保留在 git 历史）
  v2 大模型版：自然语言理解 + 多轮对话 + 知识库约束
"""

import sys

import llm_client
import knowledge
from memory import memory_manager

# Windows 终端编码兼容
sys.stdout.reconfigure(encoding="utf-8")

# 当前顾客的用户标识（命令行版只有一个用户；网页版会有多个）
USER_ID = "console_user"


def build_system_prompt():
    """
    构造 System Prompt（系统提示词）——给大模型的"岗位说明书"。

    Prompt Engineering 要点：
      1. 角色设定：电商客服
      2. 知识注入：把商品知识库和 FAQ 原文放进提示词
      3. 行为约束：只能依据知识库回答，禁止编造价格/库存/规格
      4. 兜底策略：知识库没有的数据要明说，必要时引导转人工
    """
    return f"""你是一名电商平台的AI智能客服助手，名字叫"小智"。

【你的工作准则】
1. 回答商品价格、库存、规格、售后等问题时，必须以下面的知识库为唯一依据，禁止编造任何数据。
2. 知识库中没有的信息，要诚实回复"这个问题我暂时无法确认"，并建议顾客联系人工客服，禁止瞎编。
3. 回答要简洁友好，使用中文，每次回答控制在3句话以内。
4. 顾客的问题没提到具体商品时，结合上文提到的商品理解（比如顾客刚问了蓝牙耳机，接着问"有货吗"，指的是蓝牙耳机）。
5. 顾客明确表达不满或问题超出你的能力时，建议转人工客服。
6. 本系统是演示项目，商品数据为模拟数据，如顾客询问，如实说明。

{knowledge.build_knowledge_text()}"""


def get_reply(question):
    """
    处理一条顾客消息，返回客服回复文本。
    包含：记忆读取 → 调用大模型 → 记忆写入
    """
    memory = memory_manager.get_memory(USER_ID)

    # 拼装完整对话：系统提示词 + 历史对话 + 本次提问
    messages = [{"role": "system", "content": build_system_prompt()}]
    messages += memory.get_messages()
    messages.append({"role": "user", "content": question})

    # 调用大模型
    reply = llm_client.chat(messages)

    if reply is None:
        return "抱歉，系统暂时繁忙，请稍后再试或联系人工客服。"

    # 写入对话记忆，支持后续多轮上下文
    memory.add("user", question)
    memory.add("assistant", reply)
    return reply


def main():
    print("=" * 40)
    print("  AI 电商智能客服助手（DeepSeek 驱动）")
    print("  输入「退出」结束咨询，输入「清空」重新开始")
    print("=" * 40)

    # 启动前自检：知识库和 API Key
    if not knowledge.products:
        print("警告：商品知识库为空，请检查 data/products.json")
    if not llm_client.create_client():
        print("错误：未找到 API Key（环境变量 DEEPSEEK_API_KEY），程序退出。")
        print("设置方法：Windows 设置 → 搜索\"编辑账户的环境变量\" → 新建用户变量")
        return

    while True:
        try:
            question = input("\n顾客：").strip()
        except (EOFError, KeyboardInterrupt):
            # Ctrl+C 或输入流结束
            print("\n客服：感谢您的咨询，再见！")
            break

        if not question:
            continue

        if question in ("退出", "exit", "quit"):
            print("客服：感谢您的咨询，再见！")
            break

        if question in ("清空", "清除记录", "新对话"):
            memory_manager.get_memory(USER_ID).clear()
            print("客服：已为您清空对话记录，请问有什么可以帮您？")
            continue

        reply = get_reply(question)
        print(f"客服：{reply}")


if __name__ == "__main__":
    main()
