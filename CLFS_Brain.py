from dataclasses import dataclass
from typing import Optional, List, Tuple
import re


@dataclass
class ValidationResult:
    is_valid: bool
    message: str
    original_value: Optional[str] = None
    corrected_value: Optional[str] = None
    rule_applied: Optional[str] = None


# --- Helpers ---

def _normalize_text(text: Optional[str]) -> str:
    if text is None:
        return ""
    s = str(text).strip().lower()
    s = re.sub(r"[\-_/\\(),.;:]+", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _normalize_value(value: Optional[str]) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _to_number_nullable(v: Optional[object]) -> Optional[float]:
    """Safely convert various inputs to float; return None for None/empty or unparseable values."""
    try:
        if v is None:
            return None
        s = str(v).strip()
        if s == "":
            return None
        return float(s)
    except Exception:
        return None


def _word_count(text: Optional[str]) -> int:
    if not text:
        return 0
    return len(str(text).split())


def _fuzzy_match_option(user_answer: str, options: List[str]) -> Optional[str]:
    """Simple fuzzy fallback: look for token containment or startswith matches."""
    if not user_answer or not options:
        return None
    user_lower = user_answer.lower().strip()
    # direct containment
    for opt in options:
        if opt and opt.lower().strip() == user_lower:
            return opt
    # contains
    for opt in options:
        if opt and opt.lower().strip() in user_lower:
            return opt
    # startswith
    for opt in options:
        if user_lower.startswith(opt.lower().split()[0]):
            return opt
    return None


# -------------------
# Survey Rules
# -------------------

def validate_identification_type(value: Optional[str], allowed_options: Optional[List[str]] = None) -> ValidationResult:
    """Validate identification type.

    allowed_options: canonical list of allowed option strings (from answer.json). If provided,
    the function will try exact normalized match then fallback to fuzzy.
    """
    original = value or ""
    if value is None or str(value).strip() == "":
        return ValidationResult(is_valid=False, message="Identification Type missing", original_value=original, rule_applied='ID_TYP')

    v = str(value).strip()
    if allowed_options:
        v_norm = _normalize_text(v)
        opts_map = {_normalize_text(o): o for o in allowed_options if o}
        if v_norm in opts_map:
            matched = opts_map[v_norm]
            return ValidationResult(is_valid=True, message=f"Identification type matches option: '{matched}'", original_value=original, corrected_value=matched, rule_applied='ID_TYP')
        fuzzy = _fuzzy_match_option(v, allowed_options)
        if fuzzy:
            return ValidationResult(is_valid=True, message=f"Identification type fuzzy-matched to: '{fuzzy}'", original_value=original, corrected_value=fuzzy, rule_applied='ID_TYP - fuzzy match')
        expect_list = ", ".join((allowed_options[:10])) + ("..." if len(allowed_options) > 10 else "")
        return ValidationResult(is_valid=False, message=f"Unrecognised identification type. Expected one of: {expect_list}", original_value=original, rule_applied='ID_TYP')
    else:
        # No canonical options provided — do a best-effort check
        if len(v) < 2:
            return ValidationResult(is_valid=False, message="Identification Type appears too short", original_value=original, rule_applied='ID_TYP')
        return ValidationResult(is_valid=True, message="Identification Type present (no canonical options supplied)", original_value=original, rule_applied='ID_TYP')


def validate_residential_st(value: Optional[str]) -> ValidationResult:
    original = value or ""
    if value is None or str(value).strip() == "":
        return ValidationResult(is_valid=True, message="No residential status provided", original_value=original)
    v = str(value).strip()
    if v.lower() == 'institutional unit':
        return ValidationResult(is_valid=False, message="Respondent staying in institutional unit — interview should end", original_value=original, rule_applied='RESIDENTIAL_ST')
    return ValidationResult(is_valid=True, message="Residential status acceptable", original_value=original, rule_applied='RESIDENTIAL_ST')


def validate_h_sep_y(marital_status: Optional[str]) -> ValidationResult:
    original = marital_status or ""
    if marital_status is None or str(marital_status).strip() == "":
        return ValidationResult(is_valid=True, message="No marital status", original_value=original)
    v = str(marital_status).strip()
    if v.lower() == 'separated':
        return ValidationResult(is_valid=True, message="Respondent marked as Separated", original_value=original, rule_applied='H_SEP_Y')
    return ValidationResult(is_valid=True, message="Marital status ok", original_value=original, rule_applied='H_SEP_Y')


def validate_activity_status(value: Optional[str]) -> ValidationResult:
    original = value or ""
    if value is None or str(value).strip() == "":
        return ValidationResult(is_valid=False, message="Activity status missing", original_value=original)
    v = str(value).strip().lower()
    allowed = [
        'employed', 'employee', 'employer', 'own account worker', 'contributing family worker',
        'schooling', 'studying', 'working while schooling', 'not working', 'not in labour force'
    ]
    if any(a in v for a in allowed):
        return ValidationResult(is_valid=True, message="Activity status valid", original_value=original, rule_applied='ACTIVITY_ST')
    return ValidationResult(is_valid=False, message="Unrecognised activity status", original_value=original, rule_applied='ACTIVITY_ST')


def validate_i_l(value: Optional[str]) -> ValidationResult:
    original = value or ""
    if value is None or str(value).strip() == "":
        return ValidationResult(is_valid=True, message="No looking-for-job flag provided", original_value=original)
    v = str(value).strip().lower()
    if v in ('yes', 'no', 'y', 'n'):
        return ValidationResult(is_valid=True, message="Looking-for-job flag OK", original_value=original, rule_applied='I_L')
    return ValidationResult(is_valid=False, message="Looking-for-job flag must be Yes or No", original_value=original, rule_applied='I_L')


# -------------------
# Logic Rules
# -------------------

def validate_none_of_the_above_exclusive(answer: Optional[str], none_option_text: str = "None of the above") -> ValidationResult:
    if not answer:
        return ValidationResult(is_valid=True, message="No answer provided", original_value="")
    parts = [p.strip() for p in re.split(r"[;|,]", str(answer)) if p.strip()]
    if not parts:
        return ValidationResult(is_valid=True, message="No selection provided", original_value=answer)
    normalized = [p.lower() for p in parts]
    none_norm = none_option_text.strip().lower()
    if none_norm in normalized and len([p for p in normalized if p != none_norm]) > 0:
        return ValidationResult(is_valid=False, message="None-of-the-above selected together with other responses", original_value=answer, rule_applied='NONE_OF_THE_ABOVE_EXCLUSIVE')
    return ValidationResult(is_valid=True, message="None-of-the-above exclusivity passed", original_value=answer, rule_applied='NONE_OF_THE_ABOVE_EXCLUSIVE')



def validate_travel_time_format(value: Optional[str]) -> ValidationResult:
    original = "" if value is None else str(value).strip()
    if not original:
        return ValidationResult(is_valid=True, message="No travel time provided", original_value="")
    if re.fullmatch(r"0|[1-9]\d*", original):
        return ValidationResult(is_valid=True, message="Travel time format OK", original_value=original, rule_applied='RULE_36_TRAVEL_TIME')
    return ValidationResult(is_valid=False, message="Invalid travel time format (expect integer minutes, no symbols or leading zeros)", original_value=original, rule_applied='RULE_36_TRAVEL_TIME')


# -------------------
# Cross-Field Rules
# -------------------

def validate_years_in_employment_consistency(total_years: Optional[object], years_current: Optional[object], age: Optional[object], age_started_employment: Optional[object]) -> ValidationResult:
    orig = f"total={total_years}, current={years_current}, age={age}, started={age_started_employment}"

    def _to_float(v):
        try:
            if v is None or str(v).strip() == "":
                return None
            return float(v)
        except Exception:
            return None

    t = _to_float(total_years)
    c = _to_float(years_current)
    a = _to_float(age)
    s = _to_float(age_started_employment)

    if t is None or c is None:
        return ValidationResult(is_valid=True, message="Insufficient data for years-in-employment consistency check", original_value=orig)
    if t < c:
        return ValidationResult(is_valid=False, message="Total years in employment is less than years in current job", original_value=orig, rule_applied='RULE_37_YEARS')
    if a is not None and s is not None:
        implied = a - s
        if implied < 0:
            return ValidationResult(is_valid=False, message="Inconsistent ages: started employment after current age?", original_value=orig, rule_applied='RULE_37_YEARS')
        if t > implied + 1:
            return ValidationResult(is_valid=False, message="Total years in employment exceeds plausible maximum based on age and start age", original_value=orig, rule_applied='RULE_37_YEARS')
    return ValidationResult(is_valid=True, message="Years in employment consistent", original_value=orig, rule_applied='RULE_37_YEARS')

def validate_num_children(num_children: Optional[object], age: Optional[object]) -> ValidationResult:
    orig = f"children={num_children}, age={age}"
    # use safe numeric conversion helper
    try:
        nc_f = _to_number_nullable(num_children)
        nc = None if nc_f is None else int(nc_f)
    except Exception:
        return ValidationResult(is_valid=False, message="Invalid number of children (not numeric)", original_value=orig, rule_applied='RULE_20_NUM_CHILDREN')
    try:
        a_f = _to_number_nullable(age)
        a = None if a_f is None else int(a_f)
    except Exception:
        a = None
    if nc is None:
        return ValidationResult(is_valid=True, message="No number-of-children provided", original_value=orig)
    if a is None:
        return ValidationResult(is_valid=True, message="Age unknown; cannot validate children count", original_value=orig)
    if a < 12 and nc > 0:
        return ValidationResult(is_valid=False, message="Impossible: respondent age < 12 but reported children > 0", original_value=orig, rule_applied='RULE_20_NUM_CHILDREN')
    if a < 15 and nc > 0:
        return ValidationResult(is_valid=False, message="Unusual: respondent age < 15 but reported children > 0; verify responses", original_value=orig, rule_applied='RULE_20_NUM_CHILDREN')
    return ValidationResult(is_valid=True, message="Number of children plausible", original_value=orig, rule_applied='RULE_20_NUM_CHILDREN')





# -------------------
# Financial Rules
# -------------------

def validate_oaw_income_threshold(employment_status: Optional[str], monthly_income: Optional[object]) -> ValidationResult:
    orig = f"emp={employment_status}, income={monthly_income}"
    emp = str(employment_status or "").lower()
    is_oaw = any(k in emp for k in ["own account", "own-account", "own account worker", "self-employed", "running own business"]) 
    income = _to_number_nullable(monthly_income)
    if not is_oaw:
        return ValidationResult(is_valid=True, message="Not an Own Account Worker; rule not applicable", original_value=orig, rule_applied='RULE_34_OAW_INCOME')
    if income is None:
        return ValidationResult(is_valid=True, message="No income provided; cannot validate OAW threshold", original_value=orig, rule_applied='RULE_34_OAW_INCOME')
    if income < 200:
        return ValidationResult(is_valid=False, message="Own Account Worker reports monthly income < $200; confirm with interviewer", original_value=orig, rule_applied='RULE_34_OAW_INCOME')
    return ValidationResult(is_valid=True, message="OAW income above threshold", original_value=orig, rule_applied='RULE_34_OAW_INCOME')


# End of CLFS_Brain.py


# --- Additional Top-20 validators (next 15) ---
def validate_occupation_details(employment_status: Optional[str], e_occ: Optional[str], w_desc: Optional[str]) -> ValidationResult:
    """If employed, ensure occupation code/description are present."""
    orig = f"emp={employment_status}, e_occ={e_occ}, w_desc={w_desc}"
    emp = str(employment_status or "").lower()
    is_employed = any(k in emp for k in ["employ", "working", "employee", "self-employed", "own account"]) or emp in ("employed", "w")
    if not is_employed:
        return ValidationResult(is_valid=True, message="Not employed; occupation details not applicable", original_value=orig)
    # If employed, require either occupation code or work description
    if (e_occ is None or str(e_occ).strip() == "") and (w_desc is None or str(w_desc).strip() == ""):
        return ValidationResult(is_valid=False, message="Employed but occupation code/description missing", original_value=orig, rule_applied='E_OCC_W_DESC')
    return ValidationResult(is_valid=True, message="Occupation details present", original_value=orig, rule_applied='E_OCC_W_DESC')


def validate_employment_consistency(emp_flag: Optional[str], e_empst: Optional[str], empst: Optional[str], labour_force_status: Optional[str]) -> ValidationResult:
    """Cross-check employment flags/status values for major inconsistencies."""
    orig = f"emp_flag={emp_flag}, e_empst={e_empst}, empst={empst}, labour={labour_force_status}"
    lf = str(labour_force_status or "").lower()
    indicates_working = any(k in lf for k in ["employ", "working", "employee", "own account", "oaw"]) 
    # emp_flag may be textual like 'Yes' for employed indicator
    empf = str(emp_flag or "").lower()
    # If labour indicates working but emp_flag suggests not employed => inconsistent
    if indicates_working and empf in ("no", "n", "not employed", "none", ""):
        return ValidationResult(is_valid=False, message="Labour force status indicates working but employment flag/state indicates not employed", original_value=orig, rule_applied='EMP_CONSISTENCY')
    # If labour indicates not working but emp_flag or empst indicates employed => inconsistent
    if (not indicates_working) and (empf in ("yes", "y", "employed") or (empst and 'employ' in str(empst).lower()) or (e_empst and 'employ' in str(e_empst).lower())):
        return ValidationResult(is_valid=False, message="Labour force status indicates not working but employment fields indicate employed", original_value=orig, rule_applied='EMP_CONSISTENCY')
    return ValidationResult(is_valid=True, message="Employment consistency checks passed", original_value=orig, rule_applied='EMP_CONSISTENCY')


def validate_seeking_work_logic(u_l: Optional[str], u_w: Optional[str], i_w: Optional[str], e_w: Optional[str]) -> ValidationResult:
    """Validate job-seeking and availability logic (U_L, U_W, I_W, E_W are various availability/seeking flags)."""
    orig = f"U_L={u_l}, U_W={u_w}, I_W={i_w}, E_W={e_w}"
    # Normalize yes/no
    def yn(x):
        if x is None:
            return None
        t = str(x).strip().lower()
        if t in ('yes','y','1','true'):
            return True
        if t in ('no','n','0','false'):
            return False
        return None

    ul = yn(u_l)
    uw = yn(u_w)
    iw = yn(i_w)
    ew = yn(e_w)

    # Basic contradictions: actively looking but not available
    if ul is True and uw is False:
        return ValidationResult(is_valid=False, message="Actively looking for work but not available to start/accept work", original_value=orig, rule_applied='SEEKING_LOGIC')
    # If available but not looking and explicitly indicated unavailable elsewhere, flag
    if uw is True and ul is False and iw is True:
        return ValidationResult(is_valid=False, message="Marked available but indicates other unavailability flags; inconsistent job-seeking info", original_value=orig, rule_applied='SEEKING_LOGIC')
    # If any of the flags are non-boolean/uninterpretable, mark as review
    if any(v is None for v in (ul, uw, iw, ew)):
        # Not necessarily invalid, just mark as needs review
        return ValidationResult(is_valid=True, message="Seeking/availability info partially missing or ambiguous; manual review recommended", original_value=orig, rule_applied='SEEKING_LOGIC')

    return ValidationResult(is_valid=True, message="Job-seeking and availability logic consistent", original_value=orig, rule_applied='SEEKING_LOGIC')



def validate_duration_numeric(duration: Optional[object]) -> ValidationResult:
    """Ensure duration fields (_DUR) are numeric and within reasonable bounds (0-200 years or 0-2400 months)."""
    original = "" if duration is None else str(duration).strip()
    if not original:
        return ValidationResult(is_valid=True, message="No duration provided", original_value="")
    # Extract a number
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", original)
    if not m:
        return ValidationResult(is_valid=False, message="Duration does not contain a numeric value", original_value=original, rule_applied='DURATION_NUM')
    try:
        num = float(m.group(1))
    except Exception:
        return ValidationResult(is_valid=False, message="Unable to parse duration numeric value", original_value=original, rule_applied='DURATION_NUM')
    # Heuristic: if the text mentions 'month' treat differently (months allowed up to 2400)
    if 'month' in original.lower():
        if num < 0 or num > 2400:
            return ValidationResult(is_valid=False, message="Duration in months out of expected bounds", original_value=original, rule_applied='DURATION_NUM')
    else:
        if num < 0 or num > 200:
            return ValidationResult(is_valid=False, message="Duration in years out of expected bounds", original_value=original, rule_applied='DURATION_NUM')
    return ValidationResult(is_valid=True, message="Duration numeric and within bounds", original_value=original, rule_applied='DURATION_NUM')

