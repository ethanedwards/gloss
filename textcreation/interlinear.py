import json
from promptlibrary import promptlibrary
from llm.claude import claude
from tqdm import tqdm
import asyncio
import signal
import sys
import os
from languages.language import Language
from languages.german import German
from languages.latin import Latin
from languages.oldenglish import OldEnglish
from languages.french import French
from languages.italian import Italian
from languages.spanish import Spanish
from languages.hindi import Hindi
from languages.danish import Danish
from languages.persian import Persian
from languages.chinese import Chinese
from languages.japanese import Japanese
from languages.portuguese import Portuguese

# Global variable to track interruption
interrupted = False

def signal_handler(signum, frame):
    global interrupted
    interrupted = True
    print("\nInterruption detected. Finishing current batch and saving progress...")

# Set up signal handler
signal.signal(signal.SIGINT, signal_handler)

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
    outputlist = []
    translation = gptoutput.split("&")[1]
    interlinear = gptoutput.split("&")[2]
    phraselist = interlinear.split("|")[1:-1]
    for phrase in phraselist:
        wordlist = phrase.split("*")
        wordlist = [word.strip() for word in wordlist]
        outputlist.append(wordlist)
    return outputlist, translation

def zipsources(jsonfile, stopsource: str = None, speakermode: bool = False):
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
    speaker_list = []
    for i in range(num_entries):
        source_list.append(jsonfile[i]["source"])
        translation_list.append(jsonfile[i]["translation"])
        if(speakermode):
            speaker_list.append(jsonfile[i]["speaker"])
        if((stopsource is not None) and stopsource in jsonfile[i]["source"]):
            print("break!")
            break

    print("Source list length: ", len(source_list))
    return source_list, translation_list, speaker_list





async def getTranslations(source_list, translation_list, llm, userprompt, systemprompt, language: Language = French(), speaker_list=[], output_file=None, batch_size=10, resume_from=0):
    """
    Process translations in batches with progressive writing and interruption handling.
    
    Args:
        source_list: List of source texts
        translation_list: List of translated texts  
        llm: Language model instance
        userprompt: User prompt template
        systemprompt: System prompt
        language: Language object for parsing
        speaker_list: List of speakers (optional)
        output_file: Path to output file for progressive writing
        batch_size: Number of items to process in each batch
        resume_from: Index to resume from (for resuming interrupted runs)
    """
    global interrupted
    
    # Initialize output list with None values
    outputlist = [None] * len(source_list)
    
    # Load existing progress if resuming
    if resume_from > 0 and output_file and os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf8') as f:
                existing_data = json.load(f)
                # Restore completed entries
                for i, entry in enumerate(existing_data):
                    if i < len(outputlist) and entry is not None:
                        outputlist[i] = entry
            print(f"Resuming from index {resume_from}")
        except Exception as e:
            print(f"Warning: Could not load existing progress: {e}")
    
    # Process entries in batches
    total_entries = len(source_list)
    
    for batch_start in range(resume_from, total_entries, batch_size):
        if interrupted:
            break
            
        batch_end = min(batch_start + batch_size, total_entries)
        batch_number = (batch_start - resume_from) // batch_size + 1
        print(f"\nProcessing batch {batch_number}: entries {batch_start} to {batch_end-1}")
        
        # Collect async requests for this batch
        async_requests = []
        valid_entries = []
        
        for i in range(batch_start, batch_end):
            source = source_list[i]
            translation = translation_list[i]
            
            if source.strip() and translation.strip():
                prompt = userprompt.format(portuguese=source.strip(), english=translation.strip())
                messages = llm.format_messages(userprompt=prompt, systemprompt=systemprompt)
                async_request = llm.get_completion_async(messages=messages)
                async_requests.append(async_request)
                valid_entries.append(i)
        
        # Process this batch
        if async_requests:
            try:
                # Use asyncio.gather to preserve order of results
                print(f"Waiting for {len(async_requests)} async requests to complete...")
                results = await asyncio.gather(*async_requests, return_exceptions=True)
                
                # Handle any exceptions in results
                processed_results = []
                for i, result in enumerate(results):
                    if interrupted:
                        break
                    if isinstance(result, Exception):
                        print(f"Error in request {i}: {result}")
                        processed_results.append("")  # Empty result for failed requests
                    else:
                        processed_results.append(result)
                
                results = processed_results
                
                # Build output for this batch
                for (idx, result) in zip(valid_entries, results):
                    if interrupted:
                        break
                    source = source_list[idx]
                    translation = translation_list[idx]
                    speaker = speaker_list[idx] if idx < len(speaker_list) and speaker_list[idx] is not None else None
                    
                    interlist = parseInterlinear(result)
                    parseinfo = language.parse_sent(source)
                    outputlist[idx] = {
                        "source": source, 
                        "translation": translation, 
                        "interlinear": interlist, 
                        "parseinfo": parseinfo, 
                        "rawoutput": result, 
                        "speaker": speaker
                    }
                    
            except Exception as e:
                print(f"Error processing batch {batch_number}: {e}")
                continue
        
        # Fill in empty entries for this batch
        for i in range(batch_start, batch_end):
            if outputlist[i] is None:
                speaker = speaker_list[i] if i < len(speaker_list) else None
                outputlist[i] = {
                    "source": source_list[i], 
                    "translation": translation_list[i], 
                    "interlinear": [], 
                    "parseinfo": None, 
                    "rawoutput": "", 
                    "speaker": speaker
                }
        
        # Write progress to file after each batch
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf8') as file:
                    json.dump(outputlist, file, ensure_ascii=False, indent=2)
                print(f"Progress saved to {output_file}")
            except Exception as e:
                print(f"Error saving progress: {e}")
        
        if interrupted:
            break
    
    # Handle interruption
    if interrupted:
        temp_file = f"{output_file}.temp" if output_file else "interrupted_progress.json"
        completed_count = sum(1 for entry in outputlist if entry is not None and entry.get("rawoutput", "") != "")
        
        # Find the last completed index
        last_completed_idx = -1
        for i in range(len(outputlist)):
            if outputlist[i] is not None and outputlist[i].get("rawoutput", "") != "":
                last_completed_idx = i
        
        resume_idx = last_completed_idx + 1 if last_completed_idx >= 0 else 0
        
        print(f"\n{'='*50}")
        print(f"INTERRUPTION DETECTED")
        print(f"{'='*50}")
        print(f"Progress: {completed_count}/{total_entries} entries completed")
        print(f"Last completed index: {last_completed_idx}")
        print(f"Temporary file saved as: {temp_file}")
        
        # Save to temp file
        with open(temp_file, 'w', encoding='utf8') as file:
            json.dump(outputlist, file, ensure_ascii=False, indent=2)
        
        print(f"\nTo resume, modify your script to set resume_from={resume_idx}")
        print(f"Example: getTranslations(..., resume_from={resume_idx})")
        print(f"{'='*50}")
        
        return outputlist
    
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

async def getTranslationAndInterlinearExcerpts(sourcelist, source, llm, userprompt, systemprompt, language: Language = Persian()):
    outputlist = []
    for excerpt in sourcelist:
        source.strip()
        excerpt.strip()
        prompt = userprompt.format(persian=source.strip(), excerpt=excerpt.strip())
        messages = llm.format_messages(userprompt=prompt, systemprompt=systemprompt)
        async_request = llm.get_completion_async(messages=messages)
        result = await async_request
        interlist, translation = parseInterlinearWithTranslation(result)
        parseinfo = language.parse_sent(excerpt)
        outputlist.append({"source": excerpt, "translation": translation, "interlinear": interlist, "parseinfo": parseinfo, "rawoutput": result})
    return outputlist


def getTranslationsResults(llmout, source, translation, language):
    result = llmout
    interlist = parseInterlinear(result)
    parseinfo = language.parse_sent(source)
    return {"source": source, "translation": translation, "interlinear": interlist, "parseinfo": parseinfo, "rawoutput": result}

def find_resume_point(output_file):
    """
    Helper function to find the resume point from an existing file.
    Returns the index where processing should resume.
    """
    if not os.path.exists(output_file):
        print(f"File {output_file} does not exist. Starting from beginning.")
        return 0
    
    try:
        with open(output_file, 'r', encoding='utf8') as f:
            data = json.load(f)
            
        # Find the last completed index
        last_completed_idx = -1
        completed_count = 0
        for i, entry in enumerate(data):
            if entry is not None and entry.get("rawoutput", "") != "":
                last_completed_idx = i
                completed_count += 1
        
        resume_idx = last_completed_idx + 1 if last_completed_idx >= 0 else 0
        
        print(f"Found existing progress in {output_file}:")
        print(f"- {completed_count} entries completed")
        print(f"- Last completed index: {last_completed_idx}")
        print(f"- Will resume from index: {resume_idx}")
        
        return resume_idx
        
    except Exception as e:
        print(f"Error reading {output_file}: {e}")
        return 0

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
    userprompt = lib.find_prompt_by_title("InterlinearUserGrandeSertao")
    systemprompt = lib.find_prompt_by_title("InterlinearSystemGrandeSertao")

    llm = claude()
    
    source_list, translation_list, speaker_list = zipsources("textcreation/texts/aligned/rosa1.json", speakermode=False)
    #source_list = [open("textcreation/texts/sources/sinocismtestch.txt", 'r').read()]
    #translation_list = [open("textcreation/texts/sources/sinocismtesten.txt", 'r').read()]

    #source = open("textcreation/texts/sources/afsharitasnif.txt", 'r').read()
    # split every 2 lines
    #source_list = ["\n".join(source.split("\n")[i:i+2]) for i in range(0, len(source.split("\n")), 2)]
    #sources = source.split("\n\n")
    #print("Getting translations")
    
    # Configuration for batch processing
    output_file = "textcreation/texts/interlinearouts/interlinearrosa1.json"
    batch_size = 5  # Process 5 items at a time (adjust as needed)
    
    # Automatically detect resume point from existing file
    resume_from = find_resume_point(output_file)
    
    print(f"Starting translation processing:")
    print(f"- Total entries: {len(source_list)}")
    print(f"- Batch size: {batch_size}")
    print(f"- Output file: {output_file}")
    print(f"- Resume from index: {resume_from}")
    print(f"- Language: Spanish")
    print("\nPress Ctrl+C to interrupt gracefully and save progress\n")
    
    translations = asyncio.run(getTranslations(
        source_list, 
        translation_list, 
        llm, 
        userprompt, 
        systemprompt, 
        language=Portuguese(), 
        speaker_list=speaker_list,
        output_file=output_file,
        batch_size=batch_size,
        resume_from=resume_from
    ))
    
    # Final message
    if not interrupted:
        print(f"\n✅ Processing completed successfully!")
        print(f"📁 Results saved to: {output_file}")
    else:
        print(f"\n⚠️  Processing was interrupted but progress has been saved.")
    
    #parses = asyncio.run(getParses(source_list, translation_list, llm, userprompt, systemprompt, language=Japanese()))
    #persian poems
    #interlinear = asyncio.run(getTranslationAndInterlinearExcerpts(sourcelist=source_list, source=source, llm=llm, userprompt=userprompt, systemprompt=systemprompt, language=Persian()))
   # interlinear = [interlinear] + [asyncio.run(getTranslationAndInterlinear(sources[1], llm, userprompt, systemprompt, language=Persian()))]
    
    # File writing is now handled within the getTranslations function
    # with open("textcreation/texts/interlinearouts/interlinearlabyrinth3a.json", 'w', encoding='utf8') as file:
    #     json.dump(translations, file, ensure_ascii=False)



    # translations = parseHindi()

    # with open("textcreation/texts/interlinearouts/neeleneele.json", 'w', encoding='utf8') as file:
    #     json.dump(translations, file, ensure_ascii=False)