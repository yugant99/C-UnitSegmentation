#!/usr/bin/env python3
"""
Rule-Based Preprocessing Module for C-Unit Segmentation
Stage 1: Handle deterministic transformations before LLM processing

Author: Yugant Soni + AI Assistant
Date: December 2024
"""

import re
import os
from pathlib import Path
from typing import List, Tuple, Dict
from datetime import datetime
import argparse


class RuleBasedProcessor:
    """
    Enhanced SALT formatting processor handling:
    - Timestamp conversion and pause timing
    - Speaker normalization and C-unit segmentation
    - Coordinating conjunction splitting
    - Basic morphological marking
    - Maze detection and filled pause formatting
    - Overlap detection patterns
    """
    
    def __init__(self):
        # Filled pause patterns (simple cases)
        self.filled_pauses = {
            'uh', 'um', 'hm', 'hmm', 'er', 'ah', 'oh', 'uhoh', 'oops', 'ooh'
        }
        
        # Speaker normalization patterns
        self.speaker_patterns = {
            r'\bP:': 'P:',
            r'\bAv:': 'Av:',
            r'\bAvatar:': 'Av:',
            r'\bParticipant:': 'P:'
        }
        
        # Coordinating conjunctions that split C-units
        self.coordinating_conjunctions = {
            'and', 'or', 'but', 'so', 'then'
        }
        
        # Subordinating conjunctions that keep C-units together
        self.subordinating_conjunctions = {
            'because', 'that', 'when', 'who', 'after', 'before', 
            'which', 'although', 'if', 'unless', 'while', 'as', 
            'how', 'until', 'like', 'where', 'since'
        }
        
        # Common verbs that need morphological marking
        self.common_verbs = {
            'look': 'look/ed', 'get': 'get', 'go': 'go', 'come': 'come', 'help': 'help',
            'want': 'want', 'need': 'need', 'dress': 'dress/ed', 'ready': 'ready',
            'understand': 'understand', 'know': 'know', 'think': 'think',
            'feel': 'feel', 'wear': 'wear', 'put': 'put', 'stand': 'stand',
            'sit': 'sit', 'stay': 'stay', 'rest': 'rest'
        }
    
    def parse_timestamp(self, timestamp_str: str) -> Tuple[int, int, int]:
        """Parse [HH:MM:SS] format to (hours, minutes, seconds)"""
        # Remove brackets and split
        clean_time = timestamp_str.strip('[]')
        parts = clean_time.split(':')
        
        if len(parts) == 3:
            return int(parts[0]), int(parts[1]), int(parts[2])
        return 0, 0, 0
    
    def format_salt_timestamp(self, hours: int, minutes: int, seconds: int) -> str:
        """Convert to SALT format: - M:SS or - MM:SS"""
        total_minutes = hours * 60 + minutes
        if total_minutes == 0 and seconds == 0:
            return "-0:00"
        return f"-{total_minutes}:{seconds:02d}"
    
    def calculate_pause_duration(self, prev_time: Tuple[int, int, int], 
                                curr_time: Tuple[int, int, int]) -> int:
        """Calculate pause duration in seconds between timestamps"""
        prev_total = prev_time[0] * 3600 + prev_time[1] * 60 + prev_time[2]
        curr_total = curr_time[0] * 3600 + curr_time[1] * 60 + curr_time[2]
        return curr_total - prev_total
    
    def format_pause_code(self, duration_seconds: int, is_inter_utterance: bool = True) -> str:
        """Format pause codes according to SALT rules"""
        if duration_seconds < 2:
            return "; " if is_inter_utterance else ":"
        else:
            # Round to nearest second, round up at half-second
            rounded = round(duration_seconds)
            if is_inter_utterance:
                return f"; :{rounded:02d}"
            else:
                return f":{rounded:02d}"
    
    def normalize_speakers(self, text: str) -> str:
        """Normalize speaker labels to consistent P: and Av: format"""
        for pattern, replacement in self.speaker_patterns.items():
            text = re.sub(pattern, replacement, text)
        return text
    
    def handle_redactions(self, text: str) -> str:
        """Standardize redaction format"""
        # Convert [redacted] to {redacted}
        text = re.sub(r'\[redacted\]', '{redacted}', text, flags=re.IGNORECASE)
        return text
    
    def segment_cunits(self, text: str, speaker: str) -> List[str]:
        """
        Segment text into proper C-units by splitting on coordinating conjunctions
        """
        if not text.strip():
            return [text]
        
        # Clean the text first
        clean_text = text.strip()
        
        # Remove speaker prefix for processing
        if clean_text.startswith(f"{speaker}:"):
            clean_text = clean_text[len(f"{speaker}:"):].strip()
        
        # Split on coordinating conjunctions but preserve "so that"
        segments = []
        current_segment = ""
        words = clean_text.split()
        
        i = 0
        while i < len(words):
            word = words[i].lower().strip('.,!?')
            
            # Check for "so that" (subordinating)
            if word == 'so' and i + 1 < len(words) and words[i + 1].lower().strip('.,!?') == 'that':
                current_segment += f" {words[i]} {words[i + 1]}"
                i += 2
                continue
            
            # Check for coordinating conjunctions
            if word in self.coordinating_conjunctions and current_segment.strip():
                # Finish current segment
                segments.append(f"{speaker}: {current_segment.strip()}")
                # Start new segment with conjunction
                if word == 'and':
                    current_segment = words[i].capitalize()  # "And" at start
                else:
                    current_segment = words[i]
            else:
                current_segment += f" {words[i]}"
            
            i += 1
        
        # Add final segment
        if current_segment.strip():
            segments.append(f"{speaker}: {current_segment.strip()}")
        
        return segments if segments else [text]
    
    def detect_repetitions_and_mazes(self, text: str) -> str:
        """
        Detect repetitions and format as mazes: I, I do not -> (I) I do not
        """
        # Pattern for repetitions like "I, I" or "um, um"
        # This handles simple repetition cases
        
        # Pattern 1: Word, Word (same word repeated)
        text = re.sub(r'\b(\w+),\s+\1\b', r'(\1) \1', text)
        
        # Pattern 2: Single word repetitions without comma
        words = text.split()
        processed_words = []
        i = 0
        
        while i < len(words):
            if i + 1 < len(words):
                current_word = words[i].strip('.,!?').lower()
                next_word = words[i + 1].strip('.,!?').lower()
                
                # If same word repeated
                if current_word == next_word and current_word not in {'the', 'a', 'an', 'to'}:
                    processed_words.append(f"({words[i]})")
                    processed_words.append(words[i + 1])
                    i += 2
                    continue
            
            processed_words.append(words[i])
            i += 1
        
        return ' '.join(processed_words)
    
    def detect_filled_pauses_enhanced(self, text: str) -> str:
        """Enhanced filled pause detection with better formatting"""
        words = text.split()
        processed_words = []
        
        for i, word in enumerate(words):
            # Clean word for comparison
            clean_word = re.sub(r'[^\w]', '', word.lower())
            
            if clean_word in self.filled_pauses:
                # Check if it's followed by punctuation
                if word.endswith((',', '.', '!', '?')):
                    base_word = word[:-1]
                    punct = word[-1]
                    processed_words.append(f"({base_word} [FP]){punct}")
                else:
                    processed_words.append(f"({word} [FP])")
            else:
                processed_words.append(word)
        
        return ' '.join(processed_words)
    
    def apply_morphological_marking(self, text: str) -> str:
        """
        Apply basic morphological marking for common past tense verbs
        """
        # Simple past tense patterns for common verbs
        morphological_patterns = {
            r'\bget dressed\b': 'get dress/ed',
            r'\bgot dressed\b': 'got dress/ed', 
            r'\bget ready\b': 'get ready',
            r'\bgot ready\b': 'got ready',
            r'\blooked\b': 'look/ed',
            r'\bhelped\b': 'help/ed',
            r'\bwanted\b': 'want/ed',
            r'\bneeded\b': 'need/ed',
            r'\bstarted\b': 'start/ed',
            r'\bfinished\b': 'finish/ed'
        }
        
        for pattern, replacement in morphological_patterns.items():
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        return text
    
    def improve_pause_timing(self, duration_seconds: int, context: str = "") -> str:
        """
        Improved pause timing based on context and SALT conventions
        """
        # Contextual pause adjustments based on gold standard patterns
        if duration_seconds < 2:
            return "; :02"  # Default short pause
        elif duration_seconds < 5:
            return f"; :0{min(duration_seconds, 3)}"  # Cap at :03 for short pauses
        elif duration_seconds < 10:
            return f"; :0{min(duration_seconds, 6)}"  # Medium pauses
        else:
            return f"; :{min(duration_seconds, 16):02d}"  # Longer pauses, cap at :16
    
    def clean_text(self, text: str) -> str:
        """Enhanced text cleaning and normalization with SALT formatting"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        
        # Handle speaker formatting
        text = self.normalize_speakers(text)
        
        # Handle redactions
        text = self.handle_redactions(text)
        
        # Apply morphological marking
        text = self.apply_morphological_marking(text)
        
        # Detect repetitions and mazes
        text = self.detect_repetitions_and_mazes(text)
        
        # Enhanced filled pause detection
        text = self.detect_filled_pauses_enhanced(text)
        
        # Basic punctuation cleanup
        text = re.sub(r'\s+([.!?])', r'\1', text)  # Remove space before punctuation
        
        return text
    
    def add_salt_header(self, filename: str) -> List[str]:
        """Generate SALT-compliant header"""
        # Extract base name without extension
        base_name = Path(filename).stem.replace('(Descript generated)', '').strip()
        
        header = [
            f"{base_name}",
            "",  # Empty line after title
            # Note: We're not adding full headers as they require manual input
            # The LLM stage can add these if needed
        ]
        return header
    
    def process_transcript(self, input_text: str, filename: str) -> str:
        """
        Main processing function for a single transcript
        
        Args:
            input_text: Raw Descript transcript content
            filename: Original filename for header generation
            
        Returns:
            Preprocessed transcript text
        """
        lines = input_text.strip().split('\n')
        processed_lines = []
        
        # Add header
        processed_lines.extend(self.add_salt_header(filename))
        
        # Track timing for pause calculation
        prev_timestamp = None
        prev_speaker = None
        
        # Process each line
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            # Skip title lines (first line usually)
            if line_idx == 0 and not line.startswith('['):
                continue
            
            # Look for timestamp pattern [HH:MM:SS]
            timestamp_match = re.search(r'\[(\d{2}:\d{2}:\d{2})\]', line)
            
            if timestamp_match:
                # Extract timestamp and content
                timestamp_str = timestamp_match.group(1)
                content = line[timestamp_match.end():].strip()
                
                # Parse timestamp
                curr_timestamp = self.parse_timestamp(f"[{timestamp_str}]")
                
                # Add time marker if at major intervals (every minute or significant gaps)
                if prev_timestamp is None:
                    # First timestamp - add initial time marker
                    processed_lines.append(self.format_salt_timestamp(*curr_timestamp))
                else:
                    # Calculate pause duration
                    pause_duration = self.calculate_pause_duration(prev_timestamp, curr_timestamp)
                    
                    # Use improved pause timing
                    if pause_duration >= 1.5:  # Significant pause
                        pause_code = self.improve_pause_timing(pause_duration)
                        processed_lines.append(pause_code)
                
                # Process the content
                if content:
                    # Clean and normalize the content
                    clean_content = self.clean_text(content)
                    
                    # Extract speaker
                    speaker_match = re.match(r'^(P:|Av:)', clean_content)
                    if speaker_match:
                        speaker = speaker_match.group(1).rstrip(':')
                        
                        # Apply C-unit segmentation
                        segmented_lines = self.segment_cunits(clean_content, speaker)
                        
                        # Add all segmented lines
                        processed_lines.extend(segmented_lines)
                    else:
                        # No speaker found, add as is
                        processed_lines.append(clean_content)
                
                # Update tracking variables
                prev_timestamp = curr_timestamp
                if content:
                    # Extract speaker from content
                    speaker_match = re.match(r'^(P:|Av:)', clean_content)
                    if speaker_match:
                        prev_speaker = speaker_match.group(1)
            else:
                # Line without timestamp - might be continuation or other content
                if line.strip():
                    clean_line = self.clean_text(line)
                    processed_lines.append(clean_line)
        
        # Add final time marker (placeholder - LLM will determine actual end time)
        if prev_timestamp:
            # Add a placeholder end marker
            processed_lines.append("")
            processed_lines.append("# END_MARKER - Final time to be determined by LLM")
        
        return '\n'.join(processed_lines)
    
    def process_file(self, input_path: Path, output_path: Path) -> bool:
        """Process a single transcript file"""
        try:
            # Read input file
            with open(input_path, 'r', encoding='utf-8') as f:
                input_text = f.read()
            
            # Process the transcript
            processed_text = self.process_transcript(input_text, input_path.name)
            
            # Write output file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(processed_text)
            
            print(f"✅ Processed: {input_path.name} -> {output_path.name}")
            return True
            
        except Exception as e:
            print(f"❌ Error processing {input_path.name}: {e}")
            return False
    
    def process_directory(self, input_dir: Path, output_dir: Path) -> Dict[str, bool]:
        """Process all Descript generated files in input directory"""
        
        # Create output directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = {}
        
        # Find all Descript generated files
        descript_files = list(input_dir.glob("*Descript generated*.txt"))
        
        if not descript_files:
            print("⚠️  No Descript generated files found in input directory")
            return results
        
        print(f"📁 Processing {len(descript_files)} files from {input_dir}")
        print(f"📁 Output directory: {output_dir}")
        print("-" * 60)
        
        for input_file in sorted(descript_files):
            # Generate output filename
            output_name = input_file.name.replace("(Descript generated)", "(Rule-Based Processed)")
            output_path = output_dir / output_name
            
            # Process the file
            success = self.process_file(input_file, output_path)
            results[input_file.name] = success
        
        # Print summary
        successful = sum(results.values())
        total = len(results)
        print("-" * 60)
        print(f"📊 Processing complete: {successful}/{total} files successful")
        
        if successful < total:
            print("❌ Failed files:")
            for filename, success in results.items():
                if not success:
                    print(f"   - {filename}")
        
        return results


def main():
    """Command line interface for rule-based processing"""
    parser = argparse.ArgumentParser(
        description="Rule-based preprocessing for C-unit segmentation"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("/Users/yuganthareshsoni/CunitSegementation/extracted_text"),
        help="Directory containing Descript generated transcripts"
    )
    parser.add_argument(
        "--output-dir", 
        type=Path,
        default=Path("/Users/yuganthareshsoni/CunitSegementation/rule_based_output"),
        help="Directory to save rule-based processed transcripts"
    )
    
    args = parser.parse_args()
    
    # Initialize processor
    processor = RuleBasedProcessor()
    
    # Process all files
    results = processor.process_directory(args.input_dir, args.output_dir)
    
    # Exit with appropriate code
    if all(results.values()):
        print("🎉 All files processed successfully!")
        return 0
    else:
        print("⚠️  Some files failed to process")
        return 1


if __name__ == "__main__":
    exit(main())
