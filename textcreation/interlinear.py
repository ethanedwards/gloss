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

    for source, translation in tqdm(zip(source_list, translation_list), total=len(source_list), desc="Sending requests"):
        prompt = userprompt.format(chinese=source.strip(), english=translation.strip())
        messages = llm.format_messages(userprompt=prompt, systemprompt=systemprompt)
        async_request = llm.get_completion_async(messages=messages)
        print("async request")
        async_requests.append(async_request)

    results = []
    for async_request in tqdm(asyncio.as_completed(async_requests), total=len(async_requests), desc="Processing responses"):
        result = await async_request
        results.append(result)

    for source, translation, result in tqdm(zip(source_list, translation_list, results), total=len(source_list), desc="Parsing results"):
        interlist = parseInterlinear(result)
        parseinfo = language.parse_sent(source)
        outputlist.append({"source": source, "translation": translation, "interlinear": interlist, "parseinfo": parseinfo, "rawoutput": result})

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
    userprompt = lib.find_prompt_by_title("InterlinearUserPersianPoetry")
    systemprompt = lib.find_prompt_by_title("InterlinearSystemPersianPoetry")

    llm = claude()
    
    #source_list, translation_list = zipsources("textcreation/texts/aligned/proust1.json")
    #source_list = [open("textcreation/texts/sources/sinocismtestch.txt", 'r').read()]
    #translation_list = [open("textcreation/texts/sources/sinocismtesten.txt", 'r').read()]

    source = open("textcreation/texts/sources/abuatapoem.txt", 'r').read()
    sources = source.split("\n\n")
    print("Getting translations")
    #translations = asyncio.run(getTranslations(source_list, translation_list, llm, userprompt, systemprompt, language=Chinese()))
    interlinear = asyncio.run(getTranslationAndInterlinear(sources[0], llm, userprompt, systemprompt, language=Persian()))
    interlinear = [interlinear] + [asyncio.run(getTranslationAndInterlinear(sources[1], llm, userprompt, systemprompt, language=Persian()))]
    with open("textcreation/texts/interlinearouts/interlinearabuatapoem.json", 'w', encoding='utf8') as file:
        json.dump(interlinear, file, ensure_ascii=False)



    # translations = parseHindi()

    # with open("textcreation/texts/interlinearouts/neeleneele.json", 'w', encoding='utf8') as file:
    #     json.dump(translations, file, ensure_ascii=False)