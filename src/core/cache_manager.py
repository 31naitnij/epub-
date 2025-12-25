import sqlite3
import hashlib

class CacheManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self._create_table()
    
    def _create_table(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS translations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_hash TEXT NOT NULL,
                original_text TEXT NOT NULL,
                translated_text TEXT NOT NULL,
                model_name TEXT NOT NULL,
                UNIQUE(original_hash, model_name)
            )
        ''')
        self.conn.commit()
    
    def get_translation(self, original_text, model_name):
        text_hash = hashlib.md5(original_text.encode('utf-8')).hexdigest()
        cursor = self.conn.cursor()
        cursor.execute(
            'SELECT translated_text FROM translations WHERE original_hash=? AND model_name=?',
            (text_hash, model_name)
        )
        result = cursor.fetchone()
        return result[0] if result else None
    
    def save_translation(self, original_text, translated_text, model_name):
        text_hash = hashlib.md5(original_text.encode('utf-8')).hexdigest()
        cursor = self.conn.cursor()
        cursor.execute(
            'INSERT OR REPLACE INTO translations (original_hash, original_text, translated_text, model_name) VALUES (?, ?, ?, ?)',
            (text_hash, original_text, translated_text, model_name)
        )
        self.conn.commit()
    
    def close(self):
        self.conn.close()
