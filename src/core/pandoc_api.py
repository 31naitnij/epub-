import shutil
import subprocess
import os

class PandocAPI:
    def __init__(self):
        self.executable = shutil.which("pandoc")

    def check_availability(self):
        """Check if pandoc is available in the system PATH."""
        return self.executable is not None

    def get_supported_input_formats(self):
        """Return a list of common supported input formats."""
        # This is a subset of what Pandoc supports, focused on common docs
        return [
            "docx", "epub", "odt", "pdf", "html", "md", "txt", "rtf"
        ]

    def get_supported_output_formats(self):
        """Return a list of supported output formats."""
        return [
            "docx", "epub", "pdf", "html", "md", "plain"
        ]

    def convert(self, input_path, output_path, input_format=None, output_format=None, extra_args=None, keep_tables_html=False):
        """
        Convert input_path to output_path.
        """
        if not self.executable:
            raise RuntimeError("Pandoc executable not found. Please install Pandoc and add it to PATH.")

        cmd = [self.executable, input_path, "-o", output_path]
        
        if input_format:
            cmd.extend(["-f", input_format])
        
        target_fmt = output_format
        if not target_fmt:
             target_fmt = os.path.splitext(output_path)[1].lower().replace('.', '')

        if target_fmt == "markdown" and keep_tables_html:
            target_fmt = "markdown-grid_tables-simple_tables-multiline_tables-pipe_tables"
        
        if target_fmt:
            cmd.extend(["-t", target_fmt])
        
        # A4 Paper Logic
        effective_format = target_fmt

        if "docx" in effective_format or "pdf" in effective_format:
            cmd.extend(["-V", "geometry:a4paper"])
            cmd.extend(["-V", "papersize=a4"])
        
        if extra_args:
            cmd.extend(extra_args)

        try:
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr

    def html_to_markdown(self, html_content, keep_tables_html=False):
        """Convert HTML string to Markdown string using Pandoc."""
        to_fmt = "markdown"
        if keep_tables_html:
            # Disable table extensions to force Pandoc to keep tables as raw HTML
            to_fmt = "markdown-grid_tables-simple_tables-multiline_tables-pipe_tables"
            
        result = self._convert_string(html_content, "html", to_fmt)
        
        # Patch: Fix Pandoc failing to parse shortcut syntax for classes starting with _, e.g. [text]{._Bold}
        # We convert {._Bold} -> {class="_Bold"} which Pandoc handles correctly.
        import re
        result = re.sub(r'\{\.(\_[\w-]+)\}', r'{class="\1"}', result)
        
        return result.strip()

    def markdown_to_html(self, md_content):
        """Convert Markdown string to HTML string using Pandoc."""
        return self._convert_string(md_content, "markdown", "html")

    def _convert_string(self, content, from_fmt, to_fmt):
        if not self.executable:
            return content # Fallback (not ideal)
        
        cmd = [self.executable, "-f", from_fmt, "-t", to_fmt]
        try:
            result = subprocess.run(cmd, input=content, capture_output=True, text=True, check=True, encoding='utf-8')
            return result.stdout
        except Exception:
            return content
