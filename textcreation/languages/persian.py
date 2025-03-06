from languages.language import Language
from hazm import Normalizer, POSTagger, Lemmatizer, word_tokenize

class Persian(Language):
    def __init__(self):
        self.normalizer = Normalizer()
        self.tagger = POSTagger(model='textcreation/models/pos_tagger.model')
        self.lemmatizer = Lemmatizer()

    def get_grammar(self, word:str, sent:str, ind:int):
        # Normalize and tokenize the sentence
        normalized_sent = self.normalizer.normalize(sent)
        words = word_tokenize(normalized_sent)
        # Get POS tags for the sentence
        tagged = self.tagger.tag(words)
        
        count = 0
        for token, tag in tagged:
            if token == word:
                if count == ind:
                    return tag  # Returns the POS tag for the word
                count += 1
        return "مشکل در پیدا کردن کلمه در جمله"  # "Problem finding the word in the sentence" in Persian
    
    def get_definition(self, word):
        # Placeholder for looking up a word in a Persian dictionary
        return "جستجو در فرهنگ لغت فارسی: " + word
    
    def parse_sent(self, sent: str):
        outlist = []
        normalized_sent = self.normalizer.normalize(sent)
        words = word_tokenize(normalized_sent)
        tagged = self.tagger.tag(words)
        
        for word, tag in tagged:
            try:
                lemma = self.lemmatizer.lemmatize(word)
                outlist.append((word, lemma, tag, ''))  # Morph information isn't directly available in Hazm
            except(Exception) as e:
                print("خطا در تجزیه متن فارسی")  # "Error parsing Persian text" in Persian
        
        return outlist
