# AI EPUB/DOCX 翻译工具

基于 AI 的文档翻译工具，采用统一的 Pandoc 处理流，确保在翻译过程中完美保留文档结构与表格布局。

## ✨ 核心特性

- **全格式支持**：基于 Pandoc 引擎，支持 EPUB, DOCX, MD, HTML 等多种格式。
- **原子化表格保护**：自动识别 `<table>` 块并进行独立分块，防止 AI 损坏复杂表格结构。
- **上下文连贯**：支持多轮翻译历史回溯，确保专有名词及语境的一致性。
- **断点续传**：本地缓存翻译进度，支持随时中断并从当前位置恢复。

## 🚀 快速开始

### 方式 1：下载运行 (推荐)
1. 从 [Releases](https://github.com/31naitnij/AI-EPUB-Translator/releases) 下载最新压缩包。
2. 解压并运行 `AI_EPUB_Translator.exe`。

### 方式 2：源码运行
1. 安装 Python 3.10+ 及 [Pandoc](https://pandoc.org/installing.html)。
2. 执行 `run.bat` 或 `bash run.sh`。

## 🧩 统一处理流程

本工具舍弃了复杂的容器拆解逻辑，采用更稳健的 **“中转渲染”** 流程：
1. **统一转换**：输入文件通过 Pandoc 转为 Markdown（表格强制保留为原生 HTML 标签）。
2. **原子分块**：识别 HTML 表格并强制作为独立块，文本则按段落智能切分。
3. **AI 翻译**：结合上下文历史进行流式翻译。
4. **两步导出**：`MD -> HTML -> Target`。通过中间 HTML 渲染确保表格能正确回写为 Word/EPUB 原生组件。

## 💡 注意事项

- **环境要求**：必须预装 [Pandoc](https://pandoc.org/installing.html)。
- **Token 配置**：建议分块大小 `1000 - 2000` 字符。
- **清理缓存**：若修改 Prompt 或分块策略，请先点击“清除缓存”。
- **批量翻译**：暂仅支持单文件处理。
