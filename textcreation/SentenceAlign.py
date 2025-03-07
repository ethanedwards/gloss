#The Algorithm!

from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import itertools
import json
import nltk
import re

model = SentenceTransformer('sentence-transformers/LaBSE')

def GetSimilarity(sentence1, sentence2, model):
    embeddings = model.encode([sentence1, sentence2])
    similarity_score = cosine_similarity(
        [embeddings[0]],
        [embeddings[1]]
    )
    return similarity_score



#First get both sentences pairs

def SimpleRead(filename):
    with open(filename, 'r') as file:
        content = file.read()
    segments = TokenizeSentences(content)
    return segments

def GetSentences(text1, text2):
    return TokenizeSentences(text1), TokenizeSentences(text2)

#Mostly use NLTK but have paragraphs in addition
def TokenizeSentences(text):
    # Split text by double newlines first
    paragraphs = text.split('\n\n')
    
    whitespace_preserved_sentences = []
    
    for paragraph in paragraphs:
        if not paragraph.strip():  # Skip empty paragraphs
            continue
            
        # Tokenize each paragraph into sentences
        sentences = nltk.sent_tokenize(paragraph)
        
        # Process each sentence within the paragraph
        start = 0
        for sentence in sentences:
            # Find the start of the current sentence in the paragraph
            start = paragraph.find(sentence, start)
            # Calculate the end of the current sentence
            end = start + len(sentence)
            # Extract the sentence with leading and trailing whitespace
            while start > 0 and paragraph[start-1].isspace():
                start -= 1
            while end < len(paragraph) and paragraph[end].isspace():
                end += 1
            # Append the sentence with preserved whitespace
            whitespace_preserved_sentences.append(paragraph[start:end])
            # Update the start for the next iteration
            start = end
        
        # Add a double newline after each paragraph (except the last one)
        if paragraphs.index(paragraph) < len(paragraphs) - 1:
            whitespace_preserved_sentences[-1] += '\n\n'
    
    return whitespace_preserved_sentences

# def TokenizeSentences(text):
#     paragraphs = text.split('\n')

#     # Then split each paragraph into sentences
#     sentences = [sentence.strip() for paragraph in paragraphs for sentence in nltk.sent_tokenize(paragraph)]

#     return sentences

#Main algorithm

#Define constants
minlength = 10
minscore = 0.2
lookahead = 5
lookback = 5
#Function
def AlignSentences(sourcesents, transsents, model):
    #Define the output arrays
    sourcesentsout = []
    transsentsout = []
    #Define the moving indexes
    sourceindex = 0
    transindex = 0
    #Begin iterating through source
    while(sourceindex < len(sourcesents)):
        sourcesent = sourcesents[sourceindex]
        #Check if the source sentence is long enough
        #If not, continue combining sentences until it is, or reaches the end of the array
        augment = 0
        while len(sourcesent) < minlength and sourceindex < len(sourcesents) - 1:
            sourcesent += sourcesents[sourceindex+1]
            sourceindex += 1
            augment += 1
            print("augmenting sourcesent")


        #Compare to translations
        #Make sure there are translations left
        if transindex >= len(transsents):
            print("No more translations left")
            break
        #Initialize topscore
        topscore = minscore
        toptrans = ""
        topsize = 0
        startingtrans = transindex
        #Compare the next several sentences in the translation to the source sentence
        for size in range(1, lookahead + augment + 1):
            for i in range(transindex-min(lookback, transindex), transindex + lookahead + augment - size + 1):
                combo = transsents[i : i + size]
                combsentence = " ".join(combo)
                max_index = i + size - 1
                #For each combination, get the similarity score
                score = GetSimilarity(sourcesent.strip(), combsentence.strip(), model)
                #Create penalties
                #Penalize for different sizes of source and translation
                sizedif = abs((augment+1-size) * 0.02)
                indexdif = abs((max_index-startingtrans)*0.02)
                score -= sizedif
                score -= indexdif
                #print(f'Score for {sourcesent} and {combsentence} is {score}')
                print(score)
                #If the score is higher than the topscore, update the topscore
                if score > topscore:
                    topscore = score
                    toptrans = combsentence
                    #Update the transindex
                    transindex = max_index
                    topsize = size

        
        print(f"Choice for {sourcesent} with augment {augment} was {toptrans} with size {topsize}")

        if toptrans == "":
            print(f"\n\n\nNo translation found for: {sourcesent}\n\n\n")
            toptrans = transsents[startingtrans]

        #Add the top translation to the output arrays
        sourcesentsout.append(sourcesent)
        transsentsout.append(toptrans)
        #Update the sourceindex
        sourceindex += 1
        #update the transindex to be one past whatever the top score was
        transindex += 1

    #Return the output arrays
    return sourcesentsout, transsentsout
    


def AlignSentencesBruteForce(sourcesents, transsents, model):
        #Define the output arrays
    sourcesentsout = []
    transsentsout = []
    #Define the moving indexes
    sourceindex = 0
    transindex = 0
    #Begin iterating through source
    while(sourceindex < len(sourcesents)):
        sourcesent = sourcesents[sourceindex]
        #Check if the source sentence is long enough
        #If not, continue combining sentences until it is, or reaches the end of the array
        augment = 0
        while len(sourcesent) < minlength and sourceindex < len(sourcesents) - 1:
            sourcesent += sourcesents[sourceindex+1]
            sourceindex += 1
            augment += 1
            print("augmenting sourcesent")


        #Compare to translations
        #Make sure there are translations left
        if transindex >= len(transsents):
            print("No more translations left")
            break
        #Initialize topscore
        topscore = minscore
        toptrans = ""
        topsize = 0
        startingtrans = transindex
        #Compare the next several sentences in the translation to the source sentence
        for i in range(transindex-min(lookback, transindex), transindex + lookahead + augment + 1):
            combsentence = transsents[min(i, len(transsents)-1)]
            #For each combination, get the similarity score
            score = GetSimilarity(sourcesent.strip(), combsentence.strip(), model)
            #Create penalties
            #Penalize for different sizes of source and translation
            indexdif = abs((i-startingtrans)*0.02)
            score -= indexdif
            #print(f'Score for {sourcesent} and {combsentence} is {score}')
            #If the score is higher than the topscore, update the topscore
            if score > topscore:
                topscore = score
                toptrans = combsentence
                #Update the transindex
                transindex = i

        
        print(f"Score: {topscore} \nChoice for {sourcesent} \nwith augment {augment} was \n{toptrans}")

        if toptrans == "":
            print(f"\n\n\nNo translation found for: {sourcesent}\n\n\n")
            toptrans = transsents[startingtrans]
            #break
        
        #Add the top translation to the output arrays
        sourcesentsout.append(sourcesent)
        transsentsout.append(toptrans)
        #Update the sourceindex
        sourceindex += 1
        #update the transindex to be one past whatever the top score was
        transindex += 1

    #Return the output arrays
    return sourcesentsout, transsentsout




#Testing
                
def TestFile(filename):
    sourcesents = []
    transsents = []
    with open(filename, 'r') as file:
        content = file.read()

    segments = content.split('|||\n')

    # Ensure we have an even number of segments for English-Persian pairs
    assert len(segments) % 2 == 0, "File should contain an even number of segments"

    for i in range(0, len(segments), 2):
        english_text = segments[i].strip()
        persian_text = segments[i+1].strip()
        sourcesents.append(persian_text)
        transsents.append(english_text)

    return sourcesents, transsents


#sourcesents, transsents = TestFile('../Persian/saadi2.txt')
#outsource, outrans = AlignSentences(sourcesents, transsents, model)
#for i in range(len(outsource)):
#    print(outsource[i])
#    print(outrans[i])
#    print("\n\n\n\n\n")


def write_to_json(source_list, translation_list, file_name='translation.json'):
    translation_pairs = [{'source': source, 'translation': translation} for source, translation in zip(source_list, translation_list)]

    with open(file_name, 'w', encoding='utf8') as file:
        json.dump(translation_pairs, file, ensure_ascii=False)


#Put it all together
content1 = open('textcreation/texts/sources/Witt3de.txt', 'r').read()
content2 = open('textcreation/texts/sources/Witt3en.txt', 'r').read()
# Divide the content into sections denoted by newline then a number followed by a period
# Extract sections and their numbers using regex
def extract_numbered_sections(content):
    # Match any text up until we find a newline followed by numbers and a period
    pattern = r'(?:.*?)(?:\n(\d+)\.(.*?))?(?=\n\d+\.|$)'
    matches = re.finditer(pattern, content, re.DOTALL)
    sections = []
    for match in matches:
        if match.group(1):  # if we found a number
            section_num = int(match.group(1))
            section_text = match.group(2).strip()
            sections.append(" ".join([str(section_num), section_text]))
    return sections

sections1 = extract_numbered_sections(content1)
sections2 = extract_numbered_sections(content2)


sourcelist = []
translist = []
print(len(sections1))
print(len(sections2))
assert(len(sections1) == len(sections2))
for i in range(len(sections1)):
    print(sections1[i])
    sources, trans = GetSentences(sections1[i], sections2[i])
    #sources, trans = GetSentences('../Novels/proustfr.txt', '../Novels/prousten.txt')
    outsource, outtrans = AlignSentences(sources, trans, model)
    sourcelist.extend(outsource)
    translist.extend(outtrans)
    # Add blank lines between sections
    sourcelist.append("")
    translist.append("")
    print(f"added {i}")

write_to_json(sourcelist, translist, file_name='textcreation/texts/aligned/Witt3.json')
