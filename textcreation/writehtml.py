import json
import re
from difflib import SequenceMatcher
import string
import os


#paircount file
paircountfile = "paircount.json"

stringthreshhold = 0.8

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

def processInterlinear(datalist):
    runninghtml = ""
    for entry in datalist:
        runninghtml += processSourceH(entry)
    return runninghtml

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


def processSource(entry):
    runninghtml = ""
    text = entry['source']
    translation = entry['translation']
    interlinear = entry['interlinear']
    parsinginfo = entry['parseinfo']
    # Regex pattern with capturing groups:
    # (\w+\b[^\s\w]*) captures a sequence of word characters followed by optional non-word, non-whitespace characters.
    # (\s+) captures at least one whitespace character, including newlines
    pattern = r'(\w+\b[^\s\w]*)|(\s+)'

    # Split the text and keep delimiters
    elements = re.split(pattern, text)

    # Filter out empty strings that might result from the split
    elements = [e for e in elements if e]
    throughlist = []

    # Process each element
    for i, element in enumerate(elements):
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


    return runninghtml

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


def write_html_interlinear(jsonfile, htmltemplate, htmlfileout):
    interlineartext = processInterlinear(getJSON(jsonfile))
    htmltext = open(htmltemplate, 'r').read()
    htmltext = htmltext.replace("{{interlinear}}", interlineartext)
    with open(htmlfileout, 'w', encoding='utf-8') as file:
        file.write(htmltext)



write_html_interlinear("textcreation/texts/interlinearouts/neeleneele.json", "textcreation/texts/templates/infernotemplate.html", "templates/neeleneeletrue.html")