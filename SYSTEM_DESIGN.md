# C-Unit Segmentation System Design
## Hybrid Rule-Based NLP + LLM Architecture

### Project Overview
**Goal**: Automate the transformation of raw Descript transcripts into properly segmented SALT (Systematic Analysis of Language Transcripts) format for CARE Lab's Be EPIC-VR assessments.

**Input**: Raw Descript transcripts with timestamps  
**Output**: SALT-formatted transcripts with proper C-unit segmentation, pause coding, and linguistic annotations

---

## System Architecture

### 1. Modular Pipeline Design

```
Raw Descript Transcript
         ↓
┌─────────────────────────┐
│  Stage 1: Rule-Based   │
│  Preprocessing Module  │
└─────────────────────────┘
         ↓
┌─────────────────────────┐
│  Stage 2: LLM          │
│  Refinement Module     │
└─────────────────────────┘
         ↓
┌─────────────────────────┐
│  Stage 3: Validation   │
│  & Quality Assurance   │
└─────────────────────────┘
         ↓
┌─────────────────────────┐
│  Stage 4: Evaluation   │
│  & Metrics Module      │
└─────────────────────────┘
         ↓
Final SALT Transcript
```

---

## Module Specifications

### Stage 1: Rule-Based Preprocessing Module
**Purpose**: Handle deterministic transformations and reduce complexity for LLM

**Responsibilities**:
- **Timestamp Conversion**: `[00:01:30]` → `- 1:30` (time markers) or pause codes
- **Speaker Normalization**: Ensure consistent `P:` and `Av:` formatting  
- **Basic Structure**: Add header format, time markers
- **Simple Pattern Detection**:
  - Obvious filled pauses: "uh", "um", "hm" → `(uh [FP])`
  - Basic punctuation cleanup
  - Redaction standardization: `[redacted]` → `{redacted}`
- **Text Preprocessing**: Remove extra whitespace, normalize formatting

**Input Example**:
```
VR_Call_Me_by_Your_Name
[00:00:00] P: Good morning, James. It's [redacted]. I'm your caregiver.
[00:00:14] Av: I don't need help.
```

**Output Example**:
```
VR_Call_Me_by_Your_Name
-0:00
P: Good morning, James.
P: It's {redacted}.
P: I'm your caregiver.
; :14
Av: I don't need help.
```

### Stage 2: LLM Refinement Module (Gemma 2B)
**Purpose**: Handle complex linguistic decisions requiring contextual understanding

**Responsibilities**:
- **C-Unit Segmentation**: 
  - Identify coordinating vs subordinating conjunctions
  - Split complex sentences appropriately
  - Handle conjunction-reduced utterances
- **Maze Detection & Annotation**:
  - Identify false starts, repetitions, reformulations
  - Apply parentheses correctly: `(maze content) final form`
  - Complex filled pause patterns
- **Morphological Marking**: Add `/ed`, `/s`, `/ing` annotations
- **Pause Timing Decisions**: Estimate pause durations from context
- **Advanced Linguistic Analysis**:
  - Overlapping speech detection: `<overlap>`
  - Abandoned utterances: `utterance>`
  - Complex nonverbal behavior placement

**Model Configuration**:
- **Base Model**: Gemma 2B (optimized for MacBook Air M3)
- **Fine-tuning Strategy**: Few-shot → Fine-tuning on paired examples
- **Context Window**: Process sentence-level chunks with surrounding context
- **Prompt Engineering**: Use SALT rules as system prompts

### Stage 3: Validation & Quality Assurance Module
**Purpose**: Ensure output meets SALT formatting standards

**Responsibilities**:
- **Format Validation**: Check all SALT conventions are followed
- **Consistency Checks**: Verify speaker codes, time markers, punctuation
- **Rule Compliance**: Validate against requirements.txt specifications  
- **Error Detection**: Flag potential issues for manual review
- **Post-processing**: Final cleanup and formatting

### Stage 4: Evaluation & Metrics Module
**Purpose**: Measure system performance and reliability

**Responsibilities**:
- **Cohen's Kappa Calculation**: Inter-rater reliability between system and gold standard
- **Accuracy Metrics**: 
  - C-unit boundary accuracy
  - Maze detection precision/recall
  - Morphological marking accuracy
- **Error Analysis**: Categorize and report common error patterns
- **Performance Tracking**: Monitor system improvements over time

---

## Data Flow & Processing

### Input Processing Chain
1. **Raw Transcript Ingestion**: Parse Descript format
2. **Rule-Based Transformation**: Apply deterministic rules (70% of work)
3. **LLM Processing**: Handle complex decisions (30% of work)
4. **Validation Pipeline**: Ensure quality and compliance
5. **Metrics Generation**: Calculate performance scores

### Training Data Utilization
**Available Data**:
- 3 paired examples (raw → segmented)
- ~150-180 lines per segmented transcript
- Clear transformation patterns

**Training Strategy**:
1. **Pattern Analysis**: Extract transformation rules from examples
2. **Few-Shot Prompting**: Use examples as in-context learning
3. **Fine-Tuning**: Train Gemma 2B on sentence-level transformations
4. **Iterative Improvement**: Refine based on stakeholder feedback

---

## Evaluation Framework

### Cohen's Kappa Metrics
**Measured Aspects**:
- C-unit boundary agreement
- Maze annotation agreement  
- Morphological marking agreement
- Overall transcript structure agreement

**Calculation Method**:
```python
# Segment-level comparison
def calculate_cohens_kappa(gold_standard, system_output):
    # Compare each annotation type separately
    c_unit_kappa = cohen_kappa(gold_cunits, system_cunits)
    maze_kappa = cohen_kappa(gold_mazes, system_mazes)
    morph_kappa = cohen_kappa(gold_morphs, system_morphs)
    return overall_kappa, detailed_metrics
```

### Performance Benchmarks
**Target Metrics**:
- Cohen's Kappa > 0.8 (strong agreement)
- C-unit accuracy > 90%
- Maze detection F1 > 0.85
- Processing speed < 30 seconds per transcript

---

## Implementation Phases

### Phase 1: Rule-Based Foundation
- Build preprocessing module
- Implement basic transformations
- Test on 3 examples

### Phase 2: LLM Integration  
- Set up Gemma 2B locally
- Implement few-shot prompting
- Fine-tune on available data

### Phase 3: Evaluation System
- Build Cohen's kappa calculator
- Implement comprehensive metrics
- Create performance dashboard

### Phase 4: Stakeholder Testing
- Deploy system for testing
- Collect expert feedback
- Iterative improvements

---

## Technical Stack

**Core Technologies**:
- **Python 3.9+**: Main development language
- **Transformers/HuggingFace**: LLM integration
- **Gemma 2B**: Local LLM deployment  
- **PyTorch**: Model inference
- **Pandas/NumPy**: Data processing
- **scikit-learn**: Metrics calculation

**Hardware Requirements**:
- MacBook Air M3: Sufficient for Gemma 2B
- 16GB RAM recommended
- Local deployment (no API dependencies)

---

## Success Criteria

### Technical Success
- ✅ Cohen's Kappa > 0.8 with expert annotations
- ✅ Processing time < 30 seconds per transcript
- ✅ 90%+ accuracy on C-unit segmentation
- ✅ Robust handling of all SALT formatting rules

### Business Success  
- ✅ Reduces manual transcription time by 70%+
- ✅ Maintains clinical research quality standards
- ✅ Scales to handle increased transcript volume
- ✅ Stakeholder approval for production deployment

---

## Risk Mitigation

**Technical Risks**:
- LLM hallucination → Validation module + rule constraints
- Performance issues → Optimized local deployment
- Training data limitations → Active learning + expert feedback

**Quality Risks**:
- Inconsistent output → Comprehensive validation pipeline
- Domain-specific errors → Fine-tuning on clinical data
- Edge case handling → Robust error detection + fallbacks

---

## Next Steps

1. **Architecture Review**: Stakeholder approval of design
2. **Prototype Development**: Build Stage 1 (Rule-Based Module)  
3. **LLM Integration**: Implement Gemma 2B processing
4. **Testing & Validation**: Comprehensive evaluation on examples
5. **Stakeholder Feedback**: Expert review and refinement
6. **Production Deployment**: Scale for operational use

---

*Document Version: 1.0*  
*Last Updated: December 2024*  
*Author: AI Assistant + Yugant Soni*
