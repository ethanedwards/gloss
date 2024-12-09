# app/models/click_tracker.py
import json
import os

class ClickTracker:
    def __init__(self, filename='click_counts.json'):
        self.filename = filename
        self.click_counts = self._load_counts()

    def _load_counts(self):
        if os.path.exists(self.filename):
            with open(self.filename, 'r') as f:
                return json.load(f)
        return {}

    def update_click(self, data):
        lemma = data['lemma']
        pos = data['pos']
        key = f"{lemma}|{pos}"
        
        self.click_counts[key] = self.click_counts.get(key, 0) + 1
        
        with open(self.filename, 'w') as f:
            json.dump(self.click_counts, f)
        
        return {'success': True, 'clicks': self.click_counts[key]}