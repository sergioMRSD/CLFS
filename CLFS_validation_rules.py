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


# Education validation rules (qualification vs place)
QUALIFICATION_PLACE_RULES = [
    {
        "rule_id": "QPS01",
        "qualification_values": ["Polytechnic Diploma"],
        "place_values": [
            "National University of Singapore",
            "Nanyang Technological University",
            "National Institute of Education",
            "Singapore Management University",
            "Singapore University of Technology and Design",
            "Singapore Institute of Technology",
            "Singapore University of Social Sciences (SUSS)",
        ],
        "severity": "FLAG",
        "reason": "Local universities do not award polytechnic diplomas; diplomas are awarded by polytechnics.",
        "action": "flag_for_review",
        "highlight_cells": [
            "Highest Academic Qualification",
            "Place of study for your Highest Academic Attained in?",
        ],
    },
    {
        "rule_id": "QPS02",
        "qualification_values": [
            "First Degree or equivalent",
            "Long First Degree or equivalent",
        ],
        "place_values": ["Institute of Technical Education"],
        "severity": "FLAG",
        "reason": "ITE does not award bachelor's degrees; degrees are typically awarded by universities.",
        "action": "flag_for_review",
        "highlight_cells": [
            "Highest Academic Qualification",
            "Place of study for your Highest Academic Attained in?",
        ],
    },
    {
        "rule_id": "QPS03",
        "qualification_values": ["At least 1 subject pass in GCE 'A'/'H2' Level or equivalent"],
        "place_values": [
            "National University of Singapore",
            "Nanyang Technological University",
            "National Institute of Education",
            "Singapore Management University",
            "Singapore University of Technology and Design",
            "Singapore Institute of Technology",
            "Singapore University of Social Sciences (SUSS)",
        ],
        "severity": "FLAG",
        "reason": "GCE A Levels are pre-university qualifications and are not obtained from universities.",
        "action": "flag_for_review",
        "highlight_cells": [
            "Highest Academic Qualification",
            "Place of study for your Highest Academic Attained in?",
        ],
    },
    {
        "rule_id": "QPS04",
        "qualification_values": ["Doctoral Degree or equivalent"],
        "place_values": ["Local Polytechnics", "Institute of Technical Education"],
        "severity": "FLAG",
        "reason": "Polytechnics/ITE do not award doctoral degrees; doctorates are awarded by universities.",
        "action": "flag_for_review",
        "highlight_cells": [
            "Highest Academic Qualification",
            "Place of study for your Highest Academic Attained in?",
        ],
    },
    {
        "rule_id": "QPS05",
        "qualification_values": ["PSLE Certificate ot equivalent"],
        "place_values": [
            "National University of Singapore",
            "Nanyang Technological University",
            "National Institute of Education",
            "Singapore Management University",
            "Singapore University of Technology and Design",
            "Singapore Institute of Technology",
            "Singapore University of Social Sciences (SUSS)",
        ],
        "severity": "FLAG",
        "reason": "PSLE is a primary-school level certification and is not obtained from universities.",
        "action": "flag_for_review",
        "highlight_cells": [
            "Highest Academic Qualification",
            "Place of study for your Highest Academic Attained in?",
        ],
    },
    {
        "rule_id": "QPS06",
        "qualification_values": ["Polytechnic Diploma"],
        "place_values": ["Outside of Singapore"],
        "severity": "REVIEW",
        "reason": "“Polytechnic Diploma” is Singapore-specific wording; overseas diploma may need equivalency confirmation.",
        "action": "flag_for_review",
        "highlight_cells": [
            "Highest Academic Qualification",
            "Place of study for your Highest Academic Attained in?",
        ],
    },
    {
        "rule_id": "QPS07",
        "qualification_values": ["Higher Nitec or equivalent"],
        "place_values": [
            "National University of Singapore",
            "Nanyang Technological University",
            "National Institute of Education",
            "Singapore Management University",
            "Singapore University of Technology and Design",
            "Singapore Institute of Technology",
            "Singapore University of Social Sciences (SUSS)",
        ],
        "severity": "FLAG",
        "reason": "Higher Nitec is awarded by ITE, not by universities.",
        "action": "flag_for_review",
        "highlight_cells": [
            "Highest Academic Qualification",
            "Place of study for your Highest Academic Attained in?",
        ],
    },
    {
        "rule_id": "QPS08",
        "qualification_values": ["Postgraduate Diploma", "Master's Degree or equivalent"],
        "place_values": ["Local Polytechnics", "Institute of Technical Education"],
        "severity": "FLAG",
        "reason": "Postgraduate qualifications are typically offered by universities, not by polytechnics or ITE.",
        "action": "flag_for_review",
        "highlight_cells": [
            "Highest Academic Qualification",
            "Place of study for your Highest Academic Attained in?",
        ],
    },
]


# SSEC mapping candidates: list of (code, description)
SSEC_CANDIDATES: list[tuple[str, str]] = [
    ('0', 'PRE-PRIMARY'),
    ('00', 'Pre-Primary (i.e. Nursery, Kindergarten 1, Kindergarten 2)'),
    ('1', 'PRIMARY'),
    ('11', 'Primary 1'),
    ('12', 'Primary 2'),
    ('13', 'Primary 3'),
    ('14', 'Primary 4'),
    ('15', 'Primary 5'),
    ('16', 'Primary 6'),
    ('19', 'Other primary education or equivalent'),
    ('2', 'SECONDARY'),
    ('21', 'Secondary 1'),
    ('22', 'Secondary 2'),
    ('23', 'Secondary 3'),
    ('24', 'Secondary 4'),
    ('25', 'Secondary 5'),
    ('26', 'ITE Skills Certificate (ISC)'),
    ('27', 'Other secondary education or equivalent'),
    ('28', 'Other skills certificate courses or equivalent (except ISC)'),
    ('3', 'POST-SECONDARY (NON-TERTIARY): GENERAL AND VOCATIONAL'),
    ('31', 'Pre-University 1 / Junior College 1 (general) (including Year 5 of Integrated Programme)'),
    ('32', 'Pre-University 2 / Junior College 2 (general) (including Year 6 of Integrated Programme)'),
    ('33', 'Pre-University 3 (general)'),
    ('34', 'National ITE Certificate (Nitec)'),
    ('35', 'Higher Nitec'),
    ('36', 'Master Nitec'),
    ('37', 'Other post-secondary (non-tertiary; general) education or equivalent'),
    ('38', 'Other post-secondary (non-tertiary; vocational) education or equivalent (including advanced certificate courses)'),
    ('4', 'POLYTECHNIC DIPLOMA'),
    ('41', 'Polytechnic diploma'),
    ('42', 'Polytechnic post-diploma (including polytechnic advanced/specialist diploma, diploma (conversion))'),
    ('5', 'PROFESSIONAL QUALIFICATION AND OTHER DIPLOMA'),
    ('51', 'ITE diploma'),
    ('52', 'Other locally or externally developed diploma (including NIE diploma, SIM diploma, LASALLE diploma, NAFA diploma)'),
    ('53', 'Qualification awarded by professional bodies (including ACCA, CFA)'),
    ('59', 'Other post-diploma qualifications or equivalent'),
    ('6', "BACHELOR'S OR EQUIVALENT"),
    ('61', 'First degree or equivalent'),
    ('62', 'Long first degree or equivalent'),
    ('7', "POSTGRADUATE DIPLOMA/CERTIFICATE (EXCLUDING MASTER'S AND DOCTORATE)"),
    ('70', 'Postgraduate diploma/certificate (including NIE postgraduate diploma)'),
    ('8', "MASTER'S AND DOCTORATE OR EQUIVALENT"),
    ('81', "Master's degree or equivalent"),
    ('82', 'Doctoral degree or equivalent'),
    ('X', 'NOT REPORTED'),
    ('XX', 'Not reported'),
    ('0', 'NO FORMAL QUALIFICATION / PRE-PRIMARY / LOWER PRIMARY'),
    ('01', 'Never attended school'),
    ('02', 'Pre-Primary (i.e. Nursery, Kindergarten 1, Kindergarten 2)'),
    ('03', 'Primary education without Primary School Leaving Examination (PSLE) / Primary School Proficiency Examination (PSPE) certificate or equivalent'),
    ('04', 'Certificate in BEST 1-3'),
    ('11', 'Primary School Leaving Examination (PSLE) / Primary School Proficiency Examination (PSPE) certificate or equivalent'),
    ('12', 'Certificate in BEST 4'),
    ('13', 'At least 3 achievements for different Workplace Literacy or Numeracy (WPLN) skills at Level 1 or 2'),
    ('2', 'LOWER SECONDARY'),
    ('21', "Secondary education without any subject pass at GCE 'O'/'N' Level or equivalent"),
    ('22', 'Certificate in WISE 1-3'),
    ('23', 'Basic vocational certificate (including ITE Basic Vocational Training)'),
    ('24', 'At least 3 achievements for different Workplace Literacy or Numeracy (WPLN) skills at Level 3 or 4'),
    ('3', 'SECONDARY'),
    ('31', "At least 1 subject pass at GCE 'N' Level"),
    ('32', "At least 1 subject pass at GCE 'O' Level"),
    ('33', 'National ITE Certificate (Intermediate) or equivalent (including National Technical Certificate (NTC) Grade 3, Certificate of Vocational Training, BCA Builder Certificate)'),
    ('34', 'ITE Skills Certificate (ISC) or equivalent (including Certificate of Competency, Certificate in Service Skills)'),
    ('35', 'At least 3 achievements for different Workplace Literacy or Numeracy (WPLN) skills at Level 5 and above'),
    ('39', 'Other secondary education/certificates or equivalent'),
    ('4', 'POST-SECONDARY (NON-TERTIARY): GENERAL AND VOCATIONAL'),
    ('41', "At least 1 subject pass at GCE 'A'/'H2' Level or equivalent (general)"),
    ('42', 'National ITE Certificate (Nitec) or equivalent (including Post Nitec Certificate, Specialist Nitec, Certificate in Office Skills, National Technical Certificate (NTC) Grade 2, National Certificate in Nursing, BCA Advanced Builder Certificate)'),
    ('43', 'Higher Nitec or equivalent (including Certificate in Business Skills, Industrial Technician Certificate)'),
    ('44', 'Master Nitec or equivalent (including NTC Grade 1)'),
    ('45', 'WSQ Certificate or equivalent'),
    ('46', 'WSQ Higher Certificate or equivalent'),
    ('47', 'WSQ Advanced Certificate or equivalent'),
    ('48', 'Other post-secondary (non-tertiary; general) qualifications or equivalent (including International Baccalaureate / NUS High School Diploma)'),
    ('49', 'Other post-secondary (non-tertiary; vocational) certificates/qualifications or equivalent (including SIM certificate)'),
    ('5', 'POLYTECHNIC DIPLOMA'),
    ('51', 'Polytechnic diploma'),
    ('52', 'Polytechnic post-diploma (including polytechnic advanced/specialist/management/graduate diploma, diploma (conversion))'),
    ('6', 'PROFESSIONAL QUALIFICATION AND OTHER DIPLOMA'),
    ('61', 'ITE diploma'),
    ('62', 'Other locally or externally developed diploma (including NIE diploma, SIM diploma, LASALLE diploma, NAFA diploma)'),
    ('63', 'Qualification awarded by professional bodies (including ACCA, CFA)'),
    ('64', 'WSQ diploma'),
    ('65', 'WSQ specialist diploma'),
    ('69', 'Other post-diploma qualifications or equivalent'),
    ('7', "BACHELOR'S OR EQUIVALENT"),
    ('71', 'First degree or equivalent'),
    ('72', 'Long first degree or equivalent'),
    ('8', "POSTGRADUATE DIPLOMA/CERTIFICATE (EXCLUDING MASTER'S AND DOCTORATE)"),
    ('81', 'Postgraduate diploma/certificate (including NIE postgraduate diploma)'),
    ('82', 'WSQ graduate certificate'),
    ('83', 'WSQ graduate diploma'),
    ('9', "MASTER'S AND DOCTORATE OR EQUIVALENT"),
    ('91', "Master's degree or equivalent"),
    ('92', 'Doctoral degree or equivalent'),
    ('N', 'MODULAR CERTIFICATION (NON-AWARD COURSES / NON-FULL QUALIFICATIONS)'),
    ('N1', 'At least 1 WSQ Statement of Attainment or ITE modular certificate at post-secondary level (non-tertiary) or equivalent'),
    ('N2', 'At least 1 WSQ Statement of Attainment or other modular certificate at diploma level or equivalent (including polytechnic post-diploma certificate)'),
    ('N3', 'At least 1 WSQ Statement of Attainment or other modular certificate at degree level or equivalent'),
    ('N4', 'At least 1 WSQ Statement of Attainment or other modular certificate at postgraduate level or equivalent'),
    ('N9', 'Other statements of attainment, modular certificates or equivalent'),
    ('01', 'EDUCATION'),
    ('011', 'TEACHER TRAINING'),
    ('012', 'EDUCATION SCIENCE'),
    ('013', 'TRAINER TRAINING'),
    ('02', 'FINE AND APPLIED ARTS'),
    ('021', 'FINE AND PERFORMING ARTS'),
    ('022', '3D DESIGN'),
    ('023', 'MEDIA DESIGN/PRODUCTION'),
    ('029', 'FINE AND APPLIED ARTS NOT ELSEWHERE CLASSIFIED'),
    ('03', 'HUMANITIES AND SOCIAL SCIENCES'),
    ('031', 'LANGUAGE AND CULTURAL STUDIES'),
    ('032', 'BEHAVIOURAL SCIENCE'),
    ('033', 'ECONOMICS'),
    ('034', 'SOCIAL WORK'),
    ('039', 'HUMANITIES AND SOCIAL SCIENCES NOT ELSEWHERE CLASSIFIED'),
    ('04', 'MASS COMMUNICATION AND INFORMATION SCIENCE'),
    ('041', 'MASS COMMUNICATION'),
    ('042', 'INFORMATION SCIENCE'),
    ('05', 'BUSINESS AND ADMINISTRATION'),
    ('051', 'ADMINISTRATION AND MANAGEMENT'),
    ('052', 'ACCOUNTANCY'),
    ('053', 'BANKING, INSURANCE AND FINANCIAL SERVICES'),
    ('054', 'SALES AND MARKETING'),
    ('055', 'MANAGEMENT SUPPORT SERVICES'),
    ('059', 'BUSINESS AND ADMINISTRATION NOT ELSEWHERE CLASSIFIED'),
    ('06', 'LAW'),
    ('060', 'LAW'),
    ('07', 'NATURAL AND MATHEMATICAL SCIENCES'),
    ('071', 'BIOLOGICAL SCIENCES AND TECHNOLOGIES'),
    ('072', 'PHYSICAL SCIENCES AND TECHNOLOGIES'),
    ('073', 'AGRICULTURE AND FISHERY'),
    ('074', 'VETERINARY SCIENCES'),
    ('075', 'MATHEMATICS AND STATISTICS'),
    ('079', 'NATURAL AND MATHEMATICAL SCIENCES NOT ELSEWHERE CLASSIFIED'),
    ('08', 'HEALTH SCIENCES'),
    ('081', 'GENERAL MEDICAL SCIENCES'),
    ('082', 'SPECIALISED MEDICAL SCIENCES'),
    ('083', 'DENTISTRY'),
    ('084', 'NURSING AND HEALTH CARE'),
    ('085', 'PHARMACY'),
    ('086', 'THERAPY AND REHABILITATION'),
    ('087', 'MEDICAL DIAGNOSTIC AND TREATMENT TECHNOLOGY'),
    ('089', 'HEALTH SCIENCES NOT ELSEWHERE CLASSIFIED'),
    ('09', 'INFORMATION TECHNOLOGY'),
    ('091', 'INFORMATION TECHNOLOGY'),
    ('092', 'COMPUTER OPERATIONS/TECHNICAL SUPPORT'),
    ('10', 'ARCHITECTURE, BUILDING AND REAL ESTATE'),
    ('101', 'ARCHITECTURE AND URBAN PLANNING'),
    ('102', 'SURVEYING'),
    ('103', 'BUILDING SCIENCE AND MANAGEMENT'),
    ('104', 'BUILDING TRADES'),
    ('109', 'ARCHITECTURE, BUILDING AND REAL ESTATE NOT ELSEWHERE CLASSIFIED'),
    ('11', 'ENGINEERING SCIENCES'),
    ('111', 'CHEMICAL ENGINEERING'),
    ('112', 'CIVIL ENGINEERING'),
    ('113', 'ELECTRICAL AND ELECTRONICS ENGINEERING'),
    ('114', 'MECHANICAL ENGINEERING'),
    ('115', 'MARINE ENGINEERING'),
    ('116', 'MANUFACTURING AND RELATED ENGINEERING'),
    ('119', 'ENGINEERING SCIENCES NOT ELSEWHERE CLASSIFIED'),
    ('12', 'ENGINEERING, MANUFACTURING AND RELATED TRADES'),
    ('121', 'ENGINEERING TRADES'),
    ('122', 'MANUFACTURING TRADES'),
    ('129', 'ENGINEERING, MANUFACTURING AND RELATED TRADES NOT ELSEWHERE CLASSIFIED'),
    ('13', 'SERVICES'),
    ('131', 'PERSONAL SERVICES'),
    ('132', 'FOOD SERVICES'),
    ('133', 'HOSPITALITY SERVICES'),
    ('134', 'TRANSPORT SERVICES'),
    ('135', 'SAFETY AND SECURITY SERVICES'),
    ('136', 'SPORTS AND RECREATION SERVICES'),
    ('99', 'OTHER FIELDS'),
    ('990', 'OTHER FIELDS NOT ELSEWHERE CLASSIFIED'),
    ('XX', 'NOT REPORTED'),
    ('XXX', 'NOT REPORTED'),
]


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


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    s = str(text).strip().lower()
    s = re.sub(r"[\-_/\\(),.;:]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _normalize_value(value: Optional[str]) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def best_ssec_match(qualification: str, threshold: int = 85) -> tuple[Optional[str], int]:
    qn = _normalize_text(qualification)
    if not qn or not SSEC_CANDIDATES:
        return None, 0

    best_code = None
    best_score = 0
    for code, desc in SSEC_CANDIDATES:
        dn = _normalize_text(desc)
        if not dn:
            continue
        if dn in qn or qn in dn:
            return code, 100
        import difflib
        score = int(difflib.SequenceMatcher(None, qn, dn).ratio() * 100)
        if score > best_score:
            best_code = code
            best_score = score

    if best_score >= threshold:
        return best_code, best_score
    return None, best_score


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


# RULE 2: Employment Start Age Validation
def validate_age_started_employment(value) -> ValidationResult:
    """
    RULE 2: Validate age when started employment.
    Must be a whole number between 13 and 100.

    Args:
        value: The age value to validate

    Returns:
        ValidationResult with validation status
    """
    original_str = str(value) if value is not None else ""

    if value is None or value == "":
        return ValidationResult(
            is_valid=True,
            message="No value provided",
            original_value=original_str
        )

    # Check if it's a valid integer
    if not isinstance(value, (int, float)):
        return ValidationResult(
            is_valid=False,
            message="Invalid age. Must be a whole number between 13 and 100.",
            original_value=original_str,
            rule_applied="RULE 2 - Age validation failed"
        )

    # Check if it's a whole number
    if isinstance(value, float) and not value.is_integer():
        return ValidationResult(
            is_valid=False,
            message="Invalid age. Must be a whole number between 13 and 100.",
            original_value=original_str,
            rule_applied="RULE 2 - Age validation failed"
        )

    age = int(value)

    # Check range
    if age < 13 or age > 100:
        return ValidationResult(
            is_valid=False,
            message="Invalid age. Must be a whole number between 13 and 100.",
            original_value=original_str,
            rule_applied="RULE 2 - Age validation failed"
        )

    return ValidationResult(
        is_valid=True,
        message="Valid age",
        original_value=original_str,
        rule_applied="RULE 2 - Age validation passed"
    )


# RULE 3: Bonus Validation
def validate_bonus(value) -> ValidationResult:
    """
    RULE 3: Validate bonus amount.
    Must be numeric between 0 and 99, no commas or minus signs.

    Args:
        value: The bonus value to validate

    Returns:
        ValidationResult with validation status
    """
    original_str = str(value) if value is not None else ""

    if value is None or value == "":
        return ValidationResult(
            is_valid=True,
            message="No value provided",
            original_value=original_str
        )

    # Convert to string to check for invalid characters
    if isinstance(value, str):
        if "," in value or "-" in value:
            return ValidationResult(
                is_valid=False,
                message="Invalid bonus. Must be numeric between 0 and 99, no commas or minus signs.",
                original_value=original_str,
                rule_applied="RULE 3 - Bonus validation failed"
            )
        try:
            numeric_value = float(value)
        except ValueError:
            return ValidationResult(
                is_valid=False,
                message="Invalid bonus. Must be numeric between 0 and 99, no commas or minus signs.",
                original_value=original_str,
                rule_applied="RULE 3 - Bonus validation failed"
            )
    elif isinstance(value, (int, float)):
        numeric_value = float(value)
    else:
        return ValidationResult(
            is_valid=False,
            message="Invalid bonus. Must be numeric between 0 and 99, no commas or minus signs.",
            original_value=original_str,
            rule_applied="RULE 3 - Bonus validation failed"
        )

    # Check range
    if numeric_value < 0 or numeric_value > 99:
        return ValidationResult(
            is_valid=False,
            message="Invalid bonus. Must be numeric between 0 and 99, no commas or minus signs.",
            original_value=original_str,
            rule_applied="RULE 3 - Bonus validation failed"
        )

    return ValidationResult(
        is_valid=True,
        message="Valid bonus",
        original_value=original_str,
        rule_applied="RULE 3 - Bonus validation passed"
    )


# RULE 4: Previous Company Name Validation
def validate_previous_company_name(value) -> ValidationResult:
    """
    RULE 4: Validate previous company/establishment name.
    Must contain at least 3 letters and not be purely numeric.

    Args:
        value: The company name to validate

    Returns:
        ValidationResult with validation status
    """
    original_str = str(value) if value is not None else ""

    if value is None or value == "":
        return ValidationResult(
            is_valid=True,
            message="No value provided",
            original_value=original_str
        )

    # Convert to string
    if not isinstance(value, str):
        value = str(value)

    # Count letters
    letters = re.findall(r"[A-Za-z]", value)
    if len(letters) < 3:
        return ValidationResult(
            is_valid=False,
            message="Invalid company name. Must contain at least 3 letters and not be purely numeric.",
            original_value=original_str,
            rule_applied="RULE 4 - Company name validation failed"
        )

    # Check if purely numeric (after removing spaces)
    numeric_only = value.replace(" ", "").isdigit()
    if numeric_only:
        return ValidationResult(
            is_valid=False,
            message="Invalid company name. Must contain at least 3 letters and not be purely numeric.",
            original_value=original_str,
            rule_applied="RULE 4 - Company name validation failed"
        )

    return ValidationResult(
        is_valid=True,
        message="Valid company name",
        original_value=original_str,
        rule_applied="RULE 4 - Company name validation passed"
    )


# RULE 5: Interest from Savings Validation
def validate_interest_from_savings(value) -> ValidationResult:
    """
    RULE 5: Validate interest from savings.
    Must be numeric between 0 and 10 (decimals allowed).

    Args:
        value: The interest value to validate

    Returns:
        ValidationResult with validation status
    """
    original_str = str(value) if value is not None else ""

    if value is None or value == "":
        return ValidationResult(
            is_valid=True,
            message="No value provided",
            original_value=original_str
        )

    try:
        numeric_value = float(value)
    except (ValueError, TypeError):
        return ValidationResult(
            is_valid=False,
            message="Invalid interest. Must be numeric between 0 and 10 (decimals allowed).",
            original_value=original_str,
            rule_applied="RULE 5 - Interest validation failed"
        )

    if numeric_value < 0 or numeric_value > 10:
        return ValidationResult(
            is_valid=False,
            message="Invalid interest. Must be numeric between 0 and 10 (decimals allowed).",
            original_value=original_str,
            rule_applied="RULE 5 - Interest validation failed"
        )

    return ValidationResult(
        is_valid=True,
        message="Valid interest",
        original_value=original_str,
        rule_applied="RULE 5 - Interest validation passed"
    )


# RULE 6: Dividends/Investment Interest Validation
def validate_dividends_investment_interest(value) -> ValidationResult:
    """
    RULE 6: Validate dividends and interests from investments.
    Must be numeric between 0 and 50 (decimals allowed).

    Args:
        value: The dividends/interest value to validate

    Returns:
        ValidationResult with validation status
    """
    original_str = str(value) if value is not None else ""

    if value is None or value == "":
        return ValidationResult(
            is_valid=True,
            message="No value provided",
            original_value=original_str
        )

    try:
        numeric_value = float(value)
    except (ValueError, TypeError):
        return ValidationResult(
            is_valid=False,
            message="Invalid dividends/other investment interest. Must be numeric between 0 and 50 (decimals allowed).",
            original_value=original_str,
            rule_applied="RULE 6 - Dividends validation failed"
        )

    if numeric_value < 0 or numeric_value > 50:
        return ValidationResult(
            is_valid=False,
            message="Invalid dividends/other investment interest. Must be numeric between 0 and 50 (decimals allowed).",
            original_value=original_str,
            rule_applied="RULE 6 - Dividends validation failed"
        )

    return ValidationResult(
        is_valid=True,
        message="Valid dividends/investment interest",
        original_value=original_str,
        rule_applied="RULE 6 - Dividends validation passed"
    )


# RULE 7: Freelance Work vs Own Account Worker Consistency
def validate_freelance_employment_consistency(
    employment_status: str,
    freelance_platforms: str
) -> ValidationResult:
    """
    RULE 7: Validate consistency between freelance work and employment status.
    If respondent did freelance work (not "I did not take up..."),
    employment status must be "Own Account Worker".

    Args:
        employment_status: Employment status value
        freelance_platforms: Freelance platforms value

    Returns:
        ValidationResult with validation status
    """
    if not freelance_platforms or freelance_platforms == "":
        return ValidationResult(
            is_valid=True,
            message="No freelance data provided",
            original_value=freelance_platforms or ""
        )

    freelance_str = str(freelance_platforms).strip()
    employment_str = str(employment_status).strip() if employment_status else ""

    # Check if they did NOT do freelance work
    no_freelance_option = "I did not take up freelance or assignment-based work through online platforms in the last 12 months"
    if freelance_str == no_freelance_option:
        return ValidationResult(
            is_valid=True,
            message="No freelance work - consistency check not applicable",
            original_value=freelance_str
        )

    # They did freelance work - check if employment status is Own Account Worker
    required_status = "Own Account Worker (Self-employed without paid employees)"
    if employment_str != required_status:
        return ValidationResult(
            is_valid=False,
            message="Mismatch: Freelance work selected but Employment Status is not Own Account Worker.",
            original_value=f"Employment: {employment_str}, Freelance: {freelance_str}",
            rule_applied="RULE 7 - Freelance/Employment consistency failed"
        )

    return ValidationResult(
        is_valid=True,
        message="Freelance work consistent with Own Account Worker status",
        original_value=f"Employment: {employment_str}, Freelance: {freelance_str}",
        rule_applied="RULE 7 - Freelance/Employment consistency passed"
    )


# RULE 8: Qualification vs Place of Study Validation
def validate_qualification_place(qualification: str, place: str) -> list[dict]:
    if not qualification or not place:
        return []

    qual_norm = str(qualification).strip().lower()
    place_norm = str(place).strip().lower()

    matches = []
    for rule in QUALIFICATION_PLACE_RULES:
        qual_values = [q.lower() for q in rule["qualification_values"]]
        place_values = [p.lower() for p in rule["place_values"]]
        if qual_norm in qual_values and place_norm in place_values:
            matches.append(rule)
    return matches


# RULE 9: SSEC mapping uses best_ssec_match (helper)


# RULE 10: Internship/Employment Type Validation
def validate_internship_employment_rule(internship_value: Optional[str], employment_value: Optional[str]) -> ValidationResult:
    """
    Rule 10:
    If internship/traineeship/apprenticeship == 'Yes'
    then Type of Employment must be 'Fixed-Term contract employee'.
    """
    internship = _normalize_value(internship_value)
    employment = _normalize_value(employment_value)

    if not internship or not employment:
        return ValidationResult(
            is_valid=True,
            message="No applicable values provided",
            original_value=""
        )

    if internship != "yes":
        return ValidationResult(
            is_valid=True,
            message="Internship not selected",
            original_value=internship
        )

    if employment in ("permanent employee", "casual/on-call employee"):
        return ValidationResult(
            is_valid=False,
            message="Internship/Traineeship/Apprenticeship must be Fixed-Term contract employee",
            original_value=employment,
            rule_applied="RULE 10"
        )

    return ValidationResult(
        is_valid=True,
        message="Internship employment type is valid",
        original_value=employment,
        rule_applied="RULE 10"
    )


# RULE 11: Job Title Validation
def validate_job_title_rule(job_title: Optional[str]) -> ValidationResult:
    """
    Rule 11:
    Job Title must be at least 4 letters and cannot contain numbers.
    """
    raw_value = _normalize_value(job_title)
    if not raw_value:
        return ValidationResult(
            is_valid=True,
            message="No job title provided",
            original_value=""
        )

    if len(raw_value) < 4 or any(char.isdigit() for char in raw_value):
        return ValidationResult(
            is_valid=False,
            message="Job Title must be at least 4 letters and contain no numbers",
            original_value=job_title or "",
            rule_applied="RULE 11"
        )

    return ValidationResult(
        is_valid=True,
        message="Job title is valid",
        original_value=job_title or "",
        rule_applied="RULE 11"
    )


# RULE 12: FT/PT column derived in validator


# RULE 13: Usual Hours Validation
def validate_usual_hours_value(hours_value: Optional[str]) -> ValidationResult:
    """
    Rule 13:
    Usual hours of work must be numeric when provided.
    """
    if hours_value in (None, ""):
        return ValidationResult(
            is_valid=True,
            message="No hours provided",
            original_value=""
        )

    try:
        float(hours_value)
        return ValidationResult(
            is_valid=True,
            message="Usual hours value is numeric",
            original_value=str(hours_value),
            rule_applied="RULE 13"
        )
    except (ValueError, TypeError):
        return ValidationResult(
            is_valid=False,
            message="Usual hours of work must be numeric",
            original_value=str(hours_value),
            rule_applied="RULE 13"
        )
