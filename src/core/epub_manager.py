import os
import shutil
import zipfile
import tempfile
import xml.etree.ElementTree as ET

class EpubManager:
    def __init__(self, epub_path):
        self.epub_path = epub_path
        self.temp_dir = tempfile.mkdtemp(prefix="epub_trans_")
        self.opf_file = None
        self.content_dir = None
        self.spine_items = []

    def unzip(self):
        """Unzip EPUB to temp directory."""
        with zipfile.ZipFile(self.epub_path, 'r') as zip_ref:
            zip_ref.extractall(self.temp_dir)
        self._find_opf()
        self._parse_spine()

    def _find_opf(self):
        """Find the .opf file via container.xml"""
        container_path = os.path.join(self.temp_dir, 'META-INF', 'container.xml')
        try:
            tree = ET.parse(container_path)
            root = tree.getroot()
            ns = {'ns': 'urn:oasis:names:tc:opendocument:xmlns:container'}
            root_file = root.find('.//ns:rootfile', ns)
            if root_file is None:
                root_file = root.find('.//rootfile')
            
            if root_file is not None:
                self.opf_file = os.path.join(self.temp_dir, root_file.get('full-path'))
                self.content_dir = os.path.dirname(self.opf_file)
            else:
                raise Exception("Could not find content.opf in container.xml")
        except Exception as e:
            # Fallback search
            for root, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    if file.endswith('.opf'):
                        self.opf_file = os.path.join(root, file)
                        self.content_dir = root
                        break

    def _parse_spine(self):
        """Parse OPF to get file list in order."""
        if not self.opf_file:
            return

        tree = ET.parse(self.opf_file)
        root = tree.getroot()
        namespaces = {'opf': 'http://www.idpf.org/2007/opf'}
        
        manifest = {}
        for item in root.findall('.//opf:manifest/opf:item', namespaces):
            manifest[item.get('id')] = item.get('href')

        self.spine_items = []
        for itemref in root.findall('.//opf:spine/opf:itemref', namespaces):
            idref = itemref.get('idref')
            if idref in manifest:
                full_path = os.path.join(self.content_dir, manifest[idref])
                if full_path.endswith(('.html', '.xhtml', '.htm')):
                    self.spine_items.append(full_path)

    def get_spine_files(self):
        return self.spine_items

    def cleanup(self):
        shutil.rmtree(self.temp_dir)
        
    def pack(self, output_path):
        """
        Repack the directory into an EPUB.
        Must add mimetype first, uncompressed.
        """
        with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 1. Write mimetype (STORED, not compressed)
            mimetype_path = os.path.join(self.temp_dir, "mimetype")
            if os.path.exists(mimetype_path):
                zf.write(mimetype_path, "mimetype", compress_type=zipfile.ZIP_STORED)
            else:
                zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)

            # 2. Write everything else
            for root, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    if file == "mimetype":
                        continue
                    abs_path = os.path.join(root, file)
                    rel_path = os.path.relpath(abs_path, self.temp_dir)
                    zf.write(abs_path, rel_path)
