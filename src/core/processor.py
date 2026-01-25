import os
import json
import shutil
from src.core.pandoc_api import PandocAPI
from src.core.converter import EPUBConverter, DOCXConverter
from bs4 import BeautifulSoup

class Processor:
    def __init__(self, cache_dir):
        self.cache_dir = cache_dir
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir)
        self.status = "idle" # idle, running, stopped
        self.pandoc = PandocAPI()
        self.epub_converter = EPUBConverter(self.pandoc)
        self.docx_converter = DOCXConverter(self.pandoc)

    def chunk_text(self, text, max_chars):
        """
        Atomic Chunking: 
        1. Protects <table>...</table> blocks (including nested ones) as atomic chunks.
        2. Splits remaining text by paragraph/block boundaries.
        """
        import re
        
        parts = []
        last_pos = 0
        
        # Use finditer to find all potential table starts
        # We search manually to handle nesting
        pos = 0
        while pos < len(text):
            # Find next table start
            match = re.search(r'<table.*?>', text[pos:], re.IGNORECASE | re.DOTALL)
            if not match:
                break
            
            start_idx = pos + match.start()
            
            # Found a start, now find the matching end
            # We count nesting levels
            level = 1
            search_pos = pos + match.end()
            end_idx = -1
            
            # Regex to find either a start or end tag
            tag_pattern = re.compile(r'<(/?table.*?)>', re.IGNORECASE | re.DOTALL)
            
            for m in tag_pattern.finditer(text, search_pos):
                tag_content = m.group(1).lower()
                if tag_content.startswith('table'):
                    level += 1
                elif tag_content.startswith('/table'):
                    level -= 1
                
                if level == 0:
                    end_idx = m.end()
                    break
            
            if end_idx != -1:
                # We found a complete outermost table
                if start_idx > last_pos:
                    parts.append({"type": "text", "content": text[last_pos:start_idx]})
                parts.append({"type": "table", "content": text[start_idx:end_idx]})
                last_pos = end_idx
                pos = end_idx
            else:
                # If no matching end found, treat as text and move on
                pos = search_pos

        if last_pos < len(text):
            parts.append({"type": "text", "content": text[last_pos:]})

        # Phase 2: Process text parts with standard paragraph chunking
        final_chunks = []
        boundary_pattern = r'(?<=</p>)|(?<=</div>)|(?<=</li>)|(?<=</h[1-6]>)|(?<=\n\n)|(?<=\r\n\r\n)'

        for part in parts:
            if part["type"] == "table":
                final_chunks.append(part["content"])
                continue
            
            sub_text = part["content"]
            segments = []
            cur_last_pos = 0
            for m in re.finditer(boundary_pattern, sub_text):
                segments.append(sub_text[cur_last_pos:m.end()])
                cur_last_pos = m.end()
            if cur_last_pos < len(sub_text):
                segments.append(sub_text[cur_last_pos:])

            current_chunk = ""
            for seg in segments:
                if not current_chunk:
                    current_chunk = seg
                elif len(current_chunk) + len(seg) <= max_chars:
                    current_chunk += seg
                else:
                    final_chunks.append(current_chunk)
                    current_chunk = seg
            if current_chunk:
                final_chunks.append(current_chunk)
                
        return final_chunks

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

    def process_native_init(self, input_path, max_chars, is_direct=True, only_load=False):
        """
        DEPRECATED: Native Mode is removed. Redirects to standard container processing.
        """
        return self._init_container_processing(input_path, max_chars, source_type="native", only_load=only_load)

    def process_pandoc_init(self, input_path, max_chars, only_load=False):
        """
        Unified Pandoc initialization for all formats.
        Converts input to Markdown (preserving tables) and chunks it.
        Extracts media to a local folder.
        """
        ext = os.path.splitext(input_path)[1].lower()
        cache_file = self.get_cache_filename(input_path)
        cached_data = self.load_cache(cache_file)
        
        if cached_data:
             # Basic migration for source_type if needed
             if cached_data.get("source_type") in ["pandoc_generic", "native", "pandoc_per_file", "pandoc_unified"]:
                 return cached_data

        if only_load:
            return None

        # 1. Setup working dir for media
        working_dir = self.get_working_dir(input_path)
        if not os.path.exists(working_dir):
            os.makedirs(working_dir)
        media_dir = os.path.join(working_dir, "media")
        
        # 2. Convert to Markdown with table preservation and media extraction
        temp_md = os.path.join(self.cache_dir, f"{os.path.basename(input_path)}_source.md")
        # clean_markdown=True by default now in PandocAPI
        success, msg = self.pandoc.convert(
            input_path, temp_md, 
            output_format="markdown", 
            keep_tables_html=True,
            extract_media=media_dir
        )
        if not success:
            raise RuntimeError(f"Pandoc conversion to Markdown failed: {msg}")

        with open(temp_md, 'r', encoding='utf-8') as f:
            full_md = f.read()

        # 3. Detect Cover Image
        cover_image = None
        if os.path.exists(media_dir):
            # Pandoc often extracts cover to media/cover.<ext> or media/image1.<ext>
            # We look for files containing 'cover' first
            for f in os.listdir(media_dir):
                if 'cover' in f.lower():
                    cover_image = os.path.join(media_dir, f)
                    break
            # Fallback for some epubs where cover is just the first image
            if not cover_image and os.listdir(media_dir):
                potential = os.path.join(media_dir, os.listdir(media_dir)[0])
                if os.path.getsize(potential) > 10000: # Simple heuristic for "is it a cover"
                    cover_image = potential

        # 4. Chunk (with atomic table protection)
        raw_chunks = self.chunk_text(full_md, max_chars)
        
        processed_chunks = []
        for c in raw_chunks:
            # If it's a table chunk (starts with <table), convert it to clean Markdown
            if c.strip().lower().startswith("<table"):
                # keep_tables_html=False to get Markdown table
                # clean_markdown=True is already default or handled in PandocAPI
                clean_c = self.pandoc.html_to_markdown(c, keep_tables_html=False, clean_markdown=True)
                processed_chunks.append(clean_c)
            else:
                processed_chunks.append(c)

        # 5. Structure
        cached_data = {
            "source_type": "pandoc_unified",
            "working_dir": working_dir, # Store working dir for media reference
            "input_path": input_path,
            "input_ext": ext,
            "cover_image": cover_image,
            "current_flat_idx": 0,
            "files": [
                {
                    "rel_path": "document.md",
                    "chunks": [{"orig": c, "trans": ""} for c in processed_chunks],
                    "finished": False
                }
            ],
            "finished": False
        }
        self.save_cache(cache_file, cached_data)
        return cached_data

    def _init_container_processing(self, input_path, max_chars, source_type="native", only_load=False):
        """
        DEPRECATED: Container-specific logic is removed for simplicity.
        Redirects to unified Pandoc initialization.
        """
        return self.process_pandoc_init(input_path, max_chars, only_load=only_load)

    def process_run(self, input_path, translator, context_rounds=1, callback=None, target_indices=None):
        """
        Unified run loop for all translation modes.
        """
        cache_file = self.get_cache_filename(input_path)
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
            loop_range = sorted(target_indices)
        else:
            start_idx = cached_data["current_flat_idx"]
            loop_range = range(start_idx, len(flat_list))

        self.status = "running"
        
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

    def finalize_translation(self, input_path, output_path, target_format):
        """
        Unified Finalization: Uses a two-step conversion (MD -> HTML -> Target) 
        to ensure embedded HTML tables in Markdown are correctly parsed and preserved.
        """
        cache_file = self.get_cache_filename(input_path)
        cache_data = self.load_cache(cache_file)
        if not cache_data:
            raise RuntimeError("No cache found for finalization.")

        input_ext = cache_data.get("input_ext", os.path.splitext(input_path)[1]).lower()

        # Gather translated content
        merged_translated_md = ""
        for f_data in cache_data["files"]:
            merged_translated_md += "".join([c["trans"] for c in f_data["chunks"]])

        # 1. MD -> Intermediate HTML (to normalize and parse embedded tags)
        temp_ready_md = os.path.join(self.cache_dir, "translated_final.md")
        with open(temp_ready_md, 'w', encoding='utf-8') as f:
            f.write(merged_translated_md)
        
        temp_html = os.path.join(self.cache_dir, "translated_final.html")
        success, msg = self.pandoc.convert(temp_ready_md, temp_html, output_format="html")
        if not success:
             raise RuntimeError(f"Intermediate conversion to HTML failed: {msg}")

        # 2. HTML -> Target Format
        extra_args = []
        if target_format.lower() == "docx" and input_ext == ".docx":
            # Use original as reference for styles if possible
            extra_args.append("--reference-doc")
            extra_args.append(input_path)
        
        if target_format.lower() == "epub":
            cover_img = cache_data.get("cover_image")
            if cover_img and os.path.exists(cover_img):
                extra_args.append("--epub-cover-image")
                extra_args.append(cover_img)

        # Ensure media is found (Pandoc searches relative to CWD or uses absolute paths in HTML)
        # Since we extracted to media_dir, we might need to tell Pandoc where it is or ensure paths in HTML are correct.
        # Actually, Pandoc extraction creates paths like 'media/image1.jpg' in the Markdown.
        # When converting HTML -> Target, if those folders exist in the CWD, it works.
        # We should set resources path.
        working_dir = cache_data.get("working_dir")
        if working_dir:
            extra_args.append("--resource-path")
            extra_args.append(working_dir)

        success, msg = self.pandoc.convert(temp_html, output_path, output_format=target_format, extra_args=extra_args)
        if not success:
             raise RuntimeError(f"Final conversion to {target_format.upper()} failed: {msg}")
        
        return f"Successfully exported to {target_format.upper()} via Pandoc (Two-step): {output_path}"
