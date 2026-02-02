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
# RULE 1: For any question that has an 'Others: ' option, validate and auto-correct responses
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
        ],
        "description": "Countries or places of birth"
    },
    "main_reason_living_abroad": {
        "column_name": "What is your main reason for living abroad?",
        "options": [
            "Studying",
            "Working",
        ],
        "description": "Main reason for living abroad"
    },
    "religion": {
        "column_name": "What is your religion?",
        "options": [
            "No religion",
            "Taoism/Chinese Traditional Beliefs",
            "Islam",
            "Hinduism",
            "Sikhism",
            "Christianity",
        ],
        "description": "Religion"
    },
    "reason_for_internship": {
        "column_name": "What was the main reason you were in a paid internship, traineeship, or apprenticeship?",
        "options": [
            "It was my only job option available",
            "To gain exposure/experience",
            "It is required as part of practical training towards formal professional roles or accreditation",
            "I wanted to switch to a new industry or field and took up this internship/traineeship/apprenticeship to explore its suitability",
            "I was unable to secure a full-time role in this same industry or field",
            "I was unable to secure a full-time role in another industry or field I was interested in",
        ],
        "description": "Main reason for internship/traineeship/apprenticeship"
    },
    "sets_price_for_goods_services": {
        "column_name": "Do you usually set the price for the goods or services you provide in this job?",
        "options": [
            "Yes",
            "No, prices are usually negotiated with my clients",
            "No, prices are usually set by my clients",
            "No, prices are set by a third party (e.g., intermediary/ agency)",
            "No, prices are set to a market rate",
        ],
        "description": "Whether respondent sets price for goods/services"
    },
    "reasons_self_employed": {
        "column_name": "What were your reason(s) for being self-employed?",
        "options": [
            "Income is higher as compared to working as an employee in a similar job",
            "Income is higher as compared to working as an employee in a non-similar job",
            "Gain work experience",
            "Facilitate a career transition to a new job/industry",
            "Pursue my passion or interest",
            "The work is meaningful",
        ],
        "description": "Reasons for being self-employed"
    },
    "freelance_platforms": {
        "column_name": "Did you perform any freelance or assignment-based work via any of the following online platform(s) in the last 12 months?",
        "options": [
            "Ride-hailing platforms (e.g. Grab Driver, GoPartner, Ryde Driver, TADA Driver)",
            "Food-delivery platforms (e.g. Deliveroo Rider, Foodpanda Rider, Grab Driver, Lalamove Delivery Partner)",
            "Online freelance platforms (e.g. Fiverr, Upwork, TaskRabbit)",
            "Social media platforms (e.g. Facebook Shop, Instagram)",
            "Online advertisements / marketplaces / e-Commerce websites (e.g. Carousell, Lazada, Shopee)",
            "Own website (e.g. blog, registered domain)",
            "I did not take up freelance or assignment-based work through online platforms in the last 12 months",
        ],
        "description": "Freelance/assignment-based work platforms"
    },
    "job_accommodations": {
        "column_name": "Does your current job accommodate the working arrangements you need (e.g. shorter working hours, provision of flexible work arrangements)?",
        "options": [
            "Shorter working hours",
            "Flexible work schedule (e.g. ability to work from home, flexible start/end times)",
            "Equipment and technology provision (Screen readers, ergonomic keyboards, specialised telephone etc)",
            "Working location near home",
            "Customised transport to/from the workplace",
            "Structured and routine nature of work",
        ],
        "description": "Job accommodations for working arrangements"
    },
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


def _word_count(text: str) -> int:
    """
    Count the number of words in the text.
    
    Args:
        text: The text to count words in
    
    Returns:
        Number of words
    """
    if not text:
        return 0
    return len(text.split())


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
    
    # No match - count words in the extracted answer (excluding "Others:")
    word_count = _word_count(extracted)
    
    # Only add RSPD confirmation if word count is less than minimum
    if word_count < min_words:
        confirmation_sentence = "The RSPD confirms that the following answer is correct as of this time; "
        corrected_value = f"Others: {confirmation_sentence}{extracted}"
        
        return ValidationResult(
            is_valid=True,
            message=f"Others answer approved with RSPD confirmation (original word count: {word_count}, now meets minimum requirement)",
            original_value=answer,
            corrected_value=corrected_value,
            rule_applied="RULE 1 - RSPD confirmation added"
        )
    else:
        # Word count is sufficient - no change needed
        return ValidationResult(
            is_valid=True,
            message=f"Others answer has sufficient word count ({word_count} words >= {min_words})",
            original_value=answer,
            corrected_value=None,
            rule_applied="RULE 1 - No change needed"
        )
