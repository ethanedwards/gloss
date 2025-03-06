from languages.language import Language
import fugashi
import pykakasi
from jamdict import Jamdict
jam = Jamdict()

class Japanese(Language):
    def __init__(self):
        self.tagger = fugashi.Tagger()
        self.kakasi = pykakasi.kakasi()
    
    def get_grammar(self, word: str, sent: str, ind: int):
        # Parse the sentence and find the specific word instance
        words = self.tagger(sent)
        count = 0
        for w in words:
            if w.surface == word:
                if count == ind:
                    # Return features in a format similar to spacy's morph
                    features = {
                        'POS': w.feature.pos1,
                        'Inflection': w.feature.inflection_type,
                        'Conjugation': w.feature.inflection_form
                    }
                    return features
                count += 1
        return "Problem with finding the word in the sentence."
    
    def get_definition(self, word):
        # Get the base dictionary form and reading
        word_obj = self.tagger(word)[0]
        reading = self.get_reading(word)
        return f"{word} ({reading}) - {word_obj.feature.lemma}"
    
    def get_reading(self, text):
        """Get the kana reading of text"""
        result = self.kakasi.convert(text)
        return result[0]['hira']
    
    def get_readings(self, text):
        result = self.kakasi.convert(text)
        return [(item['orig'], item['hira']) for item in result]
    
    
    def is_kanji_compound(self, text):
        # Returns True if the text contains any kanji
        return any('\u4e00' <= char <= '\u9fff' for char in text)
    
    def parse_sent(self, sent: str):
        outlist = []
        words = self.tagger(sent)
        
        for word in words:
            try:
                
                # Get reading
                reading = self.get_reading(word.surface)

                # Get definition
                definition = jam.lookup(word.feature.lemma).entries[0].senses[0].gloss[0].text
                # Append tuple with: (surface form, lemma, POS, features, reading)
                outlist.append((
                    str(word.surface),
                    str(word.feature.lemma),
                    str(word.pos),
                    reading,
                    definition
                ))
            except Exception as e:
                print(f"Error parsing Japanese: {e}")
        
        return outlist