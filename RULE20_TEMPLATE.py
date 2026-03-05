# Insert into CLFS_validation_rules.py before RULE 4

def validate_usual_hours_limit(usual_hours) -> ValidationResult:
    """
    RULE 20 (Brandon's rule): Validate usual hours of work.
    Flags when usual hours exceed 60 hours per week.
    
    Args:
        usual_hours: Numeric hours per week value
        
    Returns:
        ValidationResult with is_valid=False if hours > 60
    """
    if usual_hours is None:
        return ValidationResult(
            is_valid=True,
            message="No usual hours provided",
            original_value="None",
            rule_applied="RULE 20 - Not applicable"
        )
    
    try:
        hours = float(usual_hours)
    except (ValueError, TypeError):
        return ValidationResult(
            is_valid=True,
            message="Invalid hours format - unable to validate",
            original_value=str(usual_hours),
            rule_applied="RULE 20 - Skipped"
        )
    
    if hours > 60:
        return ValidationResult(
            is_valid=False,
            message="Usual hours of work is more than 60 — Please justify",
            original_value=str(hours),
            rule_applied="RULE 20"
        )
    
    return ValidationResult(
        is_valid=True,
        message="Usual hours within acceptable range",
        original_value=str(hours),
        rule_applied="RULE 20 - Passed"
    )
