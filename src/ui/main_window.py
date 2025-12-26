from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QTextEdit, 
                             QComboBox, QFileDialog, QSplitter, QProgressBar,
                             QMessageBox, QGroupBox, QSpinBox, QDoubleSpinBox)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon
import os
import sys

from src.core.config_manager import ConfigManager
from src.core.converter import EPUBConverter
from src.core.translator import Translator
from src.core.processor import Processor

class TranslationWorker(QThread):
    progress = Signal(int, int, str, str, bool) # current_idx, total, orig, trans, is_finished
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, processor, converter, translator, epub_path, max_chars, single_idx=None):
        super().__init__()
        self.processor = processor
        self.converter = converter
        self.translator = translator
        self.epub_path = epub_path
        self.max_chars = max_chars
        self.single_idx = single_idx

    def run(self):
        try:
            result = self.processor.process_epub(
                self.epub_path,
                self.converter,
                self.translator,
                self.max_chars,
                callback=self.progress.emit,
                single_idx=self.single_idx
            )
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI EPUB 翻译工具")
        self.resize(1100, 800)
        self.config_manager = ConfigManager()
        self.converter = EPUBConverter()
        
        self.init_ui()
        self.load_settings_history()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # 全局垂直分割器
        self.main_splitter = QSplitter(Qt.Vertical)
        
        # --- 1 & 2. 顶部设置区 (路径 + API) ---
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        # 路径选择区
        path_group = QGroupBox("文件与路径")
        path_layout = QVBoxLayout(path_group)
        
        epub_layout = QHBoxLayout()
        self.epub_path_edit = QLineEdit()
        self.epub_path_edit.setPlaceholderText("选择 EPUB 文件...")
        btn_browse_epub = QPushButton("选择文件")
        btn_browse_epub.clicked.connect(self.browse_epub)
        epub_layout.addWidget(QLabel("EPUB 文件:"))
        epub_layout.addWidget(self.epub_path_edit)
        epub_layout.addWidget(btn_browse_epub)
        path_layout.addLayout(epub_layout)

        cache_layout = QHBoxLayout()
        self.cache_path_edit = QLineEdit(os.path.join(os.getcwd(), "cache"))
        btn_browse_cache = QPushButton("选择文件夹")
        btn_browse_cache.clicked.connect(self.browse_cache)
        cache_layout.addWidget(QLabel("缓存目录:"))
        cache_layout.addWidget(self.cache_path_edit)
        cache_layout.addWidget(btn_browse_cache)
        path_layout.addLayout(cache_layout)

        output_layout = QHBoxLayout()
        self.output_path_edit = QLineEdit(os.path.join(os.getcwd(), "output"))
        btn_browse_output = QPushButton("选择文件夹")
        btn_browse_output.clicked.connect(self.browse_output)
        output_layout.addWidget(QLabel("输出目录:"))
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(btn_browse_output)
        path_layout.addLayout(output_layout)
        top_layout.addWidget(path_group)

        # API 配置区
        config_group = QGroupBox("API 配置")
        config_layout = QVBoxLayout(config_group)
        row1 = QHBoxLayout()
        self.history_combo = QComboBox()
        self.history_combo.currentIndexChanged.connect(self.on_history_selected)
        row1.addWidget(QLabel("历史:"))
        row1.addWidget(self.history_combo, 2)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("API Key")
        row1.addWidget(QLabel("Key:"))
        row1.addWidget(self.api_key_edit, 2)
        self.api_url_edit = QLineEdit("https://api.openai.com/v1")
        row1.addWidget(QLabel("URL:"))
        row1.addWidget(self.api_url_edit, 3)
        self.model_edit = QLineEdit("gpt-4o")
        row1.addWidget(QLabel("模型:"))
        row1.addWidget(self.model_edit, 1)
        self.temp_spin = QDoubleSpinBox()
        self.temp_spin.setRange(0, 2)
        self.temp_spin.setSingleStep(0.1)
        self.temp_spin.setValue(0.7)
        row1.addWidget(QLabel("温度:"))
        row1.addWidget(self.temp_spin, 0)
        self.chunk_size_spin = QSpinBox()
        self.chunk_size_spin.setRange(100, 10000)
        self.chunk_size_spin.setValue(1000)
        row1.addWidget(QLabel("分块:"))
        row1.addWidget(self.chunk_size_spin, 1)
        config_layout.addLayout(row1)

        prompt_layout = QHBoxLayout()
        default_prompt = "你是一位多语言翻译专家，将以下文本中所有英语内容翻译为中文，其他语言的内容（包括代码、专有名词、混合语言等）请保留原文，不得翻译。严格保持原文的格式，编号、标点符号、换行、空行，整体结构不变。仅输出翻译结果，不要添加任何解释、说明、问候或额外内容，也不要删减或改动原文结构。"
        self.prompt_edit = QTextEdit(default_prompt)
        self.prompt_edit.setMaximumHeight(60)
        prompt_layout.addWidget(QLabel("Prompt:"))
        prompt_layout.addWidget(self.prompt_edit)
        config_layout.addLayout(prompt_layout)
        top_layout.addWidget(config_group)
        
        self.main_splitter.addWidget(top_widget)

        # --- 3. 中间对照区 (导航 + 左右分栏) ---
        mid_widget = QWidget()
        mid_layout = QVBoxLayout(mid_widget)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        
        nav_layout = QHBoxLayout()
        self.chunk_spin = QSpinBox()
        self.chunk_spin.setRange(1, 1)
        self.chunk_spin.valueChanged.connect(self.on_chunk_spin_changed)
        nav_layout.addWidget(QLabel("全局区块编号:"))
        nav_layout.addWidget(self.chunk_spin)
        self.chunk_total_label = QLabel("/ 1")
        nav_layout.addWidget(self.chunk_total_label)
        self.btn_save_edit = QPushButton("保存修改")
        self.btn_save_edit.clicked.connect(self.save_manual_edit)
        nav_layout.addWidget(self.btn_save_edit)
        nav_layout.addStretch()
        mid_layout.addLayout(nav_layout)

        self.horizontal_splitter = QSplitter(Qt.Horizontal)
        self.orig_text_edit = QTextEdit()
        self.orig_text_edit.setPlaceholderText("原文...")
        self.orig_text_edit.setReadOnly(True)
        self.trans_text_edit = QTextEdit()
        self.trans_text_edit.setPlaceholderText("译文...")
        self.horizontal_splitter.addWidget(self.orig_text_edit)
        self.horizontal_splitter.addWidget(self.trans_text_edit)
        mid_layout.addWidget(self.horizontal_splitter)
        
        self.main_splitter.addWidget(mid_widget)

        # --- 4. 底部控制区 ---
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        ctrl_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.btn_prepare = QPushButton("仅分块处理")
        self.btn_translate_sel = QPushButton("翻译当前块")
        self.btn_start = QPushButton("全部翻译")
        self.btn_stop = QPushButton("停止")
        self.btn_clear_cache = QPushButton("清除缓存")
        self.btn_output = QPushButton("导出 EPUB")
        
        self.btn_prepare.clicked.connect(self.prepare_chunks_only)
        self.btn_translate_sel.clicked.connect(self.translate_selected_chunk)
        self.btn_start.clicked.connect(self.start_translation)
        self.btn_stop.clicked.connect(self.stop_translation)
        self.btn_clear_cache.clicked.connect(self.clear_cache)
        self.btn_output.clicked.connect(self.export_epub)
        
        self.btn_translate_sel.setEnabled(False)
        self.btn_stop.setEnabled(False)
        self.btn_output.setEnabled(False)

        ctrl_row.addWidget(self.progress_bar)
        ctrl_row.addWidget(self.btn_prepare)
        ctrl_row.addWidget(self.btn_translate_sel)
        ctrl_row.addWidget(self.btn_start)
        ctrl_row.addWidget(self.btn_stop)
        ctrl_row.addWidget(self.btn_clear_cache)
        ctrl_row.addWidget(self.btn_output)
        bottom_layout.addLayout(ctrl_row)

        self.status_label = QLabel("就绪")
        bottom_layout.addWidget(self.status_label)
        
        self.main_splitter.addWidget(bottom_widget)

        # 将主分割器添加到主布局
        main_layout.addWidget(self.main_splitter)
        
        # 设置初始比例 (Settings, Viewer, Controls)
        self.main_splitter.setStretchFactor(0, 0) # Top
        self.main_splitter.setStretchFactor(1, 1) # Viewer (Maximize)
        self.main_splitter.setStretchFactor(2, 0) # Bottom

        # Internal state
        self.worker = None
        self.processor = None
        self.current_cache_data = None

    def browse_epub(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 EPUB 文件", "", "EPUB Files (*.epub)")
        if file_path:
            self.epub_path_edit.setText(file_path)

    def browse_cache(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择缓存目录")
        if dir_path:
            self.cache_path_edit.setText(dir_path)

    def browse_output(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_path_edit.setText(dir_path)

    def load_settings_history(self):
        history = self.config_manager.get_history()
        self.history_combo.clear()
        for h in history:
            self.history_combo.addItem(f"{h.get('model')} - {h.get('api_url')}", h)
        
        if history:
            self.set_settings(history[0])

    def set_settings(self, s):
        self.api_key_edit.setText(s.get('api_key', ''))
        self.api_url_edit.setText(s.get('api_url', ''))
        self.model_edit.setText(s.get('model', ''))
        self.temp_spin.setValue(s.get('temp', 0.7))
        self.prompt_edit.setPlainText(s.get('prompt', ''))
        self.chunk_size_spin.setValue(s.get('chunk_size', 1000))

    def get_current_settings(self):
        return {
            'api_key': self.api_key_edit.text(),
            'api_url': self.api_url_edit.text(),
            'model': self.model_edit.text(),
            'temp': self.temp_spin.value(),
            'prompt': self.prompt_edit.toPlainText(),
            'chunk_size': self.chunk_size_spin.value()
        }

    def on_history_selected(self, index):
        if index >= 0:
            s = self.history_combo.itemData(index)
            self.set_settings(s)

    def prepare_chunks_only(self):
        result = self.init_processor_and_chunks()
        if result:
            self.status_label.setText("分块处理完成，可以开始浏览或选择性翻译。")
            self.btn_translate_sel.setEnabled(True)
            self.btn_output.setEnabled(True)

    def init_processor_and_chunks(self):
        epub_path = self.epub_path_edit.text()
        if not epub_path or not os.path.exists(epub_path):
            QMessageBox.warning(self, "警告", "请先选择有效的 EPUB 文件")
            return False

        settings = self.get_current_settings()
        cache_dir = self.cache_path_edit.text()
        self.processor = Processor(cache_dir)
        
        try:
            self.status_label.setText("正在执行分块解析...")
            cache_file = self.processor.get_cache_filename(epub_path)
            cache_data = self.processor.load_cache(cache_file)
            
            if not cache_data:
                working_dir = self.processor.get_working_dir(epub_path)
                self.converter.unzip_epub(epub_path, working_dir)
                files = self.converter.find_content_files(working_dir)
                cache_data = {
                    "epub_path": epub_path,
                    "current_flat_idx": 0,
                    "files": [],
                    "finished": False
                }
                for f_rel in files:
                    with open(os.path.join(working_dir, f_rel), 'r', encoding='utf-8') as f:
                        content = f.read()
                    md = self.converter.html_to_markdown(content)
                    chunks = self.processor.chunk_text(md, settings['chunk_size'])
                    cache_data["files"].append({
                        "rel_path": f_rel,
                        "chunks": [{"orig": c, "trans": ""} for c in chunks],
                        "finished": False
                    })
                self.processor.save_cache(cache_file, cache_data)
            
            self.flat_chunks = []
            for f_i, f_data in enumerate(cache_data["files"]):
                for c_i, _ in enumerate(f_data["chunks"]):
                    self.flat_chunks.append((f_i, c_i))
            
            total = len(self.flat_chunks)
            self.chunk_spin.blockSignals(True)
            self.chunk_spin.setRange(1, total)
            self.chunk_total_label.setText(f"/ {total}")
            self.chunk_spin.blockSignals(False)
            self.current_cache_data = cache_data
            self.on_chunk_spin_changed(self.chunk_spin.value())
            return True
        except Exception as e:
            QMessageBox.critical(self, "错误", f"分块处理失败: {e}")
            return False

    def translate_selected_chunk(self):
        if not self.init_processor_and_chunks(): return
        
        settings = self.get_current_settings()
        translator = Translator(
            settings['api_key'], 
            settings['api_url'], 
            settings['model'], 
            settings['temp'], 
            settings['prompt']
        )
        
        epub_path = self.epub_path_edit.text()
        current_idx = self.chunk_spin.value() - 1
        
        self.btn_start.setEnabled(False)
        self.btn_translate_sel.setEnabled(False)
        self.btn_stop.setEnabled(True)
        
        self.worker = TranslationWorker(
            self.processor, 
            self.converter, 
            translator, 
            epub_path,
            settings['chunk_size'],
            single_idx=current_idx
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()
        self.status_label.setText(f"正在翻译第 {current_idx+1} 块...")

    def start_translation(self):
        if not self.init_processor_and_chunks(): return

        settings = self.get_current_settings()
        if not settings['api_key']:
            QMessageBox.warning(self, "警告", "请填入 API Key")
            return

        # Save to history
        self.config_manager.save_config(settings)
        self.load_settings_history()

        translator = Translator(
            settings['api_key'], 
            settings['api_url'], 
            settings['model'], 
            settings['temp'], 
            settings['prompt']
        )

        epub_path = self.epub_path_edit.text()
        self.btn_start.setEnabled(False)
        self.btn_translate_sel.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_output.setEnabled(False)
        self.btn_clear_cache.setEnabled(False)
        
        self.worker = TranslationWorker(
            self.processor, 
            self.converter, 
            translator, 
            epub_path,
            settings['chunk_size']
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()
        self.status_label.setText("翻译执行中...")

    def stop_translation(self):
        if self.processor:
            self.processor.status = "stopped"
            self.status_label.setText("正在停止...")

    def on_chunk_spin_changed(self, value):
        if not hasattr(self, 'flat_chunks') or not self.flat_chunks:
            return
        
        ch_idx, ck_idx = self.flat_chunks[value - 1]
        epub_path = self.epub_path_edit.text()
        
        # Safe access to processor/cache
        cache_dir = self.cache_path_edit.text()
        temp_proc = self.processor or Processor(cache_dir)
        cache_file = temp_proc.get_cache_filename(epub_path)
        cache_data = temp_proc.load_cache(cache_file) or self.current_cache_data
        
        if cache_data and ch_idx < len(cache_data["files"]):
            chunk = cache_data["files"][ch_idx]["chunks"][ck_idx]
            self.orig_text_edit.setPlainText(chunk["orig"])
            self.trans_text_edit.setPlainText(chunk["trans"])
            self.current_indices = (ch_idx, ck_idx)
            self.status_label.setText(f"查看：文件 {ch_idx+1}, 块 {ck_idx+1}")

    def on_progress(self, current_idx, total, orig, trans, is_finished):
        self.chunk_spin.blockSignals(True)
        self.chunk_spin.setValue(current_idx + 1)
        self.chunk_spin.blockSignals(False)
        
        self.orig_text_edit.setPlainText(orig)
        self.trans_text_edit.setPlainText(trans)
        
        if is_finished:
            self.status_label.setText(f"总进度: {current_idx+1}/{total} (本块已完成)")
            # update backup cache ref
            if hasattr(self, 'flat_chunks'):
                f_idx, c_idx = self.flat_chunks[current_idx]
                self.current_indices = (f_idx, c_idx)
        else:
            self.status_label.setText(f"总进度: {current_idx+1}/{total} (正在翻译...)")

    def save_manual_edit(self):
        if not self.processor or not hasattr(self, 'current_indices'):
            QMessageBox.warning(self, "警告", "没有正在编辑的块。")
            return
            
        epub_path = self.epub_path_edit.text()
        cache_file = self.processor.get_cache_filename(epub_path)
        cache_data = self.processor.load_cache(cache_file)
        
        if cache_data:
            ch_idx, chunk_idx = self.current_indices
            cache_data["files"][ch_idx]["chunks"][chunk_idx]["trans"] = self.trans_text_edit.toPlainText()
            self.processor.save_cache(cache_file, cache_data)
            self.status_label.setText(f"已保存逻辑区块 {self.chunk_spin.value()} 的修改。")
        else:
            QMessageBox.warning(self, "警告", "未找到缓存文件。")

    def clear_cache(self):
        epub_path = self.epub_path_edit.text()
        if not epub_path:
            QMessageBox.warning(self, "警告", "请先选择 EPUB 文件")
            return
            
        cache_dir = self.cache_path_edit.text()
        proc = Processor(cache_dir)
        cache_file = proc.get_cache_filename(epub_path)
        cache_path = os.path.join(cache_dir, cache_file)
        
        reply = QMessageBox.question(self, '确认清除', '确定要清除当前书籍的翻译缓存吗？这将导致翻译重新开始。',
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            if os.path.exists(cache_path):
                os.remove(cache_path)
                QMessageBox.information(self, "成功", "缓存已清除。")
            else:
                QMessageBox.information(self, "提示", "未发现现有缓存。")

    def on_finished(self, complete):
        self.btn_start.setEnabled(True)
        self.btn_translate_sel.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_output.setEnabled(True)
        self.btn_clear_cache.setEnabled(True)
        
        if complete:
            self.save_manual_edit()
            # If it was a single chunk, we don't want to show "all finished"
            if self.worker and hasattr(self.worker, 'single_idx') and self.worker.single_idx is not None:
                self.status_label.setText(f"区块 {self.worker.single_idx+1} 翻译完成。")
            else:
                self.status_label.setText("全部翻译任务已完成！")
                QMessageBox.information(self, "完成", "翻译已结束。")
        else:
            self.status_label.setText("任务已中止。")

    def on_error(self, message):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        QMessageBox.critical(self, "错误", f"发生异常: {message}")

    def export_epub(self):
        epub_path = self.epub_path_edit.text()
        cache_file = self.processor.get_cache_filename(epub_path)
        cache_data = self.processor.load_cache(cache_file)
        
        if not cache_data:
            QMessageBox.warning(self, "警告", "未找到翻译缓存。")
            return

        output_root = self.output_path_edit.text()
        if not os.path.exists(output_root):
            os.makedirs(output_root)
            
        # Step 1: Export Markdowns to cache dir
        md_output_dir = os.path.join(self.cache_path_edit.text(), "markdown_output")
        if not os.path.exists(md_output_dir):
            os.makedirs(md_output_dir)
            
        try:
            translated_chapters = []
            for f_data in cache_data["files"]:
                full_content = "\n\n".join([c["trans"] for c in f_data["chunks"]])
                translated_chapters.append({
                    "file_name": f_data["rel_path"],
                    "translated_content": full_content
                })
            self.converter.export_markdowns(translated_chapters, md_output_dir)
            self.status_label.setText(f"Markdown 文件已导出。")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"导出 Markdown 失败: {e}")
            return

        # Step 2: Build EPUB via physical replacement
        output_name = f"translated_{os.path.basename(epub_path)}"
        output_path = os.path.join(output_root, output_name)
        working_dir = self.processor.get_working_dir(epub_path)
        
        try:
            self.status_label.setText("正在执行物理回填...")
            for f_data in translated_chapters:
                target_path = os.path.join(working_dir, f_data["file_name"])
                self.converter.replace_html_content(target_path, f_data["translated_content"])
            
            self.status_label.setText("正在打包 EPUB...")
            self.converter.rezip_epub(working_dir, output_path)
            
            QMessageBox.information(self, "成功", f"文件已导出至:\n1. MD: {md_output_dir}\n2. EPUB: {output_path}")
            self.status_label.setText("导出成功")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"编译 EPUB 失败: {e}")

if __name__ == "__main__":
    app = sys.modules.get('PySide6.QtWidgets').QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
