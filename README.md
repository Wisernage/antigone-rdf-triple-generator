# Antigone RDF Triple Generator

This program automates the extraction of RDF/Turtle triples from Antigone verse passages using the ChatGPT API. It processes verse ranges from the `[PRODUCTIONS]` directory, generates ontology-compliant triples, and saves them in the correct location structure.

## Features

- Automatically scans for verse ranges in the `[PRODUCTIONS]` directory
- Reads both ancient Greek and English text files
- Uses ChatGPT API to generate RDF/Turtle triples following the Antigone ontology
- Saves output files in the correct directory structure
- Supports processing individual verse ranges or all ranges at once
- Skips existing output files by default (configurable)

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
export OPENAI_API_KEY=your_api_key_here
```

## Usage

### Process All Verse Ranges

```bash
python antigone_triple_generator.py
```

**Note:** Both `[PRODUCTIONS]` directory and `Prompt.txt` should be in the root folder of the project.

### Process a Specific Verse Range

```bash
python antigone_triple_generator.py --verse-range verse_773_to_805
```

### Command Line Options

- `--productions-dir`: Path to the [PRODUCTIONS] directory (default: `[PRODUCTIONS]`)
- `--prompt-template`: Path to the prompt template file (default: `Prompt.txt`)
- `--api-key`: OpenAI API key (default: reads from `OPENAI_API_KEY` environment variable)
- `--model`: OpenAI model to use (default: `gpt-5.2`). Options: `gpt-5.2` (Thinking), `gpt-5.2-pro` (Pro), `gpt-5.2-chat-latest` (Instant)
- `--temperature`: Sampling temperature (default: `0.3`)
- `--max-tokens`: Maximum tokens in response (default: `4000`)
- `--no-skip-existing`: Overwrite existing output files
- `--verse-range`: Process only a specific verse range

### Examples

```bash
# Process all verse ranges with custom model
python antigone_triple_generator.py --model gpt-5.2-pro

# Process a specific range and overwrite existing file
python antigone_triple_generator.py --verse-range verse_773_to_805 --no-skip-existing

# Use custom paths
python antigone_triple_generator.py --productions-dir /path/to/productions --prompt-template /path/to/template.txt
```

## Output

Output files are saved in the same directory as the input files:
```
[PRODUCTIONS]/verse_XXX_to_YYY/triples_XXX_to_YYY.ttl
```

For example:
- `[PRODUCTIONS]/verse_773_to_805/triples_773_to_805.ttl`

## Directory Structure

The program expects the following structure (with `[PRODUCTIONS]` and `Prompt.txt` in the root folder):
```
project_root/
  [PRODUCTIONS]/
    verse_773_to_805/
      ancient_greek/
        aGR_773_to_805.txt
      english/
        en_773_to_805.txt
      triples_773_to_805.ttl  (generated)
    verse_806_to_822/
      ...
  Prompt.txt  (prompt template)
  antigone_triple_generator.py
  requirements.txt
  ...
```

## Error Handling

The program handles:
- Missing input files
- API failures and rate limits
- Invalid directory structures
- File write permissions

Errors are reported to stderr, and processing continues with the next verse range if one fails.

## Notes

- The program uses the prompt template from `Antigone-Prompt-Example.txt`
- Generated triples follow the Antigone ontology defined in `1.Antigone-Ontology.ttl`
- By default, existing output files are skipped to avoid unnecessary API calls
- The `.env` file is gitignored to protect your API key
