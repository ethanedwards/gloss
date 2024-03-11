from languages.german import German

def test_german():
    german = German()
    print(german.get_grammar("Hund", "Der Hund ist schnell.", 0))

test_german()