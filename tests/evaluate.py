# -*- coding: utf-8 -*-
"""
tests/evaluate.py —— Agent 标准评测（量化项目效果）

作用：读取 data/eval_set.json 标准问答集，逐条运行 Agent，自动计算：
  - 工具选择准确率（意图识别）
  - 事实准确率（回答是否命中知识库中的正确数据）
  - 拒答正确率（知识库无依据时是否如实说明）
  - 幻觉拦截率（是否出现禁止的编造内容）
  - 综合通过率
并输出真实结果报告到 docs/评测报告.md。

运行方式：python tests/evaluate.py
成本提示：22 条用例，每条约 2 次模型调用，合计约 0.05~0.1 元。
"""

import json
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

import business
import config
from agent import CustomerServiceAgent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_PATH = os.path.join(ROOT, "data", "eval_set.json")
REPORT_PATH = os.path.join(ROOT, "docs", "评测报告.md")


def load_cases():
    with open(EVAL_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["cases"]


def evaluate_one(case, index):
    """运行单条用例，返回评分明细"""
    # 每条用例用独立 user_id，避免上下文串扰
    agent = CustomerServiceAgent(f"eval_user_{index}")
    for ctx in case.get("context", []):
        agent.run(ctx)  # 先建立上下文，不计分

    reply = agent.run(case["question"])
    tools_used = agent.last_tool_calls

    tool_ok = any(t in tools_used for t in case.get("expect_tools", []))
    if case.get("deny"):
        fact_ok = any(w in reply for w in case.get("deny_words", []))
    else:
        fact_ok = any(w in reply for w in case.get("expect_any", []))
    forbid_ok = not any(w in reply for w in case.get("forbid", []))

    return {
        "id": case["id"],
        "category": case["category"],
        "question": case["question"],
        "tools": tools_used,
        "reply": reply,
        "tool_ok": tool_ok,
        "fact_ok": fact_ok,
        "forbid_ok": forbid_ok,
        "passed": tool_ok and fact_ok and forbid_ok,
    }


def pct(n, total):
    return f"{n / total * 100:.1f}%" if total else "N/A"


def main():
    print("=" * 70)
    print("Agent 标准评测（真实调用 DeepSeek，约 0.05~0.1 元）")
    print("=" * 70)

    business.reset_state()  # 从干净的演示数据开始
    cases = load_cases()
    records = []
    for i, case in enumerate(cases):
        try:
            r = evaluate_one(case, i)
        except Exception as e:
            r = {"id": case["id"], "category": case["category"],
                 "question": case["question"], "tools": [], "reply": f"[异常] {e}",
                 "tool_ok": False, "fact_ok": False, "forbid_ok": False,
                 "passed": False}
        records.append(r)
        mark = "✅" if r["passed"] else "❌"
        print(f"{mark} {r['id']} [{r['category']}] 工具={r['tools']} "
              f"| {r['reply'][:60]}")

    total = len(records)
    tool_pass = sum(r["tool_ok"] for r in records)
    fact_cases = [r for r in records if not load_case_deny(r["id"], cases)]
    deny_cases = [r for r in records if load_case_deny(r["id"], cases)]
    fact_pass = sum(r["fact_ok"] for r in fact_cases)
    deny_pass = sum(r["fact_ok"] for r in deny_cases)
    forbid_cases = [r for r in records if load_case_forbid(r["id"], cases)]
    forbid_pass = sum(r["forbid_ok"] for r in forbid_cases)
    overall = sum(r["passed"] for r in records)

    print("-" * 70)
    print(f"工具选择准确率：{tool_pass}/{total}  {pct(tool_pass, total)}")
    print(f"事实准确率　　：{fact_pass}/{len(fact_cases)}  {pct(fact_pass, len(fact_cases))}")
    print(f"拒答正确率　　：{deny_pass}/{len(deny_cases)}  {pct(deny_pass, len(deny_cases))}")
    print(f"幻觉拦截率　　：{forbid_pass}/{len(forbid_cases)}  {pct(forbid_pass, len(forbid_cases))}")
    print(f"综合通过率　　：{overall}/{total}  {pct(overall, total)}")

    write_report(records, {
        "total": total, "tool_pass": tool_pass,
        "fact_pass": fact_pass, "fact_total": len(fact_cases),
        "deny_pass": deny_pass, "deny_total": len(deny_cases),
        "forbid_pass": forbid_pass, "forbid_total": len(forbid_cases),
        "overall": overall,
    })
    print(f"\n报告已写入：{REPORT_PATH}")
    business.reset_state()  # 评测结束恢复干净状态


def load_case_deny(case_id, cases):
    return next(c.get("deny", False) for c in cases if c["id"] == case_id)


def load_case_forbid(case_id, cases):
    return bool(next(c.get("forbid", []) for c in cases if c["id"] == case_id))


def write_report(records, s):
    lines = [
        "# Agent 标准评测报告",
        "",
        f"- 评测日期：{date.today().isoformat()}",
        f"- 模型：`{config.MODEL_NAME}`（temperature={config.TEMPERATURE}）",
        f"- 样本数：{s['total']} 条标准问答（`data/eval_set.json`）",
        "- 评测方式：逐条真实调用 Agent，自动比对工具调用轨迹与回答文本",
        "- 数据说明：全部为本地模拟商品/订单数据，评测结果为当前演示系统实测值",
        "",
        "## 汇总指标",
        "",
        "| 指标 | 通过/总数 | 比率 |",
        "|------|-----------|------|",
        f"| 工具选择准确率（意图识别） | {s['tool_pass']}/{s['total']} | {pct(s['tool_pass'], s['total'])} |",
        f"| 事实准确率（回答命中正确数据） | {s['fact_pass']}/{s['fact_total']} | {pct(s['fact_pass'], s['fact_total'])} |",
        f"| 拒答正确率（无依据时如实说明） | {s['deny_pass']}/{s['deny_total']} | {pct(s['deny_pass'], s['deny_total'])} |",
        f"| 幻觉拦截率（未出现禁止内容） | {s['forbid_pass']}/{s['forbid_total']} | {pct(s['forbid_pass'], s['forbid_total'])} |",
        f"| **综合通过率** | **{s['overall']}/{s['total']}** | **{pct(s['overall'], s['total'])}** |",
        "",
        "## 逐条明细",
        "",
        "| 编号 | 类别 | 问题 | 调用工具 | 结果 |",
        "|------|------|------|----------|------|",
    ]
    for r in records:
        q = r["question"].replace("|", "\\|")
        tools = ", ".join(r["tools"]) or "无"
        lines.append(f"| {r['id']} | {r['category']} | {q} | `{tools}` | "
                     f"{'✅ 通过' if r['passed'] else '❌ 未通过'} |")

    failed = [r for r in records if not r["passed"]]
    lines += ["", "## 未通过用例分析", ""]
    if failed:
        for r in failed:
            checks = (f"工具={'✓' if r['tool_ok'] else '✗'} "
                      f"内容={'✓' if r['fact_ok'] else '✗'} "
                      f"禁词={'✓' if r['forbid_ok'] else '✗'}")
            lines.append(f"- **{r['id']}** {r['question']}（{checks}）")
            lines.append(f"  - 实际工具：`{r['tools']}`")
            lines.append(f"  - 实际回复：{r['reply'][:150]}")
    else:
        lines.append("本次评测全部用例通过。")

    lines += [
        "",
        "## 指标口径与局限（如实说明）",
        "",
        "- 工具选择准确率：`Agent.last_tool_calls` 是否包含该用例期望的工具之一",
        "- 事实准确率 / 拒答正确率：回答中是否出现预设关键词（字符串包含）",
        "- 幻觉拦截率：回答中是否未出现禁止出现的编造表述",
        "- 局限：样本量小（22 条）、关键词匹配法无法覆盖等价表述、模型输出有随机性；",
        "  该指标仅用于演示系统回归验证，**不代表生产环境业务准确率**，也未做过大规模人工标注评测。",
        "",
        "## 复现方式",
        "",
        "```cmd",
        ".venv\\Scripts\\python.exe tests\\evaluate.py",
        "```",
    ]
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
