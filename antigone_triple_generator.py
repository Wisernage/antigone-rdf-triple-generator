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
from typing import List, Tuple, Optional
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()


class VerseRangeProcessor:
    """Main processor for verse ranges and triple generation."""
    
    def __init__(self, productions_dir: str, prompt_template_path: str, api_key: Optional[str] = None):
        """
        Initialize the processor.
        
        Args:
            productions_dir: Path to the [PRODUCTIONS] directory
            prompt_template_path: Path to the prompt template file
            api_key: OpenAI API key (if None, reads from OPENAI_API_KEY env var)
        """
        self.productions_dir = Path(productions_dir)
        self.prompt_template_path = Path(prompt_template_path)
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable or pass api_key parameter.")
        
        self.client = OpenAI(api_key=self.api_key)
        self.prompt_template = self._load_prompt_template()
    
    def _load_prompt_template(self) -> str:
        """Load the prompt template from file."""
        try:
            with open(self.prompt_template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Prompt template not found: {self.prompt_template_path}")
    
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
            if item.is_dir() and item.name.startswith('verse_'):
                verse_ranges.append(item.name)
        
        return sorted(verse_ranges)
    
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
        
        if not ancient_greek_file.exists():
            raise FileNotFoundError(f"Ancient Greek file not found: {ancient_greek_file}")
        if not english_file.exists():
            raise FileNotFoundError(f"English file not found: {english_file}")
        
        with open(ancient_greek_file, 'r', encoding='utf-8') as f:
            ancient_greek_text = f.read().strip()
        
        with open(english_file, 'r', encoding='utf-8') as f:
            english_text = f.read().strip()
        
        return ancient_greek_text, english_text
    
    def build_prompt(self, ancient_greek_text: str, english_text: str) -> str:
        """
        Build the prompt by inserting the verse texts into the template.
        
        Args:
            ancient_greek_text: Ancient Greek text
            english_text: English translation text
            
        Returns:
            Complete prompt string
        """
        # Combine texts - you may want to adjust this format
        combined_text = f"{english_text}\n\n[Ancient Greek]\n{ancient_greek_text}"
        
        # Replace the placeholder in the template
        prompt = self.prompt_template.replace('{{ INSERT PASSAGE HERE }}', combined_text)
        
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
    
    def save_triples(self, verse_range: str, triples: str) -> Path:
        """
        Save generated triples to file.
        
        Args:
            verse_range: Verse range directory name
            triples: RDF/Turtle triples to save
            
        Returns:
            Path to the saved file
        """
        verse_dir = self.productions_dir / verse_range
        
        # Extract verse numbers
        match = re.search(r'verse_(\d+)_to_(\d+)', verse_range)
        if not match:
            raise ValueError(f"Invalid verse range format: {verse_range}")
        
        start_verse, end_verse = match.groups()
        
        # Create output file path
        output_file = verse_dir / f'triples_{start_verse}_to_{end_verse}.ttl'
        
        # Ensure directory exists
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Write triples to file
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(triples)
        
        return output_file
    
    def process_verse_range(self, verse_range: str, model: str = "gpt-5.2", temperature: float = 0.3, max_tokens: int = 4000, skip_existing: bool = True) -> Optional[Path]:
        """
        Process a single verse range: read texts, call API, save output.
        
        Args:
            verse_range: Verse range directory name
            model: OpenAI model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            skip_existing: Skip if output file already exists
            
        Returns:
            Path to output file, or None if skipped
        """
        # Check if output already exists
        match = re.search(r'verse_(\d+)_to_(\d+)', verse_range)
        if match and skip_existing:
            start_verse, end_verse = match.groups()
            output_file = self.productions_dir / verse_range / f'triples_{start_verse}_to_{end_verse}.ttl'
            if output_file.exists():
                print(f"Skipping {verse_range} - output file already exists")
                return None
        
        print(f"Processing {verse_range}...")
        
        try:
            # Read texts
            ancient_greek_text, english_text = self.read_verse_texts(verse_range)
            
            # Build prompt
            prompt = self.build_prompt(ancient_greek_text, english_text)
            
            # Call API
            print(f"  Calling ChatGPT API...")
            api_response = self.call_chatgpt_api(prompt, model, temperature, max_tokens)
            
            # Extract triples
            triples = self.extract_triples(api_response)
            
            # Save output
            output_path = self.save_triples(verse_range, triples)
            print(f"  Saved to: {output_path}")
            
            return output_path
        
        except Exception as e:
            print(f"  ERROR processing {verse_range}: {str(e)}", file=sys.stderr)
            raise
    
    def process_all(self, model: str = "gpt-5.2", temperature: float = 0.3, max_tokens: int = 4000, skip_existing: bool = True):
        """
        Process all verse ranges found in the [PRODUCTIONS] directory.
        
        Args:
            model: OpenAI model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            skip_existing: Skip if output file already exists
        """
        verse_ranges = self.find_verse_ranges()
        
        if not verse_ranges:
            print("No verse ranges found!")
            return
        
        print(f"Found {len(verse_ranges)} verse range(s) to process")
        print()
        
        for verse_range in verse_ranges:
            try:
                self.process_verse_range(verse_range, model, temperature, max_tokens, skip_existing)
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
        default='Prompt.txt',
        help='Path to the prompt template file (default: Prompt.txt)'
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
    
    args = parser.parse_args()
    
    try:
        processor = VerseRangeProcessor(
            args.productions_dir,
            args.prompt_template,
            args.api_key
        )
        
        if args.verse_range:
            # Process single verse range
            processor.process_verse_range(
                args.verse_range,
                args.model,
                args.temperature,
                args.max_tokens,
                skip_existing=not args.no_skip_existing
            )
        else:
            # Process all verse ranges
            processor.process_all(
                args.model,
                args.temperature,
                args.max_tokens,
                skip_existing=not args.no_skip_existing
            )
    
    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
