# -*- coding: utf-8 -*-
"""
tests/test_rag.py —— 轻量 RAG 检索模块测试（纯本地，不调用API，不花钱）

覆盖：文档切分、向量化、余弦检索、Top-K 排序、阈值拒答、上下文拼装
运行方式：python tests/test_rag.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

import config
import rag

results = []


def check(condition, label):
    print(f"{'✅ PASS' if condition else '❌ FAIL'} | {label}")
    results.append(condition)


def main():
    print("=" * 60)
    print("轻量 RAG 检索测试（纯本地）")
    print("=" * 60)

    idx = rag.get_index()
    check(len(idx.chunks) == 16, "知识文档切分为16块（3商品×3 + 7 FAQ）")
    check(len(idx.idf) > 100, f"词表构建成功（{len(idx.idf)} 个词项）")

    # 分词：中文单字 + 双字
    toks = rag.tokenize("蓝牙耳机")
    check("蓝牙" in toks and "耳机" in toks and "耳" in toks,
          "中文 bi-gram 分词正确")

    # 语义检索：能找到相关片段
    hits = idx.retrieve("背包防水吗")
    check(len(hits) > 0 and hits[0]["source"] == "双肩背包",
          "开放问题「背包防水吗」检索到双肩背包规格片段")
    check(hits[0]["score"] >= 0.20, "命中片段相似度达标")

    hits = idx.retrieve("怎么退货")
    check(len(hits) > 0 and hits[0]["type"] == "售后FAQ",
          "「怎么退货」优先命中 FAQ 片段")

    hits = idx.retrieve("耳机适合学生用吗")
    check(any(h["source"] == "蓝牙耳机" for h in hits),
          "语义相近但字面不同仍能召回（非关键词匹配）")

    # 阈值拒答：无关问题必须返回空
    hits = idx.retrieve("苹果手机多少钱")
    check(len(hits) == 0, "无关问题被阈值拦截 → 返回空，强制拒答")

    hits = idx.retrieve("")
    check(len(hits) == 0, "空查询返回空")

    # Top-K 控制（核心命中数）
    hits = idx.retrieve("保温杯", top_k=2)
    check(sum(1 for h in hits if h["core"]) <= 2, "Top-K 参数控制核心命中数")

    # 父文档扩展：命中商品后补充同商品其他切片，保证答案事实不漏
    hits = idx.retrieve("保温杯能保温多久")
    check(any(not h["core"] for h in hits), "父文档扩展补充了同来源切片")
    check(any("保温12小时" in h["text"] for h in hits),
          "扩展后带入了含正确答案（保温12小时）的规格切片")
    check(len(hits) <= config.RAG_MAX_CONTEXT, "注入片段总数受上限控制")

    # 上下文拼装
    ctx = idx.build_context("保温杯能保温多久")
    check("检索到的知识片段" in ctx and "保温12小时" in ctx,
          "检索结果可拼装为提示词上下文")

    ctx = idx.build_context("苹果手机多少钱")
    check(ctx == "", "无相关结果时上下文为空（不允许生成）")

    # 排序正确性
    hits = idx.retrieve("怎么退货")
    scores = [h["score"] for h in hits]
    check(scores == sorted(scores, reverse=True), "检索结果按相似度降序")

    print("-" * 60)
    print(f"测试结果：{sum(results)}/{len(results)} 通过")


if __name__ == "__main__":
    main()
