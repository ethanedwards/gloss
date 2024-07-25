from languages.language import Language
import spacy

class Spanish(Language):
    def __init__(self):
        super().__init__('Spanish')
        self.nlp = spacy.load("es_dep_news_trf")

    def get_grammar(self, word:str, sent:str, ind:int):
        # Placeholder for grammatical logic specific to Spanish
        doc = self.nlp(sent)
        count = 0
        for token in doc:
            if token.text == word:
                if count == ind:
                    return token.morph
                count += 1
        return "Problem with finding the word in the sentence."
    
    def get_definition(self, word):
        # Placeholder for looking up a word in a Spanish dictionary
        return "Looking up in Spanish dictionary: " + word
    
    def parse_sent(self, sent: str):
        outlist = []
        doc = self.nlp(sent)
        
        for token in doc:
            try:
                outlist.append((str(token.text), str(token.lemma_), str(token.pos_), str(token.morph)))
            except:
                print("Error parsing Spanish")
        
        return outlist