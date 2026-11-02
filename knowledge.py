# -*- coding: utf-8 -*-
"""
knowledge.py —— 商品知识库模块

作用：
  - 从 data/products.json 和 data/faq.json 加载知识库
  - 提供商品查询、FAQ 检索、商品推荐等函数
被谁调用：main.py（拼进提示词）、tools.py（Agent 工具调用）

设计原则：数据放 JSON 文件，代码只负责读取和查询，
以后增加商品只需要改 JSON，不用动代码。
"""

import json
import os

# data 目录的绝对路径（基于本文件位置，换电脑也能运行）
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def _load_json(filename):
    """读取 JSON 文件，失败时返回空字典并提示"""
    path = os.path.join(DATA_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"警告：知识库文件不存在 {path}")
        return {}
    except json.JSONDecodeError:
        print(f"警告：知识库文件格式错误 {path}")
        return {}


# 商品知识库与 FAQ（程序启动时加载一次）
products = _load_json("products.json")
faq = _load_json("faq.json")


def search_product(name):
    """
    按商品名查询完整信息。
    返回：dict（商品信息）或 None（找不到）
    """
    if name in products:
        return {"name": name, **products[name]}
    # 支持模糊匹配：如输入"耳机"也能匹配到"蓝牙耳机"
    for product_name, info in products.items():
        if name in product_name or product_name in name:
            return {"name": product_name, **info}
    return None


def check_stock(name):
    """查询商品库存。返回：dict 或 None"""
    product = search_product(name)
    if product:
        return {"name": product["name"], "stock": product["stock"]}
    return None


def search_faq(keyword):
    """
    FAQ 检索：关键词命中返回对应答案。
    返回：(关键词, 答案) 或 (None, None)
    """
    for key, answer in faq.items():
        if key in keyword:
            return key, answer
    return None, None


def recommend_products(category=None, budget=None):
    """
    商品推荐。
    参数：
        category: 商品类别（如"数码配件"），为 None 则不限
        budget: 预算上限，为 None 则不限
    返回：符合条件的商品列表
    """
    result = []
    for name, info in products.items():
        if category and info.get("category") != category:
            continue
        if budget is not None and info["price"] > budget:
            continue
        result.append({
            "name": name,
            "price": info["price"],
            "description": info["description"],
        })
    return result


def build_knowledge_text():
    """
    把整个知识库拼成一段文字，供拼进大模型的 System Prompt。
    这样模型回答商品问题时，依据的是真实数据而不是"编造"。
    """
    lines = ["【商品知识库】"]
    for name, info in products.items():
        lines.append(
            f"- {name}（{info['category']}）：价格{info['price']}元，"
            f"库存{info['stock']}件。{info['description']}。"
            f"规格：{info['specs']}。适合：{info['suitable_for']}。"
            f"特点：{info['features']}。售后：{info['after_sales']}。"
        )
    lines.append("\n【售后FAQ】")
    for key, answer in faq.items():
        lines.append(f"- 问：{key} 答：{answer}")
    return "\n".join(lines)


# 直接运行本文件时可自测知识库
if __name__ == "__main__":
    print(search_product("蓝牙耳机"))
    print(check_stock("保温杯"))
    print(search_faq("怎么退货"))
    print(recommend_products(budget=100))
