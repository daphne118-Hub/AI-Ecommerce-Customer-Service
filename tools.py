# -*- coding: utf-8 -*-
"""
tools.py —— Agent 的工具箱（Function Calling 的"工具"本体）

作用：定义 Agent 可以调用的工具（商品知识 + 模拟业务 + RAG 检索），每个工具：
  1. 有一个真正执行查询的 Python 函数（操作本地知识库）
  2. 有一个 JSON 格式的"说明书"（告诉大模型什么时候用、怎么传参）
被谁调用：agent.py

通俗理解：大模型是"大脑"，负责决策；tools.py 是"双手"，
负责真正去查数据。大脑不能凭空想象查询结果，必须等双手返回。
"""

import config
import knowledge
import business
import rag

# ---------- 工具实现（真正干活的函数） ----------

def search_product(name: str) -> dict:
    """按商品名查询完整信息（价格/实时库存/规格/售后等）"""
    result = knowledge.search_product(name)
    if result:
        # 结构化实时字段由业务层提供（下单会改变库存）
        result["stock"] = business.get_stock(result["name"])
        result["data_source"] = "模拟演示数据（库存为实时值）"
        return {"success": True, "data": result}
    return {"success": False, "error": f"未找到商品「{name}」，本店目前只有：{', '.join(knowledge.products.keys())}"}


def check_stock(name: str) -> dict:
    """查询指定商品的实时库存（下单扣减后立即可见）"""
    stock = business.get_stock(name)
    if stock is None:
        return {"success": False, "error": f"未找到商品「{name}」"}
    return {"success": True, "data": {
        "name": name, "stock": stock,
        "data_source": "模拟演示数据（实时库存，下单会扣减）"}}


def search_faq(keyword: str) -> dict:
    """
    混合检索 FAQ：精确关键词优先，未命中时降级为 RAG 语义检索兜底。
    解决「什么时候发货」匹配不到键为「物流」的 FAQ 这类同义问题。
    """
    key, answer = knowledge.search_faq(keyword)
    if key:
        return {"success": True, "data": {
            "keyword": key, "answer": answer, "retrieval": "关键词精确命中"}}

    hits = rag.retrieve(keyword, threshold=config.RAG_FAQ_THRESHOLD)
    faq_hits = [h for h in hits if h["type"] == "售后FAQ" and h["core"]]
    if faq_hits:
        top = faq_hits[0]
        return {"success": True, "data": {
            "keyword": top["source"],
            "answer": top["text"],
            "score": top["score"],
            "retrieval": "语义向量检索兜底"}}

    return {"success": False, "error": "FAQ 中没有相关内容，请勿编造答案"}


def recommend_product(category: str = None, budget: float = None) -> dict:
    """推荐商品，可按类别和预算过滤"""
    result = knowledge.recommend_products(category=category, budget=budget)
    if result:
        return {"success": True, "data": result}
    return {"success": False, "error": "没有符合条件的商品"}


def transfer_to_human(reason: str = "") -> dict:
    """转接人工客服（演示版：记录请求并返回转接结果）"""
    # 真实系统里这里会调用工单/客服系统 API；演示版返回模拟转接结果
    return {"success": True, "data": {"status": "已受理", "reason": reason or "顾客请求人工服务",
                                      "queue": "人工客服队列", "estimated_wait": "约2分钟"}}


# ---------- 以下 4 个工具为模拟电商业务流程（数据全部来自本地 JSON） ----------

def query_order(order_id: str) -> dict:
    """查询订单信息（模拟数据）"""
    return business.query_order(order_id)


def query_logistics(order_id: str) -> dict:
    """查询物流状态（模拟数据）"""
    return business.query_logistics(order_id)


def query_refund(order_id: str) -> dict:
    """查询退款进度（模拟数据）"""
    return business.query_refund(order_id)


def apply_after_sale(order_id: str, reason: str, sale_type: str = "退货退款") -> dict:
    """提交售后申请（模拟流程，不产生真实工单）"""
    return business.apply_after_sale(order_id, reason, sale_type)


def place_order(product_name: str, quantity: int = 1) -> dict:
    """模拟下单：校验库存 → 扣减库存 → 生成订单（真实改变系统状态）"""
    return business.place_order(product_name, quantity)


def advance_after_sale(application_id: str) -> dict:
    """推进售后申请状态机（已提交 → 审核通过 → 退款处理中 → 退款完成）"""
    return business.advance_after_sale(application_id)


# ---------- RAG 检索工具（语义检索，处理开放式/模糊问题） ----------

def search_knowledge(query: str) -> dict:
    """
    用向量检索查找知识片段。
    与 search_faq 的区别：search_faq 是精确关键词命中，
    search_knowledge 能处理「背包防水吗」「适合学生用的」这类开放式提问。
    """
    hits = rag.retrieve(query, top_k=3)
    if not hits:
        # 关键：没有可靠检索结果，必须让模型拒答，不许自由发挥
        return {"success": False,
                "error": "知识库检索未找到相关内容，请如实告知顾客无法确认，禁止编造"}
    return {"success": True, "data": {
        "hits": hits,
        "context": rag.get_index().build_context(query, top_k=3),
        "notice": "以上片段来自本地知识库向量检索，回答只能依据这些内容",
    }}


# ---------- 工具说明书（发给大模型的 JSON Schema） ----------

TOOL_SPECS = [
    {
        "type": "function",
        "function": {
            "name": "search_product",
            "description": "查询商品的完整信息，包括价格、库存、规格、适用人群、特点、售后政策。当顾客询问某个商品的详细信息或价格时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "商品名称，如：蓝牙耳机"}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": "查询某个商品的当前库存数量。当顾客询问是否有货、库存多少时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string", "description": "商品名称"}
                },
                "required": ["name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_faq",
            "description": "检索售后服务常见问题（退货、退款、物流、快递、优惠、发票）。当顾客咨询售后政策或配送问题时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": "string", "description": "问题关键词，如：退货、退款、物流"}
                },
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recommend_product",
            "description": "根据类别或预算为顾客推荐商品。当顾客想买东西但没确定具体商品、或要求推荐时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "商品类别，如：数码配件、生活用品、箱包配饰。可省略"},
                    "budget": {"type": "number", "description": "顾客的预算上限（元）。可省略"},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transfer_to_human",
            "description": "转接人工客服。当顾客明确要求人工服务、表达强烈不满、或问题超出AI能力范围时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string", "description": "转人工原因，如：顾客情绪激动、问题无法解答"}
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_order",
            "description": "根据订单号查询订单信息（商品、金额、状态、下单时间）。顾客询问某个订单的情况时使用。数据为模拟演示数据。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单号，如：DD20261101001"}
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_logistics",
            "description": "根据订单号查询物流状态（承运公司、运单号、当前位置、预计送达）。顾客询问快递到哪了、什么时候送达时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单号"}
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_refund",
            "description": "根据订单号查询退款进度（退款单号、金额、状态、预计到账时间）。顾客询问退款到哪一步时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单号"}
                },
                "required": ["order_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_after_sale",
            "description": "提交售后申请（退货/换货/维修）。顾客明确要求申请售后、退货退款时使用。注意这是演示项目的模拟申请，不会产生真实工单。",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {"type": "string", "description": "订单号"},
                    "reason": {"type": "string", "description": "申请原因，如：商品破损、不想要了"},
                    "sale_type": {"type": "string", "description": "售后类型：退货退款/换货/维修，默认退货退款"},
                },
                "required": ["order_id", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": "对商品知识库和售后FAQ做语义向量检索，用于回答开放式、模糊的问题，例如「背包防水吗」「适合学生用的有什么」「耳机续航怎么样」。当问题没有明确商品名或FAQ关键词、其他工具无法直接回答时使用。检索不到内容时必须如实拒答。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "顾客的原始问题"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "place_order",
            "description": "模拟下单：校验库存、扣减库存并生成新订单。当顾客明确表示要购买、下单时使用。数量不明确时默认1。这是演示项目的模拟交易，不会产生真实扣款。",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string", "description": "商品名称"},
                    "quantity": {"type": "integer", "description": "购买数量，默认1"},
                },
                "required": ["product_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "advance_after_sale",
            "description": "推进售后申请的状态流转（审核通过→退款处理中→退款完成），用于查询或演示售后流程进展。顾客询问售后申请能否加快、流程走到哪一步时使用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "application_id": {"type": "string", "description": "售后申请单号，如 SQ0001"}
                },
                "required": ["application_id"],
            },
        },
    },
]

# 工具名 → 函数 的映射表（执行时按名字查找）
TOOL_FUNCTIONS = {
    "search_product": search_product,
    "check_stock": check_stock,
    "search_faq": search_faq,
    "recommend_product": recommend_product,
    "transfer_to_human": transfer_to_human,
    "query_order": query_order,
    "query_logistics": query_logistics,
    "query_refund": query_refund,
    "apply_after_sale": apply_after_sale,
    "search_knowledge": search_knowledge,
    "place_order": place_order,
    "advance_after_sale": advance_after_sale,
}


def execute_tool(name: str, arguments: dict) -> dict:
    """
    执行工具（Agent 工作循环的"执行"环节）。
    统一拦截异常：工具出错时返回错误信息，而不是让整个程序崩溃，
    大模型收到错误信息后会向顾客说明，不会伪造结果。
    """
    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return {"success": False, "error": f"工具 {name} 不存在"}
    try:
        return func(**arguments) if arguments else func()
    except TypeError as e:
        return {"success": False, "error": f"工具参数错误：{e}"}
    except Exception as e:
        return {"success": False, "error": f"工具执行出错：{e}"}


# 直接运行本文件可自测工具
if __name__ == "__main__":
    import json
    print(json.dumps(search_product("蓝牙耳机"), ensure_ascii=False))
    print(json.dumps(check_stock("保温杯"), ensure_ascii=False))
    print(json.dumps(search_faq("怎么退货"), ensure_ascii=False))
    print(json.dumps(recommend_product(budget=100), ensure_ascii=False))
    print(json.dumps(execute_tool("search_product", {"name": "手机"}), ensure_ascii=False))
    print(json.dumps(execute_tool("不存在", {}), ensure_ascii=False))
