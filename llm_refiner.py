#!/usr/bin/env python3
"""
LLM Refinement Module for C-Unit Segmentation
Stage 2: Handle complex linguistic decisions using Gemma 2B

Author: Yugant Soni + AI Assistant
Date: December 2024
"""

import re
import os
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import argparse
import json
from dataclasses import dataclass

try:
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline
    print("✅ Transformers imported successfully")
except ImportError as e:
    print(f"❌ Error importing transformers: {e}")
    print("Please install with: pip install transformers torch")
    exit(1)


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


class MistralProcessor:
    """Handles Mistral 7B model operations"""
    
    def __init__(self, model_name: str = "mistralai/Mistral-7B-Instruct-v0.1"):
        self.model_name = model_name
        self.device = "mps" if torch.backends.mps.is_available() else "cpu"
        print(f"🔧 Using device: {self.device}")
        
        self.tokenizer = None
        self.model = None
        self.pipeline = None
        self._load_model()
    
    def _load_model(self):
        """Load Mistral 7B model and tokenizer"""
        try:
            print(f"📥 Loading {self.model_name}...")
            
            # Load tokenizer
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            # Load model without device_map to avoid accelerate dependency
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if self.device != "cpu" else torch.float32,
                trust_remote_code=True,
                local_files_only=True  # Use local installation
            )
            
            # Move model to device manually
            if self.device != "cpu":
                self.model = self.model.to(self.device)
            
            # Create pipeline
            self.pipeline = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if self.device != "cpu" else -1,
                torch_dtype=torch.float16 if self.device != "cpu" else torch.float32,
            )
            
            print("✅ Model loaded successfully!")
            
        except Exception as e:
            print(f"❌ Error loading model: {e}")
            print("💡 Trying with CPU fallback...")
            self._load_model_cpu_fallback()
    
    def _load_model_cpu_fallback(self):
        """Fallback to CPU-only loading"""
        try:
            self.device = "cpu"
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            self.model = AutoModelForCausalLM.from_pretrained(
                self.model_name,
                torch_dtype=torch.float32,
                trust_remote_code=True,
                local_files_only=True  # Use local installation
            )
            
            self.pipeline = pipeline(
                "text-generation",
                model=self.model,
                tokenizer=self.tokenizer,
                device=-1,
                torch_dtype=torch.float32,
            )
            
            print("✅ Model loaded on CPU!")
            
        except Exception as e:
            print(f"❌ Failed to load model: {e}")
            raise
    
    def generate_response(self, prompt: str, max_length: int = 512) -> str:
        """Generate response from Gemma model"""
        try:
            # Generate response
            response = self.pipeline(
                prompt,
                max_new_tokens=max_length,
                do_sample=True,
                temperature=0.3,
                top_p=0.9,
                pad_token_id=self.tokenizer.eos_token_id,
                eos_token_id=self.tokenizer.eos_token_id,
            )
            
            # Extract generated text
            generated_text = response[0]['generated_text']
            
            # Remove the input prompt from output
            output = generated_text[len(prompt):].strip()
            
            return output
            
        except Exception as e:
            print(f"❌ Error generating response: {e}")
            return ""


class LLMRefiner:
    """Main LLM refinement processor"""
    
    def __init__(self, model_name: str = "mistralai/Mistral-7B-Instruct-v0.1"):
        self.prompt_builder = SALTPromptBuilder()
        print("🤖 Initializing Mistral processor...")
        self.mistral = MistralProcessor(model_name)
        
        # Linguistic processing patterns
        self.coordinating_conjunctions = {
            'and', 'or', 'but', 'so', 'then'
        }
        self.subordinating_conjunctions = {
            'because', 'that', 'when', 'who', 'after', 'before', 
            'which', 'although', 'if', 'unless', 'while', 'as', 
            'how', 'until', 'like', 'where', 'since'
        }
    
    def segment_cunits(self, text: str) -> str:
        """Segment text into proper C-units using LLM"""
        prompt = self.prompt_builder.build_prompt(text, "c_unit_segmentation")
        response = self.mistral.generate_response(prompt, max_length=300)
        return response.strip()
    
    def refine_mazes(self, text: str) -> str:
        """Refine maze detection and formatting using LLM"""
        prompt = self.prompt_builder.build_prompt(text, "maze_refinement")
        response = self.mistral.generate_response(prompt, max_length=200)
        return response.strip()
    
    def add_morphological_marking(self, text: str) -> str:
        """Add morphological markings (/ed, /s, /ing) using LLM"""
        prompt = self.prompt_builder.build_prompt(text, "morphological_marking")
        response = self.mistral.generate_response(prompt, max_length=200)
        return response.strip()
    
    def process_line(self, line: str) -> str:
        """Process a single line through LLM refinement"""
        if not line.strip() or line.startswith('#') or line.startswith('-') or line.startswith(';'):
            return line  # Skip structural lines
        
        # Apply comprehensive refinement
        prompt = self.prompt_builder.build_prompt(line, "comprehensive")
        refined = self.mistral.generate_response(prompt, max_length=150)
        
        # Clean up the response
        refined = refined.strip()
        if not refined:
            return line  # Fallback to original if no response
        
        return refined
    
    def process_transcript(self, input_text: str) -> str:
        """Process entire transcript through LLM refinement"""
        lines = input_text.strip().split('\n')
        processed_lines = []
        
        print(f"🔄 Processing {len(lines)} lines through LLM...")
        
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
        
        print(f"📁 Processing {len(processed_files)} files through LLM")
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
    """Command line interface for LLM refinement"""
    parser = argparse.ArgumentParser(
        description="LLM refinement for C-unit segmentation using Mistral 7B"
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
        default="mistralai/Mistral-7B-Instruct-v0.1",
        help="Hugging Face model name to use"
    )
    
    args = parser.parse_args()
    
    # Initialize LLM refiner
    print("🚀 Initializing LLM Refiner...")
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


if __name__ == "__main__":
    exit(main())
