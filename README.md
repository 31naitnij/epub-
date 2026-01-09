# AI EPUB/DOCX 翻译工具

基于 AI 的文档翻译工具，旨在保留原文格式并提供连贯的上下文翻译。

## ✨ 核心特性

- **格式保留**：支持保留原有排版（EPUB, DOCX, Markdown）。
- **原生模式**：直接翻译 HTML/XML 源码，极致保留复杂样式（如表格、多级标题），但 Token 消耗较高。
- **上下文连贯**：智能记忆前文语境，确保翻译流畅。
- **断点续传**：自动缓存进度，支持随时中断与恢复。
- **多模式翻译**：提供"直接翻译"与"转换翻译"两种模式，平衡 Token 消耗与格式精度。

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

### EPUB 处理

| 模式 | 翻译流程 | 导出至 EPUB | 导出至其他格式 |
|------|---------|------------|---------------|
| **原生模式** | 解压 → 逐文件提取 `<body>` HTML → AI 翻译 HTML 标签 → 缓存 | 回填各 HTML 文件 → 重新打包 (保留原结构) | 合并 HTML → Pandoc 转换 |
| **转换模式** | 解压 → 逐文件转换为 Markdown → AI 翻译 Markdown → 缓存 | Markdown 转 HTML → 回填各文件 → 重新打包 | 合并 Markdown → Pandoc 转换 |

**关键点**：
- 两种模式都会先解压 EPUB，按文件分别处理，最后重新打包
- 缓存中保留原始文件相对路径 (`rel_path`)，确保导出时文件名一致
- 跳过封面、目录等非正文文件 (`titlepage`, `cover`, `nav`, `toc` 等)

---

### DOCX 处理

| 模式 | 翻译流程 | 导出至 DOCX | 导出至其他格式 |
|------|---------|------------|---------------|
| **原生模式** | 解压 → Pandoc 转 HTML → 提取 `<body>` → AI 翻译 HTML → 缓存 | HTML 转 DOCX (参考原样式) → 替换 `document.xml` → 重新打包 | 合并 HTML → Pandoc 转换 |
| **转换模式** | 解压 → Pandoc 转 Markdown → AI 翻译 Markdown → 缓存 | Markdown 转 DOCX (参考原样式) → 替换 `document.xml` → 重新打包 | 合并 Markdown → Pandoc 转换 |

**关键点**：
- DOCX 本质是 ZIP 包，包含 `word/document.xml` 等文件
- 使用 `--reference-doc` 参数保留原文样式
- 导出 DOCX 时，仅替换 `document.xml`，保留其他结构

---

### 其他格式

对于非容器格式（如 `.md`, `.html`, `.txt`），使用 Pandoc 转换为 Markdown 后统一处理。

## 💡 注意事项

- **Pandoc 依赖**：格式转换功能需预装 Pandoc。
- **Token 建议**：推荐分块大小设为 `1000 - 2000` 字符，兼顾语境与稳定性。
- **缓存说明**：如修改分块大小或 Prompt，需点击"清除缓存"后重新处理。
- **批量翻译**：目前本软件仅支持**单文件、非并发**翻译。若有批量处理需求，推荐使用 [Ebook-Translator-Calibre-Plugin](https://github.com/bookfere/Ebook-Translator-Calibre-Plugin)。
