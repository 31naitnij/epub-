import os
import re
import zipfile
import shutil
import tempfile
from bs4 import BeautifulSoup

class EPubAnchorProcessor:
    """
    针对 EPUB 的锚点文本提取提取与还原处理器。
    采用“提取 - 原地修改 - 重新打包”的极简策略，确保极致的结构保留。
    """
    
    def __init__(self, max_group_chars=2000):
        self.max_group_chars = max_group_chars
        self.temp_dir = None
        self.format_counter = 0
        
        # 稀有 Unicode 符号标记 (Mathematical White Brackets)
        self.GS = "⟬" # Group Start
        self.GE = "⟭" # Group End
        self.BS = "⟦" # Block Start
        self.BE = "⟧" # Block End
        self.AS = "⦗" # Anchor Start
        self.AE = "⦘" # Anchor End

    def extract_epub(self, epub_path):
        """将 EPUB 完整解压到临时目录"""
        self.temp_dir = tempfile.mkdtemp(prefix="epub_trans_")
        with zipfile.ZipFile(epub_path, 'r') as zip_ref:
            zip_ref.extractall(self.temp_dir)
        return self.temp_dir

    def get_xhtml_files(self):
        """遍历并返回所有 XHTML/HTML 文件路径"""
        xhtml_files = []
        for root, dirs, files in os.walk(self.temp_dir):
            for file in files:
                if file.lower().endswith(('.xhtml', '.html', '.htm')):
                    xhtml_files.append(os.path.join(root, file))
        return xhtml_files

    def extract_block_with_local_ids(self, element):
        """
        核心逻辑：提取块内文本，对格式标签使用独立编号的锚点。
        支持嵌套的格式标签，例如 [A [B]<2> C]<1>。
        """
        format_tags = []
        local_counter = [1] # 使用列表以便在闭包中修改
        
        # 定义需要标记为锚点的格式化标签
        target_tags = ['strong', 'em', 'b', 'i', 'u', 'span', 'code', 
                       'sup', 'sub', 'a', 'abbr', 'mark', 'small', 'cite', 'q']

        def recursive_extract(node):
            if isinstance(node, str):
                return node
            elif hasattr(node, 'name'):
                if node.name in target_tags:
                    # 递归处理子节点
                    child_parts = []
                    for child in node.children:
                        child_parts.append(recursive_extract(child))
                    inner_content = "".join(child_parts)
                    
                    if inner_content.strip():
                        tag_id = f"{self.AS}{local_counter[0]}{self.AE}"
                        local_counter[0] += 1
                        format_tags.append({
                            'id': tag_id,
                            'tag': node.name,
                            'attrs': dict(node.attrs),
                            'text': inner_content
                        })
                        return f"{self.BS}{inner_content}{self.BE}{tag_id}"
                    else:
                        # 对于空但带有样式的标签，或者只有空白的标签，原样保留
                        return str(node)
                elif node.name in ['br', 'hr', 'img']:
                    return str(node)
                else:
                    # 递归处理子节点（例如 DIV 里的文本）
                    child_parts = []
                    for child in node.children:
                        child_parts.append(recursive_extract(child))
                    return "".join(child_parts)
            return ""

        full_text = recursive_extract(element)
        # 清理多余空格但保留基本逻辑（可选，用户希望尽量原样）
        # full_text = re.sub(r'\s+', ' ', full_text).strip()
        
        return full_text, format_tags

    def create_blocks_from_soup(self, soup):
        """从 BeautifulSoup 对象中识别翻译块"""
        blocks = []
        # 定义常见的文本容器
        translatable_tags = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 
                             'li', 'td', 'th', 'caption', 'figcaption', 
                             'blockquote', 'dt', 'dd', 'cite']
        
        # 寻找所有可能的元素
        all_elements = soup.find_all(translatable_tags)
        
        # 过滤：如果一个元素的父级也是可翻译标签，我们仍然倾向于处理最细粒度的文本块
        # 但如果是 blockquote 包含 P，我们应该处理 P 而不是 blockquote 的整体
        # 策略：如果一个元素包含其他也在 translatable_tags 里的子元素，则跳过该元素（处理更细的）
        # 除非该元素包含的文本在子元素之外也有显著内容。
        
        for element in all_elements:
            # 检查是否有子元素也是可翻译标签
            has_translatable_child = any(child.name in translatable_tags for child in element.find_all(translatable_tags, recursive=False))
            
            if has_translatable_child:
                # 如果有子块，我们不把当前元素作为一个整体块，除非它本身有直接的非空文本子节点
                # 这种情况在 EPUB 中较少见（通常文本都在 P 里），如果发生，我们暂时跳过父级
                continue
            
            text_content = element.get_text(strip=True)
            if not text_content:
                continue
            
            text, formats = self.extract_block_with_local_ids(element)
            blocks.append({
                'element': element,
                'text': text,
                'formats': formats,
                'size': len(text)
            })
        return blocks

    def format_for_ai(self, group_blocks):
        """将一组块格式化为 AI 提示格式"""
        lines = [self.GS]
        for block in group_blocks:
            lines.append(self.BS)
            lines.append(block['text'])
            lines.append(self.BE)
        lines.append(self.GE)
        return "\n".join(lines)

    def validate_and_parse_response(self, response_text, original_group):
        """
        校验 AI 响应的结构并解析。支持嵌套块。
        """
        # 1. 提取组内内容 (处理稀有字符)
        pattern = re.escape(self.GS) + r'([\s\S]*)' + re.escape(self.GE)
        group_match = re.search(pattern, response_text)
        if not group_match:
            return None, False
        
        content = group_match.group(1).strip()
        
        # 2. 提取所有顶级分块 (处理平衡稀有括号)
        translated_texts = []
        i = 0
        while i < len(content):
            if content[i] == self.BS:
                start_idx = i
                level = 1
                j = i + 1
                while j < len(content) and level > 0:
                    if content[j] == self.BS:
                        level += 1
                    elif content[j] == self.BE:
                        level -= 1
                    j += 1
                
                if level == 0:
                    translated_texts.append(content[start_idx+1:j-1].strip())
                    i = j
                    continue
            i += 1
        
        if len(translated_texts) != len(original_group):
            return None, False
                
        return translated_texts, True

    def restore_html(self, original_block, translated_text, soup):
        """将翻译后的带锚点文本还原为 HTML 元素 (支持嵌套)"""
        format_map = {int(re.search(r'(\d+)', f['id']).group(1)): f for f in original_block['formats']}
        
        # 使用递归解析函数处理嵌套
        def parse_to_nodes(text):
            nodes = []
            last_pos = 0
            
            i = 0
            while i < len(text):
                if text[i] == self.BS:
                    start_idx = i
                    level = 1
                    j = i + 1
                    while j < len(text) and level > 0:
                        if text[j] == self.BS:
                            level += 1
                        elif text[j] == self.BE:
                            level -= 1
                        j += 1
                    
                    if level == 0:
                        # 检查后面是否有加密编号锚点
                        anchor_tail = text[j:]
                        anchor_pattern = f"^{re.escape(self.AS)}(\\d+){re.escape(self.AE)}"
                        match_anchor = re.match(anchor_pattern, anchor_tail)
                        
                        if match_anchor:
                            if start_idx > last_pos:
                                nodes.append(soup.new_string(text[last_pos:start_idx]))
                            
                            inner_content = text[start_idx+1:j-1]
                            anchor_num = int(match_anchor.group(1))
                            
                            if anchor_num in format_map:
                                fmt = format_map[anchor_num]
                                new_tag = soup.new_tag(fmt['tag'])
                                for k, v in fmt['attrs'].items():
                                    new_tag[k] = v
                                for child_node in parse_to_nodes(inner_content):
                                    new_tag.append(child_node)
                                nodes.append(new_tag)
                            else:
                                nodes.append(soup.new_string(f"{self.BS}{inner_content}{self.BE}{self.AS}{anchor_num}{self.AE}"))
                            
                            last_pos = j + match_anchor.end()
                            i = last_pos
                            continue
                i += 1
                
            if last_pos < len(text):
                nodes.append(soup.new_string(text[last_pos:]))
            return nodes

        new_nodes = parse_to_nodes(translated_text)
        original_block['element'].clear()
        for node in new_nodes:
            original_block['element'].append(node)

    def repack_epub(self, output_path):
        """原封不动打包临时目录，并优化兼容性（mimetype不压缩）"""
        if not self.temp_dir or not os.path.exists(self.temp_dir):
            raise ValueError("没有可打包的临时目录")
            
        with zipfile.ZipFile(output_path, 'w') as zipf:
            # 1. 必须先写入 mimetype 且不压缩 (EPUB 标准)
            mimetype_path = os.path.join(self.temp_dir, 'mimetype')
            if os.path.exists(mimetype_path):
                zipf.write(mimetype_path, 'mimetype', compress_type=zipfile.ZIP_STORED)
            
            # 2. 写入其余文件
            for root, dirs, files in os.walk(self.temp_dir):
                for file in files:
                    if file == 'mimetype' and root == self.temp_dir:
                        continue
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.temp_dir)
                    zipf.write(full_path, rel_path, compress_type=zipfile.ZIP_DEFLATED)
                    
    def cleanup(self):
        """清理临时目录"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
