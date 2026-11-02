# GitHub 发布指南（已发布）

> 本项目已于 2026-11-03 发布到公开仓库：
> **https://github.com/daphne118-Hub/AI-Ecommerce-Customer-Service**
>
> 实际分工：AI 完成环境准备、安全检查、本地提交与推送；**账号注册、登录与 OAuth 授权由账号本人完成**，AI 不接触密码或令牌。

## 一、发布前风险提示

- 上传到公开仓库意味着代码、文档对项目所有人可见
- 一旦把 API Key 误传上去，即使之后删除，也可能已被爬取，必须立即撤销并重新生成
- 公开仓库可能被搜索引擎收录，避免放入个人信息（真实姓名、学号、手机号等）
- GitHub 免费版公开仓库无费用；私有仓库同样免费，但若只想自己保存可选私有

## 二、发布前安全检查清单（逐项确认）

1. 确认代码里没有 API Key：`config.py` 只有 `os.getenv("DEEPSEEK_API_KEY")`
2. 确认所有 `test_api.py`、日志、`_server.log` 不含密钥明文
3. 确认 `.gitignore` 包含 `.env`、`*.key`、`.venv/`、`*.log`、`__pycache__/`、`data/state.json`
4. 确认 `.venv/` 目录不会被上传（体积大且含环境信息）
5. 确认 README 已写明「模拟演示数据，非真实电商平台」
6. 确认文档中无真实姓名、手机号、学号等隐私信息

自动检查命令（在项目根目录的 CMD 中运行）：

```cmd
findstr /S /I /N /C:"sk-" *.py *.md *.json *.txt
```

若输出为空（或只有说明文字）才安全。`sk-` 是 DeepSeek API Key 的常见前缀；如出现任何真实密钥字符串，立即撤销该 Key 并重新生成，且不要提交。

## 三、实际发布流程（已完成，供复现参考）

本机原本没有 Git，先通过国内镜像静默安装 Git for Windows 2.56，再执行：

```cmd
cd /d C:\Users\Lenovo\Desktop\AI-Ecommerce-Customer-Service
git init -b main
git add .
git status
```

`git status` 复核后确认 32 个文件中没有 `.venv/`、`.env`、`*.log`、`data/state.json`，再提交并关联远程：

```cmd
git config user.name "daphne118-Hub"
git config user.email "daphne118-Hub@users.noreply.github.com"
git commit -m "feat: 基于DeepSeek的AI电商智能客服Agent"
git remote add origin https://github.com/daphne118-Hub/AI-Ecommerce-Customer-Service.git
git push -u origin main
```

推送时 **Git Credential Manager 会弹出浏览器**，由账号本人在 GitHub 页面点 **Authorize** 完成授权（GitHub 已不支持密码推送）。仓库在网页端创建时选 Public，且**不要勾选「Add a README file」**等初始化选项（本地已有，勾了会冲突）。

发布后用 GitHub API 复查远端文件树，确认文件数与敏感文件均未遗漏。

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
