import json
import re
from difflib import SequenceMatcher
import string
import os
import uuid
import jieba  # Add this import at the top of the file

#paircount file
paircountfile = "paircount.json"

#stringthreshhold = 0.8
stringthreshhold = 0.6

# Initialize a dictionary to keep track of Italian-English pair appearances
pair_count = {}
if os.path.exists(paircountfile):
    # File exists, load it
    with open(paircountfile, 'r') as f:
        loaded_dict = json.load(f)
    pair_count = {eval(key): value for key, value in loaded_dict.items()}
    print("Loaded existing dictionary")



def normalize(modstring):
    remove_punctuation_table = str.maketrans('', '', string.punctuation)
    return modstring.translate(remove_punctuation_table).strip().lower()

def string_similarity(str1, str2):
    # Create a SequenceMatcher object with the input strings
    matcher = SequenceMatcher(None, str1, str2)
    # Get the similarity ratio
    similarity = matcher.ratio()
    return similarity

def string_similarity_normal(str1, str2):
    str1 = re.sub(r'[^\w\s]', '', str1)
    str2 = re.sub(r'[^\w\s]', '', str2)
    return string_similarity(str1, str2)


def getJSON(file):
    with open(file, 'r') as json_file:
        # Load the JSON content from the file
        data = json.load(json_file)
        
    return data

def processInterlinear(datalist, language=''):
    runninghtmls = []
    sentence_stores = []
    #Before loop
    runninghtml = ""
    stracker = sentenceTracker()
    sentence_store = sentenceStore()
    #Loop through each entry
    for entry in datalist:
        add, store = processSource(entry, stracker, language)
        #print(str(store.sentences))
        # check if the pattern \n\n\n\n\n\n all caps \n\n\n\n\n\n is in str(store.sentences) or if it has 2. 3. or 4.
        if (re.search(r'\n\s*\n\s*\n\s*\n\s*([A-Z\s]+)\n\s*\n\s*\n\s*\n', entry['source']) or re.search(r'([2-9]\.\s+)', entry['source'])):
            print(entry)
            runninghtmls.append(runninghtml)
            sentence_stores.append(sentence_store)
            runninghtml = ""
            sentence_store = sentenceStore()
        runninghtml += add
        sentence_store.sentences.update(store.sentences)
        sentence_store.wordMap.update(store.wordMap)
    runninghtmls.append(runninghtml)
    sentence_stores.append(sentence_store)


    return runninghtmls, sentence_stores

def processSourceH(entry):
    runninghtml = ""
    text = entry['source']
    translation = entry['translation']
    interlinear = entry['interlinear']
    parsinginfo = entry['parseinfo']

    # Create a list of words from the interlinear data
    words = [gloss[0] for gloss in interlinear if gloss and gloss[0]]

    # Function to find the next word in the text
    def find_next_word(text, words):
        for word in sorted(words, key=len, reverse=True):
            if text.startswith(word):
                return word
        return text[0]  # Return the first character if no word matches

    # Process the text
    remaining_text = text
    while remaining_text:
        print(len(remaining_text))
        word = find_next_word(remaining_text, words)
        
        # Find the corresponding gloss
        gloss = next((g for g in interlinear if g[0] == word), None)
        
        if gloss:
            interlineargloss = gloss[1] if len(gloss) > 1 else ""
            interlinearalt = gloss[2] if len(gloss) > 2 else ""
            interlinearlit = gloss[3] if len(gloss) > 3 else ""
            
            # Find corresponding parsing info
            parse = next((p for p in parsinginfo if p[0] == word), None)
            if parse:
                grammar = parse[3]
                dictionaryforms = parse[1]
                pos = parse[2]
            else:
                grammar = dictionaryforms = pos = ""

            runninghtml += f"""
            <div class="word" title="{grammar}">
                {word}
                <div class="gloss">{interlineargloss}</div>
                <div class="alt">{interlinearalt}</div>
                <div class="lit">{interlinearlit}</div>
                <div class="pos">{pos}</div>
                <div class="dictionary">{dictionaryforms}</div>
                <div class="sourcesentence">{text}</div>
                <div class="translation">{translation}</div>
            </div>
            """
        else:
            # Handle characters not found in interlinear data
            runninghtml += f"""
            <div class="word">
                {word}
            </div>
            """

        remaining_text = remaining_text[len(word):]

        # Add a space after each word for better formatting
        runninghtml += " "

    return runninghtml

class sentenceStore:
    sentences = {}  # Will store sentence pairs indexed by sentence ID
    wordMap = {}     # Will map word IDs to sentence IDs

class sentenceTracker:
    sentence_id = 0
    #Won't work with repetition of sentences
    current_sentence = ""

    def increase(self):
        self.sentence_id += 1

def generate_word_id(word):
    return word + str(uuid.uuid4())

def processSourceTextFirst(entry, stracker, language=''):
    runninghtml = ""
    text = entry['source']
    translation = entry['translation']
    interlinear = entry['interlinear']
    parsinginfo = entry['parseinfo']

    if stracker.current_sentence != text:
        stracker.current_sentence = text
        stracker.increase()

    sentence_store = sentenceStore()
    # Regex pattern with capturing groups:
    # (\w+\b[^\s\w]*) captures a sequence of word characters followed by optional non-word, non-whitespace characters.
    # (\s+) captures at least one whitespace character, including newlines

    # Wow so hacky
    text = text.replace("’", "653")
    text = text.replace("'", "653")
    
    pattern = r'(\w+\b[^\s\w]*)|(\s+)'

    def segment_text(text, language=''):
        """Helper function to segment text based on language"""
        if language == 'chinese':
            # Convert the list to a space-separated string for consistent processing
            return ' '.join(jieba.cut(text))
        # Add other language handlers here as needed:
        # elif language == 'japanese':
        #     return mecab.parse(text)  # Using MeCab for Japanese
        # elif language == 'hindi':
        #     return indic_tokenize.trivial_tokenize(text)  # Using Indic NLP
        else:
            return text  # Return unchanged for space-separated languages

    # Segment the text based on language
    segmented_text = segment_text(text, language)
    
    # Replace the hacky apostrophe handling with proper text preprocessing
    processed_text = segmented_text.replace("'", "'").replace("'", "'")
    
    # Split the text into elements, preserving whitespace
    elements = re.split(pattern, processed_text)
    elements = [e for e in elements if e]
    throughlist = []

    # Process each element
    for i, element in enumerate(elements):
        if "653" in element:
            element = element.replace("653", "'")
        if i not in throughlist:
            if '\n' in element:
                runninghtml += """
                </div> 
                <div class="word-group">"""
            elif element.strip() == '\t':
                runninghtml += "&nbsp;&nbsp;&nbsp;&nbsp;"
            elif element.isspace():  # This will catch other whitespace characters as well
                runninghtml += element
            else:
                print(element)
                #Word
                #Search for gloss
                word = element
                #Get interlinear gloss, needs to be able to handle multiple words
                interlineargloss = ""
                interlinearalt = ""
                interlinearlit = ""
                for j, gloss in enumerate(interlinear):
                    #Strip gloss of trailing whitespace
                    gloss[0] = gloss[0].strip()
                    firstword = gloss[0].split(" ")[0]
                    #print("comparison is " + firstword + " and " + element)

                    #Try to find exact match first
                    if string_similarity_normal(firstword, element) > stringthreshhold:
                        #Go forward and get all words in the rest of the phrase
                        #Should do nothing if only one word
                        forwardindex = i+1
                        forwardindexlookahead = i+3
                        fwords = gloss[0].split(" ")[1:]
                        for fword in fwords:
                            while forwardindex < forwardindexlookahead and forwardindex < len(elements):
                                #Add next to words
                                nextel = elements[forwardindex]
                                #print(nextel)
                                if string_similarity_normal(fword, nextel) > stringthreshhold:
                                    word += " " + fword 
                                    #Add all previous indexes to naughty list
                                    #Append all elements in the range
                                    throughlist.extend(range(i, forwardindex+1))
                                    forwardindexlookahead += 2
                                forwardindex+=1
                        try:
                            #print("Got gloss " + gloss[0] + " for word " + word + " gloss 1 is " + gloss[1])
                            interlineargloss = gloss[1]
                            #check if there are any other glosses
                            if len(gloss) > 2:
                                interlinearalt = gloss[2]
                            if len(gloss) > 3:
                                interlinearlit = gloss[3]
                            interlinear.pop(j)

                            #Break out of for loop
                        except:
                            print("Couldn't get gloss")
                        break
                #Get all words for the gloss
                grammar = ""
                dictionaryforms = ""
                pos = ""
                words = word.split(" ")
                for lookupword in words:
                    for pindex, parse in enumerate(parsinginfo):
                        if string_similarity_normal(lookupword, parse[0]) > stringthreshhold:
                            grammar += parse[3]
                            dictionaryforms += " " + str(parse[1])
                            pos += " " + str(parse[2])
                            parsinginfo.pop(pindex)
                            break
                sentence_id = stracker.sentence_id
                word_id = generate_word_id(word)
                sentence_data = {
                    'source': text,
                    'translation': translation
                }
                
                runninghtml += f"""
                <div class="word" title="{grammar}" data-word-id="{word_id}" data-sentence-id="{sentence_id}">
                    {word}
                    <div class="gloss">{interlineargloss}</div>
                    <div class="alt">{interlinearalt}</div>
                    <div class="lit">{interlinearlit}</div>
                    <div class="pos">{pos}</div>
                    <div class="dictionary">{dictionaryforms}</div>
                </div>
                """
                
                # Create a separate JSON file with sentence data
                sentence_store.sentences[sentence_id] = sentence_data
                sentence_store.wordMap[word_id] = sentence_id
    
    return runninghtml, sentence_store

def processSource(entry, stracker, language=''):
    runninghtml = ""
    text = entry['source']
    translation = entry['translation']
    interlinear = entry['interlinear']
    parsinginfo = entry['parseinfo']

    if stracker.current_sentence != text:
        stracker.current_sentence = text
        stracker.increase()

    sentence_store = sentenceStore()
    # Regex pattern with capturing groups:
    # (\w+\b[^\s\w]*) captures a sequence of word characters followed by optional non-word, non-whitespace characters.
    # (\s+) captures at least one whitespace character, including newlines

    # Wow so hacky
    text = text.replace("’", "653")
    text = text.replace("'", "653")
    
    pattern = r'(\w+\b[^\s\w]*)|(\s+)'

    def segment_text(text, language=''):
        """Helper function to segment text based on language"""
        if language == 'chinese':
            # Convert the list to a space-separated string for consistent processing
            return ' '.join(jieba.cut(text))
        # Add other language handlers here as needed:
        # elif language == 'japanese':
        #     return mecab.parse(text)  # Using MeCab for Japanese
        # elif language == 'hindi':
        #     return indic_tokenize.trivial_tokenize(text)  # Using Indic NLP
        else:
            return text  # Return unchanged for space-separated languages

    # Segment the text based on language
    segmented_text = segment_text(text, language)
    
    # Replace the hacky apostrophe handling with proper text preprocessing
    processed_text = segmented_text.replace("'", "'").replace("'", "'")
    
    # Split the text into elements, preserving whitespace
    elements = re.split(pattern, processed_text)
    elements = [e for e in elements if e]
    throughlist = []

    # Process each element
    glossoffset = 0
    element_count = len(elements)
    element_counter = 0
    while element_counter < element_count:
    #for element_counter in range(len(elements)):
        #Get element and index, strange structure so that can be repeated if interlinear gloss is a substring of the word
        element = elements[element_counter+glossoffset]
        i = element_counter+glossoffset
        if "653" in element:
            element = element.replace("653", "'")
        if i not in throughlist:
            if '\n' in element:
                runninghtml += """
                </div> 
                <div class="word-group">"""
            elif element.strip() == '\t':
                runninghtml += "&nbsp;&nbsp;&nbsp;&nbsp;"
            elif element.isspace():  # This will catch other whitespace characters as well
                runninghtml += element
            else:
                print(element)
                #Word
                #Search for gloss
                word = element
                #Get interlinear gloss, needs to be able to handle multiple words
                interlineargloss = ""
                interlinearalt = ""
                interlinearlit = ""

                # check if the gloss is a smaller substring of the word, disincluding punctuation
                word_no_punct = ''.join(c for c in word if c.isalnum())
                # pop empty interlinears
                while len(interlinear) > 0 and len(interlinear[0][0].strip()) == 0:
                    interlinear.pop(0)
                if len(interlinear) == 0:
                    print("No interlinear gloss found for word " + word)
                    element_counter += 1
                    continue
                
                gloss = interlinear[0]
                gloss_word = gloss[0].strip()
                gloss_no_punct = ''.join(c for c in gloss_word if c.isalnum())
                print(f"gloss_no_punct is {gloss_no_punct} and word_no_punct is {word_no_punct}")
                # If the cleaned word contains the cleaned gloss and they're not identical
                if len(gloss_no_punct) < len(word_no_punct) and len(gloss_no_punct) > 0 and gloss_no_punct in word_no_punct and gloss_no_punct != word_no_punct:
                    print("Found gloss " + gloss_word + " for word " + word)
                    # Update word to be the gloss unit instead
                    word = gloss_word
                    interlineargloss = gloss[1]
                    if len(gloss) > 2:
                        interlinearalt = gloss[2]
                    if len(gloss) > 3:
                        interlinearlit = gloss[3]

                    # remove the gloss substring from the element
                    elements[i] = elements[i].replace(gloss_word, '', 1)
                    interlinear.pop(0)
                    glossoffset += -1
                    element_count += 1
                # otherwise normal procedure

                else:
                    #Try to find exact match first
                    for j, gloss in enumerate(interlinear):
                        #Strip gloss of trailing whitespace
                        gloss[0] = gloss[0].strip()
                        firstword = gloss[0].split(" ")[0]
                        #print("comparison is " + firstword + " and " + element)

                        #for non spaced languages, augment until it fits
                        #glossindex = j
                        #while string_similarity_normal(firstword, element) < stringthreshhold and glossindex < len(interlinear):
                        #    firstword += interlinear[glossindex][0]
                        #    glossindex += 1
                        #    pops = glossindex - j
                        

                        #Try to find exact match first  
                        if string_similarity_normal(firstword, element) > stringthreshhold or firstword in element:
                            #Go forward and get all words in the rest of the phrase
                            #Should do nothing if only one word
                            forwardindex = i+1
                            forwardindexlookahead = i+3
                            fwords = gloss[0].split(" ")[1:]
                            for fword in fwords:
                                while forwardindex < forwardindexlookahead and forwardindex < len(elements):
                                    #Add next to words
                                    nextel = elements[forwardindex]
                                    #print(nextel)
                                    if string_similarity_normal(fword, nextel) > stringthreshhold:
                                        if language != 'chinese':
                                            word += " " + fword 
                                        else:
                                            word += fword
                                        #Add all previous indexes to naughty list
                                        #Append all elements in the range
                                        throughlist.extend(range(i, forwardindex+1))
                                        forwardindexlookahead += 2
                                    forwardindex+=1
                            try:
                                print("Got gloss " + gloss[0] + " for word " + word + " gloss 1 is " + gloss[1])
                                interlineargloss = gloss[1]
                                #check if there are any other glosses
                                if len(gloss) > 2:
                                    interlinearalt = gloss[2]
                                if len(gloss) > 3:
                                    interlinearlit = gloss[3]
                                print(f"popping gloss {j} for word {word}")
                                for k in range(j+1):
                                    interlinear.pop(0)
                                #interlinear.pop(j)
                                
                            except:
                                print(f"Couldn't get gloss for word {word}")
                            break

                #Get all words for the gloss
                grammar = ""
                dictionaryforms = ""
                pos = ""
                words = word.split(" ")
                for lookupword in words:
                    for pindex, parse in enumerate(parsinginfo):
                        if string_similarity_normal(lookupword, parse[0]) > stringthreshhold:
                            grammar += parse[3]
                            dictionaryforms += " " + str(parse[1])
                            pos += " " + str(parse[2])
                            parsinginfo.pop(pindex)
                            break
                sentence_id = stracker.sentence_id
                word_id = generate_word_id(word)
                sentence_data = {
                    'source': text,
                    'translation': translation
                }
                
                runninghtml += f"""
                <div class="word" title="{grammar}" data-word-id="{word_id}" data-sentence-id="{sentence_id}">
                    {word}
                    <div class="gloss">{interlineargloss}</div>
                    <div class="alt">{interlinearalt}</div>
                    <div class="lit">{interlinearlit}</div>
                    <div class="pos">{pos}</div>
                    <div class="dictionary">{dictionaryforms}</div>
                </div>
                """
                
                # Create a separate JSON file with sentence data
                sentence_store.sentences[sentence_id] = sentence_data
                sentence_store.wordMap[word_id] = sentence_id
        element_counter += 1
        print(f"element_counter is {element_counter} and element_count is {element_count}")
    
    return runninghtml, sentence_store

def text_to_html(text):
    html_text = (
        text.replace('&', '&amp;')  # Encode ampersand
            .replace('<', '&lt;')   # Encode less than
            .replace('>', '&gt;')   # Encode greater than
            .replace('"', '&quot;') # Encode double quotes
            .replace("'", '&#39;')  # Encode single quotes
            .replace('\n', '<br>')  # Newlines to <br>
            .replace('\t', '&nbsp;&nbsp;&nbsp;&nbsp;')  # Tabs to spaces (change the number of spaces as you see fit)
    )
    return html_text


def write_html_interlinear(jsonfile, htmltemplate, dir, textname, title, description, language=''):
    interlineartexts, sentence_stores = processInterlinear(getJSON(jsonfile), language)
    html_template = open(htmltemplate, 'r').read()
    # enumerate starts at 1
    for i, interlineartext in enumerate(interlineartexts, 1):
        htmltext = html_template.replace("{{interlinear}}", interlineartext)
        htmltext = htmltext.replace("{{Title}}", title, -1)
        htmltext = htmltext.replace("{{Description}}", description)
        page_info = '<meta name="page_number" content="' + str(i) + '">'
        if len(interlineartexts) >= i+1:
            page_info += '<meta name="next_page" content="' + str(i+1) + '">'
        if i > 1:
            page_info += '<meta name="previous_page" content="' + str(i-1) + '">'
        page_info += '<meta name="sentence_store" content="' + textname + '_' + str(i) + '">'
        htmltext = htmltext.replace("{{page_info}}", page_info)
        with open(dir + textname + "/" + textname + "_" + str(i) + ".html", 'w', encoding='utf-8') as file:
            file.write(htmltext)
        with open(dir + textname + "/sentence_stores/" + textname + "_" + str(i) + ".json", 'w') as file:
            sentence_store_dict = {}
            sentence_store_dict['sentences'] = sentence_stores[i-1].sentences
            sentence_store_dict['wordMap'] = sentence_stores[i-1].wordMap
            json.dump(sentence_store_dict, file)

        print("Wrote page " + str(i))
        # Write one file for each page, first sentence of each page has /n/n/n/n/n

write_html_interlinear("textcreation/texts/interlinearouts/interlinearabuatapoem.json", "textcreation/texts/templates/infernotemplate.html", "app/templates/texts/", "persian_poems", "Mohammad Taqi Bahar", "Mohammad Taqi Bahar", 'persian')