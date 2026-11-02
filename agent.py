# -*- coding: utf-8 -*-
"""
agent.py —— AI Agent 工作循环（本项目核心模块）

Agent 与普通聊天机器人的区别：
  普通聊天机器人：顾客问 → 大模型直接答（答案全靠模型"脑补"）
  Agent：顾客问 → 大模型思考是否需要查数据 → 调用工具执行真实查询
        → 大模型根据工具返回的真实数据组织回答

工作循环（ReAct 思路）：
  1. 把对话历史 + 工具说明书发给大模型
  2. 大模型返回 tool_calls（决定用什么工具、传什么参数）
  3. 程序执行工具，把结果回传给大模型
  4. 大模型基于真实结果生成最终回答
  5. 最多循环 3 次，防止无限调用
被谁调用：app.py（网页版）、也可以命令行直接测试
"""

import json

import config
import llm_client
import tools
from memory import memory_manager

# Agent 的系统提示词
AGENT_SYSTEM_PROMPT = """你是一名电商平台的AI智能客服Agent，名字叫"小智"。

【工作方式】
你可以调用工具查询真实的商品数据和售后政策。回答任何涉及价格、库存、规格、售后的问题前，必须先调用相应工具，禁止凭记忆编造数据。

【行为准则】
1. 顾客问商品信息 → 调用 search_product 或 check_stock。涉及价格/库存的每一次提问都必须重新调用工具，不要直接沿用历史对话里的旧数值（下单会改变库存）
2. 顾客咨询通用规则（「怎么退货」「退款多久到账」「什么时候发货」「有优惠吗」「能开发票吗」）→ 调用 search_faq，直接回答规则，不要追问订单号
3. 顾客问某个具体订单的情况（带订单号）→ 调用 query_order
4. 顾客明确询问自己某个订单的包裹/快递状态 → 调用 query_logistics；问某个订单的退款到账进度 → 调用 query_refund
5. 只有顾客明确说「我要申请退货」「帮我办理售后」→ 调用 apply_after_sale（缺少订单号或原因时先询问，不要瞎填）；单纯咨询政策不属于这一类
6. 顾客要推荐 → 调用 recommend_product
7. 顾客要求人工服务、情绪不满、或工具查询失败 → 调用 transfer_to_human
8. 工具返回 success=false 时，如实告诉顾客无法确认，不要编造
9. 回答简洁友好，中文，3句话以内，结合上下文理解顾客指代
10. 订单/物流/退款数据均为模拟演示数据，回答中不要声称来自真实电商平台
11. 开放式、模糊的问题（如「背包防水吗」「适合学生用的有什么」「续航怎么样」）→ 调用 search_knowledge 做语义检索，只能依据返回的片段回答；若该工具返回 success=false，明确告知顾客无法确认，禁止编造
12. 顾客明确要购买/下单 → 调用 place_order（会真实扣减库存并生成模拟订单）；下单成功后把订单号和金额告知顾客，并说明这是模拟交易
13. 顾客询问售后申请进展或要求推进流程 → 调用 advance_after_sale（需申请单号，没有就先询问）
"""


class CustomerServiceAgent:
    """电商智能客服 Agent"""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.memory = memory_manager.get_memory(user_id)
        self.last_tool_calls = []  # 记录最近一次 run() 实际调用的工具名
        self.last_trace = []       # 结构化决策轨迹（供网页侧边栏可视化）

    def _finish(self, reply):
        """统一收尾：保存回复（add 内部会自动触发摘要压缩）"""
        self.memory.add("assistant", reply)
        return reply

    def _call_llm(self, messages):
        """带工具的模型调用（异常处理在 llm_client 内部）"""
        client = llm_client.create_client()
        if client is None:
            return None
        try:
            response = client.chat.completions.create(
                model=config.MODEL_NAME,
                messages=messages,
                tools=tools.TOOL_SPECS,       # 告诉大模型有哪些工具可用
                max_tokens=config.MAX_TOKENS,
                temperature=config.TEMPERATURE,
                timeout=config.TIMEOUT,
            )
            return response.choices[0].message
        except Exception as e:
            print(f"[Agent 调用失败] {e}")
            return None

    def run(self, user_input: str) -> str:
        """
        Agent 主入口：接收顾客消息，返回最终回复。
        内部自动完成 工具决策 → 执行 → 生成回答 的循环。
        """
        self.memory.add("user", user_input)
        self.last_tool_calls = []  # 重置本轮工具调用记录
        self.last_trace = []       # 重置本轮决策轨迹

        # 历史过长时，memory 会生成滚动摘要，这里把它并入系统提示词
        summary = self.memory.get_summary()
        system_content = AGENT_SYSTEM_PROMPT
        if summary:
            system_content += f"\n\n【此前对话摘要（压缩后的长期记忆）】\n{summary}"

        messages = [{"role": "system", "content": system_content}]
        messages += self.memory.get_messages()

        # 工具调用循环，最多 3 轮（防止模型反复调工具不收敛）
        for step in range(1, 4):
            message = self._call_llm(messages)
            if message is None:
                return self._finish("抱歉，系统暂时繁忙，请稍后再试。")

            # 情况A：模型决定调用工具
            if message.tool_calls:
                messages.append(message)  # 先记录模型的调用请求
                for tool_call in message.tool_calls:
                    # 解析模型给的参数（解析失败也要兜底）
                    try:
                        arguments = json.loads(tool_call.function.arguments or "{}")
                    except json.JSONDecodeError:
                        arguments = {}
                    name = tool_call.function.name
                    # 执行真实工具
                    result = tools.execute_tool(name, arguments)
                    self.last_tool_calls.append(name)

                    # 结构化轨迹：决策 → 参数 → 执行结果 → RAG命中片段
                    trace_item = {
                        "step": step,
                        "tool": name,
                        "args": arguments,
                        "success": result.get("success", False),
                        "result_preview": json.dumps(
                            result, ensure_ascii=False)[:300],
                    }
                    if name == "search_knowledge" and result.get("success"):
                        trace_item["rag_hits"] = [
                            {"source": h["source"], "type": h["type"],
                             "score": h["score"]}
                            for h in result["data"]["hits"]
                        ]
                    self.last_trace.append(trace_item)

                    # 工具结果回传给模型（json.dumps 保证是字符串）
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
                continue  # 带着工具结果，再问一次模型

            # 情况B：模型直接给出最终回答
            reply = message.content or "抱歉，我没有理解您的问题，可以换个说法再试试吗？"
            return self._finish(reply)

        # 循环用尽仍未得到最终回答
        return self._finish("抱歉，这个问题我处理起来有点吃力，为您转接人工客服好吗？")


# 命令行直接测试 Agent
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    print("=" * 40)
    print("  AI 客服 Agent 测试（输入 退出 结束）")
    print("=" * 40)
    agent = CustomerServiceAgent("agent_test")
    while True:
        try:
            q = input("\n顾客：").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not q or q == "退出":
            print("客服：感谢咨询，再见！")
            break
        print(f"客服：{agent.run(q)}")
