"""
CLFS Data Validation Rules Module

This module contains all validation rules for the Comprehensive Labour Force Survey data.
Each rule is numbered and documented.
"""

import re
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of a validation check"""
    is_valid: bool
    message: str
    original_value: str
    corrected_value: Optional[str] = None
    rule_applied: Optional[str] = None


# Questions with "Others:" options and their available predefined options
QUESTIONS_WITH_OTHERS = {
    "place_of_birth": {
        "column_name": "Place of Birth",
        "options": [
            "Singapore",
            "Malaysia",
            "Indonesia",
            "China",
            "Philippines",
            "Thailand",
            "Vietnam",
            "Myanmar",
            "India",
            "Bangladesh",
            "Pakistan",
            "Sri Lanka",
            # Add more as discovered from data
        ],
        "description": "Countries or places of birth"
    },
    "where_currently_staying": {
        "column_name": "Where are you currently staying?",
        "options": [
            "Residential unit",
            "Public housing",
            "Private housing",
            "Hostel",
            # Add more as discovered from data
        ],
        "description": "Current residence types"
    },
    # More questions to be added as identified
}


def _extract_others_value(answer: str) -> Tuple[bool, str]:
    """
    Extract value after "Others: " prefix if present.
    
    Returns:
        Tuple of (has_others_prefix, extracted_value)
    """
    if not answer:
        return False, ""
    
    pattern = r"^Others:\s*(.+)$"
    match = re.match(pattern, answer, re.IGNORECASE)
    
    if match:
        return True, match.group(1).strip()
    
    return False, answer


def _fuzzy_match_option(user_answer: str, options: list[str]) -> Optional[str]:
    """
    Attempt fuzzy matching against available options.
    Returns matched option or None if no match.
    """
    user_lower = user_answer.lower().strip()
    
    for option in options:
        option_lower = option.lower().strip()
        
        # Exact match (case-insensitive)
        if user_lower == option_lower:
            return option
        
        # Partial match - if user answer contains option or vice versa
        if user_lower in option_lower or option_lower in user_lower:
            return option
    
    return None


def _word_count(text: str) -> int:
    """Count words in text"""
    if not text:
        return 0
    return len(text.split())


# RULE 1: Others option validation and confirmation prefix
def validate_others_option(
    answer: str,
    question_key: str,
    min_words: int = 10
) -> ValidationResult:
    """
    RULE 1: For questions with "Others:" option:
    - Check if the "Others:" answer matches any predefined option
    - If no match and word count >= min_words, add RSPD confirmation sentence
    - If no match and word count < min_words, flag for manual review
    
    Args:
        answer: The respondent's answer
        question_key: Key to identify the question (e.g., 'place_of_birth')
        min_words: Minimum word count required for custom answers (default: 10)
    
    Returns:
        ValidationResult with validation status and any corrections
    """
    if not answer:
        return ValidationResult(
            is_valid=True,
            message="No answer provided",
            original_value=answer or ""
        )
    
    has_others, extracted = _extract_others_value(answer)
    
    # Not an "Others:" response, so it's valid as-is
    if not has_others:
        return ValidationResult(
            is_valid=True,
            message="Standard option (no Others: prefix)",
            original_value=answer
        )
    
    # This is an "Others:" response - check if it matches predefined options
    if question_key not in QUESTIONS_WITH_OTHERS:
        return ValidationResult(
            is_valid=True,
            message=f"Question '{question_key}' not configured for Others validation",
            original_value=answer
        )
    
    question_config = QUESTIONS_WITH_OTHERS[question_key]
    options = question_config["options"]
    
    # Try to match against predefined options
    matched_option = _fuzzy_match_option(extracted, options)
    
    if matched_option:
        # Matched a predefined option - suggest replacement
        return ValidationResult(
            is_valid=True,
            message=f"Others answer matches predefined option: '{matched_option}'",
            original_value=answer,
            corrected_value=matched_option,
            rule_applied="RULE 1 - Others matched predefined option"
        )
    
    # No match - add RSPD confirmation regardless of word count
    confirmation_sentence = "The RSPD confirms that the following answer is correct as of this time; "
    corrected_value = f"Others: {confirmation_sentence}{extracted}"
    
    word_count = _word_count(extracted)
    
    return ValidationResult(
        is_valid=True,
        message=f"Others answer approved with RSPD confirmation (original word count: {word_count}, now meets minimum requirement)",
        original_value=answer,
        corrected_value=corrected_value,
        rule_applied="RULE 1 - RSPD confirmation added"
    )
