# language.py

class Language:
    def __init__(self, name):
        self.name = name

    def get_grammar(self, word:str, sentence:str, ind:int):
        """
        Get the declension of a noun.
        This should be implemented by a subclass.
        """
        raise NotImplementedError("This method should be implemented by subclass.")

    def get_definition(self, word:str, sentence:str):
        """
        Look up a word in the dictionary.
        This should be implemented by a subclass.
        """
        raise NotImplementedError("This method should be implemented by subclass.")
    def get_lemma(self, word:str, sentence:str):
        """
        Get the lemma of the word.
        This should be implemented by a subclass.
        """
        raise NotImplementedError("This method should be implemented by subclass.")
    
    def parse_sent(self, sent:str):
        """
        Parse a sentence.
        This should be implemented by a subclass.
        """
        raise NotImplementedError("This method should be implemented by subclass.")