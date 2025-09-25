#!/usr/bin/env python3
"""
System Evaluation Script for C-Unit Segmentation
Compares our hybrid system output against human-coded gold standard transcripts

Author: Yugant Soni + AI Assistant
Date: December 2024
"""

import re
import os
from pathlib import Path
from typing import List, Dict, Tuple, Set
import argparse
from dataclasses import dataclass
from difflib import SequenceMatcher
import json


@dataclass
class TranscriptMetrics:
    """Container for transcript comparison metrics"""
    file_name: str
    total_lines_system: int
    total_lines_gold: int
    c_unit_accuracy: float
    pause_accuracy: float
    filled_pause_accuracy: float
    morphological_accuracy: float
    speaker_accuracy: float
    overall_similarity: float
    detailed_comparison: Dict


class SALTEvaluator:
    """Evaluates SALT transcript quality against gold standard"""
    
    def __init__(self):
        self.results = []
        
    def extract_c_units(self, text: str) -> List[str]:
        """Extract C-units (lines starting with P: or Av:)"""
        lines = text.strip().split('\n')
        c_units = []
        for line in lines:
            line = line.strip()
            if line.startswith('P:') or line.startswith('Av:'):
                c_units.append(line)
        return c_units
    
    def extract_pause_codes(self, text: str) -> List[str]:
        """Extract pause codes (lines starting with ; or :)"""
        lines = text.strip().split('\n')
        pauses = []
        for line in lines:
            line = line.strip()
            if line.startswith(';') or line.startswith(':'):
                pauses.append(line)
        return pauses
    
    def extract_filled_pauses(self, text: str) -> List[str]:
        """Extract filled pause patterns (text with [FP])"""
        filled_pauses = re.findall(r'\([^)]*\[FP\][^)]*\)', text)
        return filled_pauses
    
    def extract_morphological_marks(self, text: str) -> List[str]:
        """Extract morphological markings (words with /)"""
        morph_marks = re.findall(r'\b\w+/\w+\b', text)
        return morph_marks
    
    def extract_speaker_lines(self, text: str) -> List[str]:
        """Extract all speaker-prefixed lines"""
        lines = text.strip().split('\n')
        speaker_lines = []
        for line in lines:
            line = line.strip()
            if line.startswith('P:') or line.startswith('Av:'):
                speaker_lines.append(line[:2])  # Just the speaker code
        return speaker_lines
    
    def calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate overall text similarity using difflib"""
        matcher = SequenceMatcher(None, text1, text2)
        return matcher.ratio()
    
    def compare_lists(self, system_list: List[str], gold_list: List[str]) -> float:
        """Compare two lists and return accuracy percentage"""
        if not gold_list:
            return 1.0 if not system_list else 0.0
        
        # Simple approach: count exact matches
        matches = 0
        max_len = max(len(system_list), len(gold_list))
        
        for i in range(min(len(system_list), len(gold_list))):
            if system_list[i] == gold_list[i]:
                matches += 1
        
        return matches / max_len if max_len > 0 else 0.0
    
    def analyze_c_unit_segmentation(self, system_text: str, gold_text: str) -> Dict:
        """Detailed analysis of C-unit segmentation quality"""
        system_cunits = self.extract_c_units(system_text)
        gold_cunits = self.extract_c_units(gold_text)
        
        analysis = {
            'system_count': len(system_cunits),
            'gold_count': len(gold_cunits),
            'count_difference': abs(len(system_cunits) - len(gold_cunits)),
            'sample_system': system_cunits[:3],
            'sample_gold': gold_cunits[:3],
        }
        
        return analysis
    
    def evaluate_transcript(self, system_file: Path, gold_file: Path) -> TranscriptMetrics:
        """Evaluate a single transcript against gold standard"""
        
        # Read files
        with open(system_file, 'r', encoding='utf-8') as f:
            system_text = f.read()
        
        with open(gold_file, 'r', encoding='utf-8') as f:
            gold_text = f.read()
        
        # Extract components
        system_cunits = self.extract_c_units(system_text)
        gold_cunits = self.extract_c_units(gold_text)
        
        system_pauses = self.extract_pause_codes(system_text)
        gold_pauses = self.extract_pause_codes(gold_text)
        
        system_fp = self.extract_filled_pauses(system_text)
        gold_fp = self.extract_filled_pauses(gold_text)
        
        system_morph = self.extract_morphological_marks(system_text)
        gold_morph = self.extract_morphological_marks(gold_text)
        
        system_speakers = self.extract_speaker_lines(system_text)
        gold_speakers = self.extract_speaker_lines(gold_text)
        
        # Calculate accuracies
        c_unit_accuracy = self.compare_lists(system_cunits, gold_cunits)
        pause_accuracy = self.compare_lists(system_pauses, gold_pauses)
        fp_accuracy = self.compare_lists(system_fp, gold_fp)
        morph_accuracy = self.compare_lists(system_morph, gold_morph)
        speaker_accuracy = self.compare_lists(system_speakers, gold_speakers)
        overall_similarity = self.calculate_similarity(system_text, gold_text)
        
        # Detailed comparison
        detailed = {
            'c_unit_analysis': self.analyze_c_unit_segmentation(system_text, gold_text),
            'pause_counts': {
                'system': len(system_pauses),
                'gold': len(gold_pauses)
            },
            'filled_pause_counts': {
                'system': len(system_fp),
                'gold': len(gold_fp)
            },
            'morphological_counts': {
                'system': len(system_morph),
                'gold': len(gold_morph)
            }
        }
        
        return TranscriptMetrics(
            file_name=system_file.name,
            total_lines_system=len(system_text.split('\n')),
            total_lines_gold=len(gold_text.split('\n')),
            c_unit_accuracy=c_unit_accuracy,
            pause_accuracy=pause_accuracy,
            filled_pause_accuracy=fp_accuracy,
            morphological_accuracy=morph_accuracy,
            speaker_accuracy=speaker_accuracy,
            overall_similarity=overall_similarity,
            detailed_comparison=detailed
        )
    
    def find_matching_files(self, system_dir: Path, gold_dir: Path) -> List[Tuple[Path, Path]]:
        """Find matching system and gold standard files"""
        matches = []
        
        # Get all system files
        system_files = list(system_dir.glob("*FLAN-T5 Refined*.txt"))
        
        for system_file in system_files:
            # Extract base name to find corresponding gold file
            base_name = system_file.name.replace(" (FLAN-T5 Refined)", "")
            base_name = base_name.replace("_Transcript", "_Transcript ")  # Handle naming variations
            
            # Look for gold standard file
            potential_gold_names = [
                f"{base_name.replace('.txt', '')} (Orthographic Segmented Transcript).txt",
                f"{base_name.replace('.txt', '')}  (Orthographic Segmented Transcript).txt",  # Double space
            ]
            
            gold_file = None
            for gold_name in potential_gold_names:
                gold_path = gold_dir / gold_name
                if gold_path.exists():
                    gold_file = gold_path
                    break
            
            if gold_file:
                matches.append((system_file, gold_file))
                print(f"✅ Found match: {system_file.name} ↔ {gold_file.name}")
            else:
                print(f"⚠️  No gold standard found for: {system_file.name}")
        
        return matches
    
    def evaluate_system(self, system_dir: Path, gold_dir: Path) -> List[TranscriptMetrics]:
        """Evaluate entire system against gold standard"""
        
        print("🔍 Finding matching transcript pairs...")
        matches = self.find_matching_files(system_dir, gold_dir)
        
        if not matches:
            print("❌ No matching files found!")
            return []
        
        print(f"📊 Evaluating {len(matches)} transcript pairs...")
        print("-" * 80)
        
        results = []
        for system_file, gold_file in matches:
            print(f"📄 Evaluating: {system_file.name}")
            metrics = self.evaluate_transcript(system_file, gold_file)
            results.append(metrics)
            
            # Print summary for this file
            print(f"   C-Unit Accuracy: {metrics.c_unit_accuracy:.2%}")
            print(f"   Pause Accuracy: {metrics.pause_accuracy:.2%}")
            print(f"   Filled Pause Accuracy: {metrics.filled_pause_accuracy:.2%}")
            print(f"   Morphological Accuracy: {metrics.morphological_accuracy:.2%}")
            print(f"   Overall Similarity: {metrics.overall_similarity:.2%}")
            print()
        
        return results
    
    def generate_report(self, results: List[TranscriptMetrics]) -> str:
        """Generate comprehensive evaluation report"""
        if not results:
            return "No results to report."
        
        # Calculate averages
        avg_c_unit = sum(r.c_unit_accuracy for r in results) / len(results)
        avg_pause = sum(r.pause_accuracy for r in results) / len(results)
        avg_fp = sum(r.filled_pause_accuracy for r in results) / len(results)
        avg_morph = sum(r.morphological_accuracy for r in results) / len(results)
        avg_speaker = sum(r.speaker_accuracy for r in results) / len(results)
        avg_similarity = sum(r.overall_similarity for r in results) / len(results)
        
        report = f"""
═══════════════════════════════════════════════════════════════════════════════
                    C-UNIT SEGMENTATION SYSTEM EVALUATION REPORT
═══════════════════════════════════════════════════════════════════════════════

📊 OVERALL SYSTEM PERFORMANCE:
├─ Files Evaluated: {len(results)}
├─ Average C-Unit Accuracy: {avg_c_unit:.1%}
├─ Average Pause Accuracy: {avg_pause:.1%}
├─ Average Filled Pause Accuracy: {avg_fp:.1%}
├─ Average Morphological Accuracy: {avg_morph:.1%}
├─ Average Speaker Accuracy: {avg_speaker:.1%}
└─ Average Overall Similarity: {avg_similarity:.1%}

📈 PERFORMANCE GRADE: {self._get_performance_grade(avg_similarity)}

📋 DETAILED RESULTS BY FILE:
"""
        
        for i, result in enumerate(results, 1):
            report += f"""
{i}. {result.file_name}
   ├─ Lines: {result.total_lines_system} (System) vs {result.total_lines_gold} (Gold)
   ├─ C-Unit Accuracy: {result.c_unit_accuracy:.1%}
   ├─ Pause Accuracy: {result.pause_accuracy:.1%}
   ├─ Filled Pause Accuracy: {result.filled_pause_accuracy:.1%}
   ├─ Morphological Accuracy: {result.morphological_accuracy:.1%}
   └─ Overall Similarity: {result.overall_similarity:.1%}
"""
        
        report += f"""
🔍 SYSTEM ANALYSIS:
├─ Strengths: {self._identify_strengths(results)}
├─ Areas for Improvement: {self._identify_weaknesses(results)}
└─ Recommendation: {self._get_recommendation(avg_similarity)}

═══════════════════════════════════════════════════════════════════════════════
"""
        
        return report
    
    def _get_performance_grade(self, similarity: float) -> str:
        """Get performance grade based on similarity"""
        if similarity >= 0.90:
            return "A+ (Excellent)"
        elif similarity >= 0.80:
            return "A (Very Good)"
        elif similarity >= 0.70:
            return "B (Good)"
        elif similarity >= 0.60:
            return "C (Acceptable)"
        else:
            return "D (Needs Improvement)"
    
    def _identify_strengths(self, results: List[TranscriptMetrics]) -> str:
        """Identify system strengths"""
        avg_speaker = sum(r.speaker_accuracy for r in results) / len(results)
        avg_fp = sum(r.filled_pause_accuracy for r in results) / len(results)
        avg_c_unit = sum(r.c_unit_accuracy for r in results) / len(results)
        
        strengths = []
        if avg_speaker > 0.9:
            strengths.append("Speaker identification")
        if avg_fp > 0.8:
            strengths.append("Filled pause detection")
        if avg_c_unit > 0.7:
            strengths.append("C-unit segmentation")
        
        return ", ".join(strengths) if strengths else "Basic formatting"
    
    def _identify_weaknesses(self, results: List[TranscriptMetrics]) -> str:
        """Identify areas needing improvement"""
        avg_pause = sum(r.pause_accuracy for r in results) / len(results)
        avg_morph = sum(r.morphological_accuracy for r in results) / len(results)
        
        weaknesses = []
        if avg_pause < 0.7:
            weaknesses.append("Pause timing accuracy")
        if avg_morph < 0.7:
            weaknesses.append("Morphological marking")
        
        return ", ".join(weaknesses) if weaknesses else "Minor refinements needed"
    
    def _get_recommendation(self, similarity: float) -> str:
        """Get recommendation based on performance"""
        if similarity >= 0.85:
            return "System ready for production use with minimal supervision"
        elif similarity >= 0.75:
            return "System suitable for use with expert review"
        else:
            return "System needs further refinement before deployment"


def main():
    """Command line interface for system evaluation"""
    parser = argparse.ArgumentParser(
        description="Evaluate C-unit segmentation system against gold standard"
    )
    parser.add_argument(
        "--system-dir",
        type=Path,
        default=Path("/Users/yuganthareshsoni/CunitSegementation/llm_refined_output"),
        help="Directory containing system output files"
    )
    parser.add_argument(
        "--gold-dir",
        type=Path,
        default=Path("/Users/yuganthareshsoni/CunitSegementation/extracted_text"),
        help="Directory containing gold standard files"
    )
    parser.add_argument(
        "--output-file",
        type=Path,
        default=Path("/Users/yuganthareshsoni/CunitSegementation/evaluation_report.txt"),
        help="Output file for evaluation report"
    )
    
    args = parser.parse_args()
    
    # Initialize evaluator
    evaluator = SALTEvaluator()
    
    # Run evaluation
    print("🚀 Starting System Evaluation...")
    print(f"📁 System Directory: {args.system_dir}")
    print(f"📁 Gold Standard Directory: {args.gold_dir}")
    print("=" * 80)
    
    results = evaluator.evaluate_system(args.system_dir, args.gold_dir)
    
    if results:
        # Generate report
        report = evaluator.generate_report(results)
        
        # Save report
        with open(args.output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        # Display report
        print(report)
        print(f"📄 Full report saved to: {args.output_file}")
        
        # Save detailed results as JSON
        json_file = args.output_file.with_suffix('.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump([
                {
                    'file_name': r.file_name,
                    'c_unit_accuracy': r.c_unit_accuracy,
                    'pause_accuracy': r.pause_accuracy,
                    'filled_pause_accuracy': r.filled_pause_accuracy,
                    'morphological_accuracy': r.morphological_accuracy,
                    'speaker_accuracy': r.speaker_accuracy,
                    'overall_similarity': r.overall_similarity,
                    'detailed_comparison': r.detailed_comparison
                }
                for r in results
            ], f, indent=2)
        
        print(f"📊 Detailed data saved to: {json_file}")
        
        return 0
    else:
        print("❌ No files could be evaluated")
        return 1


if __name__ == "__main__":
    exit(main())
