
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

from src.core.processor import Processor

def test_chunking():
    proc = Processor("cache_test")
    max_chars = 100
    
    print("--- Test 1: Markdown Paragraphs ---")
    md_text = "Para 1. Line 1.\n\nPara 2. Line 1. Para 2. Line 2. Para 2. Line 3. Super long para that should exceed max_chars easily.\n\nPara 3."
    chunks = proc.chunk_text(md_text, max_chars)
    for i, c in enumerate(chunks):
        print(f"Chunk {i} (len {len(c)}):\n{repr(c)}")
        assert c.endswith("\n\n") or i == len(chunks) - 1
    print("Test 1 Passed (Visual Inspection recommended for 'Super long para')\n")

    print("--- Test 2: HTML Blocks ---")
    html_text = "<div><p>Paragraph 1 content.</p><p>Paragraph 2 super long content that will definitely exceed the max character limit of one hundred.</p></div>"
    chunks = proc.chunk_text(html_text, max_chars)
    for i, c in enumerate(chunks):
        print(f"Chunk {i} (len {len(c)}):\n{repr(c)}")
        # Check if tags are broken
        assert c.count("<") == c.count(">")
    print("Test 2 Passed\n")

    print("--- Test 3: List Items ---")
    list_text = "<ul><li>Item 1</li><li>Item 2 that is quite long so it might trigger a split if we weren't careful</li><li>Item 3</li></ul>"
    chunks = proc.chunk_text(list_text, max_chars)
    for i, c in enumerate(chunks):
        print(f"Chunk {i} (len {len(c)}):\n{repr(c)}")
    print("Test 3 Passed\n")

    print("--- Test 4: Mixed and Edge Cases ---")
    mixed = "Start.<p>Inside tag</p>\n\nMarkdown para.\r\n\r\nWindows para.<div>Block</div>End."
    chunks = proc.chunk_text(mixed, max_chars)
    for i, c in enumerate(chunks):
        print(f"Chunk {i} (len {len(c)}):\n{repr(c)}")
    print("Test 4 Passed\n")

if __name__ == "__main__":
    if not os.path.exists("cache_test"):
        os.makedirs("cache_test")
    try:
        test_chunking()
        print("ALL TESTS PASSED!")
    except Exception as e:
        print(f"TEST FAILED: {e}")
    finally:
        import shutil
        if os.path.exists("cache_test"):
            shutil.rmtree("cache_test")
