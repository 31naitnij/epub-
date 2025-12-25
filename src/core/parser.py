from bs4 import BeautifulSoup, NavigableString
import re

class HTMLParser:
    def __init__(self):
        self.id_counter = 0
    
    def parse_file(self, file_path):
        """Parse HTML file and extract text chunks with placeholders."""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'lxml')
        chunks = []
        
        # Find all text nodes
        for element in soup.find_all(string=True):
            if isinstance(element, NavigableString):
                text = str(element).strip()
                if text and element.parent.name not in ['script', 'style']:
                    self.id_counter += 1
                    placeholder_id = f"ID_{self.id_counter:05d}"
                    placeholder = f"[#{placeholder_id}#]"
                    
                    chunks.append({
                        'id': placeholder_id,
                        'text': text
                    })
                    
                    element.replace_with(placeholder)
        
        skeleton_html = str(soup)
        return skeleton_html, chunks
    
    def restore_file(self, skeleton_html, translations, file_path):
        """Restore translated text back into HTML."""
        restored = skeleton_html
        
        for chunk_id, translated_text in translations.items():
            placeholder = f"[#{chunk_id}#]"
            restored = restored.replace(placeholder, translated_text)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(restored)
