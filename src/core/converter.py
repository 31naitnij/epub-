import zipfile
import os
import shutil
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup
from markdownify import markdownify as md
import markdown
from src.core.pandoc_api import PandocAPI

class EPUBConverter:
    def __init__(self, pandoc=None):
        self.pandoc = pandoc or PandocAPI()

    def unzip_epub(self, epub_path, extract_to):
        if not os.path.exists(extract_to):
            os.makedirs(extract_to)
        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)

    def should_skip_file(self, rel_path):
        """Identify if a file should be skipped for translation (e.g., titlepage, cover)."""
        skip_keywords = ['titlepage', 'title_page', 'cover', 'copyright', 'nav', 'toc', 'jacket', 'container']
        filename = os.path.basename(rel_path).lower()
        for kw in skip_keywords:
            if kw in filename:
                return True
        return False

    def find_content_files(self, extract_to):
        # Scan for HTML/XHTML/XML files
        content_files = []
        for root, dirs, files in os.walk(extract_to):
            for file in files:
                if file.lower().endswith(('.html', '.xhtml', '.htm', '.xml')):
                    rel_path = os.path.relpath(os.path.join(root, file), extract_to)
                    content_files.append(rel_path)
        return content_files

    def html_to_markdown(self, html_content, keep_tables_html=True):
        # Clean HTML first (optional, but Pandoc handles most stuff well)
        soup = BeautifulSoup(html_content, 'lxml')
        for tag in soup(['head', 'style', 'script', 'meta', 'link']):
            tag.decompose()
        
        target = soup.find('body') or soup
        return self.pandoc.html_to_markdown(str(target), keep_tables_html=keep_tables_html).strip()

    def markdown_to_html_fragment(self, markdown_content):
        return self.pandoc.markdown_to_html(markdown_content)

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

    def replace_html_content(self, html_path, translated_content, is_html=False):
        with open(html_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f.read(), 'lxml')
        
        body = soup.find('body')
        if not body:
            # Fallback if no body
            new_html = translated_content if is_html else self.markdown_to_html_fragment(translated_content)
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(new_html)
            return

        # Replace body content
        if is_html:
            new_body_soup = BeautifulSoup(translated_content, 'lxml').find('body') or BeautifulSoup(translated_content, 'lxml')
        else:
            new_content_html = self.markdown_to_html_fragment(translated_content)
            new_body_soup = BeautifulSoup(new_content_html, 'lxml').find('body') or BeautifulSoup(new_content_html, 'lxml')
        
        body.clear()
        for item in new_body_soup.contents:
            body.append(item)
            
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(str(soup))

class DOCXConverter:
    def __init__(self, pandoc=None):
        self.pandoc = pandoc or PandocAPI()

    def unzip_docx(self, docx_path, extract_to):
        if not os.path.exists(extract_to):
            os.makedirs(extract_to)
        with zipfile.ZipFile(docx_path, 'r') as zip_ref:
            zip_ref.extractall(extract_to)

    def rezip_docx(self, source_dir, output_path):
        with zipfile.ZipFile(output_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, source_dir)
                    z.write(full_path, rel_path)

    def find_docx_content_files(self, extract_to):
        """Locate key XML files in a DOCX structure."""
        content_files = []
        word_dir = os.path.join(extract_to, 'word')
        if not os.path.exists(word_dir):
            return content_files
        
        # document.xml is mandatory
        doc_xml = os.path.join('word', 'document.xml')
        if os.path.exists(os.path.join(extract_to, doc_xml)):
            content_files.append(doc_xml)
            
        # Headers and Footers
        for f in os.listdir(word_dir):
            if f.startswith(('header', 'footer')) and f.endswith('.xml'):
                content_files.append(os.path.join('word', f))
        
        return content_files

    def convert_docx_to_html(self, docx_path, output_html_path):
        """Convert a whole DOCX to HTML via Pandoc (used as intermediate for translation)."""
        return self.pandoc.convert(docx_path, output_html_path, output_format="html")

    def convert_html_to_docx(self, html_path, output_docx_path, reference_docx=None):
        """Convert translated HTML back to DOCX, using original as reference for styles."""
        extra_args = []
        if reference_docx and os.path.exists(reference_docx):
            extra_args = ["--reference-doc", reference_docx]
        return self.pandoc.convert(html_path, output_docx_path, output_format="docx", extra_args=extra_args)

    def extract_xml_from_docx(self, docx_path, xml_rel_path, save_to_path):
        """Extract a specific XML (like document.xml) from a DOCX zip."""
        with zipfile.ZipFile(docx_path, 'r') as zf:
            if xml_rel_path in zf.namelist():
                with open(save_to_path, 'wb') as f:
                    f.write(zf.read(xml_rel_path))
                return True
        return False
