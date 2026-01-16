# AI EPUB/DOCX 翻译工具

基于 AI 的文档翻译工具，旨在保留原文格式并提供连贯的上下文翻译。

## ✨ 核心特性

- **格式保留**：深度解析 EPUB 和 DOCX 结构。
- **表格保护**：在 Markdown 转换过程中自动保留 HTML 表格结构，防止复杂表格错乱。
- **上下文连贯**：智能记忆前文语境，确保翻译流畅。
- **断点续传**：自动缓存进度，支持随时中断与恢复。

## 🚀 快速开始

### 方式 1：下载运行 (推荐)
1. 从 [Releases](https://github.com/31naitnij/AI-EPUB-Translator/releases) 下载最新压缩包。
2. 解压并运行 `AI_EPUB_Translator.exe`。

### 方式 2：源码运行
1. 安装 Python 3.10+ 及 [Pandoc](https://pandoc.org/installing.html)。
2. 运行 `run.bat` (Windows) 或 `bash run.sh` (macOS/Linux)。

## 📖 使用指南

1. **配置路径**：选择待翻译文件及输出目录。
2. **API 设置**：填写 API Key、Base URL 及模型名称（支持 OpenAI 格式接口）。
3. **预处理**：点击"仅分块处理"解析文档。
4. **开始翻译**：点击"全部翻译"或选中部分段落翻译。
5. **导出文件**：选择目标格式并点击"导出"。

## 🧩 处理流程详解

本工具采用简化后的统一 Pandoc 处理流程，不再依赖手动解压容器，确保了更高的稳定性和更简洁的代码逻辑：

### 统一处理路径 (EPUB/DOCX/MD/HTML/...)
1. **统一转换**：所有输入格式通过 Pandoc 转换为单一的 Markdown 文件。
2. **表格保护**：转换过程中自动禁用 Markdown 表格插件，强制将表格保留为原始 HTML 代码，防止 AI 破坏复杂表格结构。
3. **独立分块**：
    - **文本块**：按段落/标题智能切分。
    - **表格块**：所有的 `<table>` 块被识别为独立、原子化的分块，确保翻译时结构完整。
4. **上下文翻译**：AI 结合前文语境进行逐块翻译。
5. **统一导出**：翻译后的 Markdown 再次通过 Pandoc 转回目标格式（如 EPUB 或 DOCX）。对于 DOCX，会使用原文件作为样式参考 (`--reference-doc`) 以尽可能保留格式。

## 💡 注意事项

- **Pandoc 依赖**：格式转换功能需预装 Pandoc。
- **Token 建议**：推荐分块大小设为 `1000 - 2000` 字符，兼顾语境与稳定性。
- **缓存说明**：如修改分块大小或 Prompt，需点击"清除缓存"后重新处理。
- **批量翻译**：目前本软件仅支持**单文件、非并发**翻译。若有批量处理需求，推荐使用 [Ebook-Translator-Calibre-Plugin](https://github.com/bookfere/Ebook-Translator-Calibre-Plugin)。
