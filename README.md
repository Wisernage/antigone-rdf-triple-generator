# Antigone RDF Triple Generator

This program automates the extraction of RDF/Turtle triples from Antigone verse passages using the ChatGPT API. It processes verse ranges from the `[PRODUCTIONS]` directory, generates ontology-compliant triples, and saves them in the correct location structure.

## Features

- Automatically scans for verse ranges in the `[PRODUCTIONS]` directory
- Reads ancient Greek, English, and modern Greek text files
- Two-stage pipeline: canonical triples from ancient Greek (aGR), then translation variants (TV) for English and modern Greek
- Uses ChatGPT API to generate RDF/Turtle triples following the Antigone ontology
- Saves output files per language: `ancient_greek/output.ttl`, `english/output.ttl`, `modern_greek/output.ttl`
- Supports processing individual verse ranges or all ranges at once
- Skips existing output files by default (configurable)
- Optional validation of generated files against the ontology

## Setup

### Prerequisites

- Python 3.8 or higher
- OpenAI API key

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up your OpenAI API key:

Copy `.env.example` to `.env` and fill in your API key:
```bash
cp .env.example .env
# Then edit .env and replace 'your_openai_api_key_here' with your actual API key
```

Or create a `.env` file manually in the project root:
```
OPENAI_API_KEY=your_api_key_here
```

Alternatively, set it as an environment variable:
```bash
# Linux/macOS
export OPENAI_API_KEY=your_api_key_here

# Windows (PowerShell)
$env:OPENAI_API_KEY="your_api_key_here"
```

## Usage

### Process All Verse Ranges

```bash
python antigone_triple_generator.py
```

**Note:** The `[PRODUCTIONS]` directory and `Context/` folder (with prompts, ontology, and demo) should be in the project root.

### Process a Specific Verse Range

```bash
python antigone_triple_generator.py --verse-range verse_773_to_805
```

### Command Line Options

- `--productions-dir`: Path to the [PRODUCTIONS] directory (default: `[PRODUCTIONS]`)
- `--canonical-prompt`: Path to the canonical prompt template (default: `Context/Prompt_canonical.txt`)
- `--translation-prompt`: Path to the translation prompt template (default: `Context/Prompt_translations.txt`)
- `--ontology`: Path to the ontology file (default: `Context/Ontology.ttl`)
- `--demo`: Path to the demo example file (default: `Context/demo_grc.ttl`)
- `--api-key`: OpenAI API key (default: reads from `OPENAI_API_KEY` environment variable)
- `--model`: OpenAI model to use (default: `gpt-5.2`). Options: `gpt-5.2` (Thinking), `gpt-5.2-pro` (Pro), `gpt-5.2-chat-latest` (Instant)
- `--temperature`: Sampling temperature (default: `0.3`)
- `--max-tokens`: Maximum tokens in response (default: `4000`)
- `--no-skip-existing`: Overwrite existing output files
- `--verse-range`: Process only a specific verse range
- `--no-validate`: Skip validation of generated output files

### Examples

```bash
# Process all verse ranges with custom model
python antigone_triple_generator.py --model gpt-5.2-pro

# Process a specific range and overwrite existing file
python antigone_triple_generator.py --verse-range verse_773_to_805 --no-skip-existing

# Use custom paths
python antigone_triple_generator.py --productions-dir /path/to/productions --canonical-prompt Context/Prompt_canonical.txt --translation-prompt Context/Prompt_translations.txt
```

## Output

Output files are saved per language in each verse range directory:
```
[PRODUCTIONS]/verse_XXX_to_YYY/ancient_greek/output.ttl   (canonical triples from aGR)
[PRODUCTIONS]/verse_XXX_to_YYY/english/output.ttl         (canonical + English TranslationVariants)
[PRODUCTIONS]/verse_XXX_to_YYY/modern_greek/output.ttl    (canonical + Modern Greek TranslationVariants)
```

For example:
- `[PRODUCTIONS]/verse_773_to_805/ancient_greek/output.ttl`
- `[PRODUCTIONS]/verse_773_to_805/english/output.ttl`
- `[PRODUCTIONS]/verse_773_to_805/modern_greek/output.ttl`

## Directory Structure

The program expects the following structure:
```
project_root/
  [PRODUCTIONS]/
    verse_773_to_805/
      ancient_greek/
        aGR_773_to_805.txt
        output.ttl  (generated)
      english/
        en_773_to_805.txt  (or aEN_773_to_805.txt)
        output.ttl  (generated)
      modern_greek/
        mGR_773_to_805.txt
        output.ttl  (generated)
    verse_806_to_822/
      ...
  Context/
    Prompt_canonical.txt
    Prompt_translations.txt
    Ontology.ttl
    demo_grc.ttl
  antigone_triple_generator.py
  validate_triples.py
  requirements.txt
  ...
```

## Validation

After generating triples, you can validate them against the ontology using the validator:

```bash
# Validate all triple files
python validate_triples.py

# Validate a specific file
python validate_triples.py --file [PRODUCTIONS]/verse_773_to_805/ancient_greek/output.ttl

# Show warnings in addition to errors
python validate_triples.py --verbose
```

Validator options:
- `--ontology`: Path to ontology file (default: `Context/Ontology.ttl`)
- `--file`: Validate a specific file
- `--productions-dir`: Validate all triple files in directory (default: `[PRODUCTIONS]`)
- `--verbose`: Show warnings in addition to errors

The validator checks:
- Property domain/range constraints (e.g., `conflictBetween` only with Character/EthicalPrinciple/Law/FateConcept)
- Valid RDF/Turtle syntax
- Proper typing of individuals
- Correct prefix usage

## Error Handling

The program handles:
- Missing input files
- API failures and rate limits
- Invalid directory structures
- File write permissions

Errors are reported to stderr, and processing continues with the next verse range if one fails.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

## Notes

- The program uses `Context/Prompt_canonical.txt` for canonical triples and `Context/Prompt_translations.txt` for translation variants
- Generated triples follow the Antigone ontology defined in `Context/Ontology.ttl`
- The validator checks both the new format (`*/output.ttl`) and legacy `triples_*.ttl` files
- By default, existing output files are skipped to avoid unnecessary API calls
- The `.env` file is gitignored to protect your API key
