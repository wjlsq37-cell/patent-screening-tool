# PatentHub AI 专利分析操作台

这是一个本地运行的专利筛查工具。用户先用一句话描述检索方向，系统通过兼容 OpenAI 协议的模型生成关键词和检索式；用户再从 PatentHub 导出 xlsx，上传到本工具后完成字段映射、专利评分、AI 摘要、法律状态分类和 Excel 多 sheet 导出。

## 功能范围

- 本地 HTML 操作台，浏览器访问 `http://127.0.0.1:8000`
- AI 设置保存和连接测试，支持 OpenAI-compatible API
- 专利需求拆解：核心关键词、扩展关键词、同义词、排除词、推荐检索式、推荐字段、注意事项
- PatentHub xlsx 上传、sheet 读取、前 10 行预览、自动字段映射和手动修正
- PatentHub 自动检索下载：本机保存账号密码，使用系统 Edge 登录、搜索并下载 xlsx
- 根据相关度、法律状态、申请人、时间、数据完整度评分排序
- 对前 N 篇专利调用 AI 总结；未配置 API Key 时使用本地摘要占位，分析流程不会中断
- 按法律状态和重点申请人拆分输出 Excel sheet
- 本地历史记录，支持重新下载和删除
- 自动化遇到验证码、滑块或二次验证时暂停，等待用户手动完成后继续

## 安装方法

建议使用 Python 3.11 或更高版本。

Windows 用户可以直接双击：

```text
install_windows.bat
```

它会在项目目录内创建 `.venv` 并安装依赖。

也可以手动安装：

```powershell
cd E:\project\Patent_screening_tool\patenthub-ai-assistant
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

如果你使用的是系统 Python，也可以直接安装依赖：

```powershell
pip install -r backend\requirements.txt
```

## 启动方法

Windows 用户可以直接双击：

```text
start_windows.bat
```

脚本会自动打开浏览器访问：

```text
http://127.0.0.1:8000
```

也可以手动启动：

```powershell
cd E:\project\Patent_screening_tool\patenthub-ai-assistant
python run.py
```

然后在浏览器打开：

```text
http://127.0.0.1:8000
```

## 如何配置 AI

进入页面顶部的“AI 设置”：

1. Base URL 填兼容 OpenAI 协议的地址，例如 `https://api.openai.com`、DeepSeek、通义千问、硅基流动或本地模型服务地址。
2. API Key 填你的密钥。密钥只保存在本机 `backend/config/config.yaml`，不会写死在代码里。
3. 模型名称填写服务商提供的模型 ID。
4. 设置 `temperature` 和 `max_tokens`。
5. 点击“保存设置”，再点击“测试连接”。

后端默认按 `/v1/chat/completions` 调用。如果 Base URL 已经以 `/v1` 结尾，会自动拼接 `/chat/completions`。

## 如何从 PatentHub 自动检索下载

1. 在“需求拆解”中生成关键词和推荐检索式。
2. 进入“上传分析”页顶部的“自动检索下载”面板。
3. 保存 PatentHub 账号和密码。账号密码只保存在本机 `backend/config/config.yaml`。
4. 填写或自动填入检索式，设置“本次最多下载”，默认 100，最大 500。
5. 点击“开始自动检索”。
6. 系统会打开 Microsoft Edge。若出现验证码、滑块或二次验证，请在 Edge 中手动完成，再回到本页面点击“我已完成验证，继续”。
7. xlsx 下载完成后，系统会自动进入现有评分、AI 总结和 Excel 导出流程。

自动化只使用正常网页登录和网站导出功能，不绕过验证码、不破解登录、不绕过网站权限。如果页面结构变化导致系统无法安全限制下载数量，会停止自动下载并提示改用手动上传。

## 如何从 PatentHub 手动导出 xlsx

1. 在“需求拆解”中生成关键词和检索式。
2. 将推荐检索式复制到 PatentHub 检索。
3. 在 PatentHub 结果页导出 xlsx。
4. 回到本工具的“上传分析”页上传该 xlsx。

## 如何上传分析

1. 在“上传分析”中选择 xlsx，点击“上传并预览”。
2. 如果文件包含多个 sheet，选择需要分析的 sheet。
3. 检查字段映射。示例 PatentHub 字段如“标题”“公开(公告)号”“权利要求1”“中文摘要”会自动映射。
4. 设置“AI 总结前 N 篇”。N 越大，模型调用次数越多。
5. 可填写重点申请人，每行一个。
6. 点击“开始分析”。
7. 分析完成后下载 Excel。

## 输出 Excel 字段说明

每个专利结果 sheet 包含：

- 排名、综合评分、相关度评分、法律状态评分、申请人评分、时间评分
- 推荐等级、专利名称、申请号、公开号、申请人、发明人
- 申请日、公开日、授权日、专利类型、法律状态、剩余保护期估算
- IPC 分类号、命中关键词、AI 简述
- 解决的问题、实现方式、核心发明点、与用户需求的关系、可能规避方向、阅读建议
- 详情链接、人工备注

输出 sheet 至少包括：

- 全部专利汇总
- 高相关专利
- 有效_授权专利
- 审中_实质审查
- 失效_终止_届满
- 驳回_撤回
- 法律状态不明
- 重点申请人
- 检索关键词与分析说明

## 如何调整评分权重

修改：

```text
backend/config/config.yaml
```

默认公式：

```text
综合评分 = 相关度评分 * 0.50
         + 法律状态评分 * 0.20
         + 申请人评分 * 0.15
         + 时间评分 * 0.10
         + 数据完整度评分 * 0.05
```

对应配置：

```yaml
analysis:
  weights:
    relevance: 0.50
    legal_status: 0.20
    applicant: 0.15
    time: 0.10
    completeness: 0.05
```

## 如何修改字段映射

修改：

```text
backend/config/field_mapping.yaml
```

每个标准字段都有 `aliases`，可以增加 PatentHub 或其他数据库导出的字段别名。例如：

```yaml
专利名称:
  aliases: [专利名称, 标题, 中文标题, 发明名称]
```

## Prompt 管理

所有 AI 提示词集中在：

```text
backend/config/prompts.yaml
```

目前包含需求拆解、相关度判断、单篇专利总结、批量总结和错误修复提示词。

## PatentHub 自动化模块说明

自动化核心文件：

```text
backend/core/patenthub_automation.py
backend/core/patenthub_downloader.py
```

当前版本已实现基础 Playwright 自动化，默认使用系统 Microsoft Edge，不在便携包中内置 Chromium。如果目标电脑没有 Edge，请安装/启用 Edge，或改用手动上传流程。

## 本地数据位置

- 上传文件：`backend/data/uploads`
- 导出文件：`backend/data/outputs`
- AI 摘要缓存：`backend/data/cache/summary_cache.json`
- 历史记录：`backend/data/history.json`

## 打包发给其他电脑

当前项目提供两类打包方式。

### 免安装便携包

推荐给没有 Python 的电脑使用。打包机需要能联网，并已安装 Python；目标电脑不需要安装 Python。

双击：

```text
build_portable_windows.bat
```

或手动执行：

```powershell
cd E:\project\Patent_screening_tool\patenthub-ai-assistant
python scripts\build_package.py --mode portable
```

打包结果会生成在：

```text
dist/
```

文件名类似：

```text
PatentHub_AI_Assistant_portable_win_amd64_py运行时版本_YYYYMMDD_HHMMSS.zip
```

便携包内包含：

- Windows x64 便携 Python 运行环境
- 已安装好的后端依赖
- 项目代码和前端页面
- 一键启动脚本 `start_windows.bat`

便携包不内置 Chromium；自动检索功能默认调用目标电脑上的 Microsoft Edge。

别人拿到便携包后：

1. 解压。
2. 双击 `start_windows.bat`。
3. 浏览器打开 `http://127.0.0.1:8000`。
4. 在“AI 设置”里填写自己的 API Key。

### 源码包

如果目标电脑已经安装 Python，也可以生成更小的源码包：

```powershell
python scripts\build_package.py --mode source
```

同时生成便携包和源码包：

```powershell
python scripts\build_package.py --mode all
```

压缩包会自动排除：

- 本机 API Key 和 `backend/config/config.yaml`
- 上传过的 xlsx
- 导出的分析结果
- AI 摘要缓存
- 历史记录
- 服务日志
- `.venv` 虚拟环境

源码包使用方式：

1. 解压。
2. 双击 `install_windows.bat`。
3. 双击 `start_windows.bat`。
4. 在“AI 设置”里填写自己的 API Key。

## 上传 GitHub

仓库中应提交代码、配置模板和脚本，不要提交本地密钥和运行数据。项目已提供 `.gitignore`，会排除：

- `backend/config/config.yaml`
- `backend/data/uploads/*`
- `backend/data/outputs/*`
- `backend/data/cache/*`
- `backend/data/history.json`
- `backend/data/server.*.log`
- `.venv/`
- `dist/`

首次上传可以执行：

```powershell
cd E:\project\Patent_screening_tool\patenthub-ai-assistant
git init
git add .
git commit -m "Initial PatentHub AI assistant"
git branch -M main
git remote add origin https://github.com/你的用户名/你的仓库名.git
git push -u origin main
```

如果误把 `config.yaml` 加入暂存区，先执行：

```powershell
git rm --cached backend/config/config.yaml
```

再重新提交。
