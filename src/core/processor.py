import os
import json
import shutil

class Processor:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        self.status = "idle" # idle, running, stopped

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

    def get_cache_filename(self, epub_filename):
        base = os.path.basename(epub_filename)
        return f"{base}_cache.json"

    def get_working_dir(self, epub_filename):
        base = os.path.basename(epub_filename)
        return os.path.join(self.cache_dir, f"{base}_extracted")

    def process_epub(self, epub_path, converter, translator, max_chars, context_rounds=1, callback=None, single_idx=None):
        cache_file = self.get_cache_filename(epub_path)
        working_dir = self.get_working_dir(epub_path)
        
        cached_data = self.load_cache(cache_file)
        
        # Initialization
        if not cached_data:
            # Step 1: Unzip
            converter.unzip_epub(epub_path, working_dir)
            files = converter.find_content_files(working_dir)
            
            cached_data = {
                "epub_path": epub_path,
                "current_flat_idx": 0,
                "files": [],
                "finished": False
            }
            
            for f_rel in files:
                if converter.should_skip_file(f_rel):
                    print(f"跳过非正文文件: {f_rel}")
                    continue
                    
                f_abs = os.path.join(working_dir, f_rel)
                with open(f_abs, 'r', encoding='utf-8') as f_obj:
                    html_content = f_obj.read()
                
                md_content = converter.html_to_markdown(html_content)
                chunks = self.chunk_text(md_content, max_chars)
                
                cached_data["files"].append({
                    "rel_path": f_rel,
                    "chunks": [{"orig": c, "trans": ""} for c in chunks],
                    "finished": False
                })
            self.save_cache(cache_file, cached_data)

        # Build flat list for progress tracking and navigation
        flat_list = []
        for f_i, f_data in enumerate(cached_data["files"]):
            for c_i, c_data in enumerate(f_data["chunks"]):
                flat_list.append((f_i, c_i))

        # Main Loop
        self.status = "running"
        start_idx = cached_data["current_flat_idx"]
        
        history = []
        
        # Build initial history if resuming
        if start_idx > 0:
            hist_start = max(0, start_idx - context_rounds)
            for i in range(hist_start, start_idx):
                pf, pc = flat_list[i]
                h_chunk = cached_data["files"][pf]["chunks"][pc]
                history.append((h_chunk["orig"], h_chunk["trans"]))

        if single_idx is not None:
            loop_range = [single_idx]
            # If translating a single chunk, we should still try to get context for it
            history = []
            hist_start = max(0, single_idx - context_rounds)
            for i in range(hist_start, single_idx):
                pf, pc = flat_list[i]
                h_chunk = cached_data["files"][pf]["chunks"][pc]
                if h_chunk["trans"]: # Only add if it has been translated
                    history.append((h_chunk["orig"], h_chunk["trans"]))
        else:
            loop_range = range(start_idx, len(flat_list))

        for i in loop_range:
            if self.status != "running":
                cached_data["current_flat_idx"] = i
                self.save_cache(cache_file, cached_data)
                return False # Stopped

            f_idx, c_idx = flat_list[i]
            file_data = cached_data["files"][f_idx]
            chunk = file_data["chunks"][c_idx]
            
            # Translate with streaming
            full_translation = ""
            for partial in translator.translate_chunk(chunk["orig"], history):
                full_translation += partial
                if callback:
                    # Send special value to indicate partial update
                    callback(i, len(flat_list), chunk["orig"], full_translation, False)
            
            chunk["trans"] = full_translation
            
            # Update history
            history.append((chunk["orig"], full_translation))
            if len(history) > context_rounds:
                history.pop(0)
            
            # Final callback for this chunk (finished=True)
            if callback:
                callback(i, len(flat_list), chunk["orig"], full_translation, True)
            
            # Auto save
            cached_data["current_flat_idx"] = i + 1
            self.save_cache(cache_file, cached_data)

        cached_data["finished"] = True
        self.save_cache(cache_file, cached_data)
        self.status = "idle"
        return True
