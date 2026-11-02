# -*- coding: utf-8 -*-
"""
rag.py —— 轻量 RAG（检索增强生成）模块

完整链路：
  知识文档整理 → 文本切分(chunk) → 向量化(TF-IDF) → 余弦相似度检索(Top-K)
  → 相似度阈值拒答 → 检索结果注入大模型提示词 → 基于检索内容生成答案

技术选型说明（重要，面试如实回答）：
  1. DeepSeek 官方没有提供 Embedding 接口，本地也没有 GPU/向量模型，
     因此使用**稀疏向量 TF-IDF + 余弦相似度**，而不是神经网络 Embedding。
     它是真实可运行的向量检索，不是关键词匹配：查询和文档都转成向量再算夹角。
  2. 中文不依赖 jieba 等分词库，用"单字 + 相邻双字(bi-gram)"构造词表，
     既能匹配「耳机」与「蓝牙耳机」，零额外依赖。
  3. 不使用 FAISS/Chroma：文档只有十几块，暴力计算余弦相似度足够，
     且省去索引维护。数据量到几千块时再换向量库。
被谁调用：tools.py（search_knowledge 工具）、tests/test_rag.py
"""

import math
import re

import config
import knowledge


# ---------- 第一步：知识文档整理与切分 ----------

def build_chunks():
    """
    把知识库切分成检索用的文档块(chunk)。
    每个商品切成 3 块（基础/规格/售后），每条 FAQ 1 块。
    切分的意义：检索更精准，注入提示词时只带相关片段，节省 token。
    """
    chunks = []

    for name, info in knowledge.products.items():
        chunks.append({
            "id": f"product:{name}:base",
            "source": name,
            "type": "商品基础信息",
            # 注意：库存会随下单变化，属于结构化实时字段，交给工具查询，
            # 不写进静态向量文档，避免检索到过期数据（职责分离）
            "text": (f"{name}属于{info['category']}，价格{info['price']}元。"
                     f"{info['description']}。（库存需调用工具实时查询）"),
        })
        chunks.append({
            "id": f"product:{name}:spec",
            "source": name,
            "type": "商品规格与适用人群",
            "text": (f"{name}的规格：{info['specs']}。"
                     f"适合人群：{info['suitable_for']}。"
                     f"产品特点：{info['features']}。"),
        })
        chunks.append({
            "id": f"product:{name}:service",
            "source": name,
            "type": "商品售后规则",
            "text": f"{name}的售后规则：{info['after_sales']}。",
        })

    for key, answer in knowledge.faq.items():
        chunks.append({
            "id": f"faq:{key}",
            "source": key,
            "type": "售后FAQ",
            "text": f"关于{key}的常见问题：{answer}",
        })

    return chunks


# ---------- 第二步：文本向量化 ----------

def tokenize(text):
    """
    中文友好的"分词"：提取中文单字 + 相邻双字、英文单词、数字。
    例：「蓝牙耳机」→ ['蓝','牙','耳','机','蓝牙','牙耳','耳机']
    """
    tokens = []
    # 英文单词与数字
    for word in re.findall(r"[a-z0-9]+", text.lower()):
        tokens.append(word)
    # 中文字符序列
    for seg in re.findall(r"[\u4e00-\u9fff]+", text):
        for ch in seg:
            tokens.append(ch)
        for i in range(len(seg) - 1):
            tokens.append(seg[i:i + 2])
    return tokens


def _build_index(chunks):
    """构建倒排索引：词 → 文档编号集合，并计算 IDF 权重"""
    n = len(chunks)
    docs_tokens = [tokenize(c["text"]) for c in chunks]
    df = {}
    for toks in docs_tokens:
        for t in set(toks):
            df[t] = df.get(t, 0) + 1
    # 平滑 IDF，避免 0 除
    idf = {t: math.log((n + 1) / (d + 1)) + 1 for t, d in df.items()}
    return docs_tokens, idf


def _vectorize(tokens, idf):
    """把词列表转成 L2 归一化的 TF-IDF 稀疏向量（dict: 词→权重）"""
    tf = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    vec = {}
    for t, freq in tf.items():
        if t in idf:  # 查询中出现词表外的新词，直接忽略
            vec[t] = (1 + math.log(freq)) * idf[t]
    norm = math.sqrt(sum(v * v for v in vec.values()))
    if norm > 0:
        vec = {t: v / norm for t, v in vec.items()}
    return vec


def _cosine(v1, v2):
    """余弦相似度：两个稀疏向量的点积（已归一化）"""
    if len(v1) > len(v2):
        v1, v2 = v2, v1
    return sum(weight * v2.get(t, 0.0) for t, weight in v1.items())


# ---------- 第三步：检索 ----------

class KnowledgeIndex:
    """知识库向量索引（程序启动时构建一次，常驻内存）"""

    def __init__(self, chunks=None):
        self.chunks = chunks if chunks is not None else build_chunks()
        docs_tokens, self.idf = _build_index(self.chunks)
        self.vectors = [_vectorize(toks, self.idf) for toks in docs_tokens]

    def retrieve(self, query, top_k=None, threshold=None, max_context=None):
        """
        检索与问题最相关的知识片段。

        两道机制：
          1. 绝对阈值拒答：所有片段相似度都低于阈值 → 返回空列表，
             调用方必须拒答，不许模型自由发挥（由标准问答集标定阈值）
          2. 父文档扩展：命中某商品后，把该商品的其余切片一起带入，
             避免「问保温多久」却漏掉正好含答案的规格切片

        返回：[{"id","text","score","source","type","core"}, ...]
              core=True 表示核心命中，False 表示父文档扩展补充
        """
        top_k = top_k or config.RAG_TOP_K
        threshold = threshold if threshold is not None else config.RAG_THRESHOLD
        max_context = max_context or config.RAG_MAX_CONTEXT

        q_vec = _vectorize(tokenize(query), self.idf)
        if not q_vec:
            return []

        all_hits = []
        for chunk, vec in zip(self.chunks, self.vectors):
            score = _cosine(q_vec, vec)
            if score > 0:
                all_hits.append({
                    "id": chunk["id"],
                    "text": chunk["text"],
                    "score": round(score, 4),
                    "source": chunk["source"],
                    "type": chunk["type"],
                })
        all_hits.sort(key=lambda x: x["score"], reverse=True)

        # 第一道：阈值拒答
        qualified = [h for h in all_hits if h["score"] >= threshold]
        if not qualified:
            return []

        core = [dict(h, core=True) for h in qualified[:top_k]]

        # 第二道：父文档扩展（同一商品/FAQ 的其余切片）
        used_ids = {h["id"] for h in core}
        sources = {h["source"] for h in core}
        for h in all_hits:
            if len(core) >= max_context:
                break
            if h["source"] in sources and h["id"] not in used_ids:
                item = dict(h, core=False)
                core.append(item)
                used_ids.add(h["id"])
        return core

    def build_context(self, query, top_k=None, threshold=None):
        """把检索结果拼成可注入提示词的上下文文本"""
        hits = self.retrieve(query, top_k, threshold)
        if not hits:
            return ""
        lines = ["【检索到的知识片段（仅可依据以下内容回答）】"]
        for h in hits:
            tag = "命中" if h["core"] else "同来源补充"
            lines.append(
                f"- [{tag}|{h['type']}|相似度{h['score']}] {h['text']}")
        return "\n".join(lines)


# 全局单例索引
_index = None


def get_index():
    global _index
    if _index is None:
        _index = KnowledgeIndex()
    return _index


def retrieve(query, top_k=None, threshold=None):
    """模块级便捷入口（参数默认取 config 中的标定值）"""
    return get_index().retrieve(query, top_k, threshold)


# ---------- 自测 ----------
if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    idx = get_index()
    print(f"知识块数量：{len(idx.chunks)}，词表大小：{len(idx.idf)}")
    for q in ["耳机适合学生用吗", "怎么退货", "背包防水吗",
              "苹果手机多少钱", "保温杯能保温多久"]:
        hits = idx.retrieve(q)
        print(f"\n查询：{q} → {len(hits)} 条命中")
        for h in hits:
            print(f"  {h['score']} | {h['type']} | {h['text'][:50]}")
