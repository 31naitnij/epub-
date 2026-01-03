import os
import json
import shutil
from src.core.pandoc_api import PandocAPI
from bs4 import BeautifulSoup

class Processor:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        self.status = "idle" # idle, running, stopped
        self.pandoc = PandocAPI()

    def chunk_text(self, text, max_chars):
        chunks = []
        start = 0
        while start < len(text):
            end = start + max_chars
            if end >= len(text):
                chunks.append(text[start:])
                break
            
            last_newline = text.rfind('\n', start, end)
            if last_newline != -1 and last_newline > start:
                end = last_newline + 1
            
            chunks.append(text[start:end])
            start = end
        return chunks

    def save_cache(self, filename, data):
        path = os.path.join(self.cache_dir, filename)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    def load_cache(self, filename):
        path = os.path.join(self.cache_dir, filename)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None

    def get_cache_filename(self, input_filename):
        base = os.path.basename(input_filename)
        return f"{base}_cache.json"

    def get_working_dir(self, input_filename):
        base = os.path.basename(input_filename)
        return os.path.join(self.cache_dir, f"{base}_extracted")

    # --- Mode 1: Legacy EPUB (Strict structure preservation) ---
    def process_epub_init(self, epub_path, converter, max_chars, direct_translate=False, only_load=False):
        """
        Initialize cache for EPUB Native mode.
        """
        cache_file = self.get_cache_filename(epub_path)
        working_dir = self.get_working_dir(epub_path)
        
        cached_data = self.load_cache(cache_file)
        
        # Check if cache matches current mode
        is_direct = cached_data.get("is_direct_html", False) if cached_data else False
        if cached_data and cached_data.get("source_type") == "epub_native" and is_direct == direct_translate:
            return cached_data

        if only_load:
            return None

        # Step 1: Unzip
        converter.unzip_epub(epub_path, working_dir)
        files = converter.find_content_files(working_dir)
        
        cached_data = {
            "source_type": "epub_native",
            "is_direct_html": direct_translate,
            "input_path": epub_path,
            "current_flat_idx": 0,
            "files": [],
            "finished": False
        }
        
        for f_rel in files:
            if converter.should_skip_file(f_rel):
                continue
                
            f_abs = os.path.join(working_dir, f_rel)
            with open(f_abs, 'r', encoding='utf-8') as f_obj:
                html_content = f_obj.read()
            
            if direct_translate:
                # Direct HTML mode: Extract body content or use full content
                soup = BeautifulSoup(html_content, 'lxml')
                body = soup.find('body')
                if body:
                    # Get inner HTML of body
                    content_to_chunk = "".join([str(x) for x in body.contents])
                else:
                    content_to_chunk = html_content
            else:
                # Standard Mode: Convert to MD
                content_to_chunk = converter.html_to_markdown(html_content)

            chunks = self.chunk_text(content_to_chunk, max_chars)
            
            cached_data["files"].append({
                "rel_path": f_rel,
                "chunks": [{"orig": c, "trans": ""} for c in chunks],
                "finished": False
            })
        self.save_cache(cache_file, cached_data)
        return cached_data

    def process_epub_run(self, epub_path, translator, context_rounds=1, callback=None, target_indices=None):
        """
        Original logic for EPUB -> EPUB execution.
        """
        cache_file = self.get_cache_filename(epub_path)
        cached_data = self.load_cache(cache_file)
        
        if not cached_data:
            return False

        # Build flat list
        flat_list = []
        for f_i, f_data in enumerate(cached_data["files"]):
            for c_i, c_data in enumerate(f_data["chunks"]):
                flat_list.append((f_i, c_i))

        # Determine loop range
        if target_indices is not None:
            # Specific indices selected
            loop_range = sorted(target_indices)
        else:
            # Resume from last stop
            start_idx = cached_data["current_flat_idx"]
            loop_range = range(start_idx, len(flat_list))

        self.status = "running"
        history = []
        
        # Main Loop
        for i in loop_range:
            if self.status != "running":
                if target_indices is None:
                    cached_data["current_flat_idx"] = i 
                self.save_cache(cache_file, cached_data)
                return False 

            f_idx, c_idx = flat_list[i]
            file_data = cached_data["files"][f_idx]
            chunk = file_data["chunks"][c_idx]
            
            # Context builder
            history = []
            hist_start = max(0, i - context_rounds)
            for hi in range(hist_start, i):
                hf, hc = flat_list[hi]
                h_chunk = cached_data["files"][hf]["chunks"][hc]
                if h_chunk["trans"]:
                    history.append((h_chunk["orig"], h_chunk["trans"]))

            # Translate with streaming
            full_translation = ""
            for partial in translator.translate_chunk(chunk["orig"], history):
                full_translation += partial
                if callback:
                    callback(i, len(flat_list), chunk["orig"], full_translation, False)
            
            chunk["trans"] = full_translation
            
            if callback:
                callback(i, len(flat_list), chunk["orig"], full_translation, True)
            
            if target_indices is None:
                cached_data["current_flat_idx"] = i + 1
            self.save_cache(cache_file, cached_data)

        if target_indices is None:
            cached_data["finished"] = True
            self.save_cache(cache_file, cached_data)
        
        self.status = "idle"
        return True

    # --- Mode 2: Pandoc (Generic) ---
    def process_pandoc_init(self, input_path, max_chars, only_load=False):
        """
        Initialize the generic cache by converting Input -> MD via Pandoc.
        """
        cache_file = self.get_cache_filename(input_path)
        cached_data = self.load_cache(cache_file)
        
        if cached_data and cached_data.get("source_type") == "pandoc_generic":
             return cached_data

        if only_load:
            return None

        # New initialization
        # 1. Convert to MD
        temp_md = os.path.join(self.cache_dir, "temp_source.md")
        success, msg = self.pandoc.convert(input_path, temp_md, "markdown")
        if not success:
            raise RuntimeError(f"Pandoc conversion failed: {msg}")

        with open(temp_md, 'r', encoding='utf-8') as f:
            full_md = f.read()

        # 2. Chunk
        chunks = self.chunk_text(full_md, max_chars)
        
        # 3. Structure (Generic has 1 'file' essentially)
        cached_data = {
            "source_type": "pandoc_generic",
            "input_path": input_path,
            "current_flat_idx": 0,
            "files": [
                {
                    "rel_path": "merged_document.md",
                    "chunks": [{"orig": c, "trans": ""} for c in chunks],
                    "finished": False
                }
            ],
            "finished": False
        }
        self.save_cache(cache_file, cached_data)
        return cached_data

    def process_pandoc_run(self, input_path, translator, context_rounds=1, callback=None, target_indices=None):
        """
        Run translation loop for generic pandoc mode.
        """
        cache_file = self.get_cache_filename(input_path)
        cached_data = self.load_cache(cache_file)
        if not cached_data: 
            return False

        # Build flat list (trivial here, but consistent interface)
        flat_list = []
        for f_i, f_data in enumerate(cached_data["files"]):
            for c_i, c_data in enumerate(f_data["chunks"]):
                flat_list.append((f_i, c_i))

        if target_indices is not None:
             loop_range = sorted(target_indices)
        else:
            start_idx = cached_data["current_flat_idx"]
            loop_range = range(start_idx, len(flat_list))

        self.status = "running"
        
        for i in loop_range:
            if self.status != "running":
                if target_indices is None:
                    cached_data["current_flat_idx"] = i
                self.save_cache(cache_file, cached_data)
                return False

            f_idx, c_idx = flat_list[i]
            file_data = cached_data["files"][f_idx]
            chunk = file_data["chunks"][c_idx]

            # Context
            history = []
            hist_start = max(0, i - context_rounds)
            for hi in range(hist_start, i):
                hf, hc = flat_list[hi]
                h_chunk = cached_data["files"][hf]["chunks"][hc]
                if h_chunk["trans"]:
                    history.append((h_chunk["orig"], h_chunk["trans"]))

            # Translate
            full_translation = ""
            for partial in translator.translate_chunk(chunk["orig"], history):
                full_translation += partial
                if callback:
                    callback(i, len(flat_list), chunk["orig"], full_translation, False)
            
            chunk["trans"] = full_translation
            if callback:
                callback(i, len(flat_list), chunk["orig"], full_translation, True)
            
            if target_indices is None:
                cached_data["current_flat_idx"] = i + 1
            self.save_cache(cache_file, cached_data)

        if target_indices is None:
            cached_data["finished"] = True
            self.save_cache(cache_file, cached_data)
        
        self.status = "idle"
        return True
