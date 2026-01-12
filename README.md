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

本工具采用统一的高保真处理流程：

### EPUB 处理
- **流程**：解压 → 逐文件转换为 Markdown (保留 HTML 表格) → AI 翻译 → 缓存
- **导出**：将翻译后的 Markdown 转回 HTML 片段 → 回填至原 EPUB 容器 → 重新打包
- **特点**：完美保留 CSS 样式、图片及原有目录结构。

### DOCX 处理
- **流程**：解压 → Pandoc 转中间 HTML → 转 Markdown (保留 HTML 表格) → AI 翻译 → 缓存
- **导出**：翻译后的内容转回 DOCX → 替换原 ZIP 包中的 `word/document.xml` → 重新打包
- **特点**：通过参考原文档 (`--reference-doc`) 尽可能还原样式。

### 其他格式
对于非容器格式（如 `.md`, `.html`, `.txt`），使用 Pandoc 转换为 Markdown 后统一处理。

## 💡 注意事项

- **Pandoc 依赖**：格式转换功能需预装 Pandoc。
- **Token 建议**：推荐分块大小设为 `1000 - 2000` 字符，兼顾语境与稳定性。
- **缓存说明**：如修改分块大小或 Prompt，需点击"清除缓存"后重新处理。
- **批量翻译**：目前本软件仅支持**单文件、非并发**翻译。若有批量处理需求，推荐使用 [Ebook-Translator-Calibre-Plugin](https://github.com/bookfere/Ebook-Translator-Calibre-Plugin)。
