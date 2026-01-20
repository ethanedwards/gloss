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

    Key checks:
    - length_ratio < 0.65: Detects LLM output truncation (most common failure mode)
      When the LLM hits output token limits, output is cut mid-word. This results
      in interlinear covering only ~40-60% of the source text.
    - First words match: Detects wrong-passage errors
    - Structural integrity: All entries should be [source, gloss] pairs
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

    if length_ratio < 0.65 and source_len > 20:
        return {
            'valid': False,
            'reason': f'Interlinear too short ({length_ratio:.0%} coverage, need 65%+)',
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

    # Check 4: Word boundary alignment - detect multi-word tokens that won't align
    # This catches cases like LLM producing ["J'", "avais oublié"] when source has "J'avais oublié"
    import unicodedata
    def normalize_for_match(text):
        """Remove accents and convert to lowercase for matching."""
        nfd = unicodedata.normalize('NFD', text)
        return ''.join(c for c in nfd if unicodedata.category(c) != 'Mn').lower()

    # Check if first interlinear token aligns with source word boundaries
    if interlinear and len(interlinear) > 0:
        first_inter_word = interlinear[0][0] if interlinear[0] else ''
        first_inter_normalized = normalize_for_match(first_inter_word).strip()

        # Get the first word from source (up to first space)
        source_words_raw = source_clean.split()
        if source_words_raw:
            first_source_word = source_words_raw[0]
            first_source_normalized = normalize_for_match(first_source_word).strip()

            # Critical check: If interlinear first word is a PROPER PREFIX of source first word,
            # this indicates the LLM split the word incorrectly (e.g., "J'" vs "J'avais")
            # This will cause alignment failures in the unified processor
            if first_source_normalized and first_inter_normalized:
                # Check if interlinear word is a strict prefix (shorter and matches start)
                if (len(first_inter_normalized) < len(first_source_normalized) and
                    first_source_normalized.startswith(first_inter_normalized) and
                    len(first_inter_normalized) >= 1):
                    # Interlinear first word is a prefix of source first word
                    # This means the LLM split the word differently than the source
                    return {
                        'valid': False,
                        'reason': f'Token boundary mismatch: interlinear "{first_inter_word}" is prefix of source "{first_source_word}" - LLM split word incorrectly',
                        'confidence': 0.3
                    }

                # Also check if they share the same prefix (at least 3 chars or full length if shorter)
                check_len = min(3, len(first_source_normalized), len(first_inter_normalized))
                if check_len >= 2:
                    if first_source_normalized[:check_len] != first_inter_normalized[:check_len]:
                        return {
                            'valid': False,
                            'reason': f'Word boundary mismatch: source starts "{first_source_word}" but interlinear starts "{first_inter_word}"',
                            'confidence': 0.4
                        }

    # Check 5: Detect problematic multi-word tokens
    # If any interlinear token contains spaces and the corresponding source position
    # doesn't naturally break at those boundaries, flag it
    position = 0
    for i, entry in enumerate(interlinear[:5]):  # Check first 5 entries
        if not entry or len(entry) < 1:
            continue
        word = entry[0]
        if ' ' in word.strip():  # Multi-word token
            # Check if this multi-word token appears as-is in the source at expected position
            word_no_space = word.replace(' ', '')
            # Find where this should appear in source
            source_remaining = source_clean[position:].lstrip()
            if source_remaining:
                # The multi-word token's characters should appear at source position
                word_normalized = normalize_for_match(word_no_space)
                source_start_normalized = normalize_for_match(source_remaining[:len(word_no_space)+5])

                # Check if source has these chars but with different spacing
                if word_normalized and source_start_normalized.startswith(word_normalized[:3]):
                    # Characters match but we have a multi-word token - potential issue
                    # Check if source actually has this as multiple words
                    source_words_here = source_remaining.split()[:3]
                    inter_words_in_token = word.split()

                    if len(inter_words_in_token) > 1 and len(source_words_here) > 0:
                        # Multi-word token but source might tokenize differently
                        # This is a warning - the unified processor may struggle
                        pass  # Allow but note the potential issue

        # Advance position
        position += len(word.replace(' ', ''))

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

            # Handle both bilingual and solo modes
            if source.strip():
                # Try to format with various language parameter combinations
                try:
                    # Try French solo format (only french parameter)
                    prompt = userprompt.format(french=source.strip())
                except KeyError:
                    try:
                        # Try French bilingual format
                        prompt = userprompt.format(french=source.strip(), english=translation.strip())
                    except KeyError:
                        try:
                            # Try Italian bilingual format
                            prompt = userprompt.format(italian=source.strip(), english=translation.strip())
                        except KeyError:
                            try:
                                # Try other language combinations
                                prompt = userprompt.format(source=source.strip(), translation=translation.strip())
                            except KeyError:
                                # Fallback: just use the source
                                print(f"Warning: Could not format prompt for entry {i}, using source as-is")
                                prompt = source.strip()

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
                            # Load promptlibrary to get retry addendum
                            try:
                                lib = promptlibrary("textcreation/promptlibrary.yml")
                                retry_addendum_prompt = lib.find_prompt_by_title("InterlinearRetryAddendum")
                                retry_addendum_formatted = retry_addendum_prompt.format(error_reason=error_reason)
                            except Exception as e:
                                print(f"Warning: Could not load retry addendum: {e}")
                                retry_addendum_formatted = f"\n\nIMPORTANT: Previous attempt failed with: {error_reason}. Please ensure the interlinear matches the source exactly."

                            # Format prompt with flexible language parameter handling
                            try:
                                prompt = userprompt.format(french=source.strip())
                            except KeyError:
                                try:
                                    prompt = userprompt.format(french=source.strip(), english=translation.strip())
                                except KeyError:
                                    try:
                                        prompt = userprompt.format(italian=source.strip(), english=translation.strip())
                                    except KeyError:
                                        try:
                                            prompt = userprompt.format(source=source.strip(), translation=translation.strip())
                                        except KeyError:
                                            prompt = source.strip()

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

                    # Fill failed entries with empty data AND mark them as failed
                    if retry_entries:
                        print(f"  ⚠ {len(retry_entries)} entries still failed after retries: {retry_entries}")
                        print("  ⚠ IMPORTANT: These entries will need manual review or re-processing!")
                        for idx in retry_entries:
                            speaker = speaker_list[idx] if idx < len(speaker_list) else None
                            outputlist[idx] = {
                                "source": source_list[idx],
                                "translation": translation_list[idx],
                                "interlinear": [],
                                "parseinfo": None,
                                "rawoutput": "",
                                "speaker": speaker,
                                "_failed_verification": True,  # Mark as failed for writehtml.py to detect
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
    return load_nt_verses(greek_file, english_file)


def load_nt_verses(greek_file, english_file):
    """
    Load NT verses from chapter:verse formatted files.
    Returns list of dicts with 'source', 'translation', and 'verse' keys.

    Handles the case where the Greek and English files may have mismatched verses
    by using a dictionary to align by verse reference.
    """
    with open(greek_file, 'r', encoding='utf-8') as f:
        greek_lines = f.readlines()
    with open(english_file, 'r', encoding='utf-8') as f:
        english_lines = f.readlines()

    # Parse Greek verses into dict
    greek_dict = {}
    for line in greek_lines:
        parts = line.split(' ', 1)
        if len(parts) == 2:
            verse_ref = parts[0].strip()
            greek_dict[verse_ref] = parts[1].strip()

    # Parse English verses into dict
    english_dict = {}
    for line in english_lines:
        parts = line.split(' ', 1)
        if len(parts) == 2:
            verse_ref = parts[0].strip()
            english_dict[verse_ref] = parts[1].strip()

    # Find common verses and build list sorted by chapter:verse
    common_refs = set(greek_dict.keys()) & set(english_dict.keys())

    def sort_key(ref):
        parts = ref.split(':')
        return (int(parts[0]), int(parts[1]))

    sorted_refs = sorted(common_refs, key=sort_key)

    verses = []
    for verse_ref in sorted_refs:
        verses.append({
            'source': greek_dict[verse_ref],
            'translation': english_dict[verse_ref],
            'verse': verse_ref
        })

    print(f"  Greek verses: {len(greek_dict)}")
    print(f"  English verses: {len(english_dict)}")
    print(f"  Common verses: {len(verses)}")

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

    # Check for French solo mode
    elif len(sys.argv) > 1 and sys.argv[1] == "--french-solo":
        print("="*60)
        print("French Solo Text Processing (No Translation)")
        print("="*60)

        # Load yml file for prompts
        lib = promptlibrary("textcreation/promptlibrary.yml")
        userprompt = lib.find_prompt_by_title("InterlinearUserFrenchSolo")
        systemprompt = lib.find_prompt_by_title("InterlinearSystemFrenchSolo")

        llm = claude()

        # Load French solo aligned data
        aligned_file = 'textcreation/texts/aligned/aligned_hazan.json'
        print(f"Loading aligned data from: {aligned_file}")

        with open(aligned_file, 'r', encoding='utf-8') as f:
            french_data = json.load(f)

        # Prepare source list (translation list is empty for solo mode)
        # Preserve verse/chapter markers for page breaks in HTML generation
        source_list = [entry["source"] for entry in french_data]
        translation_list = [entry["translation"] for entry in french_data]  # Empty strings
        verse_list = [entry.get("verse", "") for entry in french_data]  # Chapter numbers

        # Configuration for batch processing
        output_file = "textcreation/texts/interlinearouts/interlinear_hazan.json"
        batch_size = 10  # Process 10 sentences at a time

        # Automatically detect resume point from existing file
        resume_from = find_resume_point(output_file)

        print("Starting French solo translation processing:")
        print(f"- Total entries: {len(source_list)}")
        print(f"- Batch size: {batch_size}")
        print(f"- Output file: {output_file}")
        print(f"- Resume from index: {resume_from}")
        print("- Language: French (Solo mode - no translation)")
        print("\nPress Ctrl+C to interrupt gracefully and save progress\n")

        # Process with French language (lightweight)
        class FrenchLight(Language):
            """Lightweight French for batch runs."""
            def __init__(self):
                self.name = "french"

            def get_grammar(self, word: str, sent: str, ind: int):
                return ""

            def get_definition(self, word: str):
                return ""

            def parse_sent(self, sent: str):
                # Skip heavy parsing during batch runs
                return []

        # Custom processing for French solo with verse/chapter references
        async def process_french_solo():
            translations = await getTranslations(
                source_list,
                translation_list,
                llm,
                userprompt,
                systemprompt,
                language=FrenchLight(),
                speaker_list=[],
                output_file=output_file,
                batch_size=batch_size,
                resume_from=resume_from
            )

            # Add verse/chapter references to the output
            for i, verse_ref in enumerate(verse_list):
                if i < len(translations) and translations[i] is not None and verse_ref:
                    translations[i]['verse'] = verse_ref

            # Save final output with verse references
            with open(output_file, 'w', encoding='utf8') as f:
                json.dump(translations, f, ensure_ascii=False, indent=2)

            return translations

        translations = asyncio.run(process_french_solo())

        # Final message
        if not interrupted:
            print("\n✅ French solo processing completed successfully!")
            print("📁 Results saved to: " + str(output_file))
            print("🏛️ Ready for use in the Gloss interlinear reader!")
        else:
            print("\n⚠️  Processing was interrupted but progress has been saved.")
            print("📁 Partial results available at: " + str(output_file))

    # Check for Proust mode
    elif len(sys.argv) > 1 and sys.argv[1] == "--proust":
        print("="*60)
        print("Proust - Swann's Way (French with English Translation)")
        print("="*60)

        # Load yml file for prompts - use bilingual French prompts
        lib = promptlibrary("textcreation/promptlibrary.yml")
        userprompt = lib.find_prompt_by_title("InterlinearUserFrench")
        systemprompt = lib.find_prompt_by_title("InterlinearSystemFrench")

        llm = claude()

        # Load Proust aligned data
        aligned_file = 'textcreation/texts/aligned/proust1_llm_improved.json'
        print(f"Loading aligned data from: {aligned_file}")

        with open(aligned_file, 'r', encoding='utf-8') as f:
            proust_data = json.load(f)

        # Prepare source and translation lists
        source_list = [entry["source"] for entry in proust_data]
        translation_list = [entry["translation"] for entry in proust_data]

        # Configuration for batch processing
        output_file = "textcreation/texts/interlinearouts/interlinear_proust1.json"
        batch_size = 5  # Process 5 sentences at a time (Proust's sentences can be very long)

        # Automatically detect resume point from existing file
        resume_from = find_resume_point(output_file)

        print("Starting Proust Swann's Way translation processing:")
        print(f"- Total entries: {len(source_list)}")
        print(f"- Batch size: {batch_size}")
        print(f"- Output file: {output_file}")
        print(f"- Resume from index: {resume_from}")
        print("- Language: French (Proust - In Search of Lost Time)")
        print("\nPress Ctrl+C to interrupt gracefully and save progress\n")

        # Lightweight French for batch processing
        class FrenchLight(Language):
            """Lightweight French for batch runs."""
            def __init__(self):
                self.name = "french"

            def get_grammar(self, word: str, sent: str, ind: int):
                return ""

            def get_definition(self, word: str):
                return ""

            def parse_sent(self, sent: str):
                # Skip heavy parsing during batch runs
                return []

        # Process Proust
        async def process_proust():
            translations = await getTranslations(
                source_list,
                translation_list,
                llm,
                userprompt,
                systemprompt,
                language=FrenchLight(),
                speaker_list=[],
                output_file=output_file,
                batch_size=batch_size,
                resume_from=resume_from
            )

            # Save final output
            with open(output_file, 'w', encoding='utf8') as f:
                json.dump(translations, f, ensure_ascii=False, indent=2)

            return translations

        translations = asyncio.run(process_proust())

        # Final message
        if not interrupted:
            print("\n✅ Proust processing completed successfully!")
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

    # Check for Perec mode - fragmentary observational text with translation-first approach
    elif len(sys.argv) > 1 and sys.argv[1] == "--perec":
        print("="*60)
        print("Perec - Tentative d'épuisement d'un lieu parisien")
        print("(An Attempt at Exhausting a Place in Paris)")
        print("="*60)

        # Load yml file for prompts - use Perec-specific prompts
        lib = promptlibrary("textcreation/promptlibrary.yml")
        userprompt = lib.find_prompt_by_title("InterlinearUserPerec")
        systemprompt = lib.find_prompt_by_title("InterlinearSystemPerec")

        llm = claude()

        # Load Perec source text
        source_file = 'textcreation/texts/sources/perecfr.txt'
        print(f"Loading source text from: {source_file}")

        with open(source_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Clean and prepare lines
        lines = [line.strip() for line in lines]

        # Chunk lines together for context - Perec has many short fragmentary lines
        # We'll group lines into chunks of ~5-10 lines, keeping logical breaks
        #
        # WARNING: LLM OUTPUT LENGTH LIMITS
        # The interlinear format is verbose (| word*gloss | adds ~6+ chars per word).
        # Combined with translation output, chunks over ~150-200 words risk truncation.
        # The Perec format outputs BOTH translation AND interlinear, doubling output size.
        # If truncation occurs (verifier reports "Interlinear too short"), reduce target_chunk_size.
        # Observed: chunks > 200 words (1200+ chars) consistently truncated.
        #
        def chunk_perec_lines(lines, target_chunk_size=8, context_lines=3):
            """
            Chunk Perec's fragmentary text into groups for processing.
            Returns list of dicts with 'source' (to translate) and 'context' (for understanding).

            We keep section headers (I, II, III, numbers like 2, 3, etc.) as separate entries.
            We group fragmentary observations together.

            NOTE: target_chunk_size=8 can produce chunks of 200+ words for dense text.
            If LLM output truncation occurs, reduce to 4-5.
            """
            chunks = []
            current_chunk = []

            # Section markers to detect new sections
            section_markers = {'I', 'II', 'III', '2', '3', '4', '5', '6', '7', '8', '9'}

            for i, line in enumerate(lines):
                # Skip empty lines but track them for paragraph breaks
                if not line:
                    if current_chunk:
                        # Check if we've accumulated enough
                        if len(current_chunk) >= target_chunk_size:
                            # Get context from previous lines
                            start_idx = max(0, i - len(current_chunk) - context_lines)
                            context = '\n'.join(lines[start_idx:i-len(current_chunk)])

                            chunks.append({
                                'source': '\n'.join(current_chunk),
                                'context': context,
                                'translation': ''  # Will be generated
                            })
                            current_chunk = []
                    continue

                # Check for section markers - these get their own entry
                if line in section_markers:
                    # Save current chunk first
                    if current_chunk:
                        start_idx = max(0, i - len(current_chunk) - context_lines)
                        context = '\n'.join([l for l in lines[start_idx:i-len(current_chunk)] if l])
                        chunks.append({
                            'source': '\n'.join(current_chunk),
                            'context': context,
                            'translation': ''
                        })
                        current_chunk = []

                    # Add section marker as its own entry (blank - just a marker)
                    chunks.append({
                        'source': '',  # Empty source signals page break
                        'context': '',
                        'translation': '',
                        'chapter': line  # Store section number
                    })
                    continue

                # Check for date/time/place headers (La date:, L'heure:, Le lieu:, Le temps:)
                if any(line.startswith(prefix) for prefix in ['La date', 'L\'heure', 'Le lieu', 'Le temps', 'la date', 'l\'heure', 'le lieu', 'le temps']):
                    # Save current chunk first
                    if current_chunk:
                        start_idx = max(0, i - len(current_chunk) - context_lines)
                        context = '\n'.join([l for l in lines[start_idx:i-len(current_chunk)] if l])
                        chunks.append({
                            'source': '\n'.join(current_chunk),
                            'context': context,
                            'translation': ''
                        })
                        current_chunk = []

                current_chunk.append(line)

                # If chunk is getting large, save it
                if len(current_chunk) >= target_chunk_size * 2:
                    start_idx = max(0, i - len(current_chunk) - context_lines)
                    context = '\n'.join([l for l in lines[start_idx:i-len(current_chunk)] if l])
                    chunks.append({
                        'source': '\n'.join(current_chunk),
                        'context': context,
                        'translation': ''
                    })
                    current_chunk = []

            # Don't forget the last chunk
            if current_chunk:
                start_idx = max(0, len(lines) - len(current_chunk) - context_lines)
                context = '\n'.join([l for l in lines[start_idx:len(lines)-len(current_chunk)] if l])
                chunks.append({
                    'source': '\n'.join(current_chunk),
                    'context': context,
                    'translation': ''
                })

            return chunks

        # Chunk the text
        chunks = chunk_perec_lines(lines)
        print(f"Created {len(chunks)} chunks from {len(lines)} lines")

        # Filter out empty chunks but keep chapter markers
        source_list = []
        translation_list = []
        context_list = []
        chapter_markers = []

        for chunk in chunks:
            source_list.append(chunk['source'])
            translation_list.append(chunk['translation'])
            context_list.append(chunk.get('context', ''))
            chapter_markers.append(chunk.get('chapter', ''))

        # Configuration for batch processing
        output_file = "textcreation/texts/interlinearouts/interlinear_perec.json"
        batch_size = 5  # Process 5 chunks at a time

        # Automatically detect resume point from existing file
        resume_from = find_resume_point(output_file)

        print("Starting Perec translation processing:")
        print(f"- Total chunks: {len(source_list)}")
        print(f"- Batch size: {batch_size}")
        print(f"- Output file: {output_file}")
        print(f"- Resume from index: {resume_from}")
        print("- Language: French (Perec - observational/fragmentary)")
        print("\nPress Ctrl+C to interrupt gracefully and save progress\n")

        # Lightweight French for batch processing
        class FrenchLight(Language):
            """Lightweight French for batch runs."""
            def __init__(self):
                self.name = "french"

            def get_grammar(self, word: str, sent: str, ind: int):
                return ""

            def get_definition(self, word: str):
                return ""

            def parse_sent(self, sent: str):
                # Skip heavy parsing during batch runs
                return []

        # Custom processing for Perec with context and translation-first approach
        async def process_perec():
            global interrupted

            outputlist = [None] * len(source_list)

            # Load existing progress if resuming
            if resume_from > 0 and os.path.exists(output_file):
                try:
                    with open(output_file, 'r', encoding='utf8') as f:
                        existing_data = json.load(f)
                        for i, entry in enumerate(existing_data):
                            if i < len(outputlist) and entry is not None:
                                outputlist[i] = entry
                    print(f"Resuming from index {resume_from}")
                except Exception as e:
                    print(f"Warning: Could not load existing progress: {e}")

            total_entries = len(source_list)
            language = FrenchLight()

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
                    context = context_list[i]
                    chapter = chapter_markers[i]

                    # Handle chapter markers (empty source)
                    if not source.strip():
                        outputlist[i] = {
                            "source": "",
                            "translation": "",
                            "interlinear": [],
                            "parseinfo": [],
                            "rawoutput": "",
                            "chapter": chapter
                        }
                        continue

                    # Format prompt with context
                    prompt = userprompt.format(french=source.strip(), context=context.strip())
                    messages = llm.format_messages(userprompt=prompt, systemprompt=systemprompt)
                    async_request = llm.get_completion_async(messages=messages, timeout_seconds=REQUEST_TIMEOUT_SECONDS)
                    async_requests.append(async_request)
                    valid_entries.append(i)

                # Process this batch
                if async_requests:
                    try:
                        print(f"Waiting for {len(async_requests)} async requests to complete...")
                        tasks = [asyncio.create_task(coro) for coro in async_requests]
                        task_to_index = {task: idx for task, idx in zip(tasks, valid_entries)}
                        pending = set(tasks)
                        results_map = {idx: None for idx in valid_entries}

                        while pending:
                            if interrupted:
                                for t in pending:
                                    t.cancel()
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

                        # Process results
                        for idx in valid_entries:
                            if interrupted and results_map[idx] is None:
                                continue
                            result = results_map[idx] if results_map[idx] is not None else ""
                            source = source_list[idx]

                            # Parse the Perec output format: & translation & interlinear |...|
                            translation = ""
                            interlist = []

                            if result:
                                try:
                                    # Extract translation between & markers
                                    if '&' in result:
                                        parts = result.split('&')
                                        if len(parts) >= 2:
                                            translation = parts[1].strip()
                                        if len(parts) >= 3:
                                            # Parse interlinear from the rest
                                            interlinear_part = parts[2] if len(parts) > 2 else parts[-1]
                                            interlist = parseInterlinear(interlinear_part)
                                    else:
                                        # Fallback: try to parse as regular interlinear
                                        interlist = parseInterlinear(result)
                                except Exception as e:
                                    print(f"  Warning: Error parsing result for {idx}: {e}")

                            # Verify quality and track for retry
                            verification = verify_interlinear_quality(source, interlist)

                            parseinfo = language.parse_sent(source)
                            outputlist[idx] = {
                                "source": source,
                                "translation": translation,
                                "interlinear": interlist,
                                "parseinfo": parseinfo,
                                "rawoutput": result,
                                "chapter": chapter_markers[idx],
                                "verification": verification  # Store for retry tracking
                            }

                            if not verification['valid']:
                                print(f"  ⚠ Entry {idx} verification issue: {verification['reason']}")

                    except Exception as e:
                        print(f"Error processing batch {batch_number}: {type(e).__name__}: {e!r}")
                        continue

                # Retry failed entries from this batch (up to 2 retries)
                retry_entries = [i for i in range(batch_start, batch_end)
                                if outputlist[i] and outputlist[i].get('verification')
                                and not outputlist[i]['verification'].get('valid', True)]

                if retry_entries and not interrupted:
                    print(f"\n  Retrying {len(retry_entries)} failed entries from this batch...")
                    retry_addendum_prompt = None
                    try:
                        retry_addendum_prompt = lib.find_prompt_by_title("InterlinearRetryAddendum")
                    except Exception:
                        pass

                    for retry_attempt in range(2):
                        if not retry_entries or interrupted:
                            break

                        print(f"  Retry attempt {retry_attempt + 1}/2 for {len(retry_entries)} entries")

                        retry_requests = []
                        retry_indices = []

                        for idx in retry_entries:
                            source = source_list[idx]
                            context = context_list[idx]
                            error_reason = outputlist[idx].get('verification', {}).get('reason', 'Unknown error')

                            # Add retry addendum if available
                            base_prompt = userprompt.format(french=source.strip(), context=context.strip())
                            if retry_addendum_prompt:
                                prompt = base_prompt + "\n\n" + retry_addendum_prompt.format(error_reason=error_reason)
                            else:
                                prompt = base_prompt + f"\n\nIMPORTANT: Previous attempt failed: {error_reason}. Please ensure complete coverage of all words."

                            messages = llm.format_messages(userprompt=prompt, systemprompt=systemprompt)
                            async_request = llm.get_completion_async(messages=messages, timeout_seconds=REQUEST_TIMEOUT_SECONDS)
                            retry_requests.append(async_request)
                            retry_indices.append(idx)

                        # Process retry requests
                        try:
                            tasks = [asyncio.create_task(coro) for coro in retry_requests]
                            task_to_index = {task: idx for task, idx in zip(tasks, retry_indices)}
                            pending = set(tasks)

                            while pending and not interrupted:
                                done, pending = await asyncio.wait(pending, timeout=1, return_when=asyncio.FIRST_COMPLETED)
                                for t in done:
                                    idx = task_to_index[t]
                                    try:
                                        result = t.result()
                                    except Exception as e:
                                        print(f"    Error in retry for index {idx}: {e}")
                                        continue

                                    source = source_list[idx]
                                    translation = ""
                                    interlist = []

                                    if result:
                                        try:
                                            if '&' in result:
                                                parts = result.split('&')
                                                if len(parts) >= 2:
                                                    translation = parts[1].strip()
                                                if len(parts) >= 3:
                                                    interlinear_part = parts[2] if len(parts) > 2 else parts[-1]
                                                    interlist = parseInterlinear(interlinear_part)
                                            else:
                                                interlist = parseInterlinear(result)
                                        except Exception as e:
                                            print(f"    Warning: Error parsing retry result for {idx}: {e}")

                                    verification = verify_interlinear_quality(source, interlist)

                                    if verification['valid']:
                                        print(f"    ✓ Entry {idx} fixed on retry")
                                        parseinfo = language.parse_sent(source)
                                        outputlist[idx] = {
                                            "source": source,
                                            "translation": translation,
                                            "interlinear": interlist,
                                            "parseinfo": parseinfo,
                                            "rawoutput": result,
                                            "chapter": chapter_markers[idx],
                                            "verification": verification
                                        }
                                    else:
                                        print(f"    ✗ Entry {idx} still failing: {verification['reason']}")
                                        outputlist[idx]['verification'] = verification
                        except Exception as e:
                            print(f"    Error in retry batch: {e}")

                        # Update retry list for next attempt
                        retry_entries = [i for i in retry_indices
                                        if outputlist[i] and outputlist[i].get('verification')
                                        and not outputlist[i]['verification'].get('valid', True)]

                # Fill in any None entries and mark failed entries
                for i in range(batch_start, batch_end):
                    if outputlist[i] is None:
                        outputlist[i] = {
                            "source": source_list[i],
                            "translation": "",
                            "interlinear": [],
                            "parseinfo": [],
                            "rawoutput": "",
                            "chapter": chapter_markers[i],
                            "_failed_verification": True,  # Mark as failed for writehtml.py to detect
                        }
                    elif outputlist[i].get('verification') and not outputlist[i]['verification'].get('valid', True):
                        # Mark entries that failed verification but have partial data
                        outputlist[i]['_failed_verification'] = True

                # Write progress to file after each batch
                try:
                    with open(output_file, 'w', encoding='utf8') as file:
                        json.dump(outputlist, file, ensure_ascii=False, indent=2)
                    print(f"Progress saved to {output_file}")
                except Exception as e:
                    print(f"Error saving progress: {e}")

                if interrupted:
                    break

            return outputlist

        translations = asyncio.run(process_perec())

        # Check for any failed entries and warn
        failed_entries = [i for i, t in enumerate(translations) if t and t.get('_failed_verification')]
        if failed_entries:
            print("\n" + "="*60)
            print("⚠⚠⚠ WARNING: VERIFICATION FAILURES DETECTED ⚠⚠⚠")
            print("="*60)
            print(f"The following {len(failed_entries)} entries failed verification and may have")
            print("truncated or incorrect interlinear data:")
            for idx in failed_entries[:20]:  # Show first 20
                source_preview = translations[idx]['source'][:50] + "..." if len(translations[idx]['source']) > 50 else translations[idx]['source']
                print(f"  Entry {idx}: {source_preview}")
            if len(failed_entries) > 20:
                print(f"  ... and {len(failed_entries) - 20} more")
            print("\nThese entries should be re-processed or manually reviewed.")
            print("To re-process specific entries, you may need to clear them from")
            print(f"the output file: {output_file}")
            print("="*60)

        # Final message
        if not interrupted:
            print("\n✅ Perec processing completed successfully!")
            print("📁 Results saved to: " + str(output_file))
            print("🏛️ Ready for use in the Gloss interlinear reader!")
        else:
            print("\n⚠️  Processing was interrupted but progress has been saved.")
            print("📁 Partial results available at: " + str(output_file))

    # Check for Gospel of Matthew mode
    # Usage: --matthew [start_chapter] [end_chapter]
    # Examples: --matthew (all), --matthew 1 2 (chapters 1-2 only)
    elif len(sys.argv) > 1 and sys.argv[1] == "--matthew":
        # Parse optional chapter range
        start_chapter = int(sys.argv[2]) if len(sys.argv) > 2 else None
        end_chapter = int(sys.argv[3]) if len(sys.argv) > 3 else start_chapter

        chapter_desc = f"chapters {start_chapter}-{end_chapter}" if start_chapter else "all chapters"
        print("="*60)
        print(f"Gospel of Matthew (Greek) Processing - {chapter_desc}")
        print("="*60)

        # Load yml file for prompts - use same Greek prompts as Mark
        lib = promptlibrary("textcreation/promptlibrary.yml")
        userprompt = lib.find_prompt_by_title("InterlinearUserGreek")
        systemprompt = lib.find_prompt_by_title("InterlinearSystemGreek")

        llm = claude()

        # Load Gospel of Matthew verses
        print("\nLoading Gospel of Matthew verses...")
        verses = load_nt_verses(
            'textcreation/data/matthew_grc.txt',
            'textcreation/data/matthew_eng.txt'
        )

        # Filter by chapter range if specified
        if start_chapter:
            verses = [v for v in verses
                      if start_chapter <= int(v["verse"].split(":")[0]) <= end_chapter]
            print(f"  Filtered to chapters {start_chapter}-{end_chapter}: {len(verses)} verses")

        # Prepare source and translation lists, preserving verse references
        source_list = [v["source"] for v in verses]
        translation_list = [v["translation"] for v in verses]
        verse_list = [v["verse"] for v in verses]

        # Configuration for batch processing
        # Use chapter-specific output file if filtering
        if start_chapter:
            output_file = f"textcreation/texts/interlinearouts/interlinear_matthew_{start_chapter}_{end_chapter}.json"
        else:
            output_file = "textcreation/texts/interlinearouts/interlinear_matthew.json"
        batch_size = 10  # Process 10 verses at a time

        # Automatically detect resume point from existing file
        resume_from = find_resume_point(output_file)

        print("Starting Gospel of Matthew translation processing:")
        print(f"- Total verses: {len(source_list)}")
        print(f"- Batch size: {batch_size}")
        print(f"- Output file: {output_file}")
        print(f"- Resume from index: {resume_from}")
        print("- Language: Koine Greek (Gospel of Matthew)")
        print("\nPress Ctrl+C to interrupt gracefully and save progress\n")

        # Custom processing for Gospel of Matthew with verse references
        async def process_matthew():
            translations = await getTranslations(
                source_list,
                translation_list,
                llm,
                userprompt,
                systemprompt,
                language=GreekLight(),
                speaker_list=[],
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

        translations = asyncio.run(process_matthew())

        # Final message
        if not interrupted:
            print("\n✅ Gospel of Matthew processing completed successfully!")
            print("📁 Results saved to: " + str(output_file))
            print("🏛️ Ready for use in the Gloss interlinear reader!")
        else:
            print("\n⚠️  Processing was interrupted but progress has been saved.")
            print("📁 Partial results available at: " + str(output_file))

    # Check for Gospel of Luke mode
    # Usage: --luke [start_chapter] [end_chapter]
    # Examples: --luke (all), --luke 1 2 (chapters 1-2 only)
    elif len(sys.argv) > 1 and sys.argv[1] == "--luke":
        # Parse optional chapter range
        start_chapter = int(sys.argv[2]) if len(sys.argv) > 2 else None
        end_chapter = int(sys.argv[3]) if len(sys.argv) > 3 else start_chapter

        chapter_desc = f"chapters {start_chapter}-{end_chapter}" if start_chapter else "all chapters"
        print("="*60)
        print(f"Gospel of Luke (Greek) Processing - {chapter_desc}")
        print("="*60)

        # Load yml file for prompts - use same Greek prompts as Mark
        lib = promptlibrary("textcreation/promptlibrary.yml")
        userprompt = lib.find_prompt_by_title("InterlinearUserGreek")
        systemprompt = lib.find_prompt_by_title("InterlinearSystemGreek")

        llm = claude()

        # Load Gospel of Luke verses
        print("\nLoading Gospel of Luke verses...")
        verses = load_nt_verses(
            'textcreation/data/luke_grc.txt',
            'textcreation/data/luke_eng.txt'
        )

        # Filter by chapter range if specified
        if start_chapter:
            verses = [v for v in verses
                      if start_chapter <= int(v["verse"].split(":")[0]) <= end_chapter]
            print(f"  Filtered to chapters {start_chapter}-{end_chapter}: {len(verses)} verses")

        # Prepare source and translation lists, preserving verse references
        source_list = [v["source"] for v in verses]
        translation_list = [v["translation"] for v in verses]
        verse_list = [v["verse"] for v in verses]

        # Configuration for batch processing
        # Use chapter-specific output file if filtering
        if start_chapter:
            output_file = f"textcreation/texts/interlinearouts/interlinear_luke_{start_chapter}_{end_chapter}.json"
        else:
            output_file = "textcreation/texts/interlinearouts/interlinear_luke.json"
        batch_size = 10  # Process 10 verses at a time

        # Automatically detect resume point from existing file
        resume_from = find_resume_point(output_file)

        print("Starting Gospel of Luke translation processing:")
        print(f"- Total verses: {len(source_list)}")
        print(f"- Batch size: {batch_size}")
        print(f"- Output file: {output_file}")
        print(f"- Resume from index: {resume_from}")
        print("- Language: Koine Greek (Gospel of Luke)")
        print("\nPress Ctrl+C to interrupt gracefully and save progress\n")

        # Custom processing for Gospel of Luke with verse references
        async def process_luke():
            translations = await getTranslations(
                source_list,
                translation_list,
                llm,
                userprompt,
                systemprompt,
                language=GreekLight(),
                speaker_list=[],
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

        translations = asyncio.run(process_luke())

        # Final message
        if not interrupted:
            print("\n✅ Gospel of Luke processing completed successfully!")
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