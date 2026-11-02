# -*- coding: utf-8 -*-
"""
config.py —— 项目配置中心

作用：集中管理所有配置项（密钥、模型名、接口地址、参数）
被谁调用：llm_client.py、main.py、app.py
好处：以后想换模型或改参数，只需要改这一个文件
"""

import os

# DeepSeek API 配置（密钥只从环境变量读取，绝不写进代码）
API_KEY = os.getenv("DEEPSEEK_API_KEY")
BASE_URL = "https://api.deepseek.com"
MODEL_NAME = "deepseek-chat"     # DeepSeek 当前通用对话模型

# 模型调用参数
TIMEOUT = 30            # 请求超时（秒），避免网络卡死时程序无响应
MAX_TOKENS = 500        # 单次回复最大长度，控制成本
TEMPERATURE = 0.3       # 温度越低回答越稳定，客服场景要求准确优先

# 对话记忆配置
MAX_HISTORY_ROUNDS = 10  # 最多保留最近 10 轮对话，防止上下文过长增加费用

# 长对话摘要（滚动压缩）
ENABLE_SUMMARY = True    # 开关：关闭则只做简单截断
SUMMARY_TRIGGER = 12     # 历史消息超过 12 条（6轮）时触发压缩
SUMMARY_COMPRESS = 8     # 每次把最旧的 8 条压缩成摘要

# RAG 检索参数（阈值由标准问答集标定）
RAG_THRESHOLD = 0.28     # 低于此相似度视为"无可靠依据"，强制拒答
RAG_TOP_K = 3            # 核心命中片段数
RAG_MAX_CONTEXT = 4      # 含父文档扩展后最多注入的片段数
RAG_FAQ_THRESHOLD = 0.15 # FAQ 混合检索兜底阈值（限定域，可比全局阈值低）

