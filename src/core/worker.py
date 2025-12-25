import os
from PySide6.QtCore import QThread, Signal

from src.core.epub_manager import EpubManager
from src.core.parser import HTMLParser
from src.core.translator import Translator
from src.core.cache_manager import CacheManager

class TranslationWorker(QThread):
    progress_signal = Signal(int, int)  # current, total chars
    log_signal = Signal(str, str)  # source, target (stream)
    finished_signal = Signal(str)  # success message
    error_signal = Signal(str)

    def __init__(self, settings, paths):
        super().__init__()
        self.settings = settings
        self.paths = paths
        self.is_running = True

    def run(self):
        try:
            self._process()
        except Exception as e:
            self.error_signal.emit(str(e))

    def stop(self):
        self.is_running = False

    def _process(self):
        input_path = self.paths['input']
        output_dir = self.paths['output']
        cache_path = self.paths['cache']
        
        chunk_size = self.settings['chunk_size']
        
        # Init components
        epub_mgr = EpubManager(input_path)
        cache_mgr = CacheManager(cache_path)
        translator = Translator(
            self.settings['api_key'], 
            self.settings['endpoint'], 
            self.settings['model'], 
            self.settings['temperature'],
            self.settings['prompt']
        )
        parser = HTMLParser()

        # 1. Unzip
        self.log_signal.emit("System", "Unzipping EPUB...")
        epub_mgr.unzip()
        spine_files = epub_mgr.get_spine_files()
        self.log_signal.emit("System", f"Found {len(spine_files)} files to process.")

        current_chars = 0
        
        # 2. Iterate Files
        for file_path in spine_files:
            if not self.is_running: 
                break
            
            self.log_signal.emit("System", f"Processing {os.path.basename(file_path)}...")
            
            # Parse
            skeleton, chunks = parser.parse_file(file_path)
            
            # Translate Chunks
            file_translations = {}
            
            batch_chunks = []
            batch_length = 0
            
            for i, chunk in enumerate(chunks):
                if not self.is_running: 
                    break

                text = chunk['text']
                chunk_id = chunk['id']
                
                # Check Cache
                cached_text = cache_mgr.get_translation(text, self.settings['model'])
                if cached_text:
                    file_translations[chunk_id] = cached_text
                    current_chars += len(text)
                    self.progress_signal.emit(current_chars, 0)
                    self.log_signal.emit(text[:50]+"...", "[CACHED] " + cached_text[:50]+"...")
                    continue
                
                # Translate individually (no batching to ensure 1:1 mapping)
                self.log_signal.emit(text, "")
                
                translated_text = ""
                for fragment in translator.translate_block_stream(text):
                    if not self.is_running: 
                        break
                    translated_text += fragment
                    self.log_signal.emit("", fragment)
                
                if not self.is_running: 
                    break
                
                # Direct assignment - no line splitting needed
                file_translations[chunk_id] = translated_text.strip()
                cache_mgr.save_translation(text, translated_text.strip(), self.settings['model'])
                
                current_chars += len(text)
                self.progress_signal.emit(current_chars, 0)

            # Restore File
            if self.is_running:
                parser.restore_file(skeleton, file_translations, file_path)
        
        # 3. Pack
        if self.is_running:
            self.log_signal.emit("System", "Repacking EPUB...")
            base_name = os.path.splitext(os.path.basename(input_path))[0]
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            output_epub = os.path.join(output_dir, f"{base_name}_translated.epub")
            epub_mgr.pack(output_epub)
            
            epub_mgr.cleanup()
            cache_mgr.close()
            self.finished_signal.emit(f"Done! Saved to {output_epub}")
