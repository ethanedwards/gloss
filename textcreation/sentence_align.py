import ollama
import json
import re
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import itertools
import json
import nltk
import sys
import time
import os
from datetime import datetime
import logging
import traceback
from difflib import SequenceMatcher

# Configuration
DEBUG = True  # Enable verbose debug output
DEBUG_LEVEL = 1  # 0=minimal, 1=normal, 2=verbose, 3=very verbose
TEST_MODE = False  # Only process first N sentences for testing
TEST_SENTENCE_LIMIT = 15  # Number of sentences to process in test mode

# Model selection - try these in order if one fails
PREFERRED_MODELS = [
    "qwen2.5:14b",     # Best instruction following
    "mixtral:8x7b",    # Good at structured tasks
    "llama3.1:8b",     # More reliable extraction
    "qwen2.5:7b"       # Fallback
]

# Robustness settings for long runs
SAVE_PROGRESS_EVERY = 10  # Save intermediate results every N sentences
MAX_CONSECUTIVE_FAILURES = 5  # Abort if this many sentences fail in a row
LLM_RETRY_DELAY = 2  # Seconds to wait between retries on LLM errors
LLM_TIMEOUT = 60  # Seconds to wait for LLM response before timing out

# Extraction quality thresholds
MIN_LENGTH_RATIO = 0.4  # Minimum acceptable translation/source ratio
MAX_LENGTH_RATIO = 2.5  # Maximum acceptable translation/source ratio
MIN_LENGTH_RATIO_STRICT = 0.6  # Strict minimum for long sources (>100 chars)
MAX_LENGTH_RATIO_STRICT = 1.8  # Strict maximum for long sources

# Logging configuration
def setup_logging(output_file):
    """Setup comprehensive logging to file and console"""
    log_file = output_file.replace('.json', '.log')

    # Create logger
    logger = logging.getLogger('sentence_align')
    logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    logger.handlers = []

    # File handler - captures everything
    file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)

    # Console handler - only important messages
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger, log_file

# Global logger (will be initialized in main)
logger = None

def debug_print(msg, level=1, min_level=0):
    """Print debug messages with indentation levels

    Args:
        msg: Message to print
        level: Indentation level (1-5)
        min_level: Minimum DEBUG_LEVEL required to show this message
    """
    if DEBUG and DEBUG_LEVEL >= min_level:
        indent = "  " * (level - 1)
        print(f"{indent}{msg}", flush=True)

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
            
        # For Chinese text, split on common Chinese sentence-ending punctuation
        if any('\u4e00' <= char <= '\u9fff' for char in paragraph):  # Check if text contains Chinese characters
            # Common Chinese sentence-ending punctuation: 。！？!?
            sentences = []
            current_sentence = ""
            for char in paragraph:
                current_sentence += char
                if char in '。！？!?':
                    if current_sentence.strip():
                        sentences.append(current_sentence.strip())
                    current_sentence = ""
            if current_sentence.strip():  # Add any remaining text
                sentences.append(current_sentence.strip())
        else:
            # Use NLTK for non-Chinese text
            sentences = nltk.sent_tokenize(paragraph)
            
        print(f"paragraph: {paragraph}")
        print(f"sentences in paragraph: {len(sentences)}")
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

def write_to_json(source_list, translation_list, file_name='translation.json'):
    translation_pairs = [{'source': source, 'translation': translation} for source, translation in zip(source_list, translation_list)]

    with open(file_name, 'w', encoding='utf8') as file:
        json.dump(translation_pairs, file, ensure_ascii=False, indent=2)

def save_progress(source_out, trans_out, output_file, sentence_idx, is_final=False):
    """
    Save intermediate progress to both checkpoint and incremental output.

    This ensures we always have usable partial results even if interrupted.
    """
    if is_final:
        # Final save to main output file
        write_to_json(source_out, trans_out, output_file)
        msg = f"✅ Final output saved to {output_file}"
        print(f"\n{msg}")
        if logger:
            logger.info(msg)
        return output_file
    else:
        # Save to both checkpoint and incremental output
        checkpoint_file = output_file.replace('.json', f'_checkpoint_sent{sentence_idx}.json')
        incremental_file = output_file.replace('.json', '_incremental.json')

        write_to_json(source_out, trans_out, checkpoint_file)
        write_to_json(source_out, trans_out, incremental_file)

        msg = f"💾 Progress saved (sentence {sentence_idx})"
        print(f"\n{msg}")
        if logger:
            logger.info(f"Checkpoint: {checkpoint_file}")
            logger.info(f"Incremental: {incremental_file}")
        return checkpoint_file

def load_checkpoint(output_file, auto_resume=False):
    """
    Try to load the most recent checkpoint.

    Args:
        output_file: Base output filename
        auto_resume: If True, automatically resume without asking

    Returns:
        tuple: (source_out, trans_out, start_idx, trans_consumed)
    """
    base_dir = os.path.dirname(output_file) or '.'
    base_name = os.path.basename(output_file).replace('.json', '')

    # Find all checkpoint files
    checkpoint_pattern = f"{base_name}_checkpoint_sent*.json"
    checkpoints = []

    if os.path.exists(base_dir):
        for fname in os.listdir(base_dir):
            if fname.startswith(base_name) and '_checkpoint_sent' in fname:
                try:
                    checkpoint_num = int(fname.split('_checkpoint_sent')[1].split('.json')[0])
                    checkpoints.append((checkpoint_num, os.path.join(base_dir, fname)))
                except:
                    continue

    # Also check for incremental output file
    incremental_file = output_file.replace('.json', '_incremental.json')
    incremental_exists = os.path.exists(incremental_file)

    if checkpoints or incremental_exists:
        # Prefer checkpoint over incremental
        if checkpoints:
            checkpoints.sort(reverse=True)
            latest_num, latest_file = checkpoints[0]
            source_file = latest_file
            sentence_num = latest_num
        else:
            source_file = incremental_file
            sentence_num = "unknown"

        print(f"\n📂 Found saved progress:")
        print(f"   File: {source_file}")
        print(f"   Sentences completed: {sentence_num}")

        should_resume = auto_resume
        if not auto_resume:
            response = input(f"Resume from this checkpoint? (y/n): ").strip().lower()
            should_resume = (response == 'y')

        if should_resume:
            with open(source_file, 'r', encoding='utf8') as f:
                data = json.load(f)
            source_out = [pair['source'] for pair in data]
            trans_out = [pair['translation'] for pair in data]

            # Calculate how much translation was consumed
            # (We'll recalculate this in the main loop)
            trans_consumed = sum(len(t) for t in trans_out)

            start_idx = len(source_out)
            print(f"✓ Resumed from checkpoint with {len(source_out)} aligned pairs")
            if logger:
                logger.info(f"Resumed from {source_file} with {len(source_out)} pairs")
            return source_out, trans_out, start_idx, trans_consumed

    return [], [], 0, 0




def validate_and_expand_extraction(extracted, source_sent, trans_context, full_trans_remaining):
    """
    If extraction is too short, try to expand it by looking for sentence boundaries.
    This helps correct cases where LLM extracted only part of the sentence.
    
    Returns:
        str: Expanded extraction, or original if expansion not needed/possible
    """
    source_len = len(source_sent)
    extracted_len = len(extracted)
    ratio = extracted_len / source_len if source_len > 0 else 0
    
    # Only expand if source is substantial and extraction is too short
    if ratio >= 0.5 or source_len < 100:
        return extracted
    
    print(f"  ⚠️ Extraction too short (ratio={ratio:.2f}), attempting expansion...")
    if logger:
        logger.debug(f"Attempting to expand short extraction (ratio={ratio:.2f})")
    
    # Find where extraction is in the context
    idx = full_trans_remaining.find(extracted)
    if idx < 0:
        # Try normalized search
        extracted_norm = ' '.join(extracted.split())
        trans_norm = ' '.join(full_trans_remaining.split())
        idx = trans_norm.find(extracted_norm)
        if idx < 0:
            print(f"  ✗ Cannot locate extraction in context for expansion")
            return extracted
    
    # Look for sentence boundaries after extraction
    end_idx = idx + len(extracted)
    remaining = full_trans_remaining[end_idx:end_idx + 500]
    
    # Try to find next sentence boundary
    best_expansion = extracted
    best_ratio_diff = abs(ratio - 1.0)
    
    for punct in ['. ', '! ', '? ', '; ', ': ']:
        next_bound = remaining.find(punct)
        if 0 < next_bound < 400:
            expanded = extracted + remaining[:next_bound + 1].rstrip()
            new_ratio = len(expanded) / source_len
            ratio_diff = abs(new_ratio - 1.0)
            
            # Accept if this gets us closer to 1.0 ratio and stays in bounds
            if (MIN_LENGTH_RATIO <= new_ratio <= MAX_LENGTH_RATIO and 
                ratio_diff < best_ratio_diff):
                best_expansion = expanded
                best_ratio_diff = ratio_diff
    
    if best_expansion != extracted:
        new_ratio = len(best_expansion) / source_len
        print(f"  ✓ Expanded from {extracted_len} to {len(best_expansion)} chars (ratio: {ratio:.2f} → {new_ratio:.2f})")
        if logger:
            logger.info(f"Expanded extraction: {extracted_len} → {len(best_expansion)} chars")
        return best_expansion
    else:
        print(f"  ✗ No valid expansion found")
        return extracted


def select_best_model():
    """
    Try to find the best available model from our preference list.
    Returns the first model that's available.
    """
    available_models = []
    try:
        result = ollama.list()
        available_models = [model['name'] for model in result.get('models', [])]
    except Exception as e:
        print(f"⚠️ Warning: Could not list available models: {e}")
        if logger:
            logger.warning(f"Could not list models: {e}")
        return PREFERRED_MODELS[-1]  # Return fallback
    
    for preferred in PREFERRED_MODELS:
        # Check for exact match or base model match (e.g., "qwen2.5:14b" matches "qwen2.5")
        for available in available_models:
            if preferred in available or available in preferred:
                print(f"✓ Selected model: {available}")
                if logger:
                    logger.info(f"Selected model: {available}")
                return available
    
    # If none found, return first preferred and hope it works
    print(f"⚠️ No preferred models found, using: {PREFERRED_MODELS[0]}")
    if logger:
        logger.warning(f"No preferred models available, defaulting to {PREFERRED_MODELS[0]}")
    return PREFERRED_MODELS[0]


def align_with_llm_word_level(source_sents, trans_sents, model_name=None, output_file=None, resume=True):
    """
    Align source with translation sentence-by-sentence using LLM to extract matching text.

    Key improvements:
    - Eliminated backward context confusion
    - Aggressive length validation with expansion
    - Drift detection and resync
    - Better model selection
    - Simplified prompts
    """
    if model_name is None:
        model_name = select_best_model()
    
    if logger:
        logger.info("="*80)
        logger.info(f"Starting alignment with model: {model_name}")
        logger.info(f"Output file: {output_file}")
        logger.info("="*80)

    # Try to resume from checkpoint
    source_out = []
    trans_out = []
    start_idx = 0
    initial_trans_consumed = 0

    if resume and output_file:
        source_out, trans_out, start_idx, initial_trans_consumed = load_checkpoint(output_file)
        if start_idx > 0:
            msg = f"Resuming from sentence {start_idx + 1}"
            print(msg)
            if logger:
                logger.info(msg)
                logger.info(f"Initial translation consumed: {initial_trans_consumed} chars")

    # Apply test mode limit if enabled
    if TEST_MODE:
        source_sents = source_sents[:TEST_SENTENCE_LIMIT]
        debug_print(f"⚠️  TEST MODE: Limited to first {TEST_SENTENCE_LIMIT} source sentences", 1)

    debug_print(f"\n{'='*80}", 1)
    debug_print(f"Starting alignment: {len(source_sents)} source sentences, {len(trans_sents)} translation sentences", 1)
    if start_idx > 0:
        debug_print(f"Resuming from sentence {start_idx + 1}", 1)
    debug_print(f"{'='*80}", 1)

    source_idx = start_idx

    # Track cumulative translation text to ensure we're consuming it correctly
    trans_buffer = " ".join(trans_sents)
    trans_total = len(trans_buffer)
    trans_consumed = initial_trans_consumed  # Start from where we left off

    fallback_count = 0
    successful_extractions = 0
    consecutive_failures = 0
    last_save_idx = start_idx

    while source_idx < len(source_sents):
        try:
            print(f"\n{'='*80}")
            print(f"SENTENCE {source_idx + 1}/{len(source_sents)}")
            print(f"{'='*80}")

            if logger:
                logger.info(f"\n{'='*80}")
                logger.info(f"Processing sentence {source_idx + 1}/{len(source_sents)}")
                logger.info(f"{'='*80}")

            source_sent = source_sents[source_idx]
            print(f"\nSOURCE:")
            print(f"{source_sent}")
            print()

            if logger:
                logger.debug(f"Source text: {source_sent}")

            # Augment short sentences
            augment = 0
            while len(source_sent) < 10 and source_idx < len(source_sents) - 1:
                source_idx += 1
                source_sent += " " + source_sents[source_idx]
                augment += 1
                debug_print(f"Augmented with next sentence (augment={augment})", 2)

            # Get translation context
            context_length = 1200  # characters
            forward_text = trans_buffer[trans_consumed:trans_consumed + context_length]
            trans_context = forward_text  # Clean, simple context

            print(f"\nTRANSLATION CONTEXT (showing LLM what to search):")
            print(trans_context)
            print()

            if not trans_context.strip():
                print(f"⚠️  No more translation text available!")
                print(f"   Adding padding entry")
                # Add padding entry for source without translation
                source_out.append(source_sent)
                trans_out.append("[NO TRANSLATION AVAILABLE]")
                source_idx += 1
                continue

            # Try to get alignment with retries
            max_retries = 3
            matched_trans = None
            needs_more_context = False

            for attempt in range(max_retries):
                print(f"Attempt {attempt + 1}/{max_retries}...")
                matched_trans = get_alignment_with_verification(
                    source_sent,
                    trans_context,
                    trans_buffer[trans_consumed:],  # Full remaining text for verification
                    model_name,
                    attempt
                )

                if matched_trans == "NEED_MORE_CONTEXT":
                    msg = f"⚠️  LLM requesting more context - increasing context window"
                    print(msg)
                    if logger:
                        logger.warning(f"Sentence {source_idx + 1}: LLM needs more context")
                    needs_more_context = True
                    # Double the context window and retry (up to 3000 chars)
                    context_length = min(context_length * 2, 3000, len(trans_buffer) - trans_consumed)
                    trans_context = trans_buffer[trans_consumed:trans_consumed + context_length]
                    print(f"  New context length: {context_length} chars")
                    if logger:
                        logger.debug(f"Increased context to {context_length} chars")
                    # Reset matched_trans to None and continue
                    matched_trans = None
                    continue
                elif matched_trans is not None:
                    successful_extractions += 1
                    print(f"✓ Extraction successful on attempt {attempt + 1}")
                    if logger:
                        logger.info(f"Sentence {source_idx + 1}: Extraction successful on attempt {attempt + 1}")
                    break
                else:
                    print(f"✗ Attempt {attempt + 1} failed")
                    if logger:
                        logger.warning(f"Sentence {source_idx + 1}: Attempt {attempt + 1} failed")

            # After all retries, check if we still don't have a match
            if matched_trans == "NO_TRANSLATION":
                # Source has no corresponding translation (header, page number, etc.)
                msg = f"\n⚠️  No translation available for this source (likely header/formatting)"
                print(msg)
                if logger:
                    logger.warning(f"Sentence {source_idx + 1}: No translation (header/formatting)")

                # Don't consume any translation text, just mark it
                source_out.append(source_sent)
                trans_out.append("[NO TRANSLATION - HEADER/FORMATTING]")
                source_idx += 1
                # Don't count as failure since this is expected for headers
                consecutive_failures = 0
                print(f"\n✓ Pair {len(source_out)} aligned (no translation case)")
                continue

            elif matched_trans is None or matched_trans == "NEED_MORE_CONTEXT":
                # Fallback: take next sentence-ish chunk
                fallback_count += 1
                msg = f"\n⚠️  All attempts failed, using fallback extraction"
                print(msg)
                if logger:
                    logger.error(f"Sentence {source_idx + 1}: All LLM attempts failed, using fallback")

                # Simple fallback: take roughly source-length chars
                fallback_length = int(len(source_sent) * 1.2)
                matched_trans = trans_context[:fallback_length].strip()
                
                # Try to end at sentence boundary
                for punct in ['. ', '! ', '? ', '; ']:
                    last_punct = matched_trans.rfind(punct)
                    if last_punct > fallback_length * 0.5:  # At least halfway through
                        matched_trans = matched_trans[:last_punct + 1]
                        break
                
                print(f"Fallback extracted: {matched_trans}")
                if logger:
                    logger.debug(f"Fallback extraction: {matched_trans[:100]}...")

            # Try to expand if too short
            matched_trans = validate_and_expand_extraction(
                matched_trans, 
                source_sent, 
                trans_context,
                trans_buffer[trans_consumed:]
            )

            # Final sanity check on length
            ratio = len(matched_trans) / len(source_sent) if len(source_sent) > 0 else 1.0
            if len(source_sent) > 50:  # Only check substantial sources
                expected_min = len(source_sent) * MIN_LENGTH_RATIO
                expected_max = len(source_sent) * MAX_LENGTH_RATIO
                
                if not (expected_min <= len(matched_trans) <= expected_max):
                    print(f"  ⚠️ WARNING: Final extraction length {len(matched_trans)} outside expected range [{expected_min:.0f}, {expected_max:.0f}]")
                    print(f"  Ratio: {ratio:.2f} (expected: {MIN_LENGTH_RATIO:.2f} - {MAX_LENGTH_RATIO:.2f})")
                    if logger:
                        logger.warning(f"Sentence {source_idx + 1}: Length ratio {ratio:.2f} outside bounds")

            # Update consumed position
            match_pos = trans_buffer[trans_consumed:].find(matched_trans)
            if match_pos >= 0:
                # Account for skipped characters before the match
                skipped = match_pos
                if skipped > 0:
                    print(f"(Skipped {skipped} chars before match)")
                trans_consumed += match_pos + len(matched_trans)
            else:
                # Try normalized match
                matched_norm = ' '.join(matched_trans.split())
                buffer_norm = ' '.join(trans_buffer[trans_consumed:trans_consumed + len(matched_trans) * 3].split())
                match_pos = buffer_norm.find(matched_norm)
                if match_pos >= 0:
                    trans_consumed += match_pos + len(matched_trans)
                else:
                    print(f"⚠️  Warning: matched text not found in buffer at expected position")
                    trans_consumed += len(matched_trans)

            print(f"\nTranslation consumed: {trans_consumed}/{trans_total} ({trans_consumed/trans_total:.1%})")

            source_out.append(source_sent)
            trans_out.append(matched_trans)
            source_idx += 1

            print(f"\n✓ MATCHED TRANSLATION:")
            print(f"{matched_trans}")
            print(f"\n✓ Pair {len(source_out)} aligned successfully")

            # Reset consecutive failures on success
            if matched_trans is not None and matched_trans not in ["NEED_MORE_CONTEXT", "NO_TRANSLATION"]:
                consecutive_failures = 0
            else:
                consecutive_failures += 1

            # Check if too many consecutive failures
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                error_msg = f"❌ ERROR: {MAX_CONSECUTIVE_FAILURES} consecutive failures detected!"
                print(f"\n{error_msg}")
                print(f"Last successful: sentence {source_idx - consecutive_failures + 1}")
                print(f"Failed sentences: {source_idx - consecutive_failures + 2} through {source_idx + 1}")
                print(f"\nSaving progress and aborting...")

                if logger:
                    logger.critical(error_msg)
                    logger.critical(f"Last successful: sentence {source_idx - consecutive_failures + 1}")
                    logger.critical(f"Failed sentences: {source_idx - consecutive_failures + 2} through {source_idx + 1}")

                if output_file:
                    save_progress(source_out, trans_out, output_file, source_idx)
                raise RuntimeError(f"Too many consecutive failures ({consecutive_failures})")

            # Save progress periodically (both checkpoint and incremental)
            if output_file and (source_idx - last_save_idx) >= SAVE_PROGRESS_EVERY:
                save_progress(source_out, trans_out, output_file, source_idx, is_final=False)
                last_save_idx = source_idx
            # Also save after each sentence to incremental file (lightweight)
            elif output_file:
                incremental_file = output_file.replace('.json', '_incremental.json')
                write_to_json(source_out, trans_out, incremental_file)

        except KeyboardInterrupt:
            msg = f"\n\n⚠️  Interrupted by user at sentence {source_idx + 1}"
            print(msg)
            print(f"Saving progress...")
            if logger:
                logger.warning(msg)
            if output_file:
                save_progress(source_out, trans_out, output_file, source_idx, is_final=False)
                print(f"\n💾 Progress saved! You can resume by running the script again.")
                if logger:
                    logger.info("Progress saved. Resume by running script again.")
            raise
        except Exception as e:
            error_msg = f"\n❌ Unexpected error at sentence {source_idx + 1}: {e}"
            print(error_msg)
            print(f"Saving progress...")

            if logger:
                logger.critical(error_msg)
                logger.critical(f"Full traceback:\n{traceback.format_exc()}")
                logger.critical(f"Source sentence: {source_sent if 'source_sent' in locals() else 'N/A'}")
                logger.critical(f"Translation consumed: {trans_consumed}/{trans_total}")
                logger.critical(f"ERROR RECOVERY INFO:")
                logger.critical(f"  - To resume, run the script again (will auto-detect checkpoint)")
                logger.critical(f"  - Problem sentence index: {source_idx}")
                logger.critical(f"  - To skip this sentence, delete it from the source file or manually edit checkpoint")

            if output_file:
                save_progress(source_out, trans_out, output_file, source_idx, is_final=False)
                print(f"\n💾 Progress saved! Fix the error and run again to resume.")
                print(f"   Problem sentence: {source_idx + 1}")
                if logger:
                    logger.info("Progress saved before error. Can resume after fixing.")
            raise

    # Final statistics
    print(f"\n{'='*80}")
    print(f"ALIGNMENT COMPLETE!")
    print(f"{'='*80}")
    print(f"Total pairs: {len(source_out)}")
    print(f"Successful extractions: {successful_extractions}")
    print(f"Fallback extractions: {fallback_count}")
    print(f"Translation consumed: {trans_consumed}/{trans_total} ({trans_consumed/trans_total:.1%})")

    if logger:
        logger.info("="*80)
        logger.info("ALIGNMENT COMPLETE!")
        logger.info(f"Total pairs: {len(source_out)}")
        logger.info(f"Successful extractions: {successful_extractions}")
        logger.info(f"Fallback extractions: {fallback_count}")
        logger.info(f"Translation consumed: {trans_consumed}/{trans_total} ({trans_consumed/trans_total:.1%})")
        logger.info("="*80)

    # Check for unconsumed translation text
    remaining_trans = trans_total - trans_consumed
    if remaining_trans > 100:
        msg = f"\n⚠️  WARNING: {remaining_trans} chars of translation left unconsumed"
        print(msg)
        print(f"Preview: {trans_buffer[trans_consumed:trans_consumed+200]}...")
        if logger:
            logger.warning(f"{remaining_trans} chars of translation left unconsumed")
            logger.debug(f"Unconsumed preview: {trans_buffer[trans_consumed:trans_consumed+200]}")

    print(f"{'='*80}\n")

    # Save final output (overwrites incremental)
    if output_file:
        save_progress(source_out, trans_out, output_file, len(source_out) - 1, is_final=True)

    return source_out, trans_out


def get_alignment_with_verification(source_sent, trans_context, full_remaining_trans,
                                     model_name, attempt_num):
    """
    Get alignment and verify the extracted text actually exists in the translation.
    SIMPLIFIED: Plain text output - just extract the text, say PASS, or NEED_MORE_CONTEXT.
    """

    # Build simple prompt focused on word-for-word extraction
    prompt = build_simple_prompt(source_sent, trans_context, attempt_num)

    print(f"  Calling LLM (temp={0.1 if attempt_num == 0 else 0.3})...")

    # Retry logic with exponential backoff
    max_llm_retries = 3
    for llm_retry in range(max_llm_retries):
        try:
            response = ollama.generate(
                model=model_name,
                prompt=prompt,
                options={
                    "temperature": 0.1 if attempt_num == 0 else 0.3,  # Increase temp on retries
                    "num_predict": 800,  # Allow enough tokens for long sentences
                }
            )
            break  # Success, exit retry loop

        except Exception as llm_error:
            if llm_retry < max_llm_retries - 1:
                wait_time = LLM_RETRY_DELAY * (2 ** llm_retry)  # Exponential backoff
                print(f"  ⚠️  LLM error (attempt {llm_retry + 1}/{max_llm_retries}): {llm_error}")
                print(f"  Retrying in {wait_time} seconds...")
                if logger:
                    logger.error(f"LLM error (attempt {llm_retry + 1}): {llm_error}")
                    logger.debug(f"Full LLM error traceback:\n{traceback.format_exc()}")
                time.sleep(wait_time)
            else:
                error_msg = f"  ❌ LLM Error after {max_llm_retries} attempts: {llm_error}"
                print(error_msg)
                if logger:
                    logger.error(error_msg)
                    logger.debug(f"Full LLM error traceback:\n{traceback.format_exc()}")
                    logger.debug(f"Prompt sent to LLM:\n{prompt[:500]}...")
                return None

    try:
        answer = response['response'].strip()
        print(f"  LLM raw response: {answer}")

        # Handle special responses
        if answer == "PASS":
            source_len = len(source_sent.strip())
            # Validate PASS is only for short headers
            if source_len > 50:
                print(f"  ⚠️  WARNING: 'PASS' for long source ({source_len} chars) - likely an error!")
                print(f"  Source: {source_sent[:100]}...")
                if logger:
                    logger.warning(f"Suspicious PASS for {source_len} char source: {source_sent[:100]}")
                return None
            else:
                print(f"  ℹ️  LLM says: PASS (likely a header or formatting element)")
                if logger:
                    logger.info(f"PASS for source text (likely header/formatting): {source_sent[:100]}")
                return "NO_TRANSLATION"

        if answer == "NEED_MORE_CONTEXT":
            print(f"  ⚠️  LLM says: NEED_MORE_CONTEXT")
            return "NEED_MORE_CONTEXT"

        # Otherwise, treat it as extracted text
        extracted_trans = answer.strip()

        if not extracted_trans:
            print(f"  ❌ LLM returned empty text")
            return None

        print(f"  Extracted: {extracted_trans}")

        # STRICT length validation
        is_reasonable, ratio, quality_warning = check_extraction_quality(
            source_sent, extracted_trans,
            expected_ratio_min=MIN_LENGTH_RATIO,
            expected_ratio_max=MAX_LENGTH_RATIO
        )

        print(f"  Length check: source={len(source_sent)} chars, extracted={len(extracted_trans)} chars, ratio={ratio:.2f}")

        if not is_reasonable:
            print(f"  ❌ Quality check failed: {quality_warning}")

            # Reject short extractions for substantial sources
            if len(source_sent) > 100 and ratio < MIN_LENGTH_RATIO_STRICT:
                print(f"  ❌ Extraction too short for long source - rejecting!")
                if logger:
                    logger.warning(f"Rejected short extraction (ratio={ratio:.2f}) for {len(source_sent)} char source")
                return None

            # Reject over-extractions (likely multiple sentences)
            elif ratio > MAX_LENGTH_RATIO:
                print(f"  ❌ Extraction too long (ratio={ratio:.2f}) - likely multiple sentences!")
                if logger:
                    logger.warning(f"Rejected over-extraction (ratio={ratio:.2f}): {len(extracted_trans)} chars from {len(source_sent)} char source")
                return None

        # Verify the extracted translation actually exists in the context
        is_valid, verify_warning = verify_extraction(extracted_trans, full_remaining_trans)

        if is_valid:
            if verify_warning:
                print(f"  ✓ Verification passed with warning: {verify_warning}")
            else:
                print(f"  ✓ Verification passed - text found in translation")
            return extracted_trans
        else:
            print(f"  ❌ Verification failed: {verify_warning}")
            return None

    except Exception as e:
        print(f"  ❌ Error processing LLM response: {e}")
        if logger:
            logger.error(f"Error processing response: {e}")
            logger.debug(f"Full traceback:\n{traceback.format_exc()}")
        return None


def build_simple_prompt(source_sent, trans_context, attempt_num):
    """
    Build a simple prompt that just asks for plain text extraction.
    No JSON, no structured output - just copy the text word-for-word.
    """

    source_len = len(source_sent)

    # Simple examples showing direct extraction
    examples = """You extract the English translation that matches the French source sentence.

Your response should ONLY be ONE of these three things:
1. The extracted English text (word-for-word, complete)
2. The word "PASS" (only for headers/page numbers)
3. The phrase "NEED_MORE_CONTEXT" (rarely - only if text cuts off mid-word)

Examples:

Source: Longtemps, je me suis couché de bonne heure.
Translation context: FOR A LONG TIME, I went to bed early. Sometimes, my candle...
Your response: FOR A LONG TIME, I went to bed early.

Source: Je me demandais quelle heure il pouvait être; j'entendais le sifflement des trains qui, plus ou moins éloigné, comme le chant d'un oiseau dans une forêt, relevant les distances, me décrivait l'étendue de la campagne déserte où le voyageur se hâte vers la station prochaine; et le petit chemin qu'il suit va être gravé dans son souvenir.
Translation context: I would ask myself what time it might be; I could hear the whistling of the trains which, remote or nearby, like the singing of a bird in a forest, plotting the distances, described to me the extent of the deserted countryside where the traveler hastens toward the nearest station; and the little road he is following will be engraved on his memory. I would rest my cheeks...
Your response: I would ask myself what time it might be; I could hear the whistling of the trains which, remote or nearby, like the singing of a bird in a forest, plotting the distances, described to me the extent of the deserted countryside where the traveler hastens toward the nearest station; and the little road he is following will be engraved on his memory.

Source: CHAPTER 1
Translation context: For a long time, I went to bed early...
Your response: PASS

CRITICAL RULES:
1. Extract from the BEGINNING of the translation context
2. Copy the COMPLETE matching sentence - don't stop too early!
3. But DON'T extract too much - stop exactly where the French sentence ends
4. The extracted length should roughly match the source length
5. Copy word-for-word with EXACT punctuation
6. Only say "PASS" for very short headers (<20 chars)
7. Only say "NEED_MORE_CONTEXT" if text literally cuts off mid-sentence"""

    retry_note = ""
    if attempt_num > 0:
        retry_note = "\n\n**THIS IS A RETRY - Previous attempt failed. Extract more carefully!**"

    prompt = f"""{examples}

Task:
Source ({source_len} chars): {source_sent}

Translation context (extract from the START of this):
{trans_context}

Your response (just the extracted text, or PASS, or NEED_MORE_CONTEXT):{retry_note}"""

    return prompt


def verify_extraction(extracted_text, full_translation_text):
    """
    Verify that the extracted text actually appears in the translation.
    Allow for minor whitespace differences but require substantial match.

    Returns:
        tuple: (is_valid: bool, warning: str or None)
    """
    # Normalize whitespace for comparison
    extracted_normalized = ' '.join(extracted_text.split())
    translation_normalized = ' '.join(full_translation_text.split())

    # Primary check: exact match after whitespace normalization
    if extracted_normalized in translation_normalized:
        debug_print("Verification: exact match ✓", 5, min_level=3)
        return True, None

    # Secondary check: allow minor punctuation variations
    extracted_no_punct = re.sub(r'[.,;:!?]', '', extracted_normalized)
    translation_no_punct = re.sub(r'[.,;:!?]', '', translation_normalized)

    if extracted_no_punct in translation_no_punct and len(extracted_no_punct) > 10:
        debug_print("Verification: match without punctuation ✓", 5, min_level=3)
        return True, "minor_punctuation_difference"

    # Tertiary check: allow for minor word variations if substantial overlap
    if len(extracted_text) > 20:
        # Check if at least 80% of extracted text appears in translation
        words_extracted = extracted_normalized.split()
        words_in_trans = sum(1 for word in words_extracted if word in translation_normalized)
        overlap_ratio = words_in_trans / len(words_extracted) if words_extracted else 0

        if overlap_ratio > 0.8:
            debug_print(f"Verification: {overlap_ratio:.0%} word overlap ✓", 5, min_level=3)
            return True, f"paraphrase_detected_{int(overlap_ratio*100)}%_match"

    debug_print("Verification: no match found ✗", 5, min_level=2)
    return False, "text_not_found_in_translation"


def check_extraction_quality(source_text, extracted_translation, expected_ratio_min=0.5, expected_ratio_max=3.0):
    """
    Check if extracted translation length seems reasonable compared to source.

    Args:
        source_text: The source sentence
        extracted_translation: The extracted translation
        expected_ratio_min: Minimum acceptable translation/source length ratio
        expected_ratio_max: Maximum acceptable translation/source length ratio

    Returns:
        tuple: (is_reasonable: bool, ratio: float, warning: str or None)
    """
    source_len = len(source_text)
    trans_len = len(extracted_translation)
    ratio = trans_len / source_len if source_len > 0 else 0

    if ratio < expected_ratio_min:
        return False, ratio, f"too_short_ratio_{ratio:.2f}"
    elif ratio > expected_ratio_max:
        return False, ratio, f"too_long_ratio_{ratio:.2f}"
    else:
        return True, ratio, None


# Main execution
if __name__ == "__main__":
    # Default to proust for testing, but allow command line args
    if len(sys.argv) > 1:
        source_file = sys.argv[1]
        trans_file = sys.argv[2]
        output_file = sys.argv[3] if len(sys.argv) > 3 else 'textcreation/texts/aligned/output.json'
    else:
        # Test with Proust
        source_file = 'textcreation/texts/sources/proust1french.txt'
        trans_file = 'textcreation/texts/sources/proust1eng.txt'
        output_file = 'textcreation/texts/aligned/proust1_llm_improved.json'

    # Setup logging
    logger, log_file = setup_logging(output_file)

    print(f"\n{'='*80}")
    print(f"LLM-based Sentence Alignment (IMPROVED)")
    print(f"{'='*80}")
    print(f"Source: {source_file}")
    print(f"Translation: {trans_file}")
    print(f"Output: {output_file}")
    print(f"Log file: {log_file}")
    if TEST_MODE:
        print(f"TEST MODE: Only processing first {TEST_SENTENCE_LIMIT} sentences")
    print(f"{'='*80}\n")

    logger.info("="*80)
    logger.info("LLM-based Sentence Alignment (IMPROVED) - Session Start")
    logger.info(f"Source: {source_file}")
    logger.info(f"Translation: {trans_file}")
    logger.info(f"Output: {output_file}")
    logger.info(f"Test mode: {TEST_MODE}")
    if TEST_MODE:
        logger.info(f"Test limit: {TEST_SENTENCE_LIMIT} sentences")
    logger.info(f"Length ratio bounds: {MIN_LENGTH_RATIO:.2f} - {MAX_LENGTH_RATIO:.2f}")
    logger.info(f"Strict ratio bounds (>100 chars): {MIN_LENGTH_RATIO_STRICT:.2f} - {MAX_LENGTH_RATIO_STRICT:.2f}")
    logger.info("="*80)

    # Read files
    content1 = open(source_file, 'r', encoding='utf-8').read()
    content2 = open(trans_file, 'r', encoding='utf-8').read()

    # Check if files use section dividers
    if "---" in content1 and "---" in content2:
        sections1 = content1.split("---")
        sections2 = content2.split("---")
        print(f"Found {len(sections1)} sections in source, {len(sections2)} in translation")

        if len(sections1) != len(sections2):
            print(f"⚠️  WARNING: Section count mismatch!")
            print(f"   Proceeding with min({len(sections1)}, {len(sections2)}) sections")
    else:
        # Treat as single section
        sections1 = [content1]
        sections2 = [content2]
        print("No section dividers found, treating as single section")

    sourcelist = []
    translist = []

    for i in range(min(len(sections1), len(sections2))):
        print(f"\n{'='*80}")
        print(f"SECTION {i+1}/{len(sections1)}")
        print(f"{'='*80}")

        sources, trans = GetSentences(sections1[i], sections2[i])

        print(f"Tokenized into {len(sources)} source sentences, {len(trans)} translation sentences")

        # For multi-section files, save progress per section
        section_output = output_file.replace('.json', f'_section{i+1}.json') if len(sections1) > 1 else output_file

        outsource, outtrans = align_with_llm_word_level(
            sources,
            trans,
            model_name=None,  # Auto-select best model
            output_file=section_output,
            resume=True
        )

        sourcelist.extend(outsource)
        translist.extend(outtrans)

        # Add blank separator between sections
        sourcelist.append("")
        translist.append("")

        print(f"\n✓ Section {i+1} complete: {len(outsource)} alignments created")

    print(f"\n{'='*80}")
    print(f"Writing final output to {output_file}")
    print(f"Total pairs: {len(sourcelist)}")
    print(f"{'='*80}\n")

    # Final output already written by align_with_llm_word_level
    # Just verify it exists
    if not os.path.exists(output_file):
        write_to_json(sourcelist, translist, file_name=output_file)

    print(f"✓ Complete! Output written to {output_file}")
    logger.info(f"✓ Complete! Output written to {output_file}")

    # Clean up checkpoint and incremental files
    base_dir = os.path.dirname(output_file) or '.'
    base_name = os.path.basename(output_file).replace('.json', '')

    checkpoints_cleaned = 0
    for fname in os.listdir(base_dir):
        if fname.startswith(base_name) and ('_checkpoint_' in fname or '_incremental.json' in fname):
            try:
                os.remove(os.path.join(base_dir, fname))
                checkpoints_cleaned += 1
            except:
                pass

    if checkpoints_cleaned > 0:
        msg = f"🧹 Cleaned up {checkpoints_cleaned} temporary files"
        print(msg)
        logger.info(msg)

    logger.info("="*80)
    logger.info("Session completed successfully")
    logger.info(f"Full log saved to: {log_file}")
    logger.info("="*80)

    print(f"\n📋 Full log saved to: {log_file}")