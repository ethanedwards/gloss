import json
from difflib import SequenceMatcher

def load_json(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return json.load(file)

def save_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def similarity(a, b):
    return SequenceMatcher(None, a, b).ratio()

def match_interlinear(entries):
    new_entries = []
    for entry in entries:
        source = entry['source'].strip()
        best_match = None
        best_similarity = 0
        for potential_match in entries:
            interlinear_sentence = " ".join([pair[0] for pair in potential_match['interlinear']])
            sim = similarity(source, interlinear_sentence)
            if sim > best_similarity:
                best_match = potential_match['interlinear']
                best_similarity = sim
        new_entry = entry.copy()
        new_entry['interlinear'] = best_match
        new_entries.append(new_entry)
    return new_entries

def main():
    input_filename = 'textcreation/texts/interlinearouts/interlinearproust1.json'
    output_filename = 'textcreation/texts/interlinearouts/interlinearproust2.json'
    
    data = load_json(input_filename)
    corrected_data = match_interlinear(data)
    save_json(corrected_data, output_filename)

if __name__ == "__main__":
    main()