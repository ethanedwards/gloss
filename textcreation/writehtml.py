import json
import re
from difflib import SequenceMatcher
import string
import os
import uuid
import sys
import subprocess
import jieba  # Add this import at the top of the file
import MeCab
import unicodedata
from languages.japanese import Japanese
from languages.german import German
from languages.latin import Latin
from languages.oldenglish import OldEnglish
from languages.chinese import Chinese
from languages.persian import Persian
from languages.spanish import Spanish
from languages.portuguese import Portuguese
from languages.danish import Danish
from languages.french import French
from languages.italian import Italian
from languages.hindi import Hindi
from languages.hungarian import Hungarian
from morphology_simplifier import simplify_morphological_tag
# Define additional punctuation marks
ADDITIONAL_PUNCTUATION = '«»„"‹›''""-–—？，！。：；「」《》、：「」'
# Combine with standard punctuation
EXTENDED_PUNCTUATION = string.punctuation + ADDITIONAL_PUNCTUATION

wakati = MeCab.Tagger("-Owakati")


def run_automatic_verification(json_path, html_dir, text_name, starting_page=1):
    """
    Run automatic verification on both JSON and HTML outputs.
    This should be called after HTML generation completes.

    Args:
        json_path: Path to the source interlinear JSON file
        html_dir: Directory containing generated HTML files
        text_name: Base name for HTML files
        starting_page: Starting page number
    """
    print("\n" + "="*80)
    print("RUNNING AUTOMATIC POST-GENERATION VERIFICATION")
    print("="*80)

    # 1. Verify JSON data quality
    print("\n[1/2] JSON Verification")
    print("-" * 80)
    try:
        result = subprocess.run([
            sys.executable,
            "textcreation/comprehensive_verifier.py",
            json_path
        ], capture_output=True, text=True)
        print(result.stdout)
        if result.returncode != 0:
            print("⚠ JSON verification found issues")
            print("  → Consider running: python auto_fix_all_issues.py " + json_path)
    except Exception as e:
        print(f"⚠ Could not run JSON verifier: {e}")

    # 2. Verify HTML output quality
    print("\n[2/2] HTML Verification")
    print("-" * 80)
    try:
        result_html = subprocess.run([
            sys.executable,
            "verify_html.py",
            html_dir,
            json_path,
            text_name,
            str(starting_page)
        ], capture_output=True, text=True)
        print(result_html.stdout)
        if result_html.returncode != 0:
            print("⚠ HTML verification found issues")
            print("  → This may indicate problems with the HTML generation process")
    except Exception as e:
        print(f"⚠ Could not run HTML verifier: {e}")

    print("\n" + "="*80)
    print("VERIFICATION COMPLETE")
    print("="*80)


def normalize_greek(text):
    """
    Normalize Greek text by removing accents and converting to lowercase.
    This allows matching between accented/unaccented versions.
    """
    # NFD normalization separates base characters from combining marks
    nfd = unicodedata.normalize('NFD', text)
    # Filter out combining marks (category Mn = Mark, nonspacing)
    without_accents = ''.join(char for char in nfd if unicodedata.category(char) != 'Mn')
    # Convert to lowercase
    return without_accents.lower()

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

def processInterlinear(datalist, language='', pagebreak=10, verse_mode=False, use_unified=False):
    """
    Process interlinear data into HTML pages.

    Args:
        datalist: List of interlinear entries
        language: Language processing object
        pagebreak: Number of entries per page
        verse_mode: If True, handles chapter:verse references from 'verse' field
        use_unified: If True, uses the new unified processor (processSourceInterlinearUnified)
    """
    runninghtmls = []
    sentence_stores = []
    counter = 0
    #Before loop
    runninghtml = ""
    stracker = sentenceTracker()
    sentence_store = sentenceStore()

    current_sentence = datalist[0]['source']
    current_chapter = None

    #Loop through each entry
    for entry in datalist:
        # Handle verse mode (for biblical texts and philosophical propositions)
        if verse_mode and 'verse' in entry:
            verse_ref = entry['verse']  # e.g., "1:1" for Bible or "1.1" for Tractatus

            # Check if it's Bible format (with colon) or proposition format (with dots)
            if ':' in verse_ref:
                # Bible verse format: "chapter:verse"
                chapter, verse = verse_ref.split(':')

                # Add chapter heading if new chapter
                if chapter != current_chapter:
                    # If we're starting a new chapter and it's not the first chapter, trigger page break
                    if current_chapter is not None:
                        # Close current page and start new one BEFORE adding chapter heading
                        runninghtmls.append(runninghtml)
                        sentence_stores.append(sentence_store)
                        runninghtml = ""
                        sentence_store = sentenceStore()
                        counter = 0  # Reset counter for new page

                    # Add chapter heading to the NEW page (or first page if current_chapter is None)
                    runninghtml += f"""
                        </div>
                        <div class="chapter-heading">Chapter {chapter}</div>
                        <div class="word-group">"""
                    current_chapter = chapter

                # Add verse number before the verse text and line break after previous verse
                if verse != "1":  # Add line break before all verses except the first
                    runninghtml += '</div><div class="word-group">'
                runninghtml += f'<span class="verse-number">{verse}</span>'
            else:
                # Proposition format (e.g., "1", "1.1", "2.01") - treat top-level as chapters
                # Extract top-level proposition number (before first dot)
                top_level = verse_ref.split('.')[0]

                # Check if we've moved to a new top-level proposition
                if top_level != current_chapter:
                    # If we're starting a new top-level proposition and it's not the first, trigger page break
                    if current_chapter is not None:
                        # Close current page and start new one BEFORE adding chapter heading
                        runninghtmls.append(runninghtml)
                        sentence_stores.append(sentence_store)
                        runninghtml = ""
                        sentence_store = sentenceStore()
                        counter = 0  # Reset counter for new page

                    # Add chapter heading to the NEW page (or first page if current_chapter is None)
                    runninghtml += f"""
                        </div>
                        <div class="chapter-heading">Proposition {top_level}</div>
                        <div class="word-group">"""
                    current_chapter = top_level

                # Add proposition number before the proposition text and line break after previous
                # Don't add line break before the very first sub-proposition
                if '.' in verse_ref:  # Sub-propositions get line breaks
                    runninghtml += '</div><div class="word-group">'
                runninghtml += f'<span class="verse-number">{verse_ref}</span>'

        # normal languages
        #add, store = processSource(entry, stracker, language)
        # Use unified processor if requested, otherwise use legacy processors
        if use_unified:
            add, store = processSourceInterlinearUnified(entry, stracker, language)
        elif language.name.lower() in ['german', 'latin']:
            # Use simplified German processor for German/Latin to avoid punctuation doubling
            add, store = processSourceInterlinearGerman(entry, stracker, language)
        else:
            # japanese, chinese, etc.
            add, store = processSourceInterlinearFirstFixed(entry, stracker, language)
        # chinese
        # add, store = processSourceTextFirst(entry, stracker, language)
        #print(str(store.sentences))
        # check if the pattern \n\n\n\n\n\n all caps \n\n\n\n\n\n is in str(store.sentences) or if it has 2. 3. or 4.
        #Chapter Checker
        #if (re.search(r'\n\s*\n\s*\n\s*\n\s*([A-Z\s]+)\n\s*\n\s*\n\s*\n', entry['source']) or re.search(r'([2-9]\.\s+)', entry['source'])):
        if entry['source'] == "" or (entry['source'] and entry['source'].strip() == ""):
            # Blank source entries indicate chapter breaks - force page break
            if runninghtml:  # Only if we have content to save
                counter = pagebreak  # Force immediate page break
                runninghtml += """
                    </div>
                    <div class="word-group">"""
        if current_sentence != entry['source']:
            if current_sentence.endswith("\n") or entry['source'].startswith("\n"):
                runninghtml += """
                    </div>
                    <div class="word-group">"""
            current_sentence = entry['source']
        if counter == pagebreak:
            counter=0
            runninghtmls.append(runninghtml)
            sentence_stores.append(sentence_store)
            runninghtml = ""
            sentence_store = sentenceStore()
            # Reset chapter tracking for new page
            if verse_mode:
                current_chapter = None
        runninghtml += add
        sentence_store.sentences.update(store.sentences)
        sentence_store.wordMap.update(store.wordMap)

        # Don't increment counter for individual sentences - only for section breaks
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
        elif language == 'japanese':
            return ' '.join(wakati.parse(text).split())  # Using MeCab for Japanese
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


def processSourceInterlinearFirstFixed(entry, stracker, language):
    
    text = entry['source']
    translation = entry['translation']
    interlinear = entry['interlinear']
    speaker = entry['speaker'] if 'speaker' in entry else None
    parsinginfo = entry['parseinfo']
    if stracker.current_sentence != text:
        stracker.current_sentence = text
        stracker.increase()


    if speaker:
        runninghtml = f"""
                    </div> 
                    <div class="speaker">{speaker}</div>
                    <div class="word-group">"""

    else:
        runninghtml = ""

    sentence_store = sentenceStore()

    runningtext = entry['source']

    # Track punctuation that should be attached to words
    # Note: 　 is ideographic space (U+3000)
    chinese_punctuation = ['。', '，', '；', '？', '！', '：', '"', '"', ''', ''', '「', '」', '『', '』', '《', '》', '　', '、']
    
    # Store punctuation that appears before any words
    pending_start_punctuation = ""

    for gloss in interlinear:
        if len(gloss) < 2:
            continue
        gloss_word = gloss[0].strip()
        gloss_gloss = gloss[1]

        # Skip entries that are only punctuation and whitespace (quick fix for doubled punctuation in German/non-Chinese)
        # This preserves the complex Chinese punctuation handling below
        if gloss_word and all(not c.isalnum() for c in gloss_word):
            if language.name.lower() not in ['chinese', 'mandarin', 'cantonese']:
                print(f"Skipping punctuation-only gloss: '{gloss_word}'")
                continue

        sentence_id = stracker.sentence_id

        # Separate leading and trailing punctuation from the gloss word
        leading_punct = ""
        trailing_punct = ""
        gloss_word_core = gloss_word

        # Extract leading punctuation
        while gloss_word_core and gloss_word_core[0] in chinese_punctuation:
            leading_punct += gloss_word_core[0]
            gloss_word_core = gloss_word_core[1:]

        # Extract trailing punctuation
        while gloss_word_core and gloss_word_core[-1] in chinese_punctuation:
            trailing_punct = gloss_word_core[-1] + trailing_punct
            gloss_word_core = gloss_word_core[:-1]

        print(f"Processing gloss: '{gloss_word}' → core: '{gloss_word_core}', leading: '{leading_punct}', trailing: '{trailing_punct}'")

        # Create a mapping between normalized and original text positions
        char_map = []
        normalized_runningtext = ""

        # Use Greek normalization for Greek language
        is_greek = language.name.lower() in ['koine greek', 'ancient greek', 'greek']

        for i, char in enumerate(runningtext):
            if not (char.isspace() or char in EXTENDED_PUNCTUATION):
                if is_greek:
                    normalized_runningtext += normalize_greek(char)
                else:
                    normalized_runningtext += char.lower()
                char_map.append(i)

        # Normalize the gloss word (remove punctuation and spaces for matching)
        if is_greek:
            normalized_gloss = ''.join(normalize_greek(c) for c in gloss_word_core if not (c.isspace() or c in EXTENDED_PUNCTUATION))
        else:
            normalized_gloss = ''.join(c.lower() for c in gloss_word_core if not (c.isspace() or c in EXTENDED_PUNCTUATION))

        print(f"Normalized runningtext: '{normalized_runningtext[:50]}'")
        print(f"Normalized gloss: '{normalized_gloss}'")

        # Find the match in normalized text
        match_index = normalized_runningtext.find(normalized_gloss)
        
        if match_index != -1:
            # Get the actual position in the original text
            try:
                original_start_index = char_map[match_index]
                original_end_index = char_map[match_index + len(normalized_gloss) - 1] + 1
                
                # Extract the exact matching portion from the original text
                matched_original = runningtext[original_start_index:original_end_index]
                
                print(f"Found match: '{matched_original}' at positions {original_start_index}:{original_end_index}")
                
                # Extract the text before the match
                runningtext_before = runningtext[:original_start_index]
                if runningtext_before != "" and runningtext_before != "\n":
                    print(f"runningtext_before is {runningtext_before}")

                # Only create line breaks for actual line endings (punctuation followed by newline)
                if runningtext_before.strip() and (runningtext_before.endswith('，\n') or 
                                                   runningtext_before.endswith('。\n') or 
                                                   runningtext_before.endswith('；\n') or 
                                                   runningtext_before.endswith('？\n') or
                                                   runningtext_before.endswith('！\n')):
                    runninghtml += """
                    </div> 
                    <div class="word-group">"""
                
                # Process text before the current match
                elements = runningtext_before.split("\n")
                for element in elements:
                    if element == "":
                        pass  # Don't create line breaks for every empty element
                    else:
                        # Check if it's standalone punctuation
                        if element.strip() in chinese_punctuation or all(char in chinese_punctuation for char in element.strip()):
                            # Don't add to pending if it's the same as the current gloss's leading punctuation
                            # (this prevents doubling when punct appears in both runningtext and gloss)
                            if element.strip() == leading_punct:
                                print(f"Standalone punctuation '{element.strip()}' matches gloss leading punct - skipping")
                                continue
                            print(f"Standalone punctuation '{element.strip()}' found - adding to pending")
                            pending_start_punctuation += element.strip()
                            continue

                        # For other content, create word elements
                        if element.strip():
                            word_id = generate_word_id(element)
                            sentence_data = {
                                'source': text,
                                'translation': translation
                            }
                            runninghtml += getHTML(word=element, gloss="", word_id=word_id, sentence_id=sentence_id, language=language)
                            sentence_store.sentences[sentence_id] = sentence_data
                            sentence_store.wordMap[word_id] = sentence_id

                # After extracting the matched text, we need to also remove any punctuation
                # that was part of the original gloss but not part of gloss_word_core
                runningtext = runningtext[original_end_index:]

                print(f"runningtext after match removal: '{runningtext[:30]}...'")

                # Check if runningtext starts with leading punctuation that we extracted
                # (This handles cases where gloss has leading punct that was in runningtext)
                if leading_punct and runningtext.startswith(leading_punct):
                    print(f"Removing leading punctuation '{leading_punct}' from start of runningtext")
                    runningtext = runningtext[len(leading_punct):]

                # Check if runningtext starts with trailing punctuation that we extracted
                if trailing_punct and runningtext.startswith(trailing_punct):
                    print(f"Removing trailing punctuation '{trailing_punct}' from start of runningtext")
                    runningtext = runningtext[len(trailing_punct):]
                    print(f"runningtext after trailing punct removal: '{runningtext[:30]}...'")

                print(f"Final runningtext: '{runningtext[:30]}...'")


            except:
                print(f"Couldn't get match for gloss {gloss_word}")

        # Clean the gloss word for ID generation
        gloss_word_cleaned = ''.join(c for c in gloss_word_core if not (c.isspace() or re.match(r'[^\w\s]', c)))
        print(f"gloss_word_cleaned is {gloss_word_cleaned}")
        word_id = generate_word_id(gloss_word_cleaned)
        sentence_data = {
            'source': text,
            'translation': translation
        }

        #Get all words for the gloss
        grammar = ""
        dictionaryforms = ""
        pos = ""
        reading = ""
        words = language.parse_sent(gloss_word_core)
        for lookupword in words:
            if len(lookupword) > 4:
                grammar += lookupword[4]
            if len(lookupword) > 1:
                dictionaryforms += " " + lookupword[1]
            if len(lookupword) > 2:
                pos += " " + str(lookupword[2])
            if len(lookupword) > 3:
                reading += " " + str(lookupword[3])

        sentence_id = stracker.sentence_id
        word_id = generate_word_id(gloss_word_cleaned)
        sentence_data = {
            'source': text,
            'translation': translation
        }

        # Handle leading punctuation - this will be prepended to the current word, not attached to previous
        # We'll handle this when building actual_word below
        if leading_punct:
            print(f"Found leading punctuation: '{leading_punct}' - will attach to current word")

        # Check if gloss word core is empty (was only punctuation)
        if not gloss_word_core:
            # Pure punctuation entry - add it to pending so it attaches to next word
            if leading_punct:
                pending_start_punctuation += leading_punct
                print(f"Pure leading punctuation '{leading_punct}' added to pending")
            if trailing_punct:
                # If there's trailing punct but no core, attach it to the previous word
                last_word_start = runninghtml.rfind('<div class="word"')
                if last_word_start != -1:
                    tag_end = runninghtml.find('>', last_word_start) + 1
                    first_nested = runninghtml.find('<', tag_end)
                    if first_nested != -1:
                        word_text_section = runninghtml[tag_end:first_nested]
                        stripped = word_text_section.rstrip()
                        whitespace = word_text_section[len(stripped):]
                        new_section = stripped + trailing_punct + whitespace
                        runninghtml = runninghtml[:tag_end] + new_section + runninghtml[first_nested:]
                        print(f"Pure trailing punctuation '{trailing_punct}' attached to previous word")
            continue

        # Build the actual word to display
        actual_word = gloss_word_core

        # Apply any pending start punctuation to this word
        if pending_start_punctuation:
            print(f"Applying pending start punctuation '{pending_start_punctuation}' to word '{gloss_word_core}'")
            actual_word = pending_start_punctuation + actual_word
            pending_start_punctuation = ""  # Clear it after use

        # Apply leading punctuation from the gloss itself
        if leading_punct:
            print(f"Applying leading punctuation '{leading_punct}' to word '{gloss_word_core}'")
            actual_word = leading_punct + actual_word

        # Add the word to HTML
        runninghtml += getHTML(word=actual_word, gloss=gloss_gloss, word_id=word_id, sentence_id=sentence_id, language=language)
        sentence_store.sentences[sentence_id] = sentence_data
        sentence_store.wordMap[word_id] = sentence_id

        # Handle trailing punctuation - append it directly to the word in the HTML template
        if trailing_punct:
            print(f"Processing trailing punctuation: {trailing_punct}")
            # The word was just added via getHTML, which returns formatted HTML
            # We need to insert the punct into that HTML after {word_with_ruby} before the newline
            # Find the last </div> which closes the word div we just added
            last_close = runninghtml.rfind('</div>')
            if last_close != -1:
                # Go backwards from there to find our word div opening
                temp = runninghtml[:last_close]
                word_div_start = temp.rfind('<div class="word"')
                if word_div_start != -1:
                    # Find the > that closes the opening tag
                    tag_close = runninghtml.find('>', word_div_start) + 1
                    # Find the first < after that (start of nested div)
                    first_nested = runninghtml.find('<', tag_close)
                    if first_nested != -1:
                        # Get the text between tag close and first nested div
                        word_text_section = runninghtml[tag_close:first_nested]
                        # Strip trailing whitespace from word section, add punct, then add whitespace back
                        stripped = word_text_section.rstrip()
                        whitespace = word_text_section[len(stripped):]
                        new_section = stripped + trailing_punct + whitespace
                        runninghtml = runninghtml[:tag_close] + new_section + runninghtml[first_nested:]
                        print(f"Successfully attached trailing punctuation '{trailing_punct}' to current word")

        # Note: runningtext was already updated earlier to remove the matched core word.
        # Any leading/trailing punctuation from the gloss should also be removed from runningtext
        # if it's still there (this is handled above after the match)

    return runninghtml, sentence_store

def verify_interlinear_alignment(source, interlinear):
    """
    Verifies alignment between actual source and reconstructed interlinear source.
    Returns a detailed analysis of mismatches.

    Args:
        source: The actual source text
        interlinear: List of [word, gloss] pairs

    Returns:
        dict with keys:
            - 'matches': bool
            - 'source_length': int
            - 'interlinear_length': int
            - 'missing_chars': list of (position, char) tuples for chars in source but not interlinear
            - 'extra_chars': list of (position, char) tuples for chars in interlinear but not source
    """
    # Reconstruct interlinear source
    interlinear_source = ''.join([word[0] for word in interlinear if len(word) > 0])

    result = {
        'matches': source == interlinear_source,
        'source_length': len(source),
        'interlinear_length': len(interlinear_source),
        'missing_chars': [],
        'extra_chars': [],
        'source': source,
        'interlinear_source': interlinear_source
    }

    if result['matches']:
        return result

    # Character-by-character analysis
    from difflib import SequenceMatcher
    matcher = SequenceMatcher(None, source, interlinear_source)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'delete':
            # Characters in source but not in interlinear (missing chars)
            for i in range(i1, i2):
                result['missing_chars'].append((i, source[i]))
        elif tag == 'insert':
            # Characters in interlinear but not in source (extra chars)
            for j in range(j1, j2):
                result['extra_chars'].append((j, interlinear_source[j]))

    return result


def reconstruct_interlinear_with_alignment(source, interlinear, language):
    """
    Reconstructs interlinear entries by adding missing punctuation from source.

    Key insight: The LLM usually includes punctuation with words. We just need to:
    1. Match each interlinear word against the source (case-insensitive, accent-insensitive)
    2. Check if there's missing punctuation before/after the word in source
    3. Add missing punctuation to the word or as standalone entries
    4. Ignore regular spaces (handled by HTML rendering)

    Args:
        source: The actual source text
        interlinear: List of [word, gloss, ...] entries
        language: Language object

    Returns:
        List of [word, gloss, ...] entries with missing punctuation added
    """
    # Get verification analysis
    verification = verify_interlinear_alignment(source, interlinear)

    if verification['matches']:
        print("✓ Source and interlinear match perfectly")
        return interlinear

    # Check if the mismatch is catastrophic
    # Only check first words match - ignore missing_ratio since spaces aren't in interlinear
    if verification['source_length'] > 0:
        # Check if first few words match (word-level semantic check)
        source_words = source.strip().split()[:3]  # First 3 words
        # Skip <br> tags when extracting first words for comparison
        interlinear_first_words = [w[0] for w in interlinear if w and len(w) > 0 and w[0] != '<br>'][:3]

        # Normalize for comparison (including Unicode normalization for accents)
        import string
        source_normalized = ' '.join(source_words).lower()[:20]
        interlinear_normalized = ' '.join(interlinear_first_words).lower()[:20]

        # Apply NFD normalization to handle accent differences (cosí vs così)
        source_normalized = unicodedata.normalize('NFD', source_normalized)
        interlinear_normalized = unicodedata.normalize('NFD', interlinear_normalized)

        # Remove punctuation and combining marks for comparison
        source_alphanum = ''.join(c for c in source_normalized if (c.isalnum() or c.isspace()) and unicodedata.category(c) != 'Mn')
        interlinear_alphanum = ''.join(c for c in interlinear_normalized if (c.isalnum() or c.isspace()) and unicodedata.category(c) != 'Mn')

        # Check if they start similarly
        words_match = source_alphanum[:15] in interlinear_alphanum or interlinear_alphanum[:15] in source_alphanum

        # Only trigger catastrophic mismatch if first words don't match at all
        if not words_match and len(interlinear_first_words) > 0:
            print(f"⚠⚠⚠ CRITICAL: First words don't match!")
            print(f"  Source starts: {source_words}")
            print(f"  Interlinear starts: {interlinear_first_words}")
            print(f"  This entry has bad data - interlinear doesn't match source at all.")
            print(f"  Reconstructing from SOURCE to preserve original text.")

            # For catastrophic mismatches, create interlinear from source
            # Use regex to split on whitespace while keeping words with apostrophes/hyphens together
            import re

            # Split on whitespace, keeping everything else together
            tokens = source.split()
            result = []

            for token in tokens:
                if not token:
                    continue

                # Check if token ends with trailing punctuation
                trailing_punct = set('.,;:!?)]}»"' + '、。，；：！？」』》')
                leading_punct = set('([{«"' + '「『《¿¡')

                # Strip leading punctuation
                leading = ''
                while token and token[0] in leading_punct:
                    leading += token[0]
                    token = token[1:]

                # Strip trailing punctuation
                trailing = ''
                while token and token[-1] in trailing_punct:
                    trailing = token[-1] + trailing
                    token = token[:-1]

                # Add the word with punctuation attached
                if token:
                    word = leading + token + trailing
                    result.append([word, ""])
                elif leading or trailing:
                    # Pure punctuation
                    result.append([leading + trailing, ""])

            print(f"  Created {len(result)} entries from source text")
            return result

    print(f"⚠ Mismatch detected: source has {verification['source_length']} chars, "
          f"interlinear has {verification['interlinear_length']} chars")
    print(f"  Missing {len(verification['missing_chars'])} chars from interlinear")

    # Punctuation sets
    trailing_punct = set('.,;:!?)]}»"' + '、。，；：！？」』》')
    leading_punct = set('([{«"' + '「『《¿¡')

    # Walk through source and interlinear in parallel
    result = []
    source_pos = 0
    interlinear_idx = 0

    while interlinear_idx < len(interlinear):
        if len(interlinear[interlinear_idx]) == 0:
            interlinear_idx += 1
            continue

        entry = interlinear[interlinear_idx]
        word = entry[0]
        gloss = entry[1] if len(entry) > 1 else ""

        # Special handling for HTML tags like <br>
        if word == '<br>':
            # Treat as pure punctuation - don't try to find in source
            result.append(entry.copy())
            interlinear_idx += 1
            continue

        # Normalize word for matching (keep only alphanumeric, lowercase)
        # For Greek, use special normalization to remove accents
        if language and hasattr(language, 'name') and language.name.lower() in ['koine greek', 'ancient greek', 'greek']:
            word_normalized = ''.join(normalize_greek(c) for c in word if c.isalnum())
        else:
            # Use NFD normalization to handle accented characters (like ú -> u)
            word_nfd = unicodedata.normalize('NFD', word)
            # Keep only alphanumeric chars, exclude combining marks (Mn)
            word_normalized = ''.join(c.lower() for c in word_nfd if unicodedata.category(c) != 'Mn' and c.isalnum())

        if not word_normalized:
            # Pure punctuation/whitespace entry - copy it and skip past it in source
            result.append(entry.copy())

            # Try to find and skip this punctuation in the source to avoid duplicate processing
            punct_char = word.strip()
            if punct_char and source_pos < len(source):
                # Look ahead in source for this punctuation (allowing for whitespace)
                search_start = source_pos
                search_end = min(source_pos + 20, len(source))  # Look ahead up to 20 chars
                search_region = source[search_start:search_end]

                if punct_char in search_region:
                    # Find position of punctuation
                    punct_pos = search_region.find(punct_char)
                    # Skip to after the punctuation
                    source_pos = search_start + punct_pos + len(punct_char)
                    print(f"  → Skipped past '{punct_char}' in source (now at pos {source_pos})")

            interlinear_idx += 1
            continue

        # Find this word in source starting from source_pos
        # Build normalized source from current position
        source_remaining = source[source_pos:]
        source_normalized = ''
        char_map = []  # Maps normalized index -> original index

        is_greek = language and hasattr(language, 'name') and language.name.lower() in ['koine greek', 'ancient greek', 'greek']

        for i, c in enumerate(source_remaining):
            if c.isalnum():
                if is_greek:
                    source_normalized += normalize_greek(c)
                else:
                    # Use NFD to normalize accented characters
                    c_nfd = unicodedata.normalize('NFD', c)
                    for char in c_nfd:
                        if unicodedata.category(char) != 'Mn':
                            source_normalized += char.lower()
                char_map.append(i)

        # Find the word
        match_idx = source_normalized.find(word_normalized)

        if match_idx == -1:
            # Can't find word - this could be because:
            # 1. The word is missing from source (data quality issue)
            # 2. There's extra punctuation/whitespace in source that's not in interlinear
            # 3. The source has different formatting

            print(f"⚠ Warning: couldn't find '{word}' (normalized: '{word_normalized}') in source at pos {source_pos}")

            # First strategy: Check if there's just some leading punctuation/whitespace before the word
            # Look ahead a bit in the source to see if we can find the word nearby
            lookahead_limit = min(20, len(source_remaining))
            punct_prefix = ""
            found_after_punct = False

            for skip_chars in range(1, lookahead_limit):
                # Build normalized source starting from this offset
                test_remaining = source_remaining[skip_chars:]
                test_normalized = ''
                test_char_map = []

                for i, c in enumerate(test_remaining):
                    if c.isalnum():
                        if is_greek:
                            test_normalized += normalize_greek(c)
                        else:
                            c_nfd = unicodedata.normalize('NFD', c)
                            for char in c_nfd:
                                if unicodedata.category(char) != 'Mn':
                                    test_normalized += char.lower()
                        test_char_map.append(i)

                # Check if word matches at the START of this test string
                if test_normalized.startswith(word_normalized):
                    # Found it! Extract the punctuation/whitespace prefix
                    punct_prefix = source_remaining[:skip_chars]
                    found_after_punct = True
                    print(f"  → Found '{word}' after skipping prefix: {repr(punct_prefix)}")

                    # Add the prefix as unglossed standalone entries
                    for char in punct_prefix:
                        if char in ' \t\n':
                            continue  # Skip whitespace
                        else:
                            result.append([char, ""])
                            print(f"  → Added unglossed prefix: '{char}'")

                    # Update source_pos and rebuild char_map from new position
                    source_pos += skip_chars
                    source_remaining = source[source_pos:]
                    source_normalized = test_normalized
                    char_map = test_char_map
                    match_idx = 0  # Now it matches at the start
                    break

            if not found_after_punct:
                # Second strategy: The word truly isn't in source
                # Look for where interlinear resumes in source
                next_word_found = False
                next_match_pos = source_pos

                # Look at next few interlinear words to find something in the source
                for lookahead_offset in range(1, min(5, len(interlinear) - interlinear_idx)):
                    next_entry = interlinear[interlinear_idx + lookahead_offset]
                    next_word = next_entry[0]

                    if next_word == '<br>':
                        continue

                    # Normalize next word
                    next_word_nfd = unicodedata.normalize('NFD', next_word)
                    next_word_normalized = ''.join(c.lower() for c in next_word_nfd
                                                   if unicodedata.category(c) != 'Mn' and c.isalnum())

                    if not next_word_normalized:
                        continue

                    # Try to find it in source
                    next_match = source_normalized.find(next_word_normalized)
                    if next_match != -1:
                        next_match_pos = source_pos + char_map[next_match]
                        next_word_found = True
                        print(f"  → Found next word '{next_word}' at pos {next_match_pos} (word truly missing from source)")
                        break

                if next_word_found and next_match_pos > source_pos:
                    # The current word is genuinely missing - add it with gloss but note it's from interlinear
                    result.append([word, gloss])
                    print(f"  → Added missing word from interlinear: '{word}'")
                    source_pos = next_match_pos  # Jump to where source resumes
                    interlinear_idx += 1
                    continue
                else:
                    # Complete fallback: extract by length
                    extract_length = len(word)
                    if source_pos + extract_length <= len(source):
                        source_fragment = source[source_pos:source_pos + extract_length]
                        result.append([source_fragment, gloss])
                        source_pos += extract_length
                    else:
                        result.append(entry.copy())  # Fixed: append the entry directly, not wrapped in another list

                    interlinear_idx += 1
                    continue

            # If we found it after punctuation, continue with normal processing below
            if not found_after_punct:
                interlinear_idx += 1
                continue

        # Get actual positions in source
        actual_start = source_pos + char_map[match_idx]
        actual_end = source_pos + char_map[min(match_idx + len(word_normalized) - 1, len(char_map) - 1)] + 1

        # Check if match is unusually far ahead (potential false match)
        distance = actual_start - source_pos
        if distance > 50:  # More than 50 chars ahead
            print(f"⚠ WARNING: Found '{word}' at distance {distance} chars ahead (pos {source_pos} → {actual_start})")
            print(f"           This may be a false match. Source context: {repr(source[actual_start:actual_start+20])}")

        # Extract the word as it appears in source (with original case)
        source_word = source[actual_start:actual_end]

        # Check for content BEFORE the word
        before_content = source[source_pos:actual_start]

        # Process "before" content
        # First, count consecutive newlines for br tag insertion
        newline_count = 0
        i = 0
        while i < len(before_content) and before_content[i] in '\n \t':
            if before_content[i] == '\n':
                newline_count += 1
            i += 1

        # If 2+ newlines, add br markers (for chapter titles, section breaks)
        if newline_count >= 2:
            # Add (newline_count - 1) br tags as standalone entries
            for _ in range(newline_count - 1):
                result.append(['<br>', ''])
            print(f"  → Added {newline_count - 1} <br> tags for visual break")

        for c in before_content:
            if c == ' ' or c == '\t' or c == '\n':
                # Spaces and newlines - already handled above
                continue
            elif c in trailing_punct:
                # Trailing punct should attach to PREVIOUS word
                if result and c not in result[-1][0]:
                    result[-1][0] = result[-1][0] + c
                    print(f"  → Attached '{c}' to previous word: {result[-1][0]}")
            elif c in leading_punct:
                # Leading punct should attach to CURRENT word
                if c not in source_word:
                    source_word = c + source_word
                    print(f"  → Prepended '{c}' to current word")
            elif c == '\u3000':  # Ideographic space
                # Can be ignored like regular space
                continue
            else:
                # Other characters (brackets, numbers, etc.) - add as standalone
                result.append([c, ""])
                print(f"  → Added standalone: '{c}'")

        # Check for trailing punctuation AFTER the word in source
        check_pos = actual_end
        while check_pos < len(source) and not source[check_pos].isalnum() and source[check_pos] not in ' \t\n\u3000':
            c = source[check_pos]
            if c in trailing_punct and c not in source_word:
                # Add trailing punct to word
                source_word += c
                actual_end = check_pos + 1
                print(f"  → Appended '{c}' to current word")
            elif c in leading_punct:
                # This would be leading for NEXT word, stop here
                break
            else:
                # Other punct - might be standalone, check next iteration
                break
            check_pos += 1

        # Keep the original interlinear entry (with gloss preserved)
        # Only use source_word if there's a meaningful difference (added punctuation)
        # The interlinear word already has the core word + any attached punctuation
        result.append(entry.copy())

        # Move forward
        source_pos = actual_end
        interlinear_idx += 1

    # Handle remaining content at end of source
    if source_pos < len(source):
        remaining = source[source_pos:]
        if remaining.strip():  # Only if there's non-whitespace content
            print(f"  ⚠ Remaining source content not in interlinear ({len(remaining)} chars): {repr(remaining[:100])}")

            # Split remaining content into words and add as unglossed
            words_in_remaining = []
            current_word = ""
            for char in remaining:
                if char in ' \t\n':
                    if current_word:
                        words_in_remaining.append(current_word)
                        current_word = ""
                else:
                    current_word += char
            if current_word:
                words_in_remaining.append(current_word)

            # Add these words as unglossed entries
            for unglossed_word in words_in_remaining:
                if len(unglossed_word.strip()) > 0:
                    result.append([unglossed_word, ""])
                    print(f"    → Added unglossed from remaining: '{unglossed_word}'")

    return result


def processSourceInterlinearUnified(entry, stracker, language):
    """
    Universal interlinear processor that handles all languages correctly.

    This function:
    1. Verifies alignment between source and interlinear
    2. Reconstructs interlinear with missing punctuation/whitespace
    3. Processes each entry to generate HTML with proper attachments

    Works for all languages: Chinese, Japanese, German, Latin, Greek, etc.
    """
    text = entry['source']
    translation = entry['translation']
    interlinear = entry['interlinear']
    speaker = entry['speaker'] if 'speaker' in entry else None
    parsinginfo = entry['parseinfo'] if 'parseinfo' in entry else []

    if stracker.current_sentence != text:
        stracker.current_sentence = text
        stracker.increase()

    if speaker:
        runninghtml = f"""
                    </div>
                    <div class="speaker">{speaker}</div>
                    <div class="word-group">"""
    else:
        runninghtml = ""

    sentence_store = sentenceStore()
    sentence_id = stracker.sentence_id

    # Step 1: Reconstruct interlinear with proper alignment
    aligned_interlinear = reconstruct_interlinear_with_alignment(text, interlinear, language)

    # Step 2: Process each entry
    for entry_idx, entry_data in enumerate(aligned_interlinear):
        if len(entry_data) == 0:
            continue

        word = entry_data[0]
        gloss = entry_data[1] if len(entry_data) > 1 else ""

        # Skip empty entries
        if not word:
            continue

        # Special case: <br> tags for visual breaks (chapter titles, etc.)
        if word == '<br>':
            runninghtml += '<br>\n'
            continue

        # Check if this is a pure punctuation/whitespace entry
        is_pure_punct = all(not c.isalnum() for c in word)

        # Generate word ID
        word_cleaned = ''.join(c for c in word if c.isalnum())

        if is_pure_punct and not word_cleaned:
            # Pure punctuation with no alphanumeric characters
            # These are standalone elements like '[', numbers, etc.
            # We should display them, not skip them
            # Create a minimal HTML entry for display
            word_id = generate_word_id(word + str(uuid.uuid4()))
            sentence_data = {
                'source': text,
                'translation': translation
            }

            # Create simple HTML for standalone punctuation
            runninghtml += f"""
    <div class="word" title="" data-word-id="{word_id}" data-sentence-id="{sentence_id}">
        {word}
        <div class="gloss">{gloss}</div>
        <div class="alt"></div>
        <div class="pos"></div>
        <div class="reading"></div>
        <div class="grammar"></div>
        <div class="dictionary"></div>
    </div>
    """
            sentence_store.sentences[sentence_id] = sentence_data
            sentence_store.wordMap[word_id] = sentence_id
            continue

        if not word_cleaned:
            # Pure whitespace - skip
            continue

        word_id = generate_word_id(word_cleaned)
        sentence_data = {
            'source': text,
            'translation': translation
        }

        # Get parsing information
        grammar = ""
        dictionaryforms = ""
        pos = ""
        reading = ""

        # Try to find parseinfo for this word
        word_for_parsing = ''.join(c for c in word if c.isalnum())
        parseinfo_entry = None

        # Check if language is Greek to use proper normalization
        is_greek = language.name.lower() in ['koine greek', 'ancient greek', 'greek']

        if parsinginfo:
            for parse_entry in parsinginfo:
                if len(parse_entry) > 0:
                    if is_greek:
                        # For Greek, normalize to remove accents
                        word_normalized = normalize_greek(word_for_parsing)
                        parse_normalized = normalize_greek(parse_entry[0])
                        if word_normalized == parse_normalized:
                            parseinfo_entry = parse_entry
                            break
                    else:
                        # For other languages, simple case-insensitive match
                        parse_word = ''.join(c for c in parse_entry[0] if c.isalnum())
                        if parse_word.lower() == word_for_parsing.lower():
                            parseinfo_entry = parse_entry
                            break

        if parseinfo_entry:
            # parseinfo structure: [normalized_word, lemma, pos, grammar_dict_string]
            if len(parseinfo_entry) > 3:
                grammar = parseinfo_entry[3] if parseinfo_entry[3] else ""
            if len(parseinfo_entry) > 1:
                dictionaryforms = parseinfo_entry[1] if parseinfo_entry[1] else ""
            if len(parseinfo_entry) > 2:
                pos = str(parseinfo_entry[2]) if parseinfo_entry[2] else ""
            # reading is not stored in parseinfo for Greek/Latin
        else:
            # Parse using language parser
            try:
                words = language.parse_sent(word_for_parsing)
                for lookupword in words:
                    if len(lookupword) > 4:
                        grammar += lookupword[4]
                    if len(lookupword) > 1:
                        dictionaryforms += " " + lookupword[1]
                    if len(lookupword) > 2:
                        pos += " " + str(lookupword[2])
                    if len(lookupword) > 3:
                        reading += " " + str(lookupword[3])
            except:
                pass  # No parsing info available

        # Generate HTML
        # parseinfo structure for getHTML: [word, lemma, pos, grammar]
        runninghtml += getHTML(
            word=word,
            gloss=gloss,
            word_id=word_id,
            sentence_id=sentence_id,
            language=language,
            parseinfo=[(word_for_parsing, dictionaryforms.strip(), pos.strip(), grammar)] if grammar or dictionaryforms else None
        )

        sentence_store.sentences[sentence_id] = sentence_data
        sentence_store.wordMap[word_id] = sentence_id

    # After processing all words, check if source ends with multiple newlines (chapter title case)
    # Count trailing newlines in source
    trailing_newlines = 0
    for i in range(len(text) - 1, -1, -1):
        if text[i] == '\n':
            trailing_newlines += 1
        elif text[i] not in ' \t':
            break

    # If there are 2+ newlines, add <br> tags to create visual separation
    if trailing_newlines >= 2:
        runninghtml += '<br>' * (trailing_newlines - 1)

    return runninghtml, sentence_store


def processSourceInterlinearGerman(entry, stracker, language):
    """
    Simplified interlinear processing for German/Latin languages.
    Skips standalone punctuation entries to avoid doubling.
    """
    text = entry['source']
    translation = entry['translation']
    interlinear = entry['interlinear']
    speaker = entry['speaker'] if 'speaker' in entry else None
    parsinginfo = entry['parseinfo']

    if stracker.current_sentence != text:
        stracker.current_sentence = text
        stracker.increase()

    if speaker:
        runninghtml = f"""
                    </div>
                    <div class="speaker">{speaker}</div>
                    <div class="word-group">"""
    else:
        runninghtml = ""

    sentence_store = sentenceStore()
    sentence_id = stracker.sentence_id

    # Process each gloss entry
    for gloss in interlinear:
        if len(gloss) < 2:
            continue

        gloss_word = gloss[0].strip()
        gloss_gloss = gloss[1]

        # Skip entries that are ONLY punctuation (even with spaces)
        # This is the key fix for German - we don't want standalone comma entries
        if not gloss_word or all(not c.isalnum() for c in gloss_word):
            print(f"Skipping punctuation-only entry: '{gloss_word}'")
            continue

        # Generate word ID from alphanumeric characters only
        gloss_word_cleaned = ''.join(c for c in gloss_word if c.isalnum())
        if not gloss_word_cleaned:
            print(f"Skipping empty cleaned word from: '{gloss_word}'")
            continue

        word_id = generate_word_id(gloss_word_cleaned)
        sentence_data = {
            'source': text,
            'translation': translation
        }

        # Get parsing information
        grammar = ""
        dictionaryforms = ""
        pos = ""
        reading = ""

        # Parse the word (without punctuation for parsing)
        # Use the existing parseinfo if available to avoid re-parsing
        core_word = ''.join(c for c in gloss_word if c.isalnum())
        if core_word and parsinginfo:
            # Try to find this word in the parseinfo
            for parse_entry in parsinginfo:
                if len(parse_entry) > 0 and parse_entry[0] == core_word:
                    if len(parse_entry) > 4:
                        grammar = parse_entry[4]
                    if len(parse_entry) > 1:
                        dictionaryforms = parse_entry[1]
                    if len(parse_entry) > 2:
                        pos = str(parse_entry[2])
                    if len(parse_entry) > 3:
                        reading = str(parse_entry[3])
                    break

        # Add the word with its original punctuation
        runninghtml += getHTML(word=gloss_word, gloss=gloss_gloss, word_id=word_id, sentence_id=sentence_id, language=language, parseinfo=(core_word, dictionaryforms.strip(), pos.strip(), reading.strip(), grammar))
        sentence_store.sentences[sentence_id] = sentence_data
        sentence_store.wordMap[word_id] = sentence_id

    return runninghtml, sentence_store

def processSourceInterlinearFirst(entry, stracker, language):
    
    text = entry['source']
    translation = entry['translation']
    interlinear = entry['interlinear']
    speaker = entry['speaker'] if 'speaker' in entry else None
    parsinginfo = entry['parseinfo']
    if stracker.current_sentence != text:
        stracker.current_sentence = text
        stracker.increase()


    if speaker:
        runninghtml = f"""
                    </div> 
                    <div class="speaker">{speaker}</div>
                    <div class="word-group">"""

    else:
        runninghtml = ""

    sentence_store = sentenceStore()

    runningtext = entry['source']

    for gloss in interlinear:
        if len(gloss) < 2:
            continue
        gloss_word = gloss[0].strip()
        print(f"gloss is {gloss}")
        gloss_gloss = gloss[1]

        sentence_id = stracker.sentence_id

        # Create a mapping between normalized and original text positions
        char_map = []
        normalized_runningtext = ""
        
        for i, char in enumerate(runningtext):
            if not (char.isspace() or re.match(r'[^\w\s]', char)):
                normalized_runningtext += char
                char_map.append(i)
        
        # Normalize the gloss word
        normalized_gloss = ''.join(c for c in gloss_word if not (c.isspace() or re.match(r'[^\w\s]', c)))
        
        # Find the match in normalized text
        match_index = normalized_runningtext.find(normalized_gloss)
        
        if match_index != -1:
            # Get the actual position in the original text
            try:
                original_start_index = char_map[match_index]
                original_end_index = char_map[match_index + len(normalized_gloss) - 1] + 1
                
                # Extract the exact matching portion from the original text
                matched_original = runningtext[original_start_index:original_end_index]
                
                print(f"Found match: '{matched_original}' at positions {original_start_index}:{original_end_index}")
                
                # Extract the text before the match
                runningtext_before = runningtext[:original_start_index]
                if runningtext_before != "" and runningtext_before != "\n":
                    print(f"runningtext_before is {runningtext_before}")

                # Only create line breaks for actual line endings (punctuation followed by newline)
                if runningtext_before.strip() and (runningtext_before.endswith('，\n') or 
                                                   runningtext_before.endswith('。\n') or 
                                                   runningtext_before.endswith('；\n') or 
                                                   runningtext_before.endswith('？\n') or
                                                   runningtext_before.endswith('！\n')):
                    runninghtml += """
                    </div> 
                    <div class="word-group">"""
                elements = runningtext_before.split("\n")
                for element in elements:
                    if element == "":
                        pass  # Don't create line breaks for every empty element
                    else:
                        if element in EXTENDED_PUNCTUATION or element.strip() in EXTENDED_PUNCTUATION or all(char in EXTENDED_PUNCTUATION for char in element.strip()):
                            print(f"Adding unmatched punctuation: {element}")
                            continue
                            
                            # Check if this is the first item in runninghtml (no word divs yet)
                            if '<div class="word"' not in runninghtml:
                                runninghtml += element
                            else:
                                # Find the last word div and append punctuation to its main word content
                                # Find the last occurrence of word div opening tag
                                last_word_start = runninghtml.rfind('<div class="word"')
                                
                                if last_word_start != -1:
                                    # Find the end of the opening tag
                                    tag_end = runninghtml.find('>', last_word_start)
                                    
                                    if tag_end != -1:
                                        # Find the first nested div (which contains the gloss)
                                        first_nested_div = runninghtml.find('<div class="gloss">', tag_end)
                                        
                                        if first_nested_div != -1:
                                            # Insert the punctuation right before the first nested div
                                            runninghtml = runninghtml[:first_nested_div] + element + runninghtml[first_nested_div:]
                                        else:
                                            # Fallback: just add to runninghtml if structure is unexpected
                                            runninghtml += element
                                    else:
                                        # Fallback: just add to runninghtml if pattern doesn't match
                                        runninghtml += element
                                else:
                                    # Fallback: just add to runninghtml if no word div found
                                    runninghtml += element
                            continue
                        word_id = generate_word_id(runningtext_before)
                        sentence_data = {
                            'source': text,
                            'translation': translation
                        }
                        runninghtml += getHTML(word=element, gloss="", word_id=word_id, sentence_id=sentence_id, language=language)
                        sentence_store.sentences[sentence_id] = sentence_data
                        sentence_store.wordMap[word_id] = sentence_id

                runningtext = runningtext[original_end_index:]
            except:
                print(f"Couldn't get match for gloss {gloss_word}")

        gloss_word_cleaned = ''.join(c for c in gloss_word if not (c.isspace() or re.match(r'[^\w\s]', c)))
        print(f"gloss_word_cleaned is {gloss_word_cleaned}")
        word_id = generate_word_id(gloss_word_cleaned)
        sentence_data = {
            'source': text,
            'translation': translation
        }

        #Get all words for the gloss
        grammar = ""
        dictionaryforms = ""
        pos = ""
        reading = ""
        words = language.parse_sent(gloss_word)
        for lookupword in words:
            if len(lookupword) > 4:
                grammar += lookupword[4]
            if len(lookupword) > 1:
                dictionaryforms += " " + lookupword[1]
            if len(lookupword) > 2:
                pos += " " + str(lookupword[2])
            if len(lookupword) > 3:
                reading += " " + str(lookupword[3])


        sentence_id = stracker.sentence_id
        word_id = generate_word_id(gloss_word_cleaned)
        sentence_data = {
            'source': text,
            'translation': translation
        }

        if gloss_word in EXTENDED_PUNCTUATION or gloss_word.strip() in EXTENDED_PUNCTUATION:
            print(f"Adding unmatched punctuation: {gloss_word}")

            # Check if this is the first item in runninghtml (no word divs yet)
            if '<div class="word"' not in runninghtml:
                runninghtml += gloss_word
            else:
                # Find the last word div and append punctuation to its main word content
                # Find the last occurrence of word div opening tag
                last_word_start = runninghtml.rfind('<div class="word"')

                if last_word_start != -1:
                    # Find the end of the opening tag
                    tag_end = runninghtml.find('>', last_word_start)

                    if tag_end != -1:
                        # Find the first nested div (which contains the gloss)
                        first_nested_div = runninghtml.find('<div class="gloss">', tag_end)

                        if first_nested_div != -1:
                            # Insert the punctuation right before the first nested div
                            runninghtml = runninghtml[:first_nested_div] + gloss_word + runninghtml[first_nested_div:]
                        else:
                            # Fallback: just add to runninghtml if structure is unexpected
                            runninghtml += gloss_word
                    else:
                        # Fallback: just add to runninghtml if pattern doesn't match
                        runninghtml += gloss_word
                else:
                    # Fallback: just add to runninghtml if no word div found
                    runninghtml += gloss_word
            continue

        # Find matching parseinfo for this word (match by normalized form)
        word_parseinfo = None
        if parsinginfo:
            normalized_gloss_word = normalize_greek(gloss_word_core) if is_greek else gloss_word_core.lower()
            for parse_entry in parsinginfo:
                if len(parse_entry) > 0:
                    parse_word = normalize_greek(parse_entry[0]) if is_greek else parse_entry[0].lower()
                    if parse_word == normalized_gloss_word:
                        word_parseinfo = [parse_entry]  # Wrap in list for compatibility
                        break

        runninghtml += getHTML(word=gloss_word, gloss=gloss_gloss, word_id=word_id, sentence_id=sentence_id, language=language, parseinfo=word_parseinfo)
        sentence_store.sentences[sentence_id] = sentence_data
        sentence_store.wordMap[word_id] = sentence_id

        # For Greek, try to remove the word from runningtext using normalized matching
        if is_greek:
            # Find and remove the matched word from runningtext using normalized comparison
            normalized_remaining = normalize_greek(runningtext)
            normalized_gloss_word = normalize_greek(gloss_word)

            # Try to find the word in the remaining text
            pos = normalized_remaining.find(normalized_gloss_word)
            if pos != -1:
                # Count actual characters (not normalized) up to this position
                actual_pos = 0
                norm_count = 0
                for char in runningtext:
                    if not (char.isspace() or char in EXTENDED_PUNCTUATION):
                        if norm_count == pos:
                            break
                        norm_count += 1
                    actual_pos += 1

                # Find the length in the original text
                actual_end = actual_pos
                norm_count = 0
                for char in runningtext[actual_pos:]:
                    if not (char.isspace() or char in EXTENDED_PUNCTUATION):
                        norm_count += 1
                        if norm_count >= len(normalized_gloss_word):
                            actual_end = actual_pos + len(runningtext[actual_pos:actual_pos + norm_count])
                            break
                    actual_end += 1

                runningtext = runningtext[:actual_pos] + runningtext[actual_end:]
        else:
            # Original logic for non-Greek languages
            runningtext = re.sub(r'^' + re.escape(gloss_word), '', runningtext)

    return runninghtml, sentence_store

def getHTML(word, gloss, word_id, sentence_id, language, parseinfo=None):
    #Get all words for the gloss
    grammar = ""
    dictionaryforms = ""
    pos = ""

    # Use provided parseinfo if available, otherwise parse the word
    if parseinfo:
        words = parseinfo
    else:
        words = language.parse_sent(word)

    for lookupword in words:
        if len(lookupword) > 3:
            grammar += lookupword[3]  # Morphology is at index 3
        if len(lookupword) > 1:
            dictionaryforms += " " + lookupword[1]
        if len(lookupword) > 2:
            pos += " " + str(lookupword[2])

    # Generate ruby markup using kakashi
    if language.name == "japanese":
        word_with_ruby = ""
        tokens = language.get_readings(word)  # Returns list of (kanji, kana) pairs
        for kanji, kana in tokens:
            if language.is_kanji_compound(kanji):
                word_with_ruby += f'<ruby>{kanji}<rt>{kana}</rt></ruby>'
            else:
                word_with_ruby += kanji
    else:
        word_with_ruby = word

    # Get pinyin for Chinese
    if language.name == "chinese":
        reading = language.get_readings(word)
    else:
        reading = ""

    # Simplify grammatical info for Latin and Greek
    is_greek = language.name.lower() in ['koine greek', 'ancient greek', 'greek']
    if language.name == "latin" or is_greek:
        # Only simplify if grammar exists and is not empty/trivial
        if grammar and grammar.strip() and grammar.strip() != '{}':
            simplified_grammar = simplify_morphological_tag(grammar)
            # Store full grammar in title, simplified in reading for display
            reading = simplified_grammar if simplified_grammar else ""
        else:
            reading = ""


    # For Greek/Latin, use grammar field instead of reading
    grammar_display = ""
    if (language.name == "latin" or is_greek) and reading:
        grammar_display = reading
        reading = ""  # Clear reading for Greek/Latin

    addhtml = f"""
    <div class="word" title="{grammar}" data-word-id="{word_id}" data-sentence-id="{sentence_id}">
        {word_with_ruby}
        <div class="gloss">{gloss}</div>
        <div class="alt">{""}</div>
        <div class="pos">{pos}</div>
        <div class="reading">{reading}</div>
        <div class="grammar">{grammar_display}</div>
        <div class="dictionary">{dictionaryforms}</div>
    </div>
    """

    return addhtml

def processSource(entry, stracker, language=''):
    runninghtml = ""
    text = entry['source']
    translation = entry['translation']
    interlinear = entry['interlinear']
    parsinginfo = entry['parseinfo']

    if stracker.current_sentence != text:
        stracker.current_sentence = text
        stracker.increase()
        runninghtml = """
                </div> 
                <div class="word-group">"""

    sentence_store = sentenceStore()
    # Regex pattern with capturing groups:
    # (\w+\b[^\s\w]*) captures a sequence of word characters followed by optional non-word, non-whitespace characters.
    # (\s+) captures at least one whitespace character, including newlines

    # Wow so hacky
    text = text.replace("'", "653")
    text = text.replace("'", "653")
    
    pattern = r'(\w+\b[^\s\w]*)|(\s+)'

    def segment_text(text, language=''):
        """Helper function to segment text based on language"""
        if language == 'chinese':
            # Convert the list to a space-separated string for consistent processing
            return ' '.join(jieba.cut(text))
        # Add other language handlers here as needed:
        elif language == 'japanese':
            return ' '.join(wakati.parse(text).split())  # Using MeCab for Japanese
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
            elif element in EXTENDED_PUNCTUATION:
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
                while interlinear and len(interlinear) > 0 and len(interlinear[0][0].strip()) == 0:
                    interlinear.pop(0)
                if interlinear and len(interlinear) == 0:
                    print("No interlinear gloss found for word " + word)
                    element_counter += 1
                    continue

                if interlinear and len(interlinear) > 0:
                
                    gloss = interlinear[0]
                    gloss_word = gloss[0].strip()
                    gloss_no_punct = ''.join(c for c in gloss_word if c.isalnum())
                    print(f"gloss_no_punct is {gloss_no_punct} and word_no_punct is {word_no_punct}")
                    # If the cleaned word contains the cleaned gloss and they're not identical
                    if len(gloss_no_punct) < len(word_no_punct) and len(gloss_no_punct) > 0 and gloss_no_punct in word_no_punct and gloss_no_punct != word_no_punct:
                        print("Found gloss " + gloss_word + " for word " + word)
                        # Update word to be the gloss unit instead
                        word = gloss_word
                        if len(gloss) > 1:
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
                                    # Just pop the specific gloss at index j instead of multiple glosses
                                    interlinear.pop(j)
                                    
                                except:
                                    print(f"Couldn't get gloss for word {word}")
                                break

                #Get all words for the gloss
                grammar = ""
                dictionaryforms = ""
                pos = ""
                reading = ""
                words = word.split(" ")
                for lookupword in words:
                    for pindex, parse in enumerate(parsinginfo):
                        if string_similarity_normal(lookupword, parse[0]) > stringthreshhold:
                            grammar += parse[3]
                            dictionaryforms += " " + str(parse[1])
                            pos += " " + str(parse[2])
                            #reading += " " + str(parse[4])
                            parsinginfo.pop(pindex)
                            break

                if reading != "":
                    interlinearlit = reading
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


def write_html_interlinear(jsonfile, htmltemplate, dir, textname, title, description, language, starting_page=1, pagebreak=10, total_pages=None, limit_entries=None, verse_mode=False, use_unified=False):
    """
    Write HTML interlinear pages from JSON data.

    Args:
        jsonfile: Path to JSON file with interlinear data
        htmltemplate: Path to HTML template file
        dir: Directory to write output files
        textname: Name of the text (used for filenames)
        title: Title for the HTML pages
        description: Description for the HTML pages
        language: Language processing object
        starting_page: Page number to start from (chapter number in verse_mode)
        pagebreak: Number of entries per page (ignored in verse_mode with one chapter per page)
        total_pages: Total number of pages (if known)
        limit_entries: Limit processing to first N entries
        verse_mode: If True, handles chapter:verse structure from 'verse' field (one chapter per page)
        use_unified: If True, uses the new unified processor for all languages
    """
    # normal languages
    data = getJSON(jsonfile)
    if limit_entries:
        data = data[:limit_entries]

    # In verse mode, set pagebreak very high so chapters trigger page breaks
    if verse_mode:
        pagebreak = 999999  # Effectively unlimited - only chapter changes trigger page breaks

    interlineartexts, sentence_stores = processInterlinear(data, language, pagebreak, verse_mode=verse_mode, use_unified=use_unified)

    # Load original data to get translations
    original_data = getJSON(jsonfile)

    html_template = open(htmltemplate, 'r').read()
    # enumerate starts at 1
    for i, interlineartext in enumerate(interlineartexts, starting_page):
        htmltext = html_template.replace("{{interlinear}}", interlineartext)
        htmltext = htmltext.replace("{{Title}}", title, -1)
        htmltext = htmltext.replace("{{Description}}", description)

        # Add full translation if template supports it
        if "{{full_translation}}" in html_template:
            # Get the translation for this page
            page_index = i - starting_page
            if page_index < len(original_data):
                full_translation = original_data[page_index]['translation']
                # Format the translation with proper line breaks
                formatted_translation = full_translation.replace('\n', '<br>')
                htmltext = htmltext.replace("{{full_translation}}", formatted_translation)
            else:
                htmltext = htmltext.replace("{{full_translation}}", "")

        page_info = '<meta name="page_number" content="' + str(i) + '">'
        # Use total_pages if provided, otherwise fall back to length of current text
        max_pages = total_pages if total_pages is not None else len(interlineartexts) + starting_page - 1
        if i < max_pages:
            page_info += '<meta name="next_page" content="' + str(i+1) + '">'
        if i > 1:
            page_info += '<meta name="previous_page" content="' + str(i-1) + '">'
        page_info += '<meta name="sentence_store" content="' + textname + '_' + str(i) + '">'
        htmltext = htmltext.replace("{{page_info}}", page_info)
        with open(dir + textname + "/" + textname + "_" + str(i) + ".html", 'w', encoding='utf-8') as file:
            file.write(htmltext)
        with open(dir + textname + "/sentence_stores/" + textname + "_" + str(i) + ".json", 'w') as file:
            sentence_store_dict = {}
            sentence_store_dict['sentences'] = sentence_stores[i-starting_page].sentences
            sentence_store_dict['wordMap'] = sentence_stores[i-starting_page].wordMap
            json.dump(sentence_store_dict, file)

        print("Wrote page " + str(i))
        # Write one file for each page, first sentence of each page has /n/n/n/n/n

# Load the full Tang poems data
# TEST: Process just a few entries to verify punctuation fixes
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        print("TEST MODE: Processing entry 84 (page 40) with the punctuation issue")
        data = getJSON("textcreation/texts/interlinearouts/interlinear_redchamberch4.json")
        test_data = [data[84]]  # Entry 84 has the 說：『我 issue

        # Write test data to temp file
        import json
        with open("textcreation/texts/interlinearouts/test_redchamber.json", "w") as f:
            json.dump(test_data, f)

        write_html_interlinear("textcreation/texts/interlinearouts/test_redchamber.json", "textcreation/texts/templates/readingtemplate.html", "app/templates/texts/", "redchamber_test", "Dream of the Red Chamber", "Dream of the Red Chamber Chapter 4", Chinese(), starting_page=40, pagebreak=1, total_pages=40)
        print("✓ Test complete! Check app/templates/texts/redchamber_test/redchamber_test_40.html")
    elif len(sys.argv) > 1 and sys.argv[1] == "--mark":
        print("GOSPEL OF MARK MODE: Processing Gospel of Mark with chapter/verse structure")
        from languages.greek import KoineGreek

        # Process Gospel of Mark with verse mode enabled
        # This expects interlinear_mark.json to have 'verse' field with "chapter:verse" format
        # Each chapter will be on its own page (mark_1.html, mark_2.html, etc.)
        write_html_interlinear(
            "textcreation/texts/interlinearouts/interlinear_mark.json",
            "textcreation/texts/templates/greektemplate.html",
            "app/templates/texts/",
            "mark",
            "Gospel of Mark",
            "Gospel of Mark in Koine Greek",
            KoineGreek(),
            starting_page=1,
            verse_mode=True,  # Enable chapter/verse structure (one chapter per page)
            use_unified=True  # Use unified processor to preserve morphGNT parsing
        )
        print("✓ Gospel of Mark processing complete!")
        print("  Each chapter is a separate page: mark_1.html, mark_2.html, etc.")
        print("  Check app/templates/texts/mark/ for output files")
    elif len(sys.argv) > 1 and sys.argv[1] == "--tractatus":
        print("TRACTATUS MODE: Processing Tractatus Logico-Philosophicus with proposition structure")
        from languages.german import German

        # Process Tractatus with verse mode enabled
        # This expects interlinear_tractatus.json to have 'verse' field with proposition numbers (e.g., "1", "1.1", "2.01")
        # Propositions will be displayed with their numbers (like verse numbers)
        write_html_interlinear(
            "textcreation/texts/interlinearouts/interlinear_tractatus.json",
            "textcreation/texts/templates/tractatustemplate.html",
            "app/templates/texts/",
            "tractatus",
            "Tractatus Logico-Philosophicus",
            "Tractatus Logico-Philosophicus by Ludwig Wittgenstein",
            German(),
            starting_page=1,
            pagebreak=999999,  # Very high - page breaks triggered by top-level propositions (1,2,3,etc)
            verse_mode=True  # Enable proposition numbering display
        )
        print("✓ Tractatus processing complete!")
        print("  Each top-level proposition is a separate page: tractatus_1.html, tractatus_2.html, etc.")
        print("  Sub-propositions (e.g., 1.1, 1.11, 2.01) displayed with their numbers on the same page")
        print("  Check app/templates/texts/tractatus/ for output files")
    elif len(sys.argv) > 1 and sys.argv[1] == "--periodictable":
        print("PERIODIC TABLE MODE: Processing The Periodic Table (Primo Levi)")
        write_html_interlinear(
            "textcreation/texts/interlinearouts/interlinear_periodictable_with_numbers.json",
            "textcreation/texts/templates/infernotemplate.html",
            "app/templates/texts/",
            "periodictable",
            "The Periodic Table",
            "The Periodic Table",
            Italian(),
            starting_page=1,
            pagebreak=100,  # ~100 entries per chapter/page
            use_unified=True  # Use unified processor to avoid punctuation duplication
        )
        print("✓ Periodic Table processing complete!")
        print("  Check app/templates/texts/periodictable/ for output files")

        # Run automatic verification
        run_automatic_verification(
            json_path="textcreation/texts/interlinearouts/interlinear_periodictable.json",
            html_dir="app/templates/texts/periodictable/",
            text_name="periodictable",
            starting_page=1
        )

    else:
        print("FULL MODE: Processing all pages")
        write_html_interlinear("textcreation/texts/interlinearouts/interlinear_melancholy1.json", "textcreation/texts/templates/infernotemplate.html", "app/templates/texts/", "melancholy", "Melancholy", "Melancholy", Hungarian(), starting_page=1, pagebreak=1)

