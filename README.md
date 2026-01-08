# AI EPUB/DOCX 翻译工具

基于 AI 的文档翻译工具，旨在保留原文格式并提供连贯的上下文翻译。

## ✨ 核心特性

- **格式保留**：支持保留原有排版（EPUB, DOCX, Markdown）。
- **原生模式**：直接翻译 HTML/XML 源码，极致保留复杂样式（如表格、多级标题），但 Token 消耗较高。
- **上下文连贯**：智能记忆前文语境，确保翻译流畅。
- **断点续传**：自动缓存进度，支持随时中断与恢复。
- **多模式翻译**：提供“直接翻译”与“转换翻译”两种模式，平衡 Token 消耗与格式精度。

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
3. **预处理**：点击“仅分块处理”解析文档。
4. **开始翻译**：点击“全部翻译”或选中部分段落翻译。
5. **导出文件**：选择目标格式并点击“导出”。

## 🧩 运行原理

### 1. 原生模式 (Native Mode)
直接处理文档源码，不改变文件结构，最大限度保留原始样式。
- **EPUB**：解压 EPUB -> 提取内部 HTML -> AI 直接处理带标签的 HTML（保留原文 CSS 样式）-> 回填并重封。
- **DOCX**：转换 DOCX 为中间层 HTML -> AI 翻译 HTML -> 利用 Pandoc 并参考原文件样式（`--reference-doc`）重新生成 DOCX。

### 2. 转换模式 (Pandoc Mode)
利用 Pandoc 将文档转换为markdown格式，并进行翻译，最后转换回目标格式，保留一定程度的原文格式，会有区别。
- **流程**：原文件 (EPUB/DOCX) -> 转换为 Markdown -> 仅对文本/Markdown 标签翻译 -> 转换回目标格式。
- **优势**：节省 Token，减少复杂格式干扰。

## 💡 注意事项

- **Pandoc 依赖**：格式转换功能需预装 Pandoc。
- **Token 建议**：推荐分块大小设为 `1000 - 2000` 字符，兼顾语境与稳定性。
- **缓存说明**：如修改分块大小或 Prompt，需点击“清除缓存”后重新处理。
- **批量翻译**：目前本软件仅支持**单文件、非并发**翻译。若有批量处理需求，推荐使用 [Ebook-Translator-Calibre-Plugin](https://github.com/bookfere/Ebook-Translator-Calibre-Plugin)。
