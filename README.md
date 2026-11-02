# 基于 DeepSeek 大模型的 AI 电商智能客服 Agent

> 一个模拟真实电商平台客服场景的 AI Agent 系统：具备商品知识库、轻量 RAG 检索、Function Calling 工具调用、有状态模拟业务、多轮对话记忆压缩与量化评测体系。
> **演示项目声明**：所有商品、订单、物流、退款数据均为本地模拟数据，未连接任何真实电商平台。

---

## 一、项目简介与背景

传统规则式客服（关键词匹配）只能回答固定问题；单纯调用大模型的聊天机器人又容易**编造价格和库存**。

本项目把两者结合：用大模型理解自然语言和判断意图，用 **Function Calling 工具调用**去查询本地结构化数据，让回答必须基于工具返回的真实（模拟）数据；对开放式问题则用**轻量 RAG 语义检索**召回知识片段，检索不到就如实拒答。系统还提供网页聊天界面与 Agent 决策轨迹可视化，可完整演示咨询、推荐、下单、订单、物流、退款、售后、转人工流程。

## 二、核心功能

| 类别 | 功能 |
|------|------|
| 商品服务 | 商品/价格/**实时库存**/规格/适用人群查询，按类别和预算推荐 |
| 检索增强 | 知识文档切分 → TF-IDF 向量化 → 余弦相似度 Top-K → **阈值拒答** → **父文档扩展** → 注入提示词；FAQ 精确关键词 + 语义检索兜底的**混合检索** |
| 模拟业务（有状态） | 订单查询、物流跟踪、退款进度、**模拟下单（真实扣减库存）**、**售后状态机流转**、转人工；运行时状态持久化到 `data/state.json`，可一键重置 |
| Agent 能力 | 意图识别 → 自主选择 12 个工具之一 → 真实执行 → 基于结果回答；工具失败不编造；结构化决策轨迹可观测 |
| 多轮对话 | 会话历史按用户隔离、长度控制、**超长时滚动摘要压缩（长期记忆）**、一键清空 |
| 评测体系 | 22 条标准问答集自动评测：工具选择准确率、事实准确率、拒答正确率、幻觉拦截率，输出真实报告 |
| 网页界面 | Streamlit 聊天窗口、快捷提问、工具调用轨迹、RAG 命中片段、实时库存/订单/售后状态、多用户会话切换 |

## 三、技术栈与选型理由

- **语言**：Python 3.13（RAG 模块纯标准库实现，无额外依赖）
- **大模型**：DeepSeek (`deepseek-chat`)，官方兼容 OpenAI 格式的接口
- **SDK**：`openai`、`streamlit`
- **Agent 实现**：原生 Function Calling 自建工作循环，**未使用 LangChain / LangGraph**
- **数据**：本地 JSON（3 商品 × 9 字段 + 7 条 FAQ + 3 条种子订单 + 运行时状态）
- **测试**：自建集成测试 + `streamlit.testing.AppTest` 界面回归 + 自动评测脚本

> **RAG 为什么是 TF-IDF 而不是神经网络 Embedding？**
> DeepSeek 官方不提供 Embedding 接口，本地也没有 GPU/向量模型。因此用零依赖的 **TF-IDF 稀疏向量 + 中文 bi-gram 分词 + 余弦相似度**实现完整检索链路：查询和文档都转成 L2 归一化向量再算夹角，是真实向量检索而非关键词匹配。16 个文档块用暴力计算即可，不必引入 FAISS/Chroma。
> 阈值 0.28 由标准问答集标定（相关问题的 Top1 在 0.29~0.35，无关问题最高 0.257）。**未使用神经网络 Embedding 与向量数据库，这一点在面试材料中如实说明。**

> **结构化数据与非结构化文本职责分离**：价格/库存/订单会随下单变化，走工具实时查询；规格/描述/FAQ 等静态文本走 RAG 检索。RAG 文档里故意不写库存，避免检索到过期数据。命中某商品后通过「父文档扩展」把该商品其余切片一并带入，避免问「保温多久」却漏掉含答案的规格切片。

> **为什么不用 LangChain？**：一个 Agent、12 个工具、一个循环，原生 Function Calling 约 120 行即可完整实现，每一步 messages 都看得见，调试和讲解成本最低。

## 四、项目架构

```
顾客提问
   ↓
app.py（Streamlit 网页，侧边栏可观测）/ main.py（命令行对照实现）
   ↓
agent.py —— Agent 工作循环（最多 3 轮）
   ├─ 第1次调用大模型：判断意图、决定工具与参数（Function Calling）
   ├─ tools.py（12 个工具 + JSON Schema + 统一异常兜底）
   │     ├─ knowledge.py → data/products.json、faq.json（精确查询）
   │     ├─ business.py  → data/orders.json + state.json（有状态业务）
   │     └─ rag.py       → 16 个知识块向量索引（语义检索/拒答）
   ├─ 工具结果以 role=tool 回传大模型
   └─ 第2次调用大模型：基于真实结果生成回答
   ↓
memory.py 保存对话（用户隔离 / 长度控制 / 滚动摘要长期记忆）
   ↓
网页展示回答 + 🔧 工具徽章 + 决策轨迹 + RAG 命中片段
```

### 文件说明

| 文件 | 作用 | 被谁调用 | 测试方式 |
|------|------|----------|----------|
| `config.py` | 配置中心（密钥、模型、超时、温度、记忆与 RAG 参数） | 各模块 | 修改参数后运行测试 |
| `llm_client.py` | 封装 DeepSeek 调用，统一异常/超时 | main、agent、memory | `test_api.py` |
| `knowledge.py` | 商品/FAQ 加载、精确查询、推荐、拼装知识文本 | tools、rag、main | `python knowledge.py` |
| `rag.py` | 文档切分、bi-gram 分词、TF-IDF 向量化、余弦检索、阈值拒答、父文档扩展 | tools | `tests/test_rag.py` |
| `business.py` | 有状态业务：下单扣库存、售后状态机、状态持久化、重置 | tools、app | `python business.py` |
| `tools.py` | 12 个工具实现 + JSON Schema 说明书 + 统一执行入口 | agent | `python tools.py` |
| `memory.py` | 多轮记忆、用户隔离、滚动摘要 | agent、main、app | `tests/test_memory.py` |
| `agent.py` | Agent 工作循环 + 结构化决策轨迹 | app、evaluate | `tests/test_agent.py` |
| `app.py` | Streamlit 网页界面（聊天 + 侧边栏可观测性） | 浏览器 | `tests/test_app_ui.py` |
| `main.py` | 命令行版（知识库直接注入 Prompt 的对照实现） | 命令行 | `tests/test_scenarios.py` |
| `test_api.py` | DeepSeek API 连通性三步测试 | 开发者 | `python test_api.py` |
| `data/*.json` | 商品/FAQ/订单/评测集/运行时状态 | 各模块 | 各模块自测 |
| `tests/*.py` | 6 组测试 + 自动评测脚本 | 开发者 | 见第九节 |
| `docs/评测报告.md` | 22 条标准问答集的真实评测结果 | 展示/简历 | `tests/evaluate.py` |

## 五、安装方法（Windows）

项目使用独立虚拟环境 `.venv`。如需重建：

```cmd
cd /d C:\Users\Lenovo\Desktop\AI-Ecommerce-Customer-Service
D:\python\python.exe -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

> Spyder 用户：Tools → Preferences → Application → Advanced settings → Python interpreter，
> 选择 `...\.venv\Scripts\python.exe`，重启 Spyder。环境已装 `spyder-kernels` 保证兼容。

## 六、配置方法

**API Key 只通过环境变量读取，绝不写入代码。**

1. Windows 设置 → 搜索「编辑账户的环境变量」→ 用户变量 → 新建
   - 变量名：`DEEPSEEK_API_KEY`，变量值：你自己的 Key
2. 设置后**完全重启** Spyder / CMD
3. 验证：
```cmd
.venv\Scripts\python.exe -c "import os; print(bool(os.getenv('DEEPSEEK_API_KEY')))"
```
输出 `True` 即成功。

> 安全要求：不把 Key 发给任何人、不写进源码、不提交 GitHub。`.gitignore` 已排除 `.env`、`*.key`、`.venv/`、`*.log`、`data/state.json`。若怀疑泄露，立即去平台撤销并重新生成。DeepSeek 为付费服务，本项目全部开发与测试累计消耗约 0.2 元。

## 七、运行方法

**① 网页版（推荐演示）**

```cmd
cd /d C:\Users\Lenovo\Desktop\AI-Ecommerce-Customer-Service
.venv\Scripts\python.exe -m streamlit run app.py
```
浏览器打开 `http://localhost:8501`。侧边栏可切换顾客 A/B/C 验证会话隔离，查看决策轨迹、RAG 命中与实时库存。

**② 命令行版**：`.venv\Scripts\python.exe main.py`（输入「退出」结束、「清空」重置）

**③ API 连通性测试**：`.venv\Scripts\python.exe test_api.py`

**④ 标准评测**：`.venv\Scripts\python.exe tests\evaluate.py`（约 0.1 元，输出 `docs/评测报告.md`）

## 八、功能演示

| 输入 | 预期效果 | 调用的工具 |
|------|----------|-----------|
| 蓝牙耳机多少钱？ | 99 元 | `search_product` |
| 保温杯有货吗？ | 30 件（实时值） | `check_stock` |
| 什么时候发货？ | 1~2 个工作日（关键词未命中，语义兜底） | `search_faq` |
| 预算100元推荐什么？ | 蓝牙耳机、保温杯 | `recommend_product` |
| 你们有用防水面料的商品吗？ | 双肩背包防水面料（RAG 召回） | `search_knowledge` |
| 你们支持以旧换新吗？ | 检索无结果 → 明确拒答 | `search_knowledge`（失败） |
| 我要买1个蓝牙耳机，帮我下单 | 生成订单、库存 50→49 | `place_order` |
| 再问一次「还有货吗」 | 返回 49（强制重新查工具，不用旧值） | `check_stock` |
| 查一下订单 DD20261101001 | 商品/金额/状态 | `query_order` |
| 这个订单快递到哪了？ | 运输中、华东转运中心 | `query_logistics` |
| 订单 DD20261025003 退款进度？ | 平台审核中 | `query_refund` |
| 保温杯漏水，申请退货退款 | 生成售后单 SQ0001 | `apply_after_sale` |
| 帮我推进售后单 SQ0001 | 状态按状态机流转 | `advance_after_sale` |
| 给我转人工 | 转接受理与等待时间 | `transfer_to_human` |
| 苹果手机多少钱？ | 明确说明没有该商品，不编造价格 | `search_product`（失败） |

演示订单号（模拟数据）：`DD20261101001`、`DD20261028002`、`DD20261025003`。

## 九、测试结果

| 测试文件 | 覆盖内容 | 结果 |
|----------|----------|------|
| `tests/test_scenarios.py` | 价格/库存/FAQ/多轮/不编造（命令行版） | 5/5 |
| `tests/test_agent.py` | 工具意图识别与执行、转人工 | 6/6 |
| `tests/test_business.py` | 有状态业务本地逻辑 + Agent 集成 + RAG 拒答 | 38/38 |
| `tests/test_rag.py` | 切分/向量化/检索/阈值拒答/父文档扩展 | 16/16 |
| `tests/test_memory.py` | 用户隔离/长度控制/滚动摘要/失败降级 | 9/9 |
| `tests/test_app_ui.py` | 网页按钮即时渲染回归 | 2/2 |
| **合计** | | **76/76 通过** |
| `tests/evaluate.py` | 22 条标准问答集量化评测 | **22/22（综合通过率 100%）** |

评测报告（真实实测）：`docs/评测报告.md`。指标口径与局限已在报告中如实说明：样本量小、关键词比对法、模型输出有随机性，**不代表生产环境业务准确率**。

运行全部测试：
```cmd
.venv\Scripts\python.exe tests\test_scenarios.py
.venv\Scripts\python.exe tests\test_agent.py
.venv\Scripts\python.exe tests\test_business.py
.venv\Scripts\python.exe tests\test_rag.py
.venv\Scripts\python.exe tests\test_memory.py
.venv\Scripts\python.exe tests\test_app_ui.py
.venv\Scripts\python.exe tests\evaluate.py
```
（含 API 调用的测试合计约 0.1 元；纯本地测试不花钱）

**已验证的异常场景**：API Key 缺失提示、402 余额不足拦截、30 秒超时、工具参数错误/未知工具/失败均返回结构化错误、摘要 API 失败降级、库存不足拒绝下单、不存在订单/申请单拒答、Windows GBK 编码问题修复。

**评测驱动的真实修复记录**（`PROGRESS.md` 有完整记录）：评测首轮 19/22，暴露 3 个缺陷 → ① Prompt 区分「咨询规则」与「办理业务」 ② 强制价格/库存每次重新查工具（因下单会改库存） ③ FAQ 增加语义检索兜底 → 重测 22/22。

## 十、后续优化方向

1. **升级 RAG**：商品规模扩大后改用神经网络 Embedding + FAISS/Chroma 向量库，并用人工标注集做召回率评测
2. **持久化**：订单与会话写入 SQLite，支持多进程与重启恢复
3. **真实业务对接**：在获得合法授权前提下接入真实平台订单/物流 API
4. **工程化**：API 重试与降级、限流与成本核算、日志脱敏、Docker 部署
5. **评测**：扩大问答集、引入人工标注与语义相似度评分，替代关键词比对

## 十一、常见问题

- **HTTP 402 Insufficient Balance**：DeepSeek 账户余额不足，需到平台充值。
- **`No module named openai`**：Spyder 没切换到 `.venv` 解释器，见第五节。
- **UnicodeEncodeError (gbk)**：代码已统一 `sys.stdout.reconfigure(encoding='utf-8')`。
- **按钮点了要再点一次才显示**：已修复（按钮分支补 `st.rerun()`），有回归测试覆盖。
- **下单后数据想恢复**：网页侧边栏「重置演示数据」或 `business.reset_state()`。
