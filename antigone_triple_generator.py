#!/usr/bin/env python3
"""
Antigone RDF Triple Generator

This program processes verse ranges from the [PRODUCTIONS] directory,
uses ChatGPT API to generate RDF/Turtle triples following the Antigone ontology,
and saves the output files in the correct location structure.
"""

import os
import re
import sys
from pathlib import Path
from typing import List, Tuple, Optional, Dict
from dotenv import load_dotenv
from openai import OpenAI
from rdflib import Graph, Namespace
from rdflib.namespace import RDF

# Load environment variables from project directory (override so .env takes precedence over system env)
load_dotenv(Path(__file__).parent / '.env', override=True)


class VerseRangeProcessor:
    """Main processor for verse ranges and triple generation."""
    
    def __init__(self, productions_dir: str, prompt_template_path: str = None, canonical_prompt_path: str = None, translation_prompt_path: str = None, ontology_path: Optional[str] = None, demo_path: Optional[str] = None, api_key: Optional[str] = None):
        """
        Initialize the processor.
        
        Args:
            productions_dir: Path to the [PRODUCTIONS] directory
            prompt_template_path: Path to the combined prompt template (deprecated, use canonical/translation prompts)
            canonical_prompt_path: Path to the canonical prompt template (default: Context/Prompt_canonical.txt)
            translation_prompt_path: Path to the translation prompt template (default: Context/Prompt_translations.txt)
            ontology_path: Path to the ontology file (default: Context/Ontology.ttl)
            demo_path: Path to the demo example file (default: Context/demo_grc.ttl)
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
        """
        self.productions_dir = Path(productions_dir)
        # Support both old combined prompt and new separate prompts
        if prompt_template_path:
            # Old mode: use combined prompt
            self.prompt_template_path = Path(prompt_template_path)
            self.canonical_prompt_path = None
            self.translation_prompt_path = None
        else:
            # New mode: use separate prompts
            self.prompt_template_path = None
            self.canonical_prompt_path = Path(canonical_prompt_path) if canonical_prompt_path else Path('Context/Prompt_canonical.txt')
            self.translation_prompt_path = Path(translation_prompt_path) if translation_prompt_path else Path('Context/Prompt_translations.txt')
        self.ontology_path = Path(ontology_path) if ontology_path else Path('Context/Ontology.ttl')
        self.demo_path = Path(demo_path) if demo_path else Path('Context/demo_grc.ttl')
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        
        self.client = OpenAI(api_key=self.api_key)
        if self.prompt_template_path:
            # Old mode
            self.prompt_template = self._load_prompt_template()
        else:
            # New mode
            self.canonical_prompt_template = self._load_prompt_template(self.canonical_prompt_path)
            self.translation_prompt_template = self._load_prompt_template(self.translation_prompt_path)
        self.ontology_content = self._load_ontology()
        self.demo_content = self._load_demo()
    
    def _load_prompt_template(self, path: Path = None) -> str:
        """Load the prompt template from file."""
        template_path = path or self.prompt_template_path
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Prompt template not found: {template_path}")
    
    def _load_ontology(self) -> str:
        """Load the ontology file."""
        try:
            with open(self.ontology_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Ontology file not found: {self.ontology_path}")
    
    def _load_demo(self) -> str:
        """Load the demo example file."""
        try:
            with open(self.demo_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Demo file not found: {self.demo_path}")
    
    def _merge_canonical_with_translations(self, canonical_ttl: str, translation_ttl: str) -> str:
        """
        Merge canonical TTL with translation TTL for [PRODUCTIONS]_TEST format.
        Removes :text from Line individuals in canonical (translation files have minimal Lines),
        then adds TranslationVariants from translation_ttl.
        
        Args:
            canonical_ttl: Full canonical TTL (Scene, Speech, Lines with Greek text, semantic)
            translation_ttl: TTL containing only TranslationVariants (TV_Line_###_en or _ell)
            
        Returns:
            Merged TTL string
        """
        ANTIGONE = Namespace("http://example.org/antigone#")
        
        graph = Graph()
        graph.parse(data=canonical_ttl, format="turtle")
        
        # Remove :text from Line individuals (translation files have Lines without Greek text)
        lines_with_text = [
            (s, p, o) for s, p, o in graph
            if p == ANTIGONE.text and (s, RDF.type, ANTIGONE.Line) in graph
        ]
        for triple in lines_with_text:
            graph.remove(triple)
        
        # Parse and merge translation TTL (TranslationVariants)
        trans_graph = Graph()
        try:
            trans_graph.parse(data=translation_ttl, format="turtle")
        except Exception:
            return canonical_ttl  # Fallback if translation parse fails
        graph += trans_graph
        
        return graph.serialize(format="turtle", encoding="utf-8").decode("utf-8")
    
    def find_verse_ranges(self) -> List[str]:
        """
        Scan the [PRODUCTIONS] directory for verse range directories.
        
        Returns:
            List of verse range directory names (e.g., ['verse_773_to_805', ...])
        """
        verse_ranges = []
        if not self.productions_dir.exists():
            raise FileNotFoundError(f"Productions directory not found: {self.productions_dir}")
        
        for item in self.productions_dir.iterdir():
            if item.is_dir() and item.name.startswith('verse_') and 'chinese' not in item.name.lower():
                verse_ranges.append(item.name)
        
        return sorted(verse_ranges)
    
    def get_available_languages(self, verse_range: str) -> List[str]:
        """
        Detect which translation languages have input files for a verse range.
        
        Returns:
            List of language folder names: ['ancient_greek', 'english', 'modern_greek'] (modern_greek only if source exists)
        """
        verse_dir = self.productions_dir / verse_range
        match = re.search(r'verse_(\d+)_to_(\d+)', verse_range)
        if not match:
            raise ValueError(f"Invalid verse range format: {verse_range}")
        start_verse, end_verse = match.groups()
        
        languages = ['ancient_greek']  # Required
        # English: support en_ (PRODUCTIONS) and aEN_ (TEST)
        en_file = verse_dir / 'english' / f'en_{start_verse}_to_{end_verse}.txt'
        aen_file = verse_dir / 'english' / f'aEN_{start_verse}_to_{end_verse}.txt'
        if en_file.exists() or aen_file.exists():
            languages.append('english')
        # Modern Greek: optional
        mgr_file = verse_dir / 'modern_greek' / f'mGR_{start_verse}_to_{end_verse}.txt'
        if mgr_file.exists():
            languages.append('modern_greek')
        return languages
    
    def read_verse_texts(self, verse_range: str) -> Tuple[str, str]:
        """
        Read ancient Greek and English text files for a verse range.
        
        Args:
            verse_range: Verse range directory name (e.g., 'verse_773_to_805')
            
        Returns:
            Tuple of (ancient_greek_text, english_text)
        """
        verse_dir = self.productions_dir / verse_range
        
        # Extract verse numbers from directory name
        match = re.search(r'verse_(\d+)_to_(\d+)', verse_range)
        if not match:
            raise ValueError(f"Invalid verse range format: {verse_range}")
        
        start_verse, end_verse = match.groups()
        
        # Read ancient Greek file
        ancient_greek_file = verse_dir / 'ancient_greek' / f'aGR_{start_verse}_to_{end_verse}.txt'
        english_file = verse_dir / 'english' / f'en_{start_verse}_to_{end_verse}.txt'
        if not english_file.exists():
            english_file = verse_dir / 'english' / f'aEN_{start_verse}_to_{end_verse}.txt'
        
        if not ancient_greek_file.exists():
            raise FileNotFoundError(f"Ancient Greek file not found: {ancient_greek_file}")
        if not english_file.exists():
            raise FileNotFoundError(f"English file not found: {english_file}")
        
        with open(ancient_greek_file, 'r', encoding='utf-8') as f:
            ancient_greek_text = f.read().strip()
        
        with open(english_file, 'r', encoding='utf-8') as f:
            english_text = f.read().strip()
        
        return ancient_greek_text, english_text
    
    def read_translation_text(self, verse_range: str, language: str) -> str:
        """
        Read translation text for a given language.
        
        Args:
            verse_range: Verse range directory name
            language: 'english' or 'modern_greek'
            
        Returns:
            Text content
        """
        verse_dir = self.productions_dir / verse_range
        match = re.search(r'verse_(\d+)_to_(\d+)', verse_range)
        if not match:
            raise ValueError(f"Invalid verse range format: {verse_range}")
        start_verse, end_verse = match.groups()
        
        if language == 'english':
            path = verse_dir / 'english' / f'en_{start_verse}_to_{end_verse}.txt'
            if not path.exists():
                path = verse_dir / 'english' / f'aEN_{start_verse}_to_{end_verse}.txt'
        elif language == 'modern_greek':
            path = verse_dir / 'modern_greek' / f'mGR_{start_verse}_to_{end_verse}.txt'
        else:
            raise ValueError(f"Unsupported translation language: {language}")
        
        if not path.exists():
            raise FileNotFoundError(f"Translation file not found: {path}")
        with open(path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    
    def build_prompt(self, text: str, prompt_template: str, canonical_content: str = None) -> str:
        """
        Build the prompt by inserting the verse text, ontology, and demo example into the template.
        
        Args:
            text: Text to insert (Ancient Greek for canonical, English for translations)
            prompt_template: The prompt template to use
            canonical_content: Optional canonical TTL content to include for translation prompts
            
        Returns:
            Complete prompt string
        """
        # Build the complete prompt: template + ontology + demo + text
        prompt = prompt_template.replace('{{ INSERT PASSAGE HERE }}', text)
        
        # Insert ontology and demo before the text section
        # Find where to insert (before <TEXT> tag)
        if '<TEXT>' in prompt:
            # Insert ontology and demo right before <TEXT>
            ontology_section = f"\n\n<ONTOLOGY>\n{self.ontology_content}\n</ONTOLOGY>\n\n"
            demo_section = f"<EXAMPLE>\n{self.demo_content}\n</EXAMPLE>\n\n"
            
            # For translation prompts, also include canonical content if provided
            canonical_section = ""
            if canonical_content:
                canonical_section = f"<CANONICAL_TRIPLES>\n{canonical_content}\n</CANONICAL_TRIPLES>\n\n"
            
            prompt = prompt.replace('<TEXT>', ontology_section + demo_section + canonical_section + '<TEXT>')
        else:
            # Fallback: append ontology and demo at the end before the text
            canonical_section = f"\n\n<CANONICAL_TRIPLES>\n{canonical_content}\n</CANONICAL_TRIPLES>\n\n" if canonical_content else ""
            prompt = f"{prompt}\n\n<ONTOLOGY>\n{self.ontology_content}\n</ONTOLOGY>\n\n<EXAMPLE>\n{self.demo_content}\n</EXAMPLE>{canonical_section}"
        
        return prompt
    
    def call_chatgpt_api(self, prompt: str, model: str = "gpt-5.2", temperature: float = 0.3, max_tokens: int = 4000) -> str:
        """
        Call ChatGPT API to generate RDF triples.
        
        Args:
            prompt: The complete prompt
            model: OpenAI model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated RDF/Turtle triples
        """
        try:
            # GPT-5.2 uses max_completion_tokens instead of max_tokens
            api_params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are an expert annotator of Ancient Greek tragedies and an ontology-aware triple extractor."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": temperature
            }
            
            # Use max_completion_tokens for GPT-5.x models, max_tokens for older models
            if model.startswith("gpt-5"):
                api_params["max_completion_tokens"] = max_tokens
            else:
                api_params["max_tokens"] = max_tokens
            
            response = self.client.chat.completions.create(**api_params)
            
            return response.choices[0].message.content.strip()
        
        except Exception as e:
            raise RuntimeError(f"API call failed: {str(e)}")
    
    def extract_triples(self, api_response: str) -> str:
        """
        Extract clean RDF/Turtle triples from API response.
        
        Args:
            api_response: Raw API response
            
        Returns:
            Clean RDF/Turtle triples
        """
        # Remove any markdown code blocks if present
        triple_text = api_response
        
        # Remove markdown code blocks
        if '```' in triple_text:
            # Extract content between ```turtle or ``` and ```
            pattern = r'```(?:turtle|ttl)?\s*\n(.*?)\n```'
            match = re.search(pattern, triple_text, re.DOTALL)
            if match:
                triple_text = match.group(1)
            else:
                # Try without language identifier
                pattern = r'```\s*\n(.*?)\n```'
                match = re.search(pattern, triple_text, re.DOTALL)
                if match:
                    triple_text = match.group(1)
        
        return triple_text.strip()
    
    def save_triples(self, verse_range: str, triples: str, language: str) -> Path:
        """
        Save generated triples to {language}/output.ttl (PRODUCTIONS_TEST format).
        
        Args:
            verse_range: Verse range directory name
            triples: RDF/Turtle triples to save
            language: 'ancient_greek', 'english', or 'modern_greek'
            
        Returns:
            Path to the saved file
        """
        verse_dir = self.productions_dir / verse_range
        output_file = verse_dir / language / 'output.ttl'
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(triples)
        return output_file
    
    def _validate_output(self, output_path: Path, ontology_path: Optional[Path] = None) -> bool:
        """
        Run validation on a saved triple file. Returns True if valid (no errors), False otherwise.
        Prints errors and warnings to stderr.
        """
        try:
            from validate_triples import TripleValidator
        except ImportError:
            print(f"  (Validation skipped: validate_triples not available)", file=sys.stderr)
            return True
        try:
            validator = TripleValidator(ontology_path=str(ontology_path or self.ontology_path))
            is_valid, errors, warnings = validator.validate_file(output_path)
            if errors:
                print(f"  Validation ERRORS for {output_path.name}:", file=sys.stderr)
                for err in errors:
                    print(f"    ERROR: {err}", file=sys.stderr)
            if warnings:
                print(f"  Validation warnings for {output_path.name}:", file=sys.stderr)
                for warn in warnings:
                    print(f"    WARNING: {warn}", file=sys.stderr)
            return is_valid
        except Exception as e:
            print(f"  Validation failed: {e}", file=sys.stderr)
            return False
    
    def process_verse_range(self, verse_range: str, model: str = "gpt-5.2", temperature: float = 0.3, max_tokens: int = 4000, skip_existing: bool = True, validate: bool = True) -> Optional[List[Path]]:
        """
        Process a single verse range: generate canonical -> ancient_greek/output.ttl;
        for each translation language: generate TV -> merge -> {language}/output.ttl.
        
        Args:
            verse_range: Verse range directory name
            model: OpenAI model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            skip_existing: Skip if all expected output files already exist
            validate: Run validation after each save
            
        Returns:
            List of output paths, or None if skipped
        """
        languages = self.get_available_languages(verse_range)
        verse_dir = self.productions_dir / verse_range
        # In old combined mode, only ancient_greek is produced
        expected_langs = ['ancient_greek'] if self.prompt_template_path else languages
        expected_outputs = [verse_dir / lang / 'output.ttl' for lang in expected_langs]
        
        if skip_existing and all(p.exists() for p in expected_outputs):
            print(f"Skipping {verse_range} - output files already exist")
            return None
        
        print(f"Processing {verse_range}...")
        
        try:
            # Read ancient Greek (required)
            ancient_greek_text, english_text = self.read_verse_texts(verse_range)
            
            # 1. Generate and save canonical (ancient_greek/output.ttl)
            ancient_greek_path = verse_dir / 'ancient_greek' / 'output.ttl'
            if not ancient_greek_path.exists() or not skip_existing:
                print(f"  Generating canonical triples...")
                if self.prompt_template_path:
                    prompt = self.build_prompt(f"[Ancient Greek - CANONICAL ANCHOR]\n{ancient_greek_text}\n\n[English Translation]\n{english_text}", self.prompt_template)
                else:
                    prompt = self.build_prompt(ancient_greek_text, self.canonical_prompt_template)
                api_response = self.call_chatgpt_api(prompt, model, temperature, max_tokens)
                canonical_triples = self.extract_triples(api_response)
                ancient_greek_path = self.save_triples(verse_range, canonical_triples, 'ancient_greek')
                print(f"  Saved to: {ancient_greek_path}")
                if validate:
                    self._validate_output(ancient_greek_path)
            else:
                print(f"  ancient_greek/output.ttl already exists, skipping...")
                with open(ancient_greek_path, 'r', encoding='utf-8') as f:
                    canonical_triples = f.read()
            
            output_paths = [ancient_greek_path]
            
            # 2. For each translation language: generate TV, merge, save (skip in old combined mode)
            if not self.prompt_template_path:
                for lang in languages:
                    if lang == 'ancient_greek':
                        continue
                    trans_path = verse_dir / lang / 'output.ttl'
                    if trans_path.exists() and skip_existing:
                        print(f"  {lang}/output.ttl already exists, skipping...")
                        output_paths.append(trans_path)
                        continue
                    print(f"  Generating {lang} translation triples...")
                    trans_text = self.read_translation_text(verse_range, lang)
                    prompt = self.build_prompt(trans_text, self.translation_prompt_template, canonical_triples)
                    api_response = self.call_chatgpt_api(prompt, model, temperature, max_tokens)
                    translation_triples = self.extract_triples(api_response)
                    merged = self._merge_canonical_with_translations(canonical_triples, translation_triples)
                    trans_path = self.save_triples(verse_range, merged, lang)
                    print(f"  Saved to: {trans_path}")
                    if validate:
                        self._validate_output(trans_path)
                    output_paths.append(trans_path)
            
            return output_paths
        
        except Exception as e:
            print(f"  ERROR processing {verse_range}: {str(e)}", file=sys.stderr)
            raise
    
    def process_all(self, model: str = "gpt-5.2", temperature: float = 0.3, max_tokens: int = 4000, skip_existing: bool = True, validate: bool = True):
        """
        Process all verse ranges found in the [PRODUCTIONS] directory.
        
        Args:
            model: OpenAI model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            skip_existing: Skip if output files already exist
            validate: Run validation on generated files
        """
        verse_ranges = self.find_verse_ranges()
        
        if not verse_ranges:
            print("No verse ranges found!")
            return
        
        print(f"Found {len(verse_ranges)} verse range(s) to process")
        print()
        
        for verse_range in verse_ranges:
            try:
                result = self.process_verse_range(verse_range, model, temperature, max_tokens, skip_existing, validate)
                if result:
                    paths_str = ", ".join(str(p) for p in result)
                    print(f"  Completed: {paths_str}")
                print()
            except Exception as e:
                print(f"Failed to process {verse_range}: {str(e)}", file=sys.stderr)
                print()
                continue
        
        print("Processing complete!")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Generate RDF/Turtle triples from Antigone verse passages using ChatGPT API'
    )
    parser.add_argument(
        '--productions-dir',
        type=str,
        default='[PRODUCTIONS]',
        help='Path to the [PRODUCTIONS] directory (default: [PRODUCTIONS])'
    )
    parser.add_argument(
        '--prompt-template',
        type=str,
        default=None,
        help='Path to the combined prompt template file (deprecated - use --canonical-prompt and --translation-prompt instead)'
    )
    parser.add_argument(
        '--canonical-prompt',
        type=str,
        default='Context/Prompt_canonical.txt',
        help='Path to the canonical prompt template file (default: Context/Prompt_canonical.txt)'
    )
    parser.add_argument(
        '--translation-prompt',
        type=str,
        default='Context/Prompt_translations.txt',
        help='Path to the translation prompt template file (default: Context/Prompt_translations.txt)'
    )
    parser.add_argument(
        '--ontology',
        type=str,
        default='Context/Ontology.ttl',
        help='Path to the ontology file (default: Context/Ontology.ttl)'
    )
    parser.add_argument(
        '--demo',
        type=str,
        default='Context/demo_grc.ttl',
        help='Path to the demo example file (default: Context/demo_grc.ttl)'
    )
    parser.add_argument(
        '--api-key',
        type=str,
        default=None,
        help='OpenAI API key (default: reads from OPENAI_API_KEY environment variable)'
    )
    parser.add_argument(
        '--model',
        type=str,
        default='gpt-5.2',
        help='OpenAI model to use (default: gpt-5.2). Options: gpt-5.2 (Thinking), gpt-5.2-pro (Pro), gpt-5.2-chat-latest (Instant)'
    )
    parser.add_argument(
        '--temperature',
        type=float,
        default=0.3,
        help='Sampling temperature (default: 0.3)'
    )
    parser.add_argument(
        '--max-tokens',
        type=int,
        default=4000,
        help='Maximum tokens in response (default: 4000)'
    )
    parser.add_argument(
        '--no-skip-existing',
        action='store_true',
        help='Overwrite existing output files'
    )
    parser.add_argument(
        '--verse-range',
        type=str,
        default=None,
        help='Process only a specific verse range (e.g., verse_773_to_805)'
    )
    parser.add_argument(
        '--no-validate',
        action='store_true',
        help='Skip validation of generated output files'
    )
    
    args = parser.parse_args()
    
    try:
        processor = VerseRangeProcessor(
            args.productions_dir,
            args.prompt_template,
            args.canonical_prompt,
            args.translation_prompt,
            args.ontology,
            args.demo,
            args.api_key
        )
        
        if args.verse_range:
            # Process single verse range
            processor.process_verse_range(
                args.verse_range,
                args.model,
                args.temperature,
                args.max_tokens,
                skip_existing=not args.no_skip_existing,
                validate=not args.no_validate
            )
        else:
            # Process all verse ranges
            processor.process_all(
                args.model,
                args.temperature,
                args.max_tokens,
                skip_existing=not args.no_skip_existing,
                validate=not args.no_validate
            )
    
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
