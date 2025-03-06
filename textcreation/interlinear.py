import json
from promptlibrary import promptlibrary
from llm.claude import claude
from tqdm import tqdm
import asyncio
from languages.language import Language
from languages.german import German
from languages.french import French
from languages.italian import Italian
from languages.spanish import Spanish
from languages.hindi import Hindi
from languages.danish import Danish
from languages.persian import Persian
from languages.chinese import Chinese
from languages.japanese import Japanese
def parseInterlinear(gptoutput):
    outputlist = []
    phraselist = gptoutput.split("|")[1:-1]
    for phrase in phraselist:
        wordlist = phrase.split("*")
        #strip all elements of wordlist from trailing whitespace
        wordlist = [word.strip() for word in wordlist]
        outputlist.append(wordlist)

    return outputlist

def parseInterlinearWithTranslation(gptoutput):
    print(gptoutput)
    outputlist = []
    translation = gptoutput.split("&")[1]
    interlinear = gptoutput.split("&")[2]
    phraselist = interlinear.split("|")[1:-1]
    for phrase in phraselist:
        wordlist = phrase.split("*")
        wordlist = [word.strip() for word in wordlist]
        outputlist.append(wordlist)
    return outputlist, translation

def zipsources(jsonfile, stopsource: str = None):
    #Read in the jsonfile
    with open(jsonfile, 'r') as file:
        jsonfile = file.read()


    #Get number of entries in jsonfile
    jsonfile = json.loads(jsonfile)
    num_entries = len(jsonfile)

    #Json file contains a list of dictionaries with "source" and "translation"
    #Separate them into two lists of source and translation
    source_list = []
    translation_list = []
    for i in range(num_entries):
        source_list.append(jsonfile[i]["source"])
        translation_list.append(jsonfile[i]["translation"])
        if((stopsource is not None) and stopsource in jsonfile[i]["source"]):
            print("break!")
            break

    print("Source list length: ", len(source_list))
    return source_list, translation_list





async def getTranslations(source_list, translation_list, llm, userprompt, systemprompt, language: Language = French()):
    outputlist = []
    async_requests = []
    # Track indices of non-empty entries
    valid_entries = []

    # First pass - collect async requests for non-empty entries
    for i, (source, translation) in enumerate(zip(source_list, translation_list)):
        if source.strip() and translation.strip():
            prompt = userprompt.format(german=source.strip(), english=translation.strip())
            messages = llm.format_messages(userprompt=prompt, systemprompt=systemprompt)
            async_request = llm.get_completion_async(messages=messages)
            async_requests.append(async_request)
            valid_entries.append(i)
        
    # Process async requests
    results = []
    for async_request in tqdm(asyncio.as_completed(async_requests), total=len(async_requests), desc="Processing responses"):
        result = await async_request
        results.append(result)

    # Build output list preserving original order
    outputlist = [None] * len(source_list)
    for (idx, result) in zip(valid_entries, results):
        source = source_list[idx]
        translation = translation_list[idx]
        interlist = parseInterlinear(result)
        parseinfo = language.parse_sent(source)
        outputlist[idx] = {"source": source, "translation": translation, "interlinear": interlist, "parseinfo": parseinfo, "rawoutput": result}
    
    # Fill in empty entries
    for i in range(len(outputlist)):
        if outputlist[i] is None:
            outputlist[i] = {"source": source_list[i], "translation": translation_list[i], "interlinear": [], "parseinfo": None, "rawoutput": ""}

    return outputlist

async def getParses(source_list, translation_list, llm, userprompt, systemprompt, language: Language = Japanese()):
    outputlist = []
    for source, translation in tqdm(zip(source_list, translation_list), total=len(source_list), desc="Parsing results"):
        parseinfo = language.parse_sent(source)
        outputlist.append({"source": source, "translation": translation, "parseinfo": parseinfo})
    return outputlist

async def getTranslationAndInterlinear(source, llm, userprompt, systemprompt, language: Language = Persian()):
    prompt = userprompt.format(persian=source.strip())
    messages = llm.format_messages(userprompt=prompt, systemprompt=systemprompt)
    async_request = llm.get_completion_async(messages=messages)
    result = await async_request
    interlist, translation = parseInterlinearWithTranslation(result)
    parseinfo = language.parse_sent(source)
    return {"source": source, "translation": translation, "interlinear": interlist, "parseinfo": parseinfo, "rawoutput": result}

def getTranslationsResults(llmout, source, translation, language):
    result = llmout
    interlist = parseInterlinear(result)
    parseinfo = language.parse_sent(source)
    return {"source": source, "translation": translation, "interlinear": interlist, "parseinfo": parseinfo, "rawoutput": result}

def parseHindi():
    llmouts = open("textcreation/texts/interlinearouts/neeleneele.txt", 'r').read()
    llmouts = llmouts.split("##")
    sources = open("textcreation/texts/interlinearouts/neeleneeleog.txt", 'r').read()
    sources = sources.split("##")
    translations = open("textcreation/texts/interlinearouts/neeleneeleeng.txt", 'r').read()
    translations = translations.split("##")
    outputlist = []
    for source, translation, llmout in zip(sources, translations, llmouts):
        combo = getTranslationsResults(llmout, source, translation, Hindi())
        outputlist.append(combo)
    return outputlist

if __name__ == '__main__':
    #load yml file for prompts
    lib = promptlibrary("textcreation/promptlibrary.yml")
    userprompt = lib.find_prompt_by_title("InterlinearUserGerman")
    systemprompt = lib.find_prompt_by_title("InterlinearSystemGerman")

    llm = claude()
    
    source_list, translation_list = zipsources("textcreation/texts/aligned/Witt3.json")
    #source_list = [open("textcreation/texts/sources/sinocismtestch.txt", 'r').read()]
    #translation_list = [open("textcreation/texts/sources/sinocismtesten.txt", 'r').read()]

    #source = open("textcreation/texts/sources/ramkeli.txt", 'r').read()
    #sources = source.split("\n\n")
    #print("Getting translations")
    translations = asyncio.run(getTranslations(source_list, translation_list, llm, userprompt, systemprompt, language=German()))
    #parses = asyncio.run(getParses(source_list, translation_list, llm, userprompt, systemprompt, language=Japanese()))
    #interlinear = asyncio.run(getTranslationAndInterlinear(source, llm, userprompt, systemprompt, language=Persian()))
   # interlinear = [interlinear] + [asyncio.run(getTranslationAndInterlinear(sources[1], llm, userprompt, systemprompt, language=Persian()))]
    with open("textcreation/texts/interlinearouts/interlinearWitt3.json", 'w', encoding='utf8') as file:
        json.dump(translations, file, ensure_ascii=False)



    # translations = parseHindi()

    # with open("textcreation/texts/interlinearouts/neeleneele.json", 'w', encoding='utf8') as file:
    #     json.dump(translations, file, ensure_ascii=False)