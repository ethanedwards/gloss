from languages.language import Language
import spacy



class German(Language):
    def __init__(self):
        super().__init__('German')
        self.nlp = spacy.load("de_dep_news_trf")

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
        return "Looking up in German dictionary: " + word