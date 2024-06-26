from languages.language import Language
import spacy



class Danish(Language):
    def __init__(self):
        super().__init__('German')
        self.nlp = spacy.load("da_core_news_trf")

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
        # Placeholder for looking up a word in a German dictionary
        return "Looking up in Danish dictionary: " + word
    
    def parse_sent(self, sent: str):
        outlist = []
        doc = self.nlp(sent)
        
        for token in doc:
            try:
                outlist.append((str(token.text), str(token.lemma_), str(token.pos_), str(token.morph)))
            except:
                print("Error parsing Danish")
        
        return outlist
    
        
