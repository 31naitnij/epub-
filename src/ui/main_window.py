from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QLineEdit, QPushButton, QTextEdit, 
                             QComboBox, QFileDialog, QSplitter, QProgressBar,
                             QMessageBox, QGroupBox, QSpinBox, QDoubleSpinBox,
                             QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QCheckBox)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QIcon
import os
import sys
import shutil

from src.core.config_manager import ConfigManager
from src.core.converter import EPUBConverter
from src.core.translator import Translator
from src.core.processor import Processor

class TranslationWorker(QThread):
    progress = Signal(int, int, str, str, bool) # current_idx, total, orig, trans, is_finished
    finished = Signal(bool)
    error = Signal(str)

    def __init__(self, processor, converter, translator, epub_path, max_chars, context_rounds=1, target_indices=None, mode="epub_native"):
        super().__init__()
        self.processor = processor
        self.converter = converter
        self.translator = translator
        self.epub_path = epub_path
        self.max_chars = max_chars
        self.context_rounds = context_rounds
        self.target_indices = target_indices
        self.mode = mode

    def run(self):
        try:
            # Unified process_run for all modes
            result = self.processor.process_run(
                self.epub_path,
                self.translator,
                context_rounds=self.context_rounds,
                callback=self.progress.emit,
                target_indices=self.target_indices
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
        self.cache_path_edit = QLineEdit(r"E:\Downloads\transcache")
        btn_browse_cache = QPushButton("选择文件夹")
        btn_browse_cache.clicked.connect(self.browse_cache)
        cache_layout.addWidget(QLabel("缓存目录:"))
        cache_layout.addWidget(self.cache_path_edit)
        cache_layout.addWidget(btn_browse_cache)
        path_layout.addLayout(cache_layout)

        output_layout = QHBoxLayout()
        self.output_path_edit = QLineEdit(r"E:\Downloads\transoutput")
        btn_browse_output = QPushButton("选择文件夹")
        btn_browse_output.clicked.connect(self.browse_output)
        output_layout.addWidget(QLabel("输出目录:"))
        output_layout.addWidget(self.output_path_edit)
        output_layout.addWidget(btn_browse_output)
        path_layout.addLayout(output_layout)
        
        # New Output Format Selector
        format_layout = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItems(["EPUB", "DOCX (A4)", "Markdown"])
        format_layout.addWidget(QLabel("输出格式:"))
        format_layout.addWidget(self.format_combo)
        
        self.direct_mode_check = QCheckBox("原生模式(不转换格式，代码分块翻译)")
        self.direct_mode_check.setToolTip("开启后，将不转换为Markdown，直接翻译内部文本代码。对EPUB支持HTML翻译，对DOCX支持高保真XML回填。")
        format_layout.addWidget(self.direct_mode_check)
        
        format_layout.addStretch()
        path_layout.addLayout(format_layout)
        
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
        self.context_rounds_spin = QSpinBox()
        self.context_rounds_spin.setRange(1, 5)
        self.context_rounds_spin.setValue(1)
        row1.addWidget(QLabel("上下文轮数:"))
        row1.addWidget(self.context_rounds_spin, 0)
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

        # --- 3. 中间对照区 (列表 + 左右分栏) ---
        mid_widget = QWidget()
        mid_layout = QVBoxLayout(mid_widget)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        
        # New Mid Splitter: Table (Left) vs Editors (Right)
        self.mid_splitter = QSplitter(Qt.Horizontal)
        
        # Left: Chunk Table
        table_widget = QWidget()
        table_layout = QVBoxLayout(table_widget)
        table_layout.setContentsMargins(0,0,0,0)
        
        self.chunk_table = QTableWidget()
        self.chunk_table.setColumnCount(3)
        self.chunk_table.setHorizontalHeaderLabels(["ID", "状态", "原文预览"])
        self.chunk_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.chunk_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.chunk_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.chunk_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.chunk_table.setSelectionMode(QAbstractItemView.ExtendedSelection) # Allow multiple
        self.chunk_table.verticalHeader().setVisible(False) # Hide default row numbers
        self.chunk_table.itemSelectionChanged.connect(self.on_table_selection_changed)
        
        table_layout.addWidget(self.chunk_table)
        
        # Save Button below table for quick access
        self.btn_save_edit = QPushButton("保存当前块修改")
        self.btn_save_edit.clicked.connect(self.save_manual_edit)
        table_layout.addWidget(self.btn_save_edit)
        
        self.mid_splitter.addWidget(table_widget)

        # Right: Editors
        self.editor_splitter = QSplitter(Qt.Horizontal)
        self.orig_text_edit = QTextEdit()
        self.orig_text_edit.setPlaceholderText("原文...")
        self.orig_text_edit.setReadOnly(True)
        self.trans_text_edit = QTextEdit()
        self.trans_text_edit.setPlaceholderText("译文...")
        self.editor_splitter.addWidget(self.orig_text_edit)
        self.editor_splitter.addWidget(self.trans_text_edit)
        
        self.mid_splitter.addWidget(self.editor_splitter)
        
        # Set stretch: Table 1 part, Editors 3 parts
        self.mid_splitter.setStretchFactor(0, 1)
        self.mid_splitter.setStretchFactor(1, 3)
        
        mid_layout.addWidget(self.mid_splitter)
        
        self.main_splitter.addWidget(mid_widget)

        # --- 4. 底部控制区 ---
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        ctrl_row = QHBoxLayout()
        self.progress_bar = QProgressBar()
        self.btn_prepare = QPushButton("仅分块处理")
        self.btn_translate_sel = QPushButton("翻译选中块")
        self.btn_start = QPushButton("全部翻译")
        self.btn_stop = QPushButton("停止")
        self.btn_clear_cache = QPushButton("清除缓存")
        self.btn_output = QPushButton("导出")
        
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
        file_path, _ = QFileDialog.getOpenFileName(self, "选择文件", "", "All Supported Files (*.epub *.docx *.pdf *.txt *.md *.odt);;All Files (*.*)")
        if file_path:
            self.epub_path_edit.setText(file_path)
            # Try auto-load cache if exists
            self.init_processor_and_chunks(autoload=True)

    def browse_cache(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择缓存目录")
        if dir_path:
            self.cache_path_edit.setText(dir_path)
            self.config_manager.set_value('cache_dir', dir_path)

    def browse_output(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_path_edit.setText(dir_path)
            self.config_manager.set_value('output_dir', dir_path)

    def load_settings_history(self):
        # Load Global Paths
        cache_dir = self.config_manager.get_value('cache_dir')
        if cache_dir and os.path.exists(cache_dir):
            self.cache_path_edit.setText(cache_dir)
            
        output_dir = self.config_manager.get_value('output_dir')
        if output_dir and os.path.exists(output_dir):
            self.output_path_edit.setText(output_dir)

        # Load API History
        history = self.config_manager.get_history()
        self.history_combo.clear()
        for h in history:
            self.history_combo.addItem(f"{h.get('model')} - {h.get('api_url')}", h)
        
        if history:
            self.set_settings(history[0])

    def set_settings(self, s):
        self.api_key_edit.setText(s.get('api_key', ''))
        self.api_url_edit.setText(s.get('api_url', ''))
        self.model_edit.setText(s.get('model', 'gpt-4o'))
        self.temp_spin.setValue(s.get('temp', 0.7))
        self.prompt_edit.setPlainText(s.get('prompt', ""))
        self.chunk_size_spin.setValue(s['chunk_size'])
        self.context_rounds_spin.setValue(s.get('context_rounds', 1))

    def get_current_settings(self):
        return {
            'api_key': self.api_key_edit.text().strip(),
            'api_url': self.api_url_edit.text().strip(),
            'model': self.model_edit.text().strip(),
            'temp': self.temp_spin.value(),
            'prompt': self.prompt_edit.toPlainText(),
            'chunk_size': self.chunk_size_spin.value(),
            'context_rounds': self.context_rounds_spin.value()
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

    def init_processor_and_chunks(self, autoload=False):
        file_path = self.epub_path_edit.text()
        if not file_path or not os.path.exists(file_path):
            if not autoload:
               QMessageBox.warning(self, "警告", "请先选择有效的文件")
            return False

        settings = self.get_current_settings()
        cache_dir = self.cache_path_edit.text()
        self.processor = Processor(cache_dir)
        
        # Decide mode
        ext = os.path.splitext(file_path)[1].lower()
        out_fmt = self.format_combo.currentText()
        
        # Logic: 
        # If output is EPUB or DOCX and Native Mode is checked (or specifically native-friendly) -> Native
        # But we simplified: use checkbox to decide if user wants "Direct/Native"
        is_native_requested = self.direct_mode_check.isChecked()
        self.current_mode = "native" if is_native_requested else "pandoc_generic"
        
        try:
            if not autoload:
                self.status_label.setText(f"正在执行分块解析 ({self.current_mode})...")
            
            if self.current_mode == "native":
                direct_val = self.direct_mode_check.isChecked()
                cache_data = self.processor.process_native_init(file_path, settings['chunk_size'], is_direct=direct_val, only_load=autoload)
            else:
                # Pandoc Mode (Generic Markdown process)
                if not autoload and not self.processor.pandoc.check_availability():
                   QMessageBox.critical(self, "错误", "未检测到 Pandoc，无法执行此格式转换。请安装 Pandoc。")
                   return False
                cache_data = self.processor.process_pandoc_init(file_path, settings['chunk_size'], only_load=autoload)
            
            if cache_data is None:
                if autoload: return False
                # Should have been handled by processor raising error or returning None if logic failed
                return False

            self.flat_chunks = []
            self.chunk_table.setRowCount(0)
            self.chunk_table.blockSignals(True)
            
            row = 0
            for f_i, f_data in enumerate(cache_data["files"]):
                for c_i, c_data in enumerate(f_data["chunks"]):
                    self.flat_chunks.append((f_i, c_i))
                    
                    self.chunk_table.insertRow(row)
                    # ID
                    self.chunk_table.setItem(row, 0, QTableWidgetItem(str(row + 1)))
                    # Status
                    status_str = "已翻译" if c_data["trans"] else "未翻译"
                    self.chunk_table.setItem(row, 1, QTableWidgetItem(status_str))
                    # Preview
                    preview = c_data["orig"][:50].replace("\n", " ") + "..."
                    self.chunk_table.setItem(row, 2, QTableWidgetItem(preview))
                    
                    row += 1
            
            self.chunk_table.blockSignals(False)
            self.current_cache_data = cache_data
            
            # Select first row if exists
            if row > 0:
                self.chunk_table.selectRow(0)
            
            if autoload:
                self.status_label.setText("已自动加载上次的翻译进度。")
                self.btn_translate_sel.setEnabled(True)
                self.btn_output.setEnabled(True)
                
            return True
        except Exception as e:
            if not autoload:
                QMessageBox.critical(self, "错误", f"分块处理失败: {e}\n(如果是 DOCX/PDF 转换，请确保已安装 Pandoc)")
            return False

    def on_table_selection_changed(self):
        selected_items = self.chunk_table.selectedItems()
        if not selected_items: return
        
        # Determine unique rows
        rows = sorted(list(set(item.row() for item in selected_items)))
        if not rows: return
        
        # Preview first selected row
        first_row = rows[0]
        self.load_chunk_into_editor(first_row)
        
        if len(rows) > 1:
            self.status_label.setText(f"已选择 {len(rows)} 个块待翻译")
            
    def load_chunk_into_editor(self, flat_idx):
        if not hasattr(self, 'flat_chunks') or not self.flat_chunks: return
        
        # Backup currently edited if logic allows? 
        # For simplicity, we only load. Saving must be manual or auto on navigation if implemented.
        # But here we stick to manual "Save" button to avoid overwriting issues on multi-select.
        
        ch_idx, ck_idx = self.flat_chunks[flat_idx]
        cache_data = self.current_cache_data
        
        if cache_data and ch_idx < len(cache_data["files"]):
            chunk = cache_data["files"][ch_idx]["chunks"][ck_idx]
            self.orig_text_edit.setPlainText(chunk["orig"])
            self.trans_text_edit.setPlainText(chunk["trans"])
            self.current_indices = (ch_idx, ck_idx)
            self.current_flat_idx_view = flat_idx # track which row is in editor
            self.status_label.setText(f"查看：ID {flat_idx + 1}")

    def translate_selected_chunk(self):
        # Translate ALL selected rows
        if not self.init_processor_and_chunks(): return # Ensure init (though mostly redundant if already loaded)
        
        # Get selected rows
        selected_items = self.chunk_table.selectedItems()
        rows = sorted(list(set(item.row() for item in selected_items)))
        
        if not rows:
            QMessageBox.warning(self, "提示", "请先在列表中选择要翻译的块")
            return

        settings = self.get_current_settings()
        translator = Translator(
            settings['api_key'], 
            settings['api_url'], 
            settings['model'], 
            settings['temp'], 
            settings['prompt']
        )
        
        file_path = self.epub_path_edit.text()
        
        self.btn_start.setEnabled(False)
        self.btn_translate_sel.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_output.setEnabled(False)
        self.btn_clear_cache.setEnabled(False)
        
        self.worker = TranslationWorker(
            self.processor, 
            self.converter, 
            translator, 
            file_path,
            settings['chunk_size'],
            context_rounds=settings['context_rounds'],
            target_indices=rows, # Pass list of flat indices
            mode=self.current_mode
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()
        self.status_label.setText(f"开始翻译选中的 {len(rows)} 个块...")

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

        file_path = self.epub_path_edit.text()
        self.btn_start.setEnabled(False)
        self.btn_translate_sel.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_output.setEnabled(False)
        self.btn_clear_cache.setEnabled(False)
        
        self.worker = TranslationWorker(
            self.processor, 
            self.converter, 
            translator, 
            file_path,
            settings['chunk_size'],
            context_rounds=settings['context_rounds'],
            mode=self.current_mode
            # No target_indices = Process ALL from Resume point
        )
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.error.connect(self.on_error)
        self.worker.start()
        self.status_label.setText("全部翻译执行中...")

    def stop_translation(self):
        if self.processor:
            self.processor.status = "stopped"
            self.status_label.setText("正在停止...")

    def on_progress(self, current_idx, total, orig, trans, is_finished):
        if not hasattr(self, 'chunk_table'): return
        
        # 1. Update In-Memory Cache (Critical for Review)
        if hasattr(self, 'flat_chunks') and hasattr(self, 'current_cache_data'):
            f_idx, c_idx = self.flat_chunks[current_idx]
            if self.current_cache_data:
                self.current_cache_data["files"][f_idx]["chunks"][c_idx]["trans"] = trans
        
        # 2. Update Table Status
        if current_idx < self.chunk_table.rowCount():
             status_item = self.chunk_table.item(current_idx, 1)
             if status_item:
                 status_item.setText("翻译中..." if not is_finished else "已翻译")
        
        # 3. Auto-follow: Select the row being translated
        # This triggers on_table_selection_changed -> load_chunk_into_editor
        # We block signals briefly if we don't want to double-trigger, but here we WANT the trigger
        # to update the editor view.
        # However, to avoid fighting with user selection if they are browsing elsewhere,
        # we might check if the editor is currently "tracking" or just force it.
        # Given user feedback "it stays on the first", they likely WANT it to follow.
        
        # Check if we need to switch view
        cur_row = self.chunk_table.currentRow()
        if cur_row != current_idx:
            self.chunk_table.selectRow(current_idx)
            # The signal will handle loading text into editor
        else:
            # If already selected, just update the text manually because signal might not fire
            # or if it's partial stream update
            self.orig_text_edit.setPlainText(orig)
            self.trans_text_edit.setPlainText(trans)
        
        if is_finished:
            self.status_label.setText(f"总进度: {current_idx+1}/{total} (本块已完成)")
        else:
            self.status_label.setText(f"总进度: {current_idx+1}/{total} (正在翻译...)")

    def save_manual_edit(self):
        if not self.processor or not hasattr(self, 'current_indices'):
            QMessageBox.warning(self, "警告", "没有正在编辑的块。")
            return
            
        file_path = self.epub_path_edit.text()
        cache_file = self.processor.get_cache_filename(file_path)
        cache_data = self.processor.load_cache(cache_file)
        
        if cache_data:
            ch_idx, chunk_idx = self.current_indices
            cache_data["files"][ch_idx]["chunks"][chunk_idx]["trans"] = self.trans_text_edit.toPlainText()
            self.processor.save_cache(cache_file, cache_data)
            self.status_label.setText(f"已保存逻辑区块 {ch_idx, chunk_idx} 的修改。")
        else:
            QMessageBox.warning(self, "警告", "未找到缓存文件。")

    def clear_cache(self):
        file_path = self.epub_path_edit.text()
        if not file_path:
            QMessageBox.warning(self, "警告", "请先选择文件")
            return
            
        cache_dir = self.cache_path_edit.text()
        proc = Processor(cache_dir)
        cache_file = proc.get_cache_filename(file_path)
        cache_path = os.path.join(cache_dir, cache_file)
        
        reply = QMessageBox.question(self, '确认清除', '确定要清除当前书籍的翻译缓存吗？这将导致翻译重新开始。',
                                   QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            if os.path.exists(cache_path):
                os.remove(cache_path)
                QMessageBox.information(self, "成功", "缓存已清除。")
                self.init_processor_and_chunks() # Refresh table
            else:
                QMessageBox.information(self, "提示", "未发现现有缓存。")

    def on_finished(self, complete):
        self.btn_start.setEnabled(True)
        self.btn_translate_sel.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_output.setEnabled(True)
        self.btn_clear_cache.setEnabled(True)
        
        # Refresh table statuses just in case
        if hasattr(self, 'processor'):
             # We could reload cache to verify, but simple UI update is enough usually
             pass
        
        if complete:
            self.save_manual_edit()
            if self.worker and hasattr(self.worker, 'target_indices') and self.worker.target_indices:
                self.status_label.setText(f"选中块翻译完成。")
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
        file_path = self.epub_path_edit.text()
        if not self.processor:
            QMessageBox.warning(self, "警告", "请先初始化并翻译文件。")
            return

        cache_file = self.processor.get_cache_filename(file_path)
        cache_data = self.processor.load_cache(cache_file)
        
        if not cache_data:
            QMessageBox.warning(self, "警告", "未找到翻译缓存。")
            return

        output_root = self.output_path_edit.text()
        if not os.path.exists(output_root):
            os.makedirs(output_root)
            
        out_fmt_str = self.format_combo.currentText()
        # Map UI string to format
        target_format = "docx"
        if "DOCX" in out_fmt_str: target_format = "docx"
        elif "EPUB" in out_fmt_str: target_format = "epub"
        elif "Markdown" in out_fmt_str: target_format = "md"

        base_name = os.path.splitext(os.path.basename(file_path))[0]
        output_path = os.path.join(output_root, f"translated_{base_name}.{target_format}")

        try:
            self.status_label.setText("正在导出...")
            msg = self.processor.finalize_translation(file_path, output_path, target_format)
            
            self.status_label.setText("导出成功")
            QMessageBox.information(self, "成功", f"导出完成！\n{msg}")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "错误", f"导出失败: {e}")
            self.status_label.setText("导出失败")
            

if __name__ == "__main__":
    app = sys.modules.get('PySide6.QtWidgets').QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
