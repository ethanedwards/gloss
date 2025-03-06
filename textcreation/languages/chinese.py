from languages.language import Language
import spacy

class Chinese(Language):
    def __init__(self):
        self.nlp = spacy.load("zh_core_web_trf")

    def get_grammar(self, word:str, sent:str, ind:int):
        # Placeholder for noun declension logic specific to German
        doc = self.nlp(sent)
        count = 0
        for token in doc:
            if token.text == word:
                if count == ind:
                    return token.morph
                count += 1
        return "Problem with finding the word in the sentence."
    
    def get_definition(self, word):
        # Placeholder for looking up a word in a French dictionary
        return "Looking up in Chinese dictionary: " + word
    
    def parse_sent(self, sent: str):
        outlist = []
        doc = self.nlp(sent)
        
        for token in doc:
            try:
                outlist.append((str(token.text), str(token.lemma_), str(token.pos_), str(token.morph)))
            except:
                print("Error parsing French")
        
        return outlist