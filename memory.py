# -*- coding: utf-8 -*-
"""
memory.py —— 多轮对话记忆管理（短期记忆 + 滚动摘要长期记忆）

作用：管理每个用户的对话历史
  - 保存对话（顾客问 + 客服答）
  - 控制上下文长度（只保留最近 N 轮，防止费用浪费）
  - **滚动摘要**：历史过长时，让大模型把最旧的几轮压缩成一段摘要保留下来，
    而不是粗暴丢弃（长期记忆），再拼回 System Prompt
  - 支持按用户隔离（不同用户的对话互不混淆）
  - 支持清空历史
被谁调用：main.py、agent.py、app.py

通俗理解：这就是 AI 的"记忆系统"。
大模型本身没有记忆，每次调用都是全新对话，
所以必须把之前的聊天记录重新传给它，它才能"记得"上文；
但记录太长会又慢又贵，所以超长时先"做笔记"（摘要）再继续。
"""

import config
import llm_client

# 摘要专用提示词：要求保留业务关键事实，便于后续指代理解
SUMMARY_PROMPT = """请把下面这段电商客服对话压缩成简洁的中文摘要（150字以内）。
必须保留：顾客咨询过的商品名与价格、提到的订单号、已给出的结论、
以及顾客尚未解决的问题。只输出摘要本身，不要加解释。"""


class ConversationMemory:
    """单个用户的对话记忆"""

    def __init__(self):
        # 只保存 user 和 assistant 的消息，不含 system 提示词
        self.history = []
        self.summary = ""       # 压缩后的长期记忆

    def add(self, role, content):
        """保存一条消息。role 为 "user"（顾客）或 "assistant"（客服）"""
        self.history.append({"role": role, "content": content})
        self.maybe_summarize()
        self._trim()

    def _trim(self):
        """兜底控制长度：每轮 = 1条顾客 + 1条客服，超出部分丢弃最旧的"""
        max_messages = config.MAX_HISTORY_ROUNDS * 2
        if len(self.history) > max_messages:
            self.history = self.history[-max_messages:]

    def maybe_summarize(self):
        """
        历史过长时生成滚动摘要。
        失败降级：摘要 API 调用失败不影响主流程，退回简单截断。
        """
        if not config.ENABLE_SUMMARY:
            return
        if len(self.history) <= config.SUMMARY_TRIGGER:
            return

        old = self.history[:config.SUMMARY_COMPRESS]
        text = "\n".join(
            f"{'顾客' if m['role'] == 'user' else '客服'}：{m['content']}"
            for m in old)
        previous = f"已有摘要：{self.summary}\n" if self.summary else ""

        try:
            new_summary = llm_client.chat([
                {"role": "system", "content": SUMMARY_PROMPT},
                {"role": "user", "content": previous + text},
            ])
        except Exception:
            new_summary = None

        if new_summary:
            self.summary = new_summary.strip()
            # 只删除已被压缩进摘要的旧消息
            self.history = self.history[config.SUMMARY_COMPRESS:]

    def get_summary(self):
        """返回长期记忆摘要（供 Agent 并入系统提示词）"""
        return self.summary

    def clear(self):
        """清空对话历史与摘要（顾客说"清空"时调用）"""
        self.history = []
        self.summary = ""

    def get_messages(self):
        """返回对话历史，供拼接后发给大模型"""
        return list(self.history)


class MemoryManager:
    """管理多个用户的对话记忆（按 user_id 隔离）"""

    def __init__(self):
        self._memories = {}

    def get_memory(self, user_id):
        """获取指定用户的记忆，不存在则新建"""
        if user_id not in self._memories:
            self._memories[user_id] = ConversationMemory()
        return self._memories[user_id]


# 全局单例：整个程序共用一个管理器
memory_manager = MemoryManager()
