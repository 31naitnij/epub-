import zipfile
import os
import shutil
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import markdown

class EPUBConverter:
    def __init__(self):
        pass

    def unzip_epub(self, epub_path, extract_to):
        if os.path.exists(extract_to):
            shutil.rmtree(extract_to)
        os.makedirs(extract_to)
        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)

    def should_skip_file(self, rel_path):
        """Identify if a file should be skipped for translation (e.g., titlepage, cover)."""
        skip_keywords = ['titlepage', 'title_page', 'cover', 'copyright', 'nav', 'toc', 'jacket']
        filename = os.path.basename(rel_path).lower()
        for kw in skip_keywords:
            if kw in filename:
                return True
        return False

    def find_content_files(self, extract_to):
        # Scan for HTML/XHTML files
        content_files = []
        for root, dirs, files in os.walk(extract_to):
            for file in files:
                if file.lower().endswith(('.html', '.xhtml', '.htm')):
                    rel_path = os.path.relpath(os.path.join(root, file), extract_to)
                    content_files.append(rel_path)
        return content_files

    def html_to_markdown(self, html_content):
        soup = BeautifulSoup(html_content, 'lxml')
        # Filter non-text tags
        for tag in soup(['head', 'style', 'script', 'meta', 'link']):
            tag.decompose()
        
        target = soup.find('body') or soup
        # Convert to markdown
        markdown_content = md(str(target), 
                              heading_style="ATX",
                              bullets="-",
                              strip=['script', 'style', 'title'])
        return markdown_content.strip()

    def markdown_to_html_fragment(self, markdown_content):
        return markdown.markdown(markdown_content)

    def export_markdowns(self, translated_chapters, output_dir):
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
        md_paths = []
        for i, ch in enumerate(translated_chapters):
            clean_name = "".join([c if c.isalnum() or c in "._- " else "_" for c in ch['file_name']])
            if not clean_name.endswith('.md'):
                clean_name += '.md'
            md_path = os.path.join(output_dir, f"{i:03d}_{clean_name}")
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(ch['translated_content'])
            md_paths.append(md_path)
        return md_paths

    def rezip_epub(self, source_dir, output_path):
        # Standard EPUB zipping: mimetype must be first and uncompressed
        with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            # 1. mimetype first, no compression
            mimetype_path = os.path.join(source_dir, 'mimetype')
            if os.path.exists(mimetype_path):
                z.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)
            
            # 2. the rest
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, source_dir)
                    if rel_path == 'mimetype':
                        continue
                    z.write(full_path, rel_path)

    def replace_html_content(self, html_path, translated_markdown):
        with open(html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'lxml')
        
        body = soup.find('body')
        if not body:
            # Fallback if no body
            new_html = self.markdown_to_html_fragment(translated_markdown)
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(new_html)
            return

        # Replace body content
        new_content_html = self.markdown_to_html_fragment(translated_markdown)
        new_body_soup = BeautifulSoup(new_content_html, 'lxml').find('body') or BeautifulSoup(new_content_html, 'lxml')
        
        body.clear()
        for item in new_body_soup.contents:
            body.append(item)
            
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(str(soup))
