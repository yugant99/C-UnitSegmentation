#!/usr/bin/env python3
"""
Simple LLM Refinement Module using direct Ollama commands
Stage 2: Handle complex linguistic decisions using locally hosted Mistral 7B

Author: Yugant Soni + AI Assistant
Date: December 2024
"""

import subprocess
import os
from pathlib import Path
from typing import List, Dict
import argparse


class SimpleLLMRefiner:
    """Simple LLM refinement processor using direct Ollama commands"""
    
    def __init__(self, model_name: str = "mistral"):
        self.model_name = model_name
        self.system_prompt = self._build_system_prompt()
        
        # Test if model is available
        self._test_ollama()
    
    def _test_ollama(self):
        """Test if Ollama and model are available"""
        try:
            result = subprocess.run(
                ["ollama", "list"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            if result.returncode == 0:
                if self.model_name in result.stdout:
                    print(f"✅ Found {self.model_name} in Ollama")
                else:
                    print(f"⚠️  Model {self.model_name} not found in Ollama")
                    print("Available models:", result.stdout)
            else:
                print(f"❌ Ollama list failed: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            print("❌ Ollama command timed out")
        except FileNotFoundError:
            print("❌ Ollama not found. Please install Ollama first.")
            raise
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for SALT formatting"""
        return """You are a SALT transcript formatter. Apply these rules:

1. C-UNIT SEGMENTATION: Split coordinating conjunctions (and, or, but, so) into separate lines
2. MAZE DETECTION: Put false starts/repetitions in parentheses: (false start) final form  
3. MORPHOLOGICAL MARKING: Add /ed, /s, /ing to verbs: look/ed, pack/ed
4. FILLED PAUSES: Format as (uh [FP]), (um [FP])

Examples:
Input: P: Let's go and get dressed and we'll get some breakfast.
Output: P: Let's go and get dressed.
P: And we'll get some breakfast.

Input: Av: Um, I, um, um, I need to go.
Output: Av: (Um [FP]) (I) (um [FP]) (um [FP]) (I) I need to go.

Only return the corrected text, no explanations."""
    
    def generate_response(self, prompt: str) -> str:
        """Generate response using Ollama command"""
        try:
            full_prompt = f"{self.system_prompt}\n\nInput: {prompt}\nOutput:"
            
            result = subprocess.run(
                ["ollama", "run", self.model_name],
                input=full_prompt,
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                response = result.stdout.strip()
                # Clean up the response
                lines = response.split('\n')
                cleaned_lines = []
                for line in lines:
                    line = line.strip()
                    if line and not line.startswith('>>>'):
                        cleaned_lines.append(line)
                
                return '\n'.join(cleaned_lines) if cleaned_lines else prompt
            else:
                print(f"❌ Ollama error: {result.stderr}")
                return prompt
                
        except subprocess.TimeoutExpired:
            print("⏰ Ollama timed out")
            return prompt
        except Exception as e:
            print(f"❌ Error: {e}")
            return prompt
    
    def process_line(self, line: str) -> str:
        """Process a single line"""
        # Skip structural lines
        if not line.strip() or line.startswith('#') or line.startswith('-') or line.startswith(';'):
            return line
        
        # Skip lines that are already well-formatted
        if len(line.strip()) < 10:
            return line
        
        # Process the line
        refined = self.generate_response(line.strip())
        
        # Return original if no improvement
        if not refined or refined == line.strip():
            return line
        
        return refined
    
    def process_transcript(self, input_text: str) -> str:
        """Process entire transcript"""
        lines = input_text.strip().split('\n')
        processed_lines = []
        
        print(f"🔄 Processing {len(lines)} lines...")
        
        for i, line in enumerate(lines):
            if i % 20 == 0:
                print(f"   Progress: {i}/{len(lines)} lines")
            
            processed_line = self.process_line(line)
            processed_lines.append(processed_line)
        
        print("✅ Processing complete!")
        return '\n'.join(processed_lines)
    
    def process_file(self, input_path: Path, output_path: Path) -> bool:
        """Process a single file"""
        try:
            print(f"📄 Processing: {input_path.name}")
            
            with open(input_path, 'r', encoding='utf-8') as f:
                input_text = f.read()
            
            refined_text = self.process_transcript(input_text)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(refined_text)
            
            print(f"✅ Completed: {output_path.name}")
            return True
            
        except Exception as e:
            print(f"❌ Error processing {input_path.name}: {e}")
            return False
    
    def process_directory(self, input_dir: Path, output_dir: Path) -> Dict[str, bool]:
        """Process all files in directory"""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = {}
        processed_files = list(input_dir.glob("*Rule-Based Processed*.txt"))
        
        if not processed_files:
            print("⚠️  No rule-based processed files found")
            return results
        
        print(f"📁 Processing {len(processed_files)} files")
        print(f"📁 Output directory: {output_dir}")
        print("-" * 60)
        
        for input_file in sorted(processed_files):
            output_name = input_file.name.replace("(Rule-Based Processed)", "(LLM Refined)")
            output_path = output_dir / output_name
            
            success = self.process_file(input_file, output_path)
            results[input_file.name] = success
        
        successful = sum(results.values())
        total = len(results)
        print("-" * 60)
        print(f"📊 Complete: {successful}/{total} files successful")
        
        return results


def main():
    """Command line interface"""
    parser = argparse.ArgumentParser(description="Simple LLM refinement using Ollama")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("/Users/yuganthareshsoni/CunitSegementation/rule_based_output"),
        help="Input directory"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/yuganthareshsoni/CunitSegementation/llm_refined_output"),
        help="Output directory"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="mistral",
        help="Ollama model name"
    )
    
    args = parser.parse_args()
    
    print("🚀 Starting Simple LLM Refiner...")
    
    try:
        refiner = SimpleLLMRefiner(args.model)
        results = refiner.process_directory(args.input_dir, args.output_dir)
        
        if all(results.values()):
            print("🎉 All files processed successfully!")
            return 0
        else:
            print("⚠️  Some files failed")
            return 1
            
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())

