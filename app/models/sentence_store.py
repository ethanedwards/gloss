# app/models/sentence_store.py
import json
import os

class SentenceStore:
    def __init__(self, base_path):
        self.base_path = base_path

    def get_sentences(self, text_name):
        file_path = os.path.join(self.base_path, f'sentence_{text_name}.json')
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return None