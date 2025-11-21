import json
from promptlibrary import promptlibrary
from llm.claude import claude
from tqdm import tqdm
import asyncio
import signal
import os
from languages.language import Language
from languages.hungarian import Hungarian
from languages.italian import Italian
from languages.greek import KoineGreek
"""Lightweight language implementations to avoid heavy model deps during batch runs."""
class ChineseLight(Language):
    def __init__(self):
        self.name = "chinese"

    def get_grammar(self, word: str, sent: str, ind: int):
        return ""

    def get_definition(self, word: str):
        return ""

    def parse_sent(self, sent: str):
        # Skip heavy parsing to avoid spaCy transformer dependency
        return []

class GreekLight(Language):
    """Lightweight Greek for batch runs that defers to KoineGreek when needed."""
    def __init__(self):
        self.name = "greek"
        self._koine = None

    def _ensure_koine(self):
        if self._koine is None:
            self._koine = KoineGreek()

    def get_grammar(self, word: str, sent: str, ind: int):
        self._ensure_koine()
        return self._koine.get_grammar(word, sent, ind)

    def get_definition(self, word: str):
        self._ensure_koine()
        return self._koine.get_definition(word)

    def parse_sent(self, sent: str):
        self._ensure_koine()
        return self._koine.parse_sent(sent)

# Global variable to track interruption
interrupted = False
REQUEST_TIMEOUT_SECONDS = int(os.getenv("GLOSS_API_TIMEOUT", "600"))

def signal_handler(signum, frame):
    global interrupted
    interrupted = True
    print("\nInterruption detected. Finishing current batch and saving progress...")

# Set up signal handler
signal.signal(signal.SIGINT, signal_handler)

def verify_interlinear_quality(source, interlinear):
    """
    Verifies that the interlinear matches the source text.

    Returns:
        dict with 'valid' (bool), 'reason' (str), and 'confidence' (float 0-1)
    """
    if not interlinear:
        return {'valid': False, 'reason': 'Empty interlinear', 'confidence': 0.0}

    # Check 0: Structural integrity - all entries should have exactly 2 elements [source, gloss]
    # Exception: entries with only whitespace/newlines might be [''] or ['<br>'] which we can auto-fix
    malformed_entries = []
    for i, entry in enumerate(interlinear):
        if not isinstance(entry, list):
            malformed_entries.append(i)
        elif len(entry) == 1:
            # Single-element entry - check if it's whitespace that can be auto-fixed
            if entry[0].strip() in ('', '<br>'):
                # Auto-fix: convert to proper format
                interlinear[i] = ['<br>', ''] if entry[0].strip() == '' else entry + ['']
            else:
                # Non-whitespace single element - this is malformed
                malformed_entries.append(i)
        elif len(entry) != 2:
            malformed_entries.append(i)

    if malformed_entries:
        return {
            'valid': False,
            'reason': f'Malformed interlinear entries (not [source, gloss] pairs): positions {malformed_entries[:5]}',
            'confidence': 0.0
        }

    # Reconstruct source from interlinear
    interlinear_text = ''.join([word[0] for word in interlinear if word and len(word) > 0])
    source_clean = source.strip()

    source_len = len(source_clean)
    interlinear_len = len(interlinear_text)

    if source_len == 0:
        return {'valid': True, 'reason': 'Empty source', 'confidence': 1.0}

    # Check 1: Length ratio (interlinear should be similar length to source)
    length_ratio = interlinear_len / source_len if source_len > 0 else 0

    if length_ratio > 2.0:
        return {
            'valid': False,
            'reason': f'Interlinear too long ({length_ratio:.1f}x source)',
            'confidence': 0.0
        }

    if length_ratio < 0.5 and source_len > 20:
        return {
            'valid': False,
            'reason': f'Interlinear too short ({length_ratio:.1f}x source)',
            'confidence': 0.3
        }

    # Check 2: First words match (semantic check)
    source_words = source_clean.split()[:3]
    interlinear_first_words = [w[0] for w in interlinear if w][:3]

    if len(source_words) >= 2 and len(interlinear_first_words) >= 2:
        # Normalize for comparison (remove accents, punctuation, case, whitespace)
        import unicodedata

        def normalize_text(text):
            # Convert to NFD (decomposed) form, remove diacritics, keep only alphanumeric
            nfd = unicodedata.normalize('NFD', text.lower())
            return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn' and (c.isalnum() or c.isspace()))

        source_normalized = normalize_text(' '.join(source_words))
        interlinear_normalized = normalize_text(' '.join(interlinear_first_words))

        # Remove whitespace for comparison
        source_compact = source_normalized.replace(' ', '')
        interlinear_compact = interlinear_normalized.replace(' ', '')

        # Check if they start similarly (first 15 alphanumeric chars)
        min_length = min(15, len(source_compact), len(interlinear_compact))

        if min_length >= 5:  # Only check if we have at least 5 chars
            source_prefix = source_compact[:min_length]
            interlinear_prefix = interlinear_compact[:min_length]

            # Calculate similarity (how many chars match)
            matches = sum(1 for a, b in zip(source_prefix, interlinear_prefix) if a == b)
            similarity = matches / min_length

            # Require at least 60% similarity for the first words
            if similarity < 0.6:
                return {
                    'valid': False,
                    'reason': f'First words mismatch: "{source_words}" vs "{interlinear_first_words}"',
                    'confidence': similarity
                }

    # Check 3: Character coverage (how much of source is in interlinear)
    source_chars = set(c.lower() for c in source_clean if c.isalnum())
    interlinear_chars = set(c.lower() for c in interlinear_text if c.isalnum())

    if source_chars:
        coverage = len(source_chars & interlinear_chars) / len(source_chars)
        if coverage < 0.5:
            return {
                'valid': False,
                'reason': f'Low character coverage ({coverage:.0%})',
                'confidence': coverage
            }

    # All checks passed
    return {'valid': True, 'reason': 'OK', 'confidence': 1.0}


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





async def getTranslations(source_list, translation_list, llm, userprompt, systemprompt, language: Language, speaker_list=[], output_file=None, batch_size=10, resume_from=0):
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
                prompt = userprompt.format(italian=source.strip(), english=translation.strip())
                messages = llm.format_messages(userprompt=prompt, systemprompt=systemprompt)
                async_request = llm.get_completion_async(messages=messages, timeout_seconds=REQUEST_TIMEOUT_SECONDS)
                async_requests.append(async_request)
                valid_entries.append(i)
        
        # Process this batch
        if async_requests:
            try:
                print(f"Waiting for {len(async_requests)} async requests to complete...")
                # Create tasks so we can cancel if interrupted
                tasks = [asyncio.create_task(coro) for coro in async_requests]
                task_to_index = {task: idx for task, idx in zip(tasks, valid_entries)}
                pending = set(tasks)
                # Pre-fill results with None to preserve order
                results_map = {idx: None for idx in valid_entries}

                while pending:
                    if interrupted:
                        # Cancel any remaining tasks immediately
                        for t in pending:
                            t.cancel()
                        # Drain cancellations
                        await asyncio.gather(*pending, return_exceptions=True)
                        break

                    done, pending = await asyncio.wait(pending, timeout=1, return_when=asyncio.FIRST_COMPLETED)
                    for t in done:
                        idx = task_to_index[t]
                        try:
                            res = t.result()
                        except Exception as e:
                            print(f"Error in request for index {idx}: {type(e).__name__}: {e!r}")
                            res = ""
                        results_map[idx] = res

                # Build output for this batch in the original order
                # Track entries that need retry
                retry_entries = []

                for idx in valid_entries:
                    if interrupted and results_map[idx] is None:
                        # Skip unfinished entries on interrupt
                        continue
                    result = results_map[idx] if results_map[idx] is not None else ""
                    source = source_list[idx]
                    translation = translation_list[idx]
                    speaker = speaker_list[idx] if idx < len(speaker_list) and speaker_list[idx] is not None else None

                    interlist = parseInterlinear(result) if result else []

                    # Verify quality
                    verification = verify_interlinear_quality(source, interlist)

                    if not verification['valid']:
                        print(f"  ⚠ Entry {idx} FAILED verification: {verification['reason']}")
                        retry_entries.append(idx)
                    else:
                        # Only save if verification passed
                        parseinfo = language.parse_sent(source)
                        outputlist[idx] = {
                            "source": source,
                            "translation": translation,
                            "interlinear": interlist,
                            "parseinfo": parseinfo,
                            "rawoutput": result,
                            "speaker": speaker,
                        }

                # Retry failed entries (max 2 retries)
                if retry_entries and not interrupted:
                    print(f"\n  Retrying {len(retry_entries)} failed entries...")
                    for retry_attempt in range(2):
                        if not retry_entries:
                            break

                        print(f"  Retry attempt {retry_attempt + 1}/{2} for {len(retry_entries)} entries")

                        retry_requests = []
                        retry_indices = []

                        for idx in retry_entries:
                            source = source_list[idx]
                            translation = translation_list[idx]

                            # Get the verification result to include error reason
                            interlist = parseInterlinear(results_map.get(idx, '')) if results_map.get(idx) else []
                            verification = verify_interlinear_quality(source, interlist)
                            error_reason = verification['reason']

                            # Add retry addendum with error reason
                            retry_addendum = promptlib.retry_addendum
                            if retry_addendum:
                                retry_addendum_formatted = retry_addendum.format(error_reason=error_reason)
                            else:
                                retry_addendum_formatted = f"\n\nIMPORTANT: Previous attempt failed with: {error_reason}. Please ensure the interlinear matches the source exactly."

                            prompt = userprompt.format(italian=source.strip(), english=translation.strip())
                            prompt_with_addendum = prompt + retry_addendum_formatted

                            messages = llm.format_messages(userprompt=prompt_with_addendum, systemprompt=systemprompt)
                            async_request = llm.get_completion_async(messages=messages, timeout_seconds=REQUEST_TIMEOUT_SECONDS)
                            retry_requests.append(async_request)
                            retry_indices.append(idx)

                        # Wait for retry results
                        retry_results = await asyncio.gather(*retry_requests, return_exceptions=True)

                        still_failing = []
                        for idx, result in zip(retry_indices, retry_results):
                            if isinstance(result, Exception):
                                print(f"    Entry {idx}: Error - {result}")
                                still_failing.append(idx)
                                continue

                            source = source_list[idx]
                            translation = translation_list[idx]
                            speaker = speaker_list[idx] if idx < len(speaker_list) else None

                            interlist = parseInterlinear(result) if result else []
                            verification = verify_interlinear_quality(source, interlist)

                            if verification['valid']:
                                print(f"    Entry {idx}: ✓ Passed on retry")
                                parseinfo = language.parse_sent(source)
                                outputlist[idx] = {
                                    "source": source,
                                    "translation": translation,
                                    "interlinear": interlist,
                                    "parseinfo": parseinfo,
                                    "rawoutput": result,
                                    "speaker": speaker,
                                }
                            else:
                                print(f"    Entry {idx}: ✗ Still failing - {verification['reason']}")
                                still_failing.append(idx)

                        retry_entries = still_failing

                    # Fill failed entries with empty data
                    if retry_entries:
                        print(f"  ⚠ {len(retry_entries)} entries still failed after retries: {retry_entries}")
                        for idx in retry_entries:
                            speaker = speaker_list[idx] if idx < len(speaker_list) else None
                            outputlist[idx] = {
                                "source": source_list[idx],
                                "translation": translation_list[idx],
                                "interlinear": [],
                                "parseinfo": None,
                                "rawoutput": "",
                                "speaker": speaker,
                            }

            except asyncio.CancelledError:
                # Propagate cancellation
                raise
            except KeyboardInterrupt:
                # Propagate KeyboardInterrupt if it occurs
                raise
            except Exception as e:
                print(f"Error processing batch {batch_number}: {type(e).__name__}: {e!r}")
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
        
        print("\n" + "="*50)
        print("INTERRUPTION DETECTED")
        print("="*50)
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

async def getParses(source_list, translation_list, llm, userprompt, systemprompt, language: Language):
    outputlist = []
    for source, translation in tqdm(zip(source_list, translation_list), total=len(source_list), desc="Parsing results"):
        parseinfo = language.parse_sent(source)
        outputlist.append({"source": source, "translation": translation, "parseinfo": parseinfo})
    return outputlist

async def getTranslationAndInterlinear(source, llm, userprompt, systemprompt, language: Language):
    prompt = userprompt.format(persian=source.strip())
    messages = llm.format_messages(userprompt=prompt, systemprompt=systemprompt)
    async_request = llm.get_completion_async(messages=messages)
    result = await async_request
    interlist, translation = parseInterlinearWithTranslation(result)
    parseinfo = language.parse_sent(source)
    return {"source": source, "translation": translation, "interlinear": interlist, "parseinfo": parseinfo, "rawoutput": result}

async def getTranslationAndInterlinearExcerpts(sourcelist, source, llm, userprompt, systemprompt, language: Language):
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

def load_mark_verses(greek_file, english_file):
    """
    Load Gospel of Mark verses from the chapter:verse formatted files.
    Returns list of dicts with 'source', 'translation', and 'verse' keys.
    """
    with open(greek_file, 'r', encoding='utf-8') as f:
        greek_lines = f.readlines()
    with open(english_file, 'r', encoding='utf-8') as f:
        english_lines = f.readlines()

    verses = []
    for greek_line, english_line in zip(greek_lines, english_lines):
        # Parse "1:1 Text..." format
        greek_parts = greek_line.split(' ', 1)
        english_parts = english_line.split(' ', 1)

        if len(greek_parts) == 2 and len(english_parts) == 2:
            verse_ref = greek_parts[0]  # e.g., "1:1"
            greek_text = greek_parts[1].strip()
            english_text = english_parts[1].strip()

            verses.append({
                'source': greek_text,
                'translation': english_text,
                'verse': verse_ref
            })

    return verses

def load_tractatus_propositions(aligned_json):
    """
    Load Tractatus propositions from aligned JSON file.
    Returns list of dicts with 'source', 'translation', and 'proposition' keys.
    """
    with open(aligned_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # The aligned JSON already has the right format with 'proposition' field
    # Just rename to 'verse' for consistency with verse_mode processing
    propositions = []
    for entry in data:
        propositions.append({
            'source': entry['source'],
            'translation': entry['translation'],
            'verse': entry['proposition']  # Use 'verse' field for verse_mode compatibility
        })

    return propositions

# Note: parseHindi() removed to avoid importing heavy dependencies in environments
# where they are not available. Re-add if needed with appropriate optional imports.

if __name__ == '__main__':
    import sys

    # Check for Gospel of Mark mode
    if len(sys.argv) > 1 and sys.argv[1] == "--mark":
        print("="*60)
        print("Gospel of Mark (Greek) Processing")
        print("="*60)

        # Load yml file for prompts
        lib = promptlibrary("textcreation/promptlibrary.yml")
        # You will need to create these prompts in promptlibrary.yml
        userprompt = lib.find_prompt_by_title("InterlinearUserGreek")
        systemprompt = lib.find_prompt_by_title("InterlinearSystemGreek")

        llm = claude()

        # Load Gospel of Mark verses
        verses = load_mark_verses(
            'textcreation/data/mark_grc.txt',
            'textcreation/data/mark_eng.txt'
        )

        # Prepare source and translation lists, preserving verse references
        source_list = [v["source"] for v in verses]
        translation_list = [v["translation"] for v in verses]
        verse_list = [v["verse"] for v in verses]  # Store verse references

        # Configuration for batch processing
        output_file = "textcreation/texts/interlinearouts/interlinear_mark.json"
        batch_size = 10  # Process 10 verses at a time

        # Automatically detect resume point from existing file
        resume_from = find_resume_point(output_file)

        print("Starting Gospel of Mark translation processing:")
        print(f"- Total verses: {len(source_list)}")
        print(f"- Batch size: {batch_size}")
        print(f"- Output file: {output_file}")
        print(f"- Resume from index: {resume_from}")
        print("- Language: Koine Greek (Gospel of Mark)")
        print("\nPress Ctrl+C to interrupt gracefully and save progress\n")

        # Custom processing for Gospel of Mark with verse references
        async def process_mark():
            translations = await getTranslations(
                source_list,
                translation_list,
                llm,
                userprompt,
                systemprompt,
                language=GreekLight(),
                speaker_list=[],  # No speakers in Gospel
                output_file=output_file,
                batch_size=batch_size,
                resume_from=resume_from
            )

            # Add verse references to the output
            for i, verse_ref in enumerate(verse_list):
                if i < len(translations) and translations[i] is not None:
                    translations[i]['verse'] = verse_ref

            # Save final output with verse references
            with open(output_file, 'w', encoding='utf8') as f:
                json.dump(translations, f, ensure_ascii=False, indent=2)

            return translations

        translations = asyncio.run(process_mark())

        # Final message
        if not interrupted:
            print("\n✅ Gospel of Mark processing completed successfully!")
            print("📁 Results saved to: " + str(output_file))
            print("🏛️ Ready for use in the Gloss interlinear reader!")
        else:
            print("\n⚠️  Processing was interrupted but progress has been saved.")
            print("📁 Partial results available at: " + str(output_file))

    # Check for Tractatus mode
    elif len(sys.argv) > 1 and sys.argv[1] == "--tractatus":
        print("="*60)
        print("Tractatus Logico-Philosophicus (German) Processing")
        print("="*60)

        # Load yml file for prompts
        lib = promptlibrary("textcreation/promptlibrary.yml")
        # Use German prompts
        userprompt = lib.find_prompt_by_title("InterlinearUserGerman")
        systemprompt = lib.find_prompt_by_title("InterlinearSystemGerman")

        llm = claude()

        # Load Tractatus propositions from aligned JSON
        propositions = load_tractatus_propositions(
            'textcreation/texts/aligned/tractatus.json'
        )

        # Prepare source and translation lists, preserving proposition references
        source_list = [p["source"] for p in propositions]
        translation_list = [p["translation"] for p in propositions]
        verse_list = [p["verse"] for p in propositions]  # Store proposition numbers as 'verse'

        # Configuration for batch processing
        output_file = "textcreation/texts/interlinearouts/interlinear_tractatus.json"
        batch_size = 10  # Process 10 propositions at a time

        # Automatically detect resume point from existing file
        resume_from = find_resume_point(output_file)

        print("Starting Tractatus translation processing:")
        print(f"- Total propositions: {len(source_list)}")
        print(f"- Batch size: {batch_size}")
        print(f"- Output file: {output_file}")
        print(f"- Resume from index: {resume_from}")
        print("- Language: German (Tractatus)")
        print("\nPress Ctrl+C to interrupt gracefully and save progress\n")

        # Custom processing for Tractatus with proposition references
        async def process_tractatus():
            from languages.german import German

            translations = await getTranslations(
                source_list,
                translation_list,
                llm,
                userprompt,
                systemprompt,
                language=German(),
                speaker_list=[],  # No speakers in Tractatus
                output_file=output_file,
                batch_size=batch_size,
                resume_from=resume_from
            )

            # Add proposition references to the output
            for i, verse_ref in enumerate(verse_list):
                if i < len(translations) and translations[i] is not None:
                    translations[i]['verse'] = verse_ref

            # Save final output with proposition references
            with open(output_file, 'w', encoding='utf8') as f:
                json.dump(translations, f, ensure_ascii=False, indent=2)

            return translations

        translations = asyncio.run(process_tractatus())

        # Final message
        if not interrupted:
            print("\n✅ Tractatus processing completed successfully!")
            print("📁 Results saved to: " + str(output_file))
            print("🏛️ Ready for use in the Gloss interlinear reader!")
        else:
            print("\n⚠️  Processing was interrupted but progress has been saved.")
            print("📁 Partial results available at: " + str(output_file))

    else:
        # Default: Hungarian Melancholy processing
        # Load yml file for prompts
        lib = promptlibrary("textcreation/promptlibrary.yml")
        userprompt = lib.find_prompt_by_title("InterlinearUserItalian")
        systemprompt = lib.find_prompt_by_title("InterlinearSystemItalian")

        llm = claude()

        # Process redchamberch3 aligned data
        with open('textcreation/texts/aligned/periodictable.json', 'r', encoding='utf-8') as f:
            redchamber_data = json.load(f)

        # Prepare source and translation lists
        source_list = [entry["source"] for entry in redchamber_data]
        translation_list = [entry["translation"] for entry in redchamber_data]
        speaker_list = []  # No speaker info in red chamber sections

        # Configuration for batch processing
        output_file = "textcreation/texts/interlinearouts/interlinear_periodictable.json"
        batch_size = 2  # Process 2 sections at a time for better handling (these are large sections)

        # Automatically detect resume point from existing file
        resume_from = find_resume_point(output_file)

        print("Starting Melancholy 1 translation processing:")
        print(f"- Total entries: {len(source_list)}")
        print(f"- Batch size: {batch_size}")
        print(f"- Output file: {output_file}")
        print(f"- Resume from index: {resume_from}")
        print("- Language: Hungarian (Melancholy 1)")
        print("\nPress Ctrl+C to interrupt gracefully and save progress\n")

        translations = asyncio.run(getTranslations(
            source_list,
            translation_list,
            llm,
            userprompt,
            systemprompt,
            language=Italian(),
            speaker_list=speaker_list,
            output_file=output_file,
            batch_size=batch_size,
            resume_from=resume_from
        ))

        # Final message
        if not interrupted:
            print("\n✅ Periodic Table processing completed successfully!")
            print("📁 Results saved to: " + str(output_file))
            print("🏛️ Ready for use in the Gloss interlinear reader!")
        else:
            print("\n⚠️  Processing was interrupted but progress has been saved.")
            print("📁 Partial results available at: " + str(output_file))