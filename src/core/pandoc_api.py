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

    def convert(self, input_path, output_path, input_format=None, output_format=None, extra_args=None):
        """
        Convert input_path to output_path.
        """
        if not self.executable:
            raise RuntimeError("Pandoc executable not found. Please install Pandoc and add it to PATH.")

        cmd = [self.executable, input_path, "-o", output_path]
        
        if input_format:
            cmd.extend(["-f", input_format])
        if output_format:
            cmd.extend(["-t", output_format])
        
        # A4 Paper Logic
        target_ext = os.path.splitext(output_path)[1].lower().replace('.', '')
        effective_format = output_format if output_format else target_ext

        if effective_format in ['docx', 'pdf']:
            cmd.extend(["-V", "geometry:a4paper"])
            cmd.extend(["-V", "papersize=a4"])
        
        if extra_args:
            cmd.extend(extra_args)

        try:
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr

    def html_to_markdown(self, html_content):
        """Convert HTML string to Markdown string using Pandoc."""
        return self._convert_string(html_content, "html", "markdown")

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
