<!-- ebaa5bd8-2ebb-4971-b591-cb964fc48267 c4424570-9b5a-4f55-bc60-b1a27200de9d -->
# Rule 16: Implement Filled Pause Detection

## Problem Analysis

Current evaluation shows:

- Filled Pause Accuracy: 0.0% across ALL files
- Missing 25-27 filled pauses per file on average
- Raw hesitation markers exist in Descript input but aren't transformed to SALT notation
- Example: "Av: Um, um, okay I guess" should become "Av: (Um [FP]) (um [FP]) okay, I guess"

## Implementation Strategy

### Step 1: Create Filled Pause Detection Engine

**File**: `rule_based_processor.py`

**Location**: Add new method after `segment_cunits_proper()` (around line 290)

**Function**: `detect_filled_pauses_enhanced(self, text: str) -> str`

**Core Logic**:

- Pattern-based detection of hesitation markers
- Context analysis to avoid false positives
- SALT transformation: "um" → "(um [FP])"
- Handle multiple consecutive filled pauses

### Step 2: Implement Pattern Recognition

**Approach**: Instruction-based, not hardcoded lists

- Identify common hesitation patterns: /^(uh|um|hm|er|ah)$/i
- Check word boundaries to avoid partial matches
- Consider phonetic variations and case sensitivity
- Validate standalone hesitation markers vs meaningful speech

### Step 3: Add Context Analysis

**Smart Detection Rules**:

- Only mark standalone hesitation words
- Skip if part of larger meaningful word (e.g., "umbrella" contains "um")
- Handle punctuation around filled pauses
- Preserve original capitalization in SALT notation

### Step 4: Integrate with Processing Pipeline

**File**: `rule_based_processor.py`

**Location**: Lines 800-806 in `process_transcript()` method

**Integration Point**: After basic cleaning, before C-unit segmentation

**Flow**: Input parsing → Basic cleaning → **Filled pause detection** → C-unit segmentation → Output

### Step 5: Create Test Function

**Function**: `test_rule_16_filled_pauses()`

**Test Cases**:

- Single filled pause: "Um, okay" → "(Um [FP]) okay"
- Multiple consecutive: "Um, uh, yes" → "(Um [FP]) (uh [FP]) yes"
- Mixed with speech: "I, um, don't know" → "I (um [FP]) don't know"
- False positive avoidance: "umbrella" remains "umbrella"

### Step 6: Benchmark and Validate

**Target Files**: Same 10 files as Rule 4 test

**Expected Results**:

- Filled Pause Accuracy: 0% → 80-90%
- Overall System Accuracy: 7.6% → 15-20%
- No regression in C-unit or speaker accuracy

## Implementation Details

### Core Detection Function:

```python
def detect_filled_pauses_enhanced(self, text: str) -> str:
    # 1. Tokenize text while preserving punctuation
    # 2. Identify hesitation patterns with word boundaries
    # 3. Apply context analysis for validation
    # 4. Transform to SALT notation: word → (word [FP])
    # 5. Reconstruct text with proper spacing
```

### Integration Point:

```python
# In process_transcript(), add after line 800:
clean_content = self.handle_redactions(raw_content)
# NEW: Add filled pause detection
clean_content = self.detect_filled_pauses_enhanced(clean_content)
# EXISTING: Continue with C-unit segmentation
segmented_cunits = self.segment_cunits_proper(clean_content, speaker)
```

## Success Criteria

1. **Filled Pause Accuracy**: 0% → 80%+ across all files
2. **Overall Accuracy Boost**: 7.6% → 15-20% system accuracy
3. **Pattern Recognition**: Correctly identify hesitation markers in context
4. **SALT Compliance**: Proper "(word [FP])" notation formatting
5. **No Regression**: Maintain existing C-unit and speaker accuracy

## Files Modified

- `rule_based_processor.py` (main implementation and integration)

## Testing Strategy

- Unit test filled pause detection with various input patterns
- Process same 10 files as previous benchmarks
- Compare against Rule 4 baseline results
- Validate specific improvements in files with high filled pause counts (VR_Howl's_Moving_Castle: 26 expected, VR_Falcon: 27 expected)

## Risk Mitigation

- Implement as separate function first before integration
- Test pattern recognition independently
- Maintain existing processing pipeline integrity
- Ability to disable filled pause detection if issues arise

### To-dos

- [ ] Create parse_descript_line_properly() function to extract timestamp, speaker, and content without segmentation
- [ ] Remove segment_cunits() call from process_transcript() to stop over-segmentation
- [ ] Add test_rule_1_parsing() function to validate input parsing works correctly
- [ ] Modify content processing to preserve single line per Descript input
- [ ] Test Rule 1 fix on VR_Call_Me_by_Your_Name file and verify no over-segmentation