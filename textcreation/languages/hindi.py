import stanza

from languages.language import Language

class Hindi(Language):
    def __init__(self):
        super().__init__('Hindi')
        # Downloading the Hindi model if not already downloaded
        stanza.download('hi')
        self.nlp = stanza.Pipeline('hi')

    def get_grammar(self, word: str, sent: str, ind: int):
        doc = self.nlp(sent)
        count = 0
        for sentence in doc.sentences:
            for token in sentence.tokens:
                if token.words[0].text == word:
                    if count == ind:
                        return token.words[0].feats
                    count += 1
        return "Problem with finding the word in the sentence."

    def get_definition(self, word):
        # Placeholder for Hindi dictionary lookup
        return "Looking up in Hindi dictionary: " + word
    
    def parse_sent(self, sent: str):
        outlist = []
        doc = self.nlp(sent)
        
        for sentence in doc.sentences:
            for token in sentence.tokens:
                for word in token.words:
                    try:
                        outlist.append((str(word.text), str(word.lemma), str(word.pos), str(word.feats)))
                    except:
                        print("Error parsing Hindi")
        
        return outlist