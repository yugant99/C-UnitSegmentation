#!/usr/bin/env python3
"""
LLM Refinement Module for C-Unit Segmentation using Ollama
Stage 2: Handle complex linguistic decisions using locally hosted Mistral 7B

Author: Yugant Soni + AI Assistant
Date: December 2024
"""

import re
import os
import json
import requests
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import argparse
from dataclasses import dataclass


@dataclass
class SALTExample:
    """Container for SALT transformation examples"""
    input_text: str
    expected_output: str
    transformation_type: str


class SALTPromptBuilder:
    """Builds prompts for SALT formatting tasks"""
    
    def __init__(self):
        self.system_prompt = self._build_system_prompt()
        self.examples = self._load_examples()
    
    def _build_system_prompt(self) -> str:
        """Build comprehensive system prompt with SALT rules"""
        return """You are a specialized linguistic assistant for SALT (Systematic Analysis of Language Transcripts) formatting. Your task is to refine partially processed transcripts according to SALT conventions.

KEY RULES:
1. C-UNIT SEGMENTATION:
   - Split coordinating conjunctions (and, or, but, so, then) into separate c-units
   - Keep subordinating conjunctions (because, that, when, who, after, before, so that, which, although, if, unless, while, as, how, until, like, where, since) as one c-unit
   - Treat yes/no/okay responses as separate c-units

2. MAZE DETECTION:
   - Identify false starts, repetitions, reformulations
   - Format as: (maze content) final form
   - Use [FP] for filled pauses within mazes: (uh [FP])

3. MORPHOLOGICAL MARKING:
   - Add /ed, /s, /ing to verbs and words: look/ed, pack/ed, jump/s

4. PAUSE REFINEMENT:
   - Use : for intra-utterance pauses
   - Use ; for inter-utterance pauses
   - Add duration if ≥2 seconds: :03, ; :05

5. SPECIAL CODES:
   - Overlapping speech: <overlap>
   - Abandoned utterances: utterance>
   - Unintelligible: X (word), XX (segment), XXX (utterance)

OUTPUT FORMAT: Return only the refined transcript text, no explanations."""

    def _load_examples(self) -> List[SALTExample]:
        """Load few-shot examples for in-context learning"""
        return [
            SALTExample(
                input_text="P: Let's go and get dressed and we'll get some breakfast.",
                expected_output="P: Let's go and get dressed.\nP: And we'll get some breakfast.",
                transformation_type="coordinating_conjunction"
            ),
            SALTExample(
                input_text="Av: (Um, [FP]) I, (um, [FP]) (um, [FP]) I need to go.",
                expected_output="Av: (Um [FP]) (I) (um [FP]) (um [FP]) (I) I need to go.",
                transformation_type="maze_refinement"
            ),
            SALTExample(
                input_text="Av: When the boy look in the jar he saw that the frog was missing.",
                expected_output="Av: When the boy look/ed in the jar he saw that the frog was missing.",
                transformation_type="morphological_marking"
            ),
            SALTExample(
                input_text="P: Do you want apples Av: yes",
                expected_output="P: Do you want <apples>\nAv: <Yes>.",
                transformation_type="overlap_detection"
            )
        ]
    
    def build_prompt(self, input_text: str, task_type: str = "comprehensive") -> str:
        """Build prompt for specific SALT refinement task"""
        
        # Add few-shot examples
        examples_text = ""
        for example in self.examples[:2]:  # Use first 2 examples
            examples_text += f"\nInput: {example.input_text}\nOutput: {example.expected_output}\n"
        
        prompt = f"""{self.system_prompt}

EXAMPLES:{examples_text}

Now refine this transcript according to SALT conventions:

Input: {input_text}
Output:"""
        
        return prompt


class OllamaProcessor:
    """Handles Ollama API operations for local Mistral model"""
    
    def __init__(self, model_name: str = "mistral:latest", base_url: str = "http://localhost:11434"):
        self.model_name = model_name
        self.base_url = base_url
        self.api_url = f"{base_url}/api/generate"
        
        # Test connection
        self._test_connection()
    
    def _test_connection(self):
        """Test if Ollama is running and model is available"""
        try:
            # Test if Ollama is running
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code == 200:
                models = response.json().get("models", [])
                model_names = [model["name"] for model in models]
                
                if self.model_name in model_names:
                    print(f"✅ Found {self.model_name} in Ollama")
                else:
                    print(f"⚠️  Model {self.model_name} not found. Available models: {model_names}")
                    # Use first available model as fallback
                    if model_names:
                        self.model_name = model_names[0]
                        print(f"🔄 Using {self.model_name} instead")
            else:
                print(f"❌ Ollama API returned status {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Cannot connect to Ollama at {self.base_url}")
            print(f"   Error: {e}")
            print("   Please ensure Ollama is running: 'ollama serve'")
            raise ConnectionError("Cannot connect to Ollama")
    
    def generate_response(self, prompt: str, max_tokens: int = 150) -> str:
        """Generate response from Ollama model"""
        try:
            payload = {
                "model": self.model_name,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.3,
                    "top_p": 0.9,
                    "num_predict": max_tokens,
                    "stop": ["\n\n", "Input:", "Output:"]
                }
            }
            
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                generated_text = result.get("response", "").strip()
                return generated_text
            else:
                print(f"❌ Ollama API error: {response.status_code}")
                return ""
                
        except requests.exceptions.RequestException as e:
            print(f"❌ Error calling Ollama API: {e}")
            return ""
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            return ""


class LLMRefiner:
    """Main LLM refinement processor using Ollama"""
    
    def __init__(self, model_name: str = "mistral:latest"):
        self.prompt_builder = SALTPromptBuilder()
        print("🤖 Initializing Ollama Mistral processor...")
        self.ollama = OllamaProcessor(model_name)
        
        # Linguistic processing patterns
        self.coordinating_conjunctions = {
            'and', 'or', 'but', 'so', 'then'
        }
        self.subordinating_conjunctions = {
            'because', 'that', 'when', 'who', 'after', 'before', 
            'which', 'although', 'if', 'unless', 'while', 'as', 
            'how', 'until', 'like', 'where', 'since'
        }
    
    def process_line(self, line: str) -> str:
        """Process a single line through LLM refinement"""
        if not line.strip() or line.startswith('#') or line.startswith('-') or line.startswith(';'):
            return line  # Skip structural lines
        
        # Apply comprehensive refinement
        prompt = self.prompt_builder.build_prompt(line, "comprehensive")
        refined = self.ollama.generate_response(prompt, max_tokens=100)
        
        # Clean up the response
        refined = refined.strip()
        
        # Remove any extra formatting or explanations
        lines = refined.split('\n')
        if lines:
            refined = lines[0].strip()
        
        if not refined or refined == line:
            return line  # Fallback to original if no useful response
        
        return refined
    
    def process_transcript(self, input_text: str) -> str:
        """Process entire transcript through LLM refinement"""
        lines = input_text.strip().split('\n')
        processed_lines = []
        
        print(f"🔄 Processing {len(lines)} lines through Ollama Mistral...")
        
        for i, line in enumerate(lines):
            if i % 10 == 0:
                print(f"   Progress: {i}/{len(lines)} lines")
            
            processed_line = self.process_line(line)
            processed_lines.append(processed_line)
        
        print("✅ LLM processing complete!")
        return '\n'.join(processed_lines)
    
    def process_file(self, input_path: Path, output_path: Path) -> bool:
        """Process a single file through LLM refinement"""
        try:
            print(f"📄 Processing: {input_path.name}")
            
            # Read input
            with open(input_path, 'r', encoding='utf-8') as f:
                input_text = f.read()
            
            # Process through LLM
            refined_text = self.process_transcript(input_text)
            
            # Write output
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(refined_text)
            
            print(f"✅ Completed: {input_path.name} -> {output_path.name}")
            return True
            
        except Exception as e:
            print(f"❌ Error processing {input_path.name}: {e}")
            return False
    
    def process_directory(self, input_dir: Path, output_dir: Path) -> Dict[str, bool]:
        """Process all rule-based files through LLM refinement"""
        
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results = {}
        
        # Find all rule-based processed files
        processed_files = list(input_dir.glob("*Rule-Based Processed*.txt"))
        
        if not processed_files:
            print("⚠️  No rule-based processed files found")
            return results
        
        print(f"📁 Processing {len(processed_files)} files through Ollama Mistral")
        print(f"📁 Output directory: {output_dir}")
        print("-" * 60)
        
        for input_file in sorted(processed_files):
            # Generate output filename
            output_name = input_file.name.replace("(Rule-Based Processed)", "(LLM Refined)")
            output_path = output_dir / output_name
            
            # Process the file
            success = self.process_file(input_file, output_path)
            results[input_file.name] = success
        
        # Print summary
        successful = sum(results.values())
        total = len(results)
        print("-" * 60)
        print(f"📊 LLM processing complete: {successful}/{total} files successful")
        
        return results


def main():
    """Command line interface for LLM refinement using Ollama"""
    parser = argparse.ArgumentParser(
        description="LLM refinement for C-unit segmentation using Ollama Mistral"
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=Path("/Users/yuganthareshsoni/CunitSegementation/rule_based_output"),
        help="Directory containing rule-based processed transcripts"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/Users/yuganthareshsoni/CunitSegementation/llm_refined_output"),
        help="Directory to save LLM refined transcripts"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="mistral:latest",
        help="Ollama model name to use"
    )
    
    args = parser.parse_args()
    
    # Initialize LLM refiner
    print("🚀 Initializing Ollama LLM Refiner...")
    try:
        refiner = LLMRefiner(args.model)
        
        # Process all files
        results = refiner.process_directory(args.input_dir, args.output_dir)
        
        # Exit with appropriate code
        if all(results.values()):
            print("🎉 All files processed successfully!")
            return 0
        else:
            print("⚠️  Some files failed to process")
            return 1
            
    except ConnectionError:
        print("💡 To start Ollama, run: ollama serve")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
