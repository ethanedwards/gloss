import json
import re
from difflib import SequenceMatcher
import string
import os


#paircount file
paircountfile = "paircount.json"

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
        runninghtml += processSource(entry)
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
                for j, gloss in enumerate(interlinear):
                    #Strip gloss of trailing whitespace
                    gloss[0] = gloss[0].strip()
                    firstword = gloss[0].split(" ")[0]
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
                            interlineargloss = gloss[1]
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


stringthreshhold = 0.8

with open(f'texts/html/hamannfirst2.html', 'w', encoding='utf-8') as file:
    file.write("""
<!DOCTYPE html>
<html>
<head>
<style>
.interlinear-container {
    direction: ltr;
    margin: 0 120px;
}

.word-group {
    display: flex;
    flex-flow: row wrap;
    /* If you want a gap between word groups */
    margin-bottom: 20px; /* Adjust as necessary */
}

/* Increase the font size of the main word container */
.interlinear-container .word {
    padding: 10px;
    font-size: 1.2em; /* Adjust the size as needed */
}

/* Decrease the font size of gloss */
.interlinear-container .word .gloss {
    display: block;
    font-size: 0.8em; /* Adjust the size as needed */
    user-select: none;
}

/* Shrink the font size and change alignment of grammar */
.interlinear-container .word .grammar {
    display: block;
    font-size: 0.6em; /* Adjust the size as needed */
    text-align: right; /* Aligns text to the right */
    user-select: none;
}

/* Hide pos and dictionary completely */
.interlinear-container .word .pos,
.interlinear-container .word .dictionary,
.interlinear-container .word .sourcesentence,
.interlinear-container .word .translation {
    display: none;
    user-select: none;
}
               
.chat-interface {
    width: 25%; /* Adjust based on your preference */
    padding: 20px;
    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
    max-height: 600px; /* Or whatever height matches your design */
    overflow-y: auto; /* Enable scrollbar if the content overflows */
    float: right;
}

.chat-message {
    margin-bottom: 20px;
    padding: 10px;
    background-color: #f0f0f0;
    border-radius: 10px;
}

.tutor, .student {
    font-weight: bold;
}

.message-text {
    margin-top: 5px;
}
               
.chat-input {
    display: flex;
    justify-content: space-between;
    padding: 10px;
}

#studentInput {
    width: 80%;
    margin-right: 10px;
}

button {
    width: 18%;
    cursor: pointer;
}
.hidden-gloss {
    color: transparent; /* Makes the text transparent */
}

</style>
</head>

<body>
    <div class="interlinear-container">    
        <div class="word-group">
    """)

    file.write(processInterlinear(getJSON("texts/interlinearouts/interlinearhamannfirst.json")))

    file.write("""
    </div>
</div>
<script>
document.addEventListener('keydown', function(event) {
    // Check if the pressed key is 'a' or 'A'
    if (event.key === 'a' || event.key === 'A') {
        // Select all elements with the class name 'gloss'
        const glossElements = document.querySelectorAll('.gloss');

        // Toggle the 'hidden-gloss' class for each gloss element
        glossElements.forEach(function(glossElement) {
            if (glossElement.classList.contains('hidden-gloss')) {
                // If the gloss is hidden (transparent), remove the class to show it
                glossElement.classList.remove('hidden-gloss');
            } else {
                // If the gloss is shown, add the class to hide it
                glossElement.classList.add('hidden-gloss');
            }
        });
    }
});
</script>
<script src="chat-script.js"></script>
</body>
</html>
    """)
serializable_dict = {str(key): value for key, value in pair_count.items()}

# Now you can dump this dictionary into a JSON file
with open(paircountfile, 'w') as f:
    json.dump(serializable_dict, f, ensure_ascii=False)