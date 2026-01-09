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
        Improved chunking: Split by paragraph/block boundaries (Markdown \n\n or HTML closing tags).
        Ensures that paragraphs are NEVER split, even if they exceed max_chars.
        """
        import re
        # Detailed boundaries: HTML block closures, Markdown double newlines, list items
        # Used lookbehind to include the delimiter in the segment
        pattern = r'(?<=</p>)|(?<=</div>)|(?<=</li>)|(?<=</h[1-6]>)|(?<=\n\n)|(?<=\r\n\r\n)'
        
        # 1. Identify all boundary positions and split into atomic segments
        segments = []
        last_pos = 0
        for m in re.finditer(pattern, text):
            segments.append(text[last_pos:m.end()])
            last_pos = m.end()
        if last_pos < len(text):
            segments.append(text[last_pos:])

        # 2. Greedy aggregation that respects atomicity
        chunks = []
        current_chunk = ""
        for seg in segments:
            if not current_chunk:
                current_chunk = seg
                continue
            
            if len(current_chunk) + len(seg) <= max_chars:
                current_chunk += seg
            else:
                chunks.append(current_chunk)
                current_chunk = seg
                
        if current_chunk:
            chunks.append(current_chunk)
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

    def process_native_init(self, input_path, max_chars, is_direct=True, only_load=False):
        """
        Combined logic for EPUB/DOCX Native Mode (Direct BeautifulSoup translation).
        """
        return self._init_container_processing(input_path, max_chars, is_direct=is_direct, source_type="native", only_load=only_load)

    def process_pandoc_init(self, input_path, max_chars, only_load=False):
        """
        Generic Pandoc path. For containers (EPUB/DOCX), we now use per-file processing to preserve structure.
        For other formats, we use the merged path.
        """
        ext = os.path.splitext(input_path)[1].lower()
        if ext in ['.epub', '.docx']:
             return self._init_container_processing(input_path, max_chars, is_direct=False, source_type="pandoc_per_file", only_load=only_load)
        
        # Original merged path for non-containers
        cache_file = self.get_cache_filename(input_path)
        cached_data = self.load_cache(cache_file)
        if cached_data and cached_data.get("source_type") == "pandoc_generic":
             return cached_data

        if only_load:
            return None

        # 1. Convert to MD
        temp_md = os.path.join(self.cache_dir, "temp_source.md")
        success, msg = self.pandoc.convert(input_path, temp_md, output_format="markdown")
        if not success:
            raise RuntimeError(f"Pandoc conversion failed: {msg}")

        with open(temp_md, 'r', encoding='utf-8') as f:
            full_md = f.read()

        # 2. Chunk
        chunks = self.chunk_text(full_md, max_chars)
        
        # 3. Structure
        cached_data = {
            "source_type": "pandoc_generic",
            "input_path": input_path,
            "input_ext": ext,
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

    def _init_container_processing(self, input_path, max_chars, is_direct=True, source_type="native", only_load=False):
        ext = os.path.splitext(input_path)[1].lower()
        cache_file = self.get_cache_filename(input_path)
        working_dir = self.get_working_dir(input_path)
        
        cached_data = self.load_cache(cache_file)
        
        # If it's the old merged format, we DON'T overwrite it here, allowing user to still export via Pandoc conversion.
        # But if user clicks 'Start' on a new container, they likely want the new per-file behavior.
        # To balance safety and utility: only reload if it's already a per-file format or if strictly loading.
        if cached_data:
            if cached_data.get("source_type") in ["native", "pandoc_per_file"]:
                # If folder is missing, re-extract but keep translation data
                if not os.path.exists(working_dir):
                    if ext == '.epub':
                        self.epub_converter.unzip_epub(input_path, working_dir)
                    elif ext == '.docx':
                        self.docx_converter.unzip_docx(input_path, working_dir)
                
                # Migrate old cache (add missing fields)
                needs_save = False
                if "input_ext" not in cached_data:
                    cached_data["input_ext"] = ext
                    needs_save = True
                if "working_dir" not in cached_data:
                    cached_data["working_dir"] = working_dir
                    needs_save = True
                
                if needs_save:
                    self.save_cache(cache_file, cached_data)
                return cached_data
            
            if only_load:
                return cached_data

        if only_load:
            return None

        # Ensure working dir exists and content is extracted
        if ext == '.epub':
            self.epub_converter.unzip_epub(input_path, working_dir)
        elif ext == '.docx':
            self.docx_converter.unzip_docx(input_path, working_dir)

        cached_data = {
            "source_type": source_type,
            "is_direct": is_direct,
            "input_path": input_path,
            "input_ext": ext,
            "working_dir": working_dir,
            "current_flat_idx": 0,
            "files": [],
            "finished": False
        }

        if ext == '.epub':
            files = self.epub_converter.find_content_files(working_dir)
            for f_rel in files:
                if self.epub_converter.should_skip_file(f_rel):
                    continue
                f_abs = os.path.join(working_dir, f_rel)
                with open(f_abs, 'r', encoding='utf-8') as f_obj:
                    html_content = f_obj.read()
                
                if is_direct:
                    soup = BeautifulSoup(html_content, 'lxml')
                    body = soup.find('body')
                    content_to_chunk = "".join([str(x) for x in body.contents]) if body else html_content
                else:
                    content_to_chunk = self.epub_converter.html_to_markdown(html_content)

                chunks = self.chunk_text(content_to_chunk, max_chars)
                cached_data["files"].append({
                    "rel_path": f_rel,
                    "chunks": [{"orig": c, "trans": ""} for c in chunks],
                    "finished": False
                })

        elif ext == '.docx':
            # Intermediate HTML for translation
            intermediate_html = os.path.join(self.cache_dir, f"{os.path.basename(input_path)}_intermediate.html")
            success, msg = self.docx_converter.convert_docx_to_html(input_path, intermediate_html)
            if not success:
                raise RuntimeError(f"DOCX to HTML conversion failed: {msg}")

            with open(intermediate_html, 'r', encoding='utf-8') as f:
                html_content = f.read()

            soup = BeautifulSoup(html_content, 'lxml')
            body = soup.find('body')
            content_to_chunk = "".join([str(x) for x in body.contents]) if body else html_content

            chunks = self.chunk_text(content_to_chunk, max_chars)
            cached_data["files"].append({
                "rel_path": "document_content.html",
                "chunks": [{"orig": c, "trans": ""} for c in chunks],
                "finished": False
            })

        self.save_cache(cache_file, cached_data)
        return cached_data

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
        Finalize translation by either re-packing to the same format or converting via Pandoc.
        Ensures structure preservation if output_format == input_ext.
        """
        cache_file = self.get_cache_filename(input_path)
        cache_data = self.load_cache(cache_file)
        if not cache_data:
            raise RuntimeError("No cache found for finalization.")

        input_ext = cache_data.get("input_ext", os.path.splitext(input_path)[1]).lower()
        working_dir = cache_data.get("working_dir", self.get_working_dir(input_path))
        source_type = cache_data.get("source_type", "native")

        # Gather translated content
        translated_files = []
        for f_data in cache_data["files"]:
            full_content = "".join([c["trans"] for c in f_data["chunks"]])
            translated_files.append({
                "rel_path": f_data["rel_path"],
                "content": full_content
            })

        # Logic for Structure Preservation (Input Format == Output Format)
        if target_format.lower() == input_ext.replace('.', ''):
            if input_ext == '.epub':
                if not working_dir or not os.path.exists(working_dir):
                    self.epub_converter.unzip_epub(input_path, working_dir)
                
                is_direct = cache_data.get("is_direct", True)
                replaced_count = 0
                for tf in translated_files:
                    if tf["rel_path"] == "merged_document.md":
                         continue
                         
                    target_file_path = os.path.join(working_dir, tf["rel_path"])
                    if os.path.exists(target_file_path):
                         self.epub_converter.replace_html_content(target_file_path, tf["content"], is_html=is_direct)
                         replaced_count += 1

                if replaced_count > 0:
                    self.epub_converter.rezip_epub(working_dir, output_path)
                    return f"EPUB structure preserved ({replaced_count} files replaced) and exported: {output_path}"
                else:
                    return "No structural files found to replace in the original EPUB container. Falling back to Pandoc conversion."
            
            elif input_ext == '.docx':
                if not working_dir or not os.path.exists(working_dir):
                    self.docx_converter.unzip_docx(input_path, working_dir)
                
                # Check if we have the virtual content file
                doc_content = next((tf["content"] for tf in translated_files if tf["rel_path"] == "document_content.html"), None)
                if doc_content:
                    # DOCX Surgical replacement
                    temp_html = os.path.join(self.cache_dir, "temp_final.html")
                    with open(temp_html, 'w', encoding='utf-8') as f:
                        f.write(doc_content)
                    
                    temp_translated_docx = os.path.join(self.cache_dir, "temp_translated.docx")
                    self.docx_converter.convert_html_to_docx(temp_html, temp_translated_docx, reference_docx=input_path)
                    
                    # Replace document.xml
                    self.docx_converter.extract_xml_from_docx(temp_translated_docx, "word/document.xml", os.path.join(working_dir, "word", "document.xml"))
                    # Rezip
                    self.docx_converter.rezip_docx(working_dir, output_path)
                    return f"DOCX structure preserved and exported: {output_path}"
                else:
                    return "No structural content found to replace in the original DOCX container. Falling back to Pandoc conversion."

        # Fallback to Pandoc Conversion for all other cases
        # Merge all content to a single MD/HTML for Pandoc
        is_html = (source_type == "native" or cache_data.get("is_direct", True))
        merged_content = "\n\n".join([tf["content"] for tf in translated_files])
        
        temp_source = os.path.join(self.cache_dir, "temp_ready." + ("html" if is_html else "md"))
        with open(temp_source, 'w', encoding='utf-8') as f:
            f.write(merged_content)
        
        extra_args = []
        if target_format == "docx":
            extra_args = ["--reference-doc", input_path] if input_ext == ".docx" else []

        success, msg = self.pandoc.convert(temp_source, output_path, output_format=target_format, extra_args=extra_args)
        if not success:
            raise RuntimeError(f"Final conversion failed: {msg}")
        
        return f"Converted and exported to {target_format.upper()} (Merged): {output_path}"
