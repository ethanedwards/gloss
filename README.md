# Gloss - AI-Assisted Foreign Language Reading System

Public facing site for the Gloss program - an AI-assisted foreign language reading system that combines insights from global literacy traditions with Large Language Models to facilitate reading texts in their original languages without prior study.

## Overview

Gloss creates interlinear annotated texts with integrated AI tutoring capabilities. The system processes source texts to generate word-by-word glosses, grammatical information, and interactive HTML interfaces for language learners.

## Quick Start

### Running the Application

```bash
# Development server
python run.py

# Or legacy entry point
python app.py
```

Visit `http://localhost:5000` to access the application.

### Processing a New Text

```bash
# Activate the language processing environment
source ~/anaconda3/etc/profile.d/conda.sh
conda activate langlearn

# Run the full processing pipeline (example: Italian text)
python textcreation/writehtml.py --periodictable
```

## Text Processing Pipeline

The system uses a comprehensive pipeline to convert raw texts into interactive interlinear HTML:

### 1. Sentence Alignment (`SentenceAlign.py`)

Aligns source language sentences with translation sentences using semantic similarity (LaBSE embeddings).

```bash
python textcreation/SentenceAlign.py <source_file> <translation_file> <output_json>
```

**Output:** JSON file with aligned sentence pairs

### 2. Interlinear Generation (`interlinear.py`)

Generates word-by-word glosses using Claude API with integrated verification.

```bash
python textcreation/interlinear.py
```

**Features:**
- Batch processing with configurable batch sizes
- Automatic retry with error context on verification failures
- Progress saving for long processing runs
- Integrated quality verification
- Language-specific morphological analysis

**Output:** JSON file with interlinear glosses at `textcreation/texts/interlinearouts/`

### 3. Verification (`comprehensive_verifier.py`)

Verifies the quality of generated interlinear data.

```bash
python textcreation/comprehensive_verifier.py <interlinear_file.json>
```

**Checks:**
- Malformed structure (missing elements, wrong array lengths)
- Missing glosses (words without translations)
- Isolated punctuation without glosses
- Source reconstruction mismatches
- Unicode normalization issues

**Output:** Detailed report of issues with entry indices

### 4. Auto-Fixing (`auto_fix_all_issues.py`)

Automatically repairs common structural issues in interlinear data.

```bash
python auto_fix_all_issues.py <interlinear_file.json>
```

**Fixes:**
- Single-element arrays → add empty gloss
- Three-element arrays → keep first two
- Missing glosses for punctuation → add empty gloss
- Missing glosses for proper nouns → add empty gloss

### 5. HTML Generation (`writehtml.py`)

Converts verified interlinear JSON into interactive HTML pages.

```bash
python textcreation/writehtml.py --periodictable
# Or for other texts:
python textcreation/writehtml.py --mark      # Gospel of Mark
python textcreation/writehtml.py --tractatus # Tractatus Logico-Philosophicus
```

**Features:**
- Unified processor for all languages (prevents punctuation duplication)
- Unicode normalization for accent variations
- Chapter detection via blank source entries
- Automatic page breaks
- Sentence store generation for AJAX loading
- Integrated verification after generation

**Output:**
- HTML files at `app/templates/texts/<textname>/`
- Sentence stores at `app/templates/texts/<textname>/sentence_stores/`

### 6. HTML Verification (`verify_html.py`)

Verifies that generated HTML matches the source JSON data.

```bash
python verify_html.py <html_dir> <json_path> <text_name> [starting_page]
```

**Example:**
```bash
python verify_html.py app/templates/texts/periodictable/ \
    textcreation/texts/interlinearouts/interlinear_periodictable.json \
    periodictable 1
```

**Checks:**
- Missing glosses in HTML
- Word count mismatches between JSON and HTML
- Gloss preservation from JSON to HTML

## Pipeline Workflow

### Complete Text Processing Flow

```
Raw Text Files
      ↓
[1. SentenceAlign.py]
      ↓
Aligned JSON (source + translation pairs)
      ↓
[2. interlinear.py] ← Uses Claude API
      ↓
Interlinear JSON (with word-by-word glosses)
      ↓
[3. comprehensive_verifier.py] ← Automatic in interlinear.py
      ↓
Verification Report
      ↓
[4. auto_fix_all_issues.py] ← Manual if needed
      ↓
Clean Interlinear JSON
      ↓
[5. writehtml.py] ← Runs verifier automatically
      ↓
HTML Files + Sentence Stores
      ↓
[6. verify_html.py] ← Automatic in writehtml.py
      ↓
HTML Verification Report
      ↓
Production-Ready HTML
```

## Automatic Verification & Fixing

The pipeline now includes automatic verification and fixing at key stages:

### During Interlinear Generation (`interlinear.py`)

- **Automatic verification** after each LLM response
- **Automatic retry** with error context if verification fails
- **Progress saving** to resume from interruptions

### During HTML Generation (`writehtml.py`)

- **Automatic JSON verification** before processing (runs `comprehensive_verifier.py`)
- **Automatic HTML verification** after generation (runs `verify_html.py`)
- **Detailed error reporting** with entry indices for manual inspection

### Configuration

Edit `textcreation/writehtml.py` at the bottom to add new texts:

```python
elif len(sys.argv) > 1 and sys.argv[1] == "--yourtext":
    write_html_interlinear(
        "textcreation/texts/interlinearouts/interlinear_yourtext.json",
        "textcreation/texts/templates/yourtemplate.html",
        "app/templates/texts/",
        "yourtext",
        "Your Text Title",
        "Your Text Description",
        YourLanguage(),
        starting_page=1,
        pagebreak=100,
        use_unified=True  # Always use unified processor!
    )
```

## Language Support

The system supports multiple languages through modular language processors:

- **Chinese**: Jieba segmentation + pinyin readings
- **Japanese**: MeCab parsing + ruby text for kanji
- **Latin**: Morphological analysis with simplified grammar tags
- **Italian**: spaCy morphological parsing
- **Koine Greek**: Accent normalization for ancient Greek
- **German, Spanish, Portuguese, Danish, French, Hungarian, Hindi, Persian**: Various NLP libraries

See `textcreation/languages/` for language-specific implementations.

## Key Files

### Text Processing
- `textcreation/SentenceAlign.py` - Sentence alignment
- `textcreation/interlinear.py` - Main interlinear generation
- `textcreation/writehtml.py` - HTML generation
- `textcreation/comprehensive_verifier.py` - JSON verification
- `verify_html.py` - HTML verification
- `auto_fix_all_issues.py` - Automatic issue fixing

### Configuration
- `textcreation/promptlibrary.py` + `promptlibrary.yml` - LLM prompts
- `config.py` - Environment configuration and API keys

### Application
- `run.py` - Development server entry point
- `app/routes/text_routes.py` - Text display routing
- `app/routes/api_routes.py` - API endpoints for chat
- `app/static/gloss.js` - Frontend interactivity
- `app/static/gloss.css` - Responsive styling

## Troubleshooting

### Missing Glosses in HTML

Run the HTML verifier to identify issues:
```bash
python verify_html.py app/templates/texts/<textname>/ \
    textcreation/texts/interlinearouts/interlinear_<textname>.json \
    <textname> 1
```

### Interlinear Data Issues

Run the comprehensive verifier:
```bash
python textcreation/comprehensive_verifier.py \
    textcreation/texts/interlinearouts/interlinear_<textname>.json
```

Then auto-fix common issues:
```bash
python auto_fix_all_issues.py \
    textcreation/texts/interlinearouts/interlinear_<textname>.json
```

### Punctuation Duplication

Ensure `use_unified=True` is set in `writehtml.py` for your text. The unified processor prevents punctuation duplication issues.

### Unicode/Accent Issues

The system uses NFD normalization to handle accent variations (e.g., `cosí` vs `così`). If you see "First words don't match" errors, this is handled automatically.

## Current Text Collection

- **Classical**: Dante's Inferno (Italian), Augustine's Confessions (Latin), The Dream of the Red Chamber (Chinese), The Periodic Table (Italian)
- **Modern Literature**: Jhumpa Lahiri stories, García Márquez works
- **Games/Media**: Nine Sols (Chinese), Castlevania (Japanese)
- **Poetry**: Persian poems, Schiller's "An die Freude"
- **Religious**: Gospel of Mark (Koine Greek)
- **Philosophy**: Tractatus Logico-Philosophicus (German)

## Development

### Dependencies

Install Python dependencies:
```bash
pip install -r requirements.txt
```

Key dependencies:
- Flask (web framework)
- sentence-transformers (sentence alignment)
- anthropic (Claude API)
- jieba (Chinese segmentation)
- MeCab (Japanese parsing)
- spaCy (morphological analysis)
- Language-specific NLP libraries

### Adding a New Language

1. Create a new language class in `textcreation/languages/`
2. Implement `parse_sent()` and `get_readings()` methods
3. Add language-specific tokenization logic
4. Update `writehtml.py` to import the new language

See `textcreation/languages/language.py` for the base interface.

## Architecture Notes

### Frontend Features
- Responsive design (mobile/desktop)
- Interactive glosses (click to reveal/hide)
- Text selection for AI tutoring context
- Integrated AI chat with streaming responses
- Page-based navigation with metadata

### Backend Architecture
- Blueprint structure for modular Flask app
- Async batch processing for LLM requests
- Sentence store caching for efficient text loading
- Graceful error handling and resume capabilities
- Unicode normalization throughout

### Performance Considerations
- Batch LLM requests (configurable batch size)
- Progressive saving during long processing
- Lazy loading of text data via AJAX
- Mobile-optimized touch interface

## Contributing

When adding new features or fixing bugs:

1. Use the verification tools to ensure data quality
2. Test with `verify_html.py` after HTML generation
3. Update this README and CLAUDE.md with changes
4. Set `use_unified=True` for all new text processors

## License

[Your License Here]
