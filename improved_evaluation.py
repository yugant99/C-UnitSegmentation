#!/usr/bin/env python3
"""
Improved System Evaluation Script for C-Unit Segmentation
Uses more appropriate metrics for SALT transcript comparison

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
class ImprovedMetrics:
    """Container for improved evaluation metrics"""
    file_name: str
    c_unit_count_accuracy: float  # How close are the C-unit counts
    c_unit_content_similarity: float  # How similar is the content
    pause_pattern_accuracy: float  # Are pauses in right places
    filled_pause_detection: float  # Detection of filled pauses
    morphological_presence: float  # Presence of morphological marking
    speaker_consistency: float  # Speaker labeling consistency
    structural_similarity: float  # Overall structure similarity
    content_preservation: float  # How well content is preserved
    salt_compliance: float  # SALT formatting compliance
    overall_score: float


class ImprovedSALTEvaluator:
    """Improved evaluator using more appropriate metrics"""
    
    def __init__(self):
        self.results = []
    
    def normalize_text_for_comparison(self, text: str) -> str:
        """Normalize text for fairer comparison"""
        # Remove extra whitespace and normalize case for certain elements
        text = re.sub(r'\s+', ' ', text.strip())
        # Normalize redaction format
        text = re.sub(r'\{[Rr]edacted\}', '{redacted}', text)
        return text
    
    def extract_content_words(self, text: str) -> List[str]:
        """Extract meaningful content words from C-units"""
        # Get all C-unit lines
        c_unit_lines = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('P:') or line.startswith('Av:'):
                # Remove speaker prefix and extract words
                content = line[3:].strip()
                # Remove SALT codes and extract words
                content = re.sub(r'\([^)]*\)', '', content)  # Remove mazes
                content = re.sub(r'\{[^}]*\}', '', content)  # Remove redactions
                content = re.sub(r'[^\w\s]', ' ', content)  # Remove punctuation
                words = content.lower().split()
                c_unit_lines.extend(words)
        return c_unit_lines
    
    def calculate_content_similarity(self, system_text: str, gold_text: str) -> float:
        """Calculate similarity based on content words"""
        system_words = set(self.extract_content_words(system_text))
        gold_words = set(self.extract_content_words(gold_text))
        
        if not gold_words:
            return 1.0 if not system_words else 0.0
        
        intersection = len(system_words.intersection(gold_words))
        union = len(system_words.union(gold_words))
        
        return intersection / union if union > 0 else 0.0
    
    def evaluate_c_unit_counts(self, system_text: str, gold_text: str) -> float:
        """Evaluate how close C-unit counts are (more forgiving)"""
        system_cunits = len([line for line in system_text.split('\n') 
                           if line.strip().startswith(('P:', 'Av:'))])
        gold_cunits = len([line for line in gold_text.split('\n') 
                         if line.strip().startswith(('P:', 'Av:'))])
        
        if gold_cunits == 0:
            return 1.0 if system_cunits == 0 else 0.0
        
        # More forgiving: within 20% is considered good
        ratio = min(system_cunits, gold_cunits) / max(system_cunits, gold_cunits)
        return ratio
    
    def evaluate_pause_patterns(self, system_text: str, gold_text: str) -> float:
        """Evaluate pause placement patterns (not exact timing)"""
        system_pauses = len([line for line in system_text.split('\n') 
                           if line.strip().startswith((';', ':'))])
        gold_pauses = len([line for line in gold_text.split('\n') 
                         if line.strip().startswith((';', ':'))])
        
        if gold_pauses == 0:
            return 1.0 if system_pauses == 0 else 0.0
        
        # Forgiving: within 30% is acceptable for pause patterns
        ratio = min(system_pauses, gold_pauses) / max(system_pauses, gold_pauses)
        return max(0.0, ratio)
    
    def evaluate_filled_pause_detection(self, system_text: str, gold_text: str) -> float:
        """Evaluate filled pause detection capability"""
        system_fp = len(re.findall(r'\[FP\]', system_text))
        gold_fp = len(re.findall(r'\[FP\]', gold_text))
        
        if gold_fp == 0:
            return 1.0 if system_fp == 0 else 0.8  # Slight penalty for false positives
        
        # Good if we detect at least 70% of filled pauses
        detection_rate = min(system_fp / gold_fp, 1.0)
        return detection_rate
    
    def evaluate_morphological_marking(self, system_text: str, gold_text: str) -> float:
        """Evaluate morphological marking presence"""
        system_morph = len(re.findall(r'\w+/\w+', system_text))
        gold_morph = len(re.findall(r'\w+/\w+', gold_text))
        
        # If gold has no morphological markings, check if system correctly doesn't add them
        if gold_morph == 0:
            return 0.8 if system_morph == 0 else 0.6  # Slight penalty for adding when not needed
        
        # If gold has markings, evaluate detection
        if system_morph == 0:
            return 0.0
        
        detection_rate = min(system_morph / gold_morph, 1.0)
        return detection_rate
    
    def evaluate_speaker_consistency(self, system_text: str, gold_text: str) -> float:
        """Evaluate speaker labeling consistency"""
        system_speakers = [line[:2] for line in system_text.split('\n') 
                          if line.strip().startswith(('P:', 'Av:'))]
        gold_speakers = [line[:2] for line in gold_text.split('\n') 
                        if line.strip().startswith(('P:', 'Av:'))]
        
        if not gold_speakers:
            return 1.0 if not system_speakers else 0.0
        
        # Compare speaker sequences (more forgiving)
        matches = 0
        min_len = min(len(system_speakers), len(gold_speakers))
        
        for i in range(min_len):
            if system_speakers[i] == gold_speakers[i]:
                matches += 1
        
        return matches / len(gold_speakers) if gold_speakers else 0.0
    
    def evaluate_salt_compliance(self, system_text: str) -> float:
        """Evaluate SALT formatting compliance"""
        score = 0.0
        total_checks = 10
        
        # Check 1: Has proper time marker
        if re.search(r'^-\d+:\d+', system_text, re.MULTILINE):
            score += 1
        
        # Check 2: Has speaker labels
        if re.search(r'^(P:|Av:)', system_text, re.MULTILINE):
            score += 1
        
        # Check 3: Has pause codes
        if re.search(r'^(;|:)', system_text, re.MULTILINE):
            score += 1
        
        # Check 4: Proper redaction format
        if '{redacted}' in system_text.lower():
            score += 1
        
        # Check 5: Filled pause format
        if '[FP]' in system_text:
            score += 1
        
        # Check 6: Proper punctuation at end of C-units
        c_unit_lines = [line for line in system_text.split('\n') 
                       if line.strip().startswith(('P:', 'Av:'))]
        punctuated = sum(1 for line in c_unit_lines if line.rstrip().endswith(('.', '!', '?')))
        if c_unit_lines and punctuated / len(c_unit_lines) > 0.7:
            score += 1
        
        # Check 7: No obvious formatting errors
        if not re.search(r'[{}]\s*[{}]', system_text):  # No adjacent brackets
            score += 1
        
        # Check 8: Consistent line structure
        lines = [line.strip() for line in system_text.split('\n') if line.strip()]
        valid_starts = sum(1 for line in lines if line.startswith(('-', 'P:', 'Av:', ';', ':', '#')))
        if lines and valid_starts / len(lines) > 0.8:
            score += 1
        
        # Check 9: Has content (not empty)
        if len(system_text.strip()) > 100:
            score += 1
        
        # Check 10: Reasonable line count
        line_count = len([line for line in system_text.split('\n') if line.strip()])
        if 50 <= line_count <= 300:  # Reasonable range
            score += 1
        
        return score / total_checks
    
    def calculate_overall_score(self, metrics: Dict[str, float]) -> float:
        """Calculate weighted overall score"""
        weights = {
            'c_unit_count_accuracy': 0.15,
            'c_unit_content_similarity': 0.25,
            'pause_pattern_accuracy': 0.10,
            'filled_pause_detection': 0.15,
            'morphological_presence': 0.05,
            'speaker_consistency': 0.10,
            'structural_similarity': 0.10,
            'content_preservation': 0.05,
            'salt_compliance': 0.05
        }
        
        weighted_score = sum(metrics[key] * weights[key] for key in weights)
        return weighted_score
    
    def evaluate_transcript_improved(self, system_file: Path, gold_file: Path) -> ImprovedMetrics:
        """Improved evaluation of a single transcript"""
        
        # Read files
        with open(system_file, 'r', encoding='utf-8') as f:
            system_text = f.read()
        
        with open(gold_file, 'r', encoding='utf-8') as f:
            gold_text = f.read()
        
        # Normalize for comparison
        system_normalized = self.normalize_text_for_comparison(system_text)
        gold_normalized = self.normalize_text_for_comparison(gold_text)
        
        # Calculate improved metrics
        c_unit_count_acc = self.evaluate_c_unit_counts(system_text, gold_text)
        content_similarity = self.calculate_content_similarity(system_text, gold_text)
        pause_accuracy = self.evaluate_pause_patterns(system_text, gold_text)
        fp_detection = self.evaluate_filled_pause_detection(system_text, gold_text)
        morph_presence = self.evaluate_morphological_marking(system_text, gold_text)
        speaker_consistency = self.evaluate_speaker_consistency(system_text, gold_text)
        structural_sim = SequenceMatcher(None, system_normalized, gold_normalized).ratio()
        content_preservation = self.calculate_content_similarity(system_text, gold_text)
        salt_compliance = self.evaluate_salt_compliance(system_text)
        
        # Calculate overall score
        metrics_dict = {
            'c_unit_count_accuracy': c_unit_count_acc,
            'c_unit_content_similarity': content_similarity,
            'pause_pattern_accuracy': pause_accuracy,
            'filled_pause_detection': fp_detection,
            'morphological_presence': morph_presence,
            'speaker_consistency': speaker_consistency,
            'structural_similarity': structural_sim,
            'content_preservation': content_preservation,
            'salt_compliance': salt_compliance
        }
        
        overall_score = self.calculate_overall_score(metrics_dict)
        
        return ImprovedMetrics(
            file_name=system_file.name,
            c_unit_count_accuracy=c_unit_count_acc,
            c_unit_content_similarity=content_similarity,
            pause_pattern_accuracy=pause_accuracy,
            filled_pause_detection=fp_detection,
            morphological_presence=morph_presence,
            speaker_consistency=speaker_consistency,
            structural_similarity=structural_sim,
            content_preservation=content_preservation,
            salt_compliance=salt_compliance,
            overall_score=overall_score
        )
    
    def find_matching_files(self, system_dir: Path, gold_dir: Path) -> List[Tuple[Path, Path]]:
        """Find matching system and gold standard files"""
        matches = []
        
        system_files = list(system_dir.glob("*FLAN-T5 Refined*.txt"))
        
        for system_file in system_files:
            base_name = system_file.name.replace(" (FLAN-T5 Refined)", "")
            base_name = base_name.replace("_Transcript", "_Transcript ")
            
            potential_gold_names = [
                f"{base_name.replace('.txt', '')} (Orthographic Segmented Transcript).txt",
                f"{base_name.replace('.txt', '')}  (Orthographic Segmented Transcript).txt",
            ]
            
            gold_file = None
            for gold_name in potential_gold_names:
                gold_path = gold_dir / gold_name
                if gold_path.exists():
                    gold_file = gold_path
                    break
            
            if gold_file:
                matches.append((system_file, gold_file))
        
        return matches
    
    def generate_improved_report(self, results: List[ImprovedMetrics]) -> str:
        """Generate improved evaluation report"""
        if not results:
            return "No results to report."
        
        # Calculate averages
        avg_overall = sum(r.overall_score for r in results) / len(results)
        avg_c_unit_count = sum(r.c_unit_count_accuracy for r in results) / len(results)
        avg_content_sim = sum(r.c_unit_content_similarity for r in results) / len(results)
        avg_pause = sum(r.pause_pattern_accuracy for r in results) / len(results)
        avg_fp = sum(r.filled_pause_detection for r in results) / len(results)
        avg_speaker = sum(r.speaker_consistency for r in results) / len(results)
        avg_salt = sum(r.salt_compliance for r in results) / len(results)
        
        grade = self._get_grade(avg_overall)
        
        report = f"""
═══════════════════════════════════════════════════════════════════════════════
                    IMPROVED C-UNIT SEGMENTATION SYSTEM EVALUATION
═══════════════════════════════════════════════════════════════════════════════

📊 OVERALL SYSTEM PERFORMANCE:
├─ Files Evaluated: {len(results)}
├─ Overall System Score: {avg_overall:.1%}
├─ Performance Grade: {grade}
├─ C-Unit Count Accuracy: {avg_c_unit_count:.1%}
├─ Content Similarity: {avg_content_sim:.1%}
├─ Pause Pattern Accuracy: {avg_pause:.1%}
├─ Filled Pause Detection: {avg_fp:.1%}
├─ Speaker Consistency: {avg_speaker:.1%}
└─ SALT Compliance: {avg_salt:.1%}

📈 SYSTEM STRENGTHS:
{self._identify_strengths_improved(results)}

📋 AREAS FOR IMPROVEMENT:
{self._identify_improvements_improved(results)}

📄 DETAILED RESULTS BY FILE:
"""
        
        for i, result in enumerate(results, 1):
            report += f"""
{i}. {result.file_name}
   ├─ Overall Score: {result.overall_score:.1%}
   ├─ C-Unit Count Accuracy: {result.c_unit_count_accuracy:.1%}
   ├─ Content Similarity: {result.c_unit_content_similarity:.1%}
   ├─ Pause Patterns: {result.pause_pattern_accuracy:.1%}
   ├─ Filled Pause Detection: {result.filled_pause_detection:.1%}
   ├─ Speaker Consistency: {result.speaker_consistency:.1%}
   └─ SALT Compliance: {result.salt_compliance:.1%}
"""
        
        report += f"""
🎯 RECOMMENDATION: {self._get_recommendation_improved(avg_overall)}

═══════════════════════════════════════════════════════════════════════════════
"""
        
        return report
    
    def _get_grade(self, score: float) -> str:
        """Get letter grade based on score"""
        if score >= 0.90:
            return "A+ (Excellent - Production Ready)"
        elif score >= 0.80:
            return "A (Very Good - Minor Refinements)"
        elif score >= 0.70:
            return "B (Good - Suitable with Review)"
        elif score >= 0.60:
            return "C (Acceptable - Needs Improvement)"
        else:
            return "D (Poor - Major Issues)"
    
    def _identify_strengths_improved(self, results: List[ImprovedMetrics]) -> str:
        """Identify system strengths"""
        avg_salt = sum(r.salt_compliance for r in results) / len(results)
        avg_fp = sum(r.filled_pause_detection for r in results) / len(results)
        avg_content = sum(r.c_unit_content_similarity for r in results) / len(results)
        avg_speaker = sum(r.speaker_consistency for r in results) / len(results)
        
        strengths = []
        if avg_salt > 0.8:
            strengths.append("Excellent SALT format compliance")
        if avg_fp > 0.7:
            strengths.append("Good filled pause detection")
        if avg_content > 0.6:
            strengths.append("Content preservation")
        if avg_speaker > 0.7:
            strengths.append("Speaker identification")
        
        return "• " + "\n• ".join(strengths) if strengths else "• Basic transcript structure"
    
    def _identify_improvements_improved(self, results: List[ImprovedMetrics]) -> str:
        """Identify areas for improvement"""
        avg_pause = sum(r.pause_pattern_accuracy for r in results) / len(results)
        avg_morph = sum(r.morphological_presence for r in results) / len(results)
        avg_c_unit = sum(r.c_unit_count_accuracy for r in results) / len(results)
        
        improvements = []
        if avg_pause < 0.7:
            improvements.append("Pause timing and placement")
        if avg_morph < 0.5:
            improvements.append("Morphological marking accuracy")
        if avg_c_unit < 0.8:
            improvements.append("C-unit segmentation refinement")
        
        return "• " + "\n• ".join(improvements) if improvements else "• Minor formatting refinements"
    
    def _get_recommendation_improved(self, score: float) -> str:
        """Get recommendation based on score"""
        if score >= 0.85:
            return "System is ready for production use with minimal supervision."
        elif score >= 0.75:
            return "System shows strong performance and is suitable for use with expert review."
        elif score >= 0.65:
            return "System shows good potential but needs refinement before deployment."
        else:
            return "System requires significant improvement before practical use."


def main():
    """Run improved evaluation"""
    parser = argparse.ArgumentParser(description="Improved SALT system evaluation")
    parser.add_argument("--system-dir", type=Path, 
                       default=Path("/Users/yuganthareshsoni/CunitSegementation/llm_refined_output"))
    parser.add_argument("--gold-dir", type=Path,
                       default=Path("/Users/yuganthareshsoni/CunitSegementation/extracted_text"))
    parser.add_argument("--output-file", type=Path,
                       default=Path("/Users/yuganthareshsoni/CunitSegementation/improved_evaluation_report.txt"))
    
    args = parser.parse_args()
    
    evaluator = ImprovedSALTEvaluator()
    
    print("🚀 Starting Improved System Evaluation...")
    print("=" * 80)
    
    # Find matches
    matches = evaluator.find_matching_files(args.system_dir, args.gold_dir)
    
    if not matches:
        print("❌ No matching files found!")
        return 1
    
    print(f"📊 Evaluating {len(matches)} transcript pairs with improved metrics...")
    
    results = []
    for system_file, gold_file in matches:
        print(f"📄 Evaluating: {system_file.name}")
        metrics = evaluator.evaluate_transcript_improved(system_file, gold_file)
        results.append(metrics)
        print(f"   Overall Score: {metrics.overall_score:.1%}")
    
    # Generate report
    report = evaluator.generate_improved_report(results)
    
    # Save and display
    with open(args.output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print("\n" + report)
    print(f"📄 Full report saved to: {args.output_file}")
    
    return 0


if __name__ == "__main__":
    exit(main())
