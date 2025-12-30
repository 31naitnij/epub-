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

    def convert(self, input_path, output_path, output_format=None, extra_args=None):
        """
        Convert input_path to output_path.
        If output_format is 'pdf' or 'docx', force A4 paper size.
        """
        if not self.executable:
            raise RuntimeError("Pandoc executable not found. Please install Pandoc and add it to PATH.")

        cmd = [self.executable, input_path, "-o", output_path]
        
        # Determine format from extension if not provided, or explicit override
        if output_format:
            cmd.extend(["-t", output_format])
        
        # A4 Paper Logic
        # Determine actual target format string (either from arg or extension)
        target_ext = os.path.splitext(output_path)[1].lower().replace('.', '')
        effective_format = output_format if output_format else target_ext

        if effective_format in ['docx', 'pdf']:
            # Apply A4 geometry/papersize
            # For PDF (via latex/wkhtmltopdf), usually -V geometry:a4paper or -V papersize=a4 work
            # For DOCX, we cannot easily set page size via simple args without a reference doc,
            # but we can try to pass standard metadata or default to what Pandoc offers.
            # Pandoc's default for PDF via LaTeX is usually A4 or Letter depending on locale.
            # We explicitly set it.
            cmd.extend(["-V", "geometry:a4paper"])
            cmd.extend(["-V", "papersize=a4"])
        
        if extra_args:
            cmd.extend(extra_args)

        try:
            # Run pandoc
            # Capture output for debugging
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return True, result.stdout
        except subprocess.CalledProcessError as e:
            return False, e.stderr
