import json
from difflib import SequenceMatcher
from tqdm import tqdm
import signal
import sys
import traceback
import os
import re

# Global flag for graceful interruption
interrupted = False

def signal_handler(signum, frame):
    global interrupted
    interrupted = True
    print("\nInterruption detected. Finishing current comparison and saving progress...")

signal.signal(signal.SIGINT, signal_handler)

def load_json(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return json.load(file)

def save_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def normalize_text(text):
    """Normalize text for better matching"""
    if not text:
        return ""
    
    # Remove leading/trailing whitespace and normalize internal whitespace
    text = text.strip()
    # Replace multiple whitespace characters with single space
    text = re.sub(r'\s+', ' ', text)
    # Remove leading newlines and extra punctuation spacing
    text = text.lstrip('\n')
    
    return text

def normalize_text_aggressive(text):
    """More aggressive normalization for stubborn cases"""
    if not text:
        return ""
    
    # Start with basic normalization
    text = normalize_text(text)
    # Remove all punctuation except letters, numbers, and spaces
    text = re.sub(r'[^\w\s]', '', text)
    # Convert to lowercase
    text = text.lower()
    
    return text

def extract_interlinear_text(interlinear_data):
    """Extract Spanish text from interlinear data safely"""
    try:
        if not interlinear_data:
            return ""
        
        words = []
        for pair in interlinear_data:
            if pair and len(pair) >= 1:
                word = pair[0].strip()
                if word:
                    words.append(word)
        
        return " ".join(words)
    except Exception as e:
        print(f"Error extracting interlinear text: {e}")
        return ""

def similarity(a, b):
    """Calculate similarity between two strings"""
    if not a or not b:
        return 0.0
    try:
        return SequenceMatcher(None, a, b).ratio()
    except Exception as e:
        print(f"Error computing similarity: {e}")
        return 0.0

def find_exact_match(source_norm, entries, interlinear_texts_norm, exclude_index=None):
    """Find exact match in the entries"""
    for i, interlinear_norm in enumerate(interlinear_texts_norm):
        if exclude_index is not None and i == exclude_index:
            continue
        if source_norm == interlinear_norm:
            return i, 1.0
    return None, 0.0

def find_partial_word_match(source_words, entries, interlinear_texts_norm, exclude_index=None, min_word_overlap=0.6):
    """Find matches based on word overlap when exact matching fails"""
    if not source_words:
        return None, 0.0
        
    source_word_set = set(source_words)
    best_match = None
    best_similarity = 0.0
    
    for i, interlinear_norm in enumerate(interlinear_texts_norm):
        if exclude_index is not None and i == exclude_index:
            continue
        if not interlinear_norm:
            continue
            
        interlinear_words = interlinear_norm.split()
        if not interlinear_words:
            continue
            
        interlinear_word_set = set(interlinear_words)
        
        # Calculate word overlap ratio
        intersection = source_word_set.intersection(interlinear_word_set)
        union = source_word_set.union(interlinear_word_set)
        
        if union:
            word_overlap_ratio = len(intersection) / len(union)
            if word_overlap_ratio >= min_word_overlap and len(intersection) >= 3:  # At least 3 common words
                # Also check overall string similarity
                string_sim = similarity(source_words, interlinear_words)
                combined_score = (word_overlap_ratio * 0.6) + (string_sim * 0.4)  # Weight word overlap more
                
                if combined_score > best_similarity:
                    best_similarity = combined_score
                    best_match = i
    
    return best_match, best_similarity

def find_best_match(source_norm, entries, interlinear_texts_norm, aggressive_norm_texts, exclude_index=None, min_threshold=0.95):
    """Find the best match using multiple strategies"""
    best_match = None
    best_similarity = 0.0
    match_method = "none"
    
    # Strategy 1: Try exact match with normalized text
    match_idx, sim = find_exact_match(source_norm, entries, interlinear_texts_norm, exclude_index)
    if match_idx is not None:
        return match_idx, sim, "exact"
    
    # Strategy 2: Try high-similarity match with normalized text
    for i, interlinear_norm in enumerate(interlinear_texts_norm):
        if exclude_index is not None and i == exclude_index:
            continue
        if not interlinear_norm:
            continue
        
        sim = similarity(source_norm, interlinear_norm)
        if sim > best_similarity and sim >= min_threshold:
            best_similarity = sim
            best_match = i
            match_method = "high_sim"
    
    if best_match is not None:
        return best_match, best_similarity, match_method
    
    # Strategy 3: Try aggressive normalization (remove punctuation, lowercase)
    source_aggressive = normalize_text_aggressive(source_norm)
    if source_aggressive:
        for i, interlinear_aggressive in enumerate(aggressive_norm_texts):
            if exclude_index is not None and i == exclude_index:
                continue
            if not interlinear_aggressive:
                continue
            
            if source_aggressive == interlinear_aggressive:
                return i, 0.98, "aggressive_exact"  # High confidence but mark as aggressive match
            
            sim = similarity(source_aggressive, interlinear_aggressive)
            if sim > best_similarity and sim >= 0.9:  # Lower threshold for aggressive matching
                best_similarity = sim
                best_match = i
                match_method = "aggressive_sim"
    
    # Strategy 4: Word-based partial matching for really stubborn cases
    if best_similarity < 0.7:  # Only if we haven't found anything decent yet
        source_words = source_norm.split()
        partial_match, partial_sim = find_partial_word_match(
            source_words, entries, interlinear_texts_norm, exclude_index, min_word_overlap=0.4
        )
        if partial_match is not None and partial_sim > best_similarity:
            best_match = partial_match
            best_similarity = partial_sim
            match_method = "word_overlap"
    
    return best_match, best_similarity, match_method

def match_interlinear_improved(entries, min_threshold=0.95, resume_from=0):
    """
    Improved matching algorithm that prioritizes exact matches
    """
    global interrupted
    new_entries = []
    error_count = 0
    exact_matches = 0
    processing_errors = 0
    match_stats = {"exact": 0, "high_sim": 0, "aggressive_exact": 0, "aggressive_sim": 0, "word_overlap": 0}
    
    print("Pre-processing all entries...")
    
    # Pre-compute normalized texts for all entries
    source_texts_norm = []
    interlinear_texts_norm = []
    aggressive_norm_texts = []
    
    for i, entry in enumerate(tqdm(entries, desc="Normalizing texts")):
        try:
            # Normalize source text
            source = entry.get('source', '').strip()
            source_norm = normalize_text(source)
            source_texts_norm.append(source_norm)
            
            # Extract and normalize interlinear text
            interlinear_text = extract_interlinear_text(entry.get('interlinear', []))
            interlinear_norm = normalize_text(interlinear_text)
            interlinear_texts_norm.append(interlinear_norm)
            
            # Aggressive normalization
            aggressive_norm_texts.append(normalize_text_aggressive(interlinear_text))
            
        except Exception as e:
            print(f"Error pre-processing entry {i+1}: {e}")
            source_texts_norm.append("")
            interlinear_texts_norm.append("")
            aggressive_norm_texts.append("")
            processing_errors += 1
    
    print(f"Processing {len(entries)} entries (starting from {resume_from})...")
    if processing_errors > 0:
        print(f"Warning: {processing_errors} entries had pre-processing errors")
    
    # Process entries
    for i in range(len(entries)):
        if i < resume_from:
            new_entries.append(entries[i])
            continue
            
        if interrupted:
            print(f"Interrupted at entry {i+1}. Saving progress...")
            break
            
        entry = entries[i]
        
        try:
            source_norm = source_texts_norm[i]
            
            if not source_norm:
                # Handle empty source
                new_entry = entry.copy()
                new_entry['interlinear'] = []
                new_entry['match_error'] = True
                new_entry['similarity_score'] = 0.0
                new_entry['error_reason'] = 'empty_source'
                new_entries.append(new_entry)
                error_count += 1
                continue
            
            # Find the best match
            best_match_idx, best_similarity, match_method = find_best_match(
                source_norm, 
                entries, 
                interlinear_texts_norm, 
                aggressive_norm_texts,
                exclude_index=i,  # Don't match with self
                min_threshold=min_threshold
            )
            
            new_entry = entry.copy()
            
            if best_match_idx is not None and best_similarity >= min_threshold:
                # Good match found
                new_entry['interlinear'] = entries[best_match_idx].get('interlinear', [])
                new_entry['similarity_score'] = best_similarity
                new_entry['matched_entry'] = best_match_idx
                new_entry['match_method'] = match_method
                
                # Track match statistics
                match_stats[match_method] = match_stats.get(match_method, 0) + 1
                
                if best_similarity >= 0.999:
                    exact_matches += 1
                    
            elif best_match_idx is not None and best_similarity >= 0.7:  # Lower threshold for partial matches
                # Partial match found
                new_entry['interlinear'] = entries[best_match_idx].get('interlinear', [])
                new_entry['similarity_score'] = best_similarity
                new_entry['matched_entry'] = best_match_idx
                new_entry['match_method'] = match_method
                new_entry['partial_match'] = True
                
                match_stats[match_method] = match_stats.get(match_method, 0) + 1
                    
            else:
                # No good match found
                if i < 50:  # Only show first 50 errors to avoid spam
                    print(f"\nPOOR MATCH for entry {i+1}:")
                    print(f"Source: {entry.get('source', '')[:100]}...")
                    print(f"Best similarity: {best_similarity:.3f} (method: {match_method})")
                    if best_match_idx is not None:
                        best_interlinear = extract_interlinear_text(entries[best_match_idx].get('interlinear', []))
                        print(f"Best match: {best_interlinear[:100]}...")
                    print("---")
                
                new_entry['interlinear'] = []
                new_entry['match_error'] = True
                new_entry['similarity_score'] = best_similarity
                new_entry['best_match_entry'] = best_match_idx
                new_entry['error_reason'] = 'low_similarity'
                new_entry['match_method'] = match_method
                error_count += 1
                
            new_entries.append(new_entry)
            
            # Progress update
            if (i + 1) % 500 == 0:
                print(f"Processed {i+1}/{len(entries)} entries. Exact matches: {exact_matches}, Errors: {error_count}")
                
        except Exception as e:
            print(f"\nFATAL ERROR processing entry {i+1}: {e}")
            print(f"Traceback: {traceback.format_exc()}")
            
            error_entry = entry.copy()
            error_entry['interlinear'] = []
            error_entry['processing_error'] = True
            error_entry['error_message'] = str(e)
            new_entries.append(error_entry)
            processing_errors += 1
            continue
    
    # Add remaining entries if interrupted
    if interrupted and i < len(entries) - 1:
        print(f"Adding remaining {len(entries) - i - 1} unprocessed entries...")
        for j in range(i + 1, len(entries)):
            new_entries.append(entries[j])
    
    print(f"\nProcessing complete!")
    print(f"Total entries: {len(new_entries)}")
    print(f"Exact matches: {exact_matches}")
    print(f"Match method breakdown:")
    for method, count in match_stats.items():
        if count > 0:
            print(f"  {method}: {count}")
    print(f"Errors (similarity < {min_threshold}): {error_count}")
    print(f"Processing errors: {processing_errors}")
    
    return new_entries

def main():
    input_filename = 'textcreation/texts/interlinearouts/interlinearlabyrinth4_alignment_fixed.json'
    output_filename = 'textcreation/texts/interlinearouts/interlinearlabyrinth4rematched.json'
    
    # Configuration
    similarity_threshold = 0.95  # Much higher threshold since we expect exact matches
    resume_from = 0
    
    try:
        print(f"Loading data from {input_filename}...")
        data = load_json(input_filename)
        print(f"Loaded {len(data)} entries")
        
        # Check for existing output to resume from
        if os.path.exists(output_filename) and resume_from == 0:
            try:
                existing_data = load_json(output_filename)
                resume_from = len(existing_data)
                print(f"Found existing output with {resume_from} entries. Resuming from entry {resume_from + 1}")
            except:
                print("Could not read existing output file, starting fresh")
                resume_from = 0
        
        corrected_data = match_interlinear_improved(
            data, 
            min_threshold=similarity_threshold,
            resume_from=resume_from
        )
        
        print(f"Saving results to {output_filename}...")
        save_json(corrected_data, output_filename)
        
        print(f"Results saved to {output_filename}")
        
    except Exception as e:
        print(f"FATAL ERROR in main: {e}")
        print(f"Traceback: {traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    main()