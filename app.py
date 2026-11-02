# -*- coding: utf-8 -*-
"""
app.py —— AI 电商智能客服网页版（Streamlit）

作用：把 Agent 包装成可在浏览器中使用的聊天界面。
相比初版升级：
  - 侧边栏展示 Agent 结构化决策轨迹（决策→参数→执行结果）
  - 展示 RAG 检索命中的知识片段与相似度
  - 展示实时库存、订单、售后状态机（有状态业务可视化）
  - 多用户会话切换，演示记忆隔离
运行方式：streamlit run app.py（浏览器自动打开）
"""

import json
import sys

import streamlit as st

import business
import config
import knowledge
import llm_client
import tools
from agent import CustomerServiceAgent

# 页面基础配置（必须最先执行）
st.set_page_config(
    page_title="AI 电商智能客服",
    page_icon="🛒",
    layout="wide",
)

# Windows 编码兼容
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

st.markdown("""
<style>
    .app-title {text-align: center; padding: 6px 0 2px;}
    .app-sub {text-align: center; color: #888; font-size: 14px;
              margin-bottom: 18px;}
    .tool-badge {background: #eef4ff; color: #3b6fe0; border-radius: 12px;
                 padding: 2px 10px; font-size: 12px; margin: 2px;}
</style>
""", unsafe_allow_html=True)

st.markdown("<h1 class='app-title'>🛒 AI 电商智能客服助手</h1>", unsafe_allow_html=True)
st.markdown(
    "<p class='app-sub'>DeepSeek 大模型 · Function Calling Agent · "
    "轻量 RAG 检索 · 有状态模拟业务（全部为模拟演示数据）</p>",
    unsafe_allow_html=True)


# ---------- 会话状态初始化（按用户隔离） ----------
USERS = ["顾客A", "顾客B", "顾客C"]

if "user_id" not in st.session_state:
    st.session_state.user_id = USERS[0]
if "chats" not in st.session_state:
    st.session_state.chats = {u: [] for u in USERS}        # 每人的聊天记录
if "traces" not in st.session_state:
    st.session_state.traces = {u: {} for u in USERS}       # 每条回复的工具徽章
if "last_trace" not in st.session_state:
    st.session_state.last_trace = {u: [] for u in USERS}   # 最近一轮决策轨迹
if "agents" not in st.session_state:
    st.session_state.agents = {}                            # 每人的 Agent 实例


def get_agent():
    """获取当前用户的 Agent（不同用户记忆互相隔离）"""
    uid = st.session_state.user_id
    if uid not in st.session_state.agents:
        st.session_state.agents[uid] = CustomerServiceAgent(uid)
    return st.session_state.agents[uid]


def send_message(text: str):
    """发送顾客消息 → Agent 处理 → 记录回复与决策轨迹"""
    uid = st.session_state.user_id
    agent = get_agent()
    st.session_state.chats[uid].append({"role": "user", "content": text})

    with st.spinner("小智思考中（模型决策 + 工具调用）..."):
        reply = agent.run(text)

    st.session_state.chats[uid].append({"role": "assistant", "content": reply})
    idx = len(st.session_state.chats[uid]) - 1
    st.session_state.traces[uid][idx] = list(agent.last_tool_calls)
    st.session_state.last_trace[uid] = list(agent.last_trace)


def send_and_rerun(text: str):
    """发送消息并立即重绘（修复按钮点击后延迟一轮显示的问题）"""
    send_message(text)
    st.rerun()


def clear_chat():
    """清空当前用户的聊天记录与对话记忆"""
    uid = st.session_state.user_id
    st.session_state.chats[uid] = []
    st.session_state.traces[uid] = {}
    st.session_state.last_trace[uid] = []
    get_agent().memory.clear()


# ---------- 侧边栏：Agent 可观测性 + 业务状态 ----------
with st.sidebar:
    st.header("⚙️ 控制台")

    selected = st.selectbox("当前会话（用户隔离演示）", USERS,
                            index=USERS.index(st.session_state.user_id))
    st.session_state.user_id = selected

    st.caption(f"模型：`{config.MODEL_NAME}` · 工具：{len(tools.TOOL_SPECS)} 个 · "
               f"RAG 阈值：{config.RAG_THRESHOLD}")

    if st.button("🧹 清空当前会话", use_container_width=True):
        clear_chat()
        st.rerun()
    if st.button("♻️ 重置演示数据（库存/订单）", use_container_width=True):
        business.reset_state()
        st.rerun()

    # --- 最近一轮 Agent 决策轨迹 ---
    st.subheader("🔍 最近一轮决策轨迹")
    trace = st.session_state.last_trace[selected]
    if not trace:
        st.caption("发送消息后，这里会显示模型选了什么工具、传了什么参数、返回了什么。")
    else:
        for item in trace:
            label = f"Step {item['step']} · `{item['tool']}` " \
                    f"{'✅' if item['success'] else '❌'}"
            with st.expander(label, expanded=True):
                st.caption("模型给的参数")
                st.code(json.dumps(item["args"], ensure_ascii=False, indent=2),
                        language="json")
                st.caption("工具真实返回（截断）")
                st.code(item["result_preview"], language="json")

    # --- RAG 命中片段 ---
    rag_hits = [h for item in trace for h in item.get("rag_hits", [])]
    if rag_hits:
        st.subheader("📚 RAG 检索命中")
        for h in rag_hits:
            st.caption(f"`{h['source']}` · {h['type']} · 相似度 **{h['score']}**")

    # --- 有状态业务实时数据 ---
    st.subheader("📦 实时业务状态（模拟）")
    for name in knowledge.products:
        st.caption(f"{name}：库存 **{business.get_stock(name)}** 件")
    st.caption(f"订单总数：{len(business.list_demo_orders())}")
    apps = business.list_applications()
    if apps:
        st.caption("售后状态机：")
        for a in apps:
            st.caption(f"· {a['application_id']} → {a['status']}")
    else:
        st.caption("售后状态机：暂无申请")


# ---------- 启动自检 ----------
if not llm_client.create_client():
    st.error("未检测到 API Key！请先设置环境变量 DEEPSEEK_API_KEY，"
             "然后重新运行本页面。（密钥永远不会被写进代码）")
    st.stop()

# ---------- 主区：聊天记录 ----------
uid = st.session_state.user_id
messages = st.session_state.chats[uid]
traces = st.session_state.traces[uid]

for i, msg in enumerate(messages):
    if msg["role"] == "user":
        with st.chat_message("user", avatar="🧑"):
            st.markdown(msg["content"])
    else:
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(msg["content"])
            tools_used = traces.get(i)
            if tools_used:
                badges = "".join(
                    f"<span class='tool-badge'>🔧 {t}</span>" for t in tools_used)
                st.markdown(badges, unsafe_allow_html=True)

# ---------- 顶部功能栏 ----------
col1, col2, col3 = st.columns([2, 1, 1])
with col2:
    if st.button("👤 转人工客服", use_container_width=True):
        send_and_rerun("请帮我转接人工客服")

# ---------- 快捷提问（两行，覆盖全部能力） ----------
st.markdown("---")
st.caption("💡 快捷提问（覆盖 商品 / FAQ / 推荐 / 业务 / RAG / 拒答）：")
tips = st.columns(4)
if tips[0].button("蓝牙耳机多少钱"):
    send_and_rerun("蓝牙耳机多少钱？")
if tips[1].button("保温杯有货吗"):
    send_and_rerun("保温杯有货吗？库存多少？")
if tips[2].button("怎么退货"):
    send_and_rerun("买的东西不想要了，怎么退货？")
if tips[3].button("100元内推荐"):
    send_and_rerun("我预算100元以内，帮我推荐一下")

tips2 = st.columns(4)
if tips2[0].button("📦 模拟下单"):
    send_and_rerun("我要买1个蓝牙耳机，帮我下单")
if tips2[1].button("🔍 RAG 开放问题"):
    send_and_rerun("你们店里有用防水面料做的商品吗？")
if tips2[2].button("🚫 测试拒答"):
    send_and_rerun("你们支持以旧换新吗？")
if tips2[3].button("📮 查物流"):
    send_and_rerun("订单 DD20261101001 的快递到哪了？")

st.caption("📦 演示订单（模拟数据）：`DD20261101001`（运输中） · "
           "`DD20261028002`（已签收） · `DD20261025003`（退款中）")

# ---------- 输入框 ----------
if question := st.chat_input("请输入您的问题，例如：蓝牙耳机多少钱？"):
    send_message(question)
    st.rerun()

# ---------- 页脚 ----------
st.markdown(
    "<p style='text-align:center;color:#aaa;font-size:12px;margin-top:24px'>"
    f"模型：{config.MODEL_NAME} · 工具 {len(tools.TOOL_SPECS)} 个 · "
    "轻量 RAG（TF-IDF + 余弦相似度 + 阈值拒答 + 父文档扩展）</p>",
    unsafe_allow_html=True)
