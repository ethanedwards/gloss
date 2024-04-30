import json
from promptlibrary import promptlibrary
from llm.claude import claude
import asyncio
from languages.language import Language
from languages.german import German

def parseInterlinear(gptoutput):
    outputlist = []
    phraselist = gptoutput.split("|")[1:-1]
    for phrase in phraselist:
        wordlist = phrase.split("*")
        #strip all elements of wordlist from trailing whitespace
        wordlist = [word.strip() for word in wordlist]
        outputlist.append(wordlist)

    return outputlist


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


async def getTranslations(source_list, translation_list, llm, userprompt, systemprompt, language: Language = German()):
    outputlist = []
    async_requests = []

    for source, translation in zip(source_list, translation_list):
        prompt = userprompt.format(german=source.strip(), english=translation.strip())
        messages = llm.format_messages(userprompt=prompt, systemprompt=systemprompt)
        async_request = llm.get_completion_async(messages=messages)
        print("async request")
        async_requests.append(async_request)
    results = await asyncio.gather(*async_requests)

    for source, translation, result in zip(source_list, translation_list, results):
        interlist = parseInterlinear(result)
        parseinfo = language.parse_sent(source)
        outputlist.append({"source": source, "translation": translation, "interlinear": interlist, "parseinfo": parseinfo, "rawoutput": result})

    return outputlist

if __name__ == '__main__':
    #load yml file for prompts
    lib = promptlibrary("promptlibrary.yml")
    userprompt = lib.find_prompt_by_title("InterlinearUserGerman")
    systemprompt = lib.find_prompt_by_title("InterlinearSystemGerman")

    llm = claude()
    
    source_list, translation_list = zipsources("texts/aligned/hamannfirst.json")
    print("Getting translations")
    #translations = getTranslations(source_list, translation_list, llm, userprompt, systemprompt)
    translations = asyncio.run(getTranslations(source_list, translation_list, llm, userprompt, systemprompt))
    # print(translations)
    with open("texts/interlinearouts/interlinearhamannfirst.json", 'w', encoding='utf8') as file:
        json.dump(translations, file, ensure_ascii=False)