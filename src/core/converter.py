import os
from src.core.pandoc_api import PandocAPI

class EPUBConverter:
    def __init__(self, pandoc=None):
        self.pandoc = pandoc or PandocAPI()

    def html_to_markdown(self, html_content, keep_tables_html=True):
        return self.pandoc.html_to_markdown(html_content, keep_tables_html=keep_tables_html).strip()

    def markdown_to_html_fragment(self, markdown_content):
        return self.pandoc.markdown_to_html(markdown_content)

class DOCXConverter:
    def __init__(self, pandoc=None):
        self.pandoc = pandoc or PandocAPI()

    def convert_docx_to_html(self, docx_path, output_html_path):
        """Convert a whole DOCX to HTML via Pandoc."""
        return self.pandoc.convert(docx_path, output_html_path, output_format="html")

    def convert_html_to_docx(self, html_path, output_docx_path, reference_docx=None):
        """Convert HTML back to DOCX, using original as reference for styles."""
        extra_args = []
        if reference_docx and os.path.exists(reference_docx):
            extra_args = ["--reference-doc", reference_docx]
        return self.pandoc.convert(html_path, output_docx_path, output_format="docx", extra_args=extra_args)
