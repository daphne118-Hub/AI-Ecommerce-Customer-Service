# GitHub 发布指南（需用户确认后才执行上传）

> 上传代码属于公开操作，涉及账号登录与个人信息，必须由你本人决定并执行。
> 本文档只做准备说明，**AI 不会替你登录账号或推送代码**。

## 一、发布前风险提示

- 上传到公开仓库意味着代码、文档对项目所有人可见
- 一旦把 API Key 误传上去，即使之后删除，也可能已被爬取，必须立即撤销并重新生成
- 公开仓库可能被搜索引擎收录，避免放入个人信息（真实姓名、学号、手机号等）
- GitHub 免费版公开仓库无费用；私有仓库同样免费，但若只想自己保存可选私有

## 二、发布前安全检查清单（逐项确认）

1. 确认代码里没有 API Key：`config.py` 只有 `os.getenv("DEEPSEEK_API_KEY")`
2. 确认所有 `test_api.py`、日志、`_server.log` 不含密钥明文
3. 确认 `.gitignore` 包含 `.env`、`*.key`、`.venv/`、`*.log`、`__pycache__/`
4. 确认 `.venv/` 目录不会被上传（体积大且含环境信息）
5. 确认 README 已写明「模拟演示数据，非真实电商平台」
6. 确认文档中无真实姓名、手机号、学号等隐私信息

自动检查命令（在项目根目录的 CMD 中运行）：

```cmd
findstr /S /I /N /C:"sk-" *.py *.md *.json *.txt
```

若输出为空（或只有说明文字）才安全。`sk-` 是 DeepSeek API Key 的常见前缀；如出现任何真实密钥字符串，立即撤销该 Key 并重新生成，且不要提交。

## 三、上传步骤（本人执行）

```cmd
cd /d C:\Users\Lenovo\Desktop\AI-Ecommerce-Customer-Service
git init
git add .
git status
```

**执行 `git status` 后先检查文件列表**：确认没有 `.venv/`、没有 `.env`、没有日志文件，再继续：

```cmd
git commit -m "feat: 基于DeepSeek的AI电商智能客服Agent（知识库+工具调用+多轮对话+网页界面）"
```

然后在 GitHub 网页上新建仓库（New repository），仓库名：
`AI-Ecommerce-Customer-Service`，选择 Public 或 Private，**不要勾选「Add a README file」**（本地已有）。创建后按页面提示执行：

```cmd
git remote add origin https://github.com/你的用户名/AI-Ecommerce-Customer-Service.git
git branch -M main
git push -u origin main
```

## 四、仓库展示建议

- README.md 会自动显示在仓库首页（已写好）
- 在 GitHub 仓库页添加 3-5 张界面截图（截图前先在网页里清空聊天记录，避免显示任何个人信息）
- 在 About 里填写描述：`基于 DeepSeek 大模型的 AI 电商智能客服 Agent | Function Calling | 多轮对话 | Streamlit`
- 添加 topics：`ai-agent`、`deepseek`、`function-calling`、`python`、`streamlit`、`ecommerce`

## 五、如果已经误传了密钥

1. 立刻到 DeepSeek 平台撤销该 Key 并生成新 Key
2. 更新本机用户环境变量 `DEEPSEEK_API_KEY`，重启 Spyder
3. 单纯 `git rm` 或改文件不够，历史记录里仍有密钥，需要清理 git 历史或删除仓库重建
4. 检查 DeepSeek 账户账单是否有异常调用
