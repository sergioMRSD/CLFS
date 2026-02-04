#!/usr/bin/env python3
"""
Data Validation Script for Census/Survey Data
==============================================

This script validates census or survey data against reference classification systems:
- SSIC 2025: Singapore Standard Industrial Classification
- SSEC 2020: Singapore Standard Educational Classification (Field of Study)
- SSOC 2024: Singapore Standard Occupational Classification

Validation Rules:
1. Industry codes (present/last) must exist in SSIC 2025
2. Field of study codes must exist in SSEC 2020
3. Occupation codes (last) must exist in SSOC 2024
4. Employment status must be valid
5. Household reference person count validation
6. Language/dialect consistency with ethnicity
7. Postal code validation
8. Conditional free text validation

Author: Data Validation System
Date: 2026-01-13
"""

from dataclasses import dataclass
from datetime import datetime
import logging
import re
from typing import List, Optional, Set

import pandas as pd


# ==========================================================================
# Configuration and Setup
# ==========================================================================

@dataclass
class ValidationConfig:
    """Configuration for validation parameters."""

    # Reference file paths (adjust paths as needed)
    ssic_2025_path: str = "reference_data/ssic2025-classification-structure.xlsx"
    ssec_2020_path: str = "reference_data/Classification of LEA EQA and FOS SSEC 2020.xlsx"
    ssoc_2024_path: str = "reference_data/ssoc2024-classification-structure.xlsx"

    # Sheet names
    ssic_sheet: str = "SSIC 2025 Structure"
    ssec_fos_sheet: str = "SSEC2020 (FOS)"
    ssoc_sheet: str = "SSOC 2024 Structure"

    # Skip rows (header rows in reference files)
    skip_rows: int = 3

    # Valid employment status codes
    valid_employment_status: Optional[Set[str]] = None

    # Optional path to an HQA/SSOC -> expected GMI ranges mapping file (Excel or CSV)
    hqa_ssoc_gmi_map_path: Optional[str] = None
    hqa_ssoc_gmi_map_sheet: str = "Sheet1"

    # Chinese language/dialect codes
    chinese_languages: Optional[Set[str]] = None

    # Chinese ethnicity codes
    chinese_ethnicity_codes: Optional[Set[str]] = None

    def __post_init__(self) -> None:
        if self.valid_employment_status is None:
            self.valid_employment_status = {
                "1",
                "2",
                "3",
                "4",
                "5",
                "6",
                "7",
                "8",
                "9",
                "E",
                "U",
                "O",
                "R",
            }

        if self.chinese_languages is None:
            self.chinese_languages = {
                "MANDARIN",
                "HOKKIEN",
                "TEOCHEW",
                "CANTONESE",
                "HAKKA",
                "HAINANESE",
                "FOOCHOW",
                "SHANGHAINESE",
                "OTHER_CHINESE",
            }

        if self.chinese_ethnicity_codes is None:
            self.chinese_ethnicity_codes = {"1", "C", "CHINESE"}


@dataclass
class ValidationResult:
    """Structure to hold validation results"""
    # Index from DataFrame can be ints or other hashable types; allow any
    row_index: object
    validation_type: str
    severity: str  # 'Error', 'Warning', 'Routing'
    message: str
    field_name: Optional[str]
    field_value: Optional[str]
    household_id: Optional[str] = None


# ============================================================================
# Logging Setup
# ============================================================================

def setup_logging(log_file: str = "validation.log") -> logging.Logger:
    """Setup logging configuration"""
    logger = logging.getLogger("DataValidator")
    logger.setLevel(logging.INFO)

    # File handler
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


# ============================================================================
# Reference Data Loader
# ============================================================================

class ReferenceDataLoader:
    """Loads and manages reference classification data."""

    def __init__(self, config: ValidationConfig, logger: logging.Logger):
        self.config = config
        self.logger = logger
        self.ssic_codes: Set[str] = set()
        self.ssec_codes: Set[str] = set()
        self.ssoc_codes: Set[str] = set()
        # Mapping: key -> (min_gmi, max_gmi)
        # key is tuple (hqa_code, ssoc_code) where either element can be empty string to indicate wildcard
        self.hqa_ssoc_gmi_map = {}

    def load_all_references(self) -> bool:
        try:
            self.logger.info("Loading reference data...")
            self.load_ssic_2025()
            self.load_ssec_2020()
            self.load_ssoc_2024()
            self.logger.info("All reference data loaded successfully")
            return True
        except Exception as exc:
            self.logger.error("Failed to load reference data: %s", exc)
            return False

    def _load_codes_from_excel(self, path: str, sheet_name: str) -> Set[str]:
        df = pd.read_excel(path, sheet_name=sheet_name, skiprows=self.config.skip_rows)
        codes: Set[str] = set()
        if df.shape[1] == 0:
            return codes

        code_column = df.iloc[:, 0]
        for code in code_column:
            if pd.notna(code) and str(code).strip():
                codes.add(str(code).strip())
        return codes

    def load_ssic_2025(self) -> None:
        self.logger.info("Loading SSIC 2025 from %s", self.config.ssic_2025_path)
        try:
            self.ssic_codes = self._load_codes_from_excel(self.config.ssic_2025_path, self.config.ssic_sheet)
            self.logger.info("Loaded %d SSIC 2025 codes", len(self.ssic_codes))
        except Exception as exc:
            self.logger.error("Error loading SSIC 2025: %s", exc)

    def load_ssec_2020(self) -> None:
        self.logger.info("Loading SSEC 2020 from %s", self.config.ssec_2020_path)
        try:
            self.ssec_codes = self._load_codes_from_excel(self.config.ssec_2020_path, self.config.ssec_fos_sheet)
            self.logger.info("Loaded %d SSEC 2020 codes", len(self.ssec_codes))
        except Exception as exc:
            self.logger.error("Error loading SSEC 2020: %s", exc)

    def load_ssoc_2024(self) -> None:
        self.logger.info("Loading SSOC 2024 from %s", self.config.ssoc_2024_path)
        try:
            self.ssoc_codes = self._load_codes_from_excel(self.config.ssoc_2024_path, self.config.ssoc_sheet)
            self.logger.info("Loaded %d SSOC 2024 codes", len(self.ssoc_codes))
        except Exception as exc:
            self.logger.error("Error loading SSOC 2024: %s", exc)

    def load_hqa_ssoc_gmi_mapping(self) -> None:
        """
        Load optional mapping between HQA, SSOC and expected GMI ranges.

        Expected columns (case-insensitive):
          - hqa (code)
          - ssoc (code)
          - gmi_min (numeric, can be 0)
          - gmi_max (numeric, or blank to indicate open-ended)

        Stores entries in self.hqa_ssoc_gmi_map as { (hqa, ssoc): (min, max) }
        Use empty string for wildcard entries.
        """
        path = self.config.hqa_ssoc_gmi_map_path
        if not path:
            self.logger.debug("No HQA/SSOC→GMI mapping path configured; skipping mapping load")
            return

        try:
            self.logger.info("Loading HQA/SSOC→GMI mapping from %s", path)
            if path.lower().endswith('.csv'):
                df = pd.read_csv(path)
            else:
                df = pd.read_excel(path, sheet_name=self.config.hqa_ssoc_gmi_map_sheet)

            for _, r in df.iterrows():
                hqa = str(r.get('hqa', '') or r.get('HQA', '') or '').strip()
                ssoc = str(r.get('ssoc', '') or r.get('SSOC', '') or '').strip()
                # Safely parse numeric min/max values from the row. Avoid calling float(None).
                gmi_min = 0.0
                try:
                    raw_min = (
                        r.get('gmi_min')
                        if 'gmi_min' in r
                        else r.get('GMI_MIN')
                        if 'GMI_MIN' in r
                        else r.get('gmiMin')
                    )
                except Exception:
                    raw_min = r.get('gmi_min')
                if pd.notna(raw_min) and str(raw_min).strip() != '':
                    try:
                        gmi_min = float(str(raw_min).strip())
                    except Exception:
                        gmi_min = 0.0

                gmi_max = None
                try:
                    raw_max = (
                        r.get('gmi_max')
                        if 'gmi_max' in r
                        else r.get('GMI_MAX')
                        if 'GMI_MAX' in r
                        else r.get('gmiMax')
                    )
                except Exception:
                    raw_max = r.get('gmi_max')
                if pd.notna(raw_max) and str(raw_max).strip() != '':
                    try:
                        gmi_max = float(str(raw_max).strip())
                    except Exception:
                        gmi_max = None

                key = (hqa, ssoc)
                self.hqa_ssoc_gmi_map[key] = (gmi_min, gmi_max)
            self.logger.info("Loaded %d HQA/SSOC→GMI mapping rows", len(self.hqa_ssoc_gmi_map))
        except Exception as exc:
            self.logger.error("Failed to load HQA/SSOC→GMI mapping: %s", exc)

    def is_valid_ssic(self, code: Optional[str]) -> bool:
        if code is None:
            return False
        return str(code).strip() in self.ssic_codes

    def is_valid_ssec(self, code: Optional[str]) -> bool:
        if code is None:
            return False
        return str(code).strip() in self.ssec_codes

    def is_valid_ssoc(self, code: Optional[str]) -> bool:
        if code is None:
            return False
        return str(code).strip() in self.ssoc_codes


# ============================================================================
# Validation Rules Engine
# ============================================================================

class DataValidator:
    """Main validation engine for census/survey data"""

    def __init__(self, config: ValidationConfig, ref_loader: ReferenceDataLoader, logger: logging.Logger):
        self.config = config
        self.ref_loader = ref_loader
        self.logger = logger
        self.validation_results: List[ValidationResult] = []

    def validate_dataframe(self, df: pd.DataFrame) -> List[ValidationResult]:
        """
        Run all validation rules on the input dataframe

        Args:
            df: Input dataframe to validate

        Returns:
            List of ValidationResult objects
        """
        self.validation_results = []
        self.logger.info(f"Starting validation on {len(df)} records")

        # Run individual validation rules
        self.validate_present_industry(df)
        self.validate_last_industry(df)
        self.validate_field_of_study(df)
        self.validate_last_occupation(df)
        self.validate_employment_status(df)
        self.validate_household_reference_person(df)
        self.validate_language_ethnicity_consistency(df)
        self.validate_postal_code(df)
        self.validate_free_text_fields(df)
        # Additional requested checks
        self.validate_oaw_income_low(df)
        self.validate_others_interviewer_remarks(df)
        self.validate_overseas_income_high(df)
        self.validate_multiple_jobs(df)
        # Table-based GMI checks (HQA x SSOC -> expected GMI ranges)
        self.validate_gmi_against_hqa_ssoc(df)

        self.logger.info(f"Validation complete. Found {len(self.validation_results)} issues")
        return self.validation_results

    # ========================================================================
    # Validation Rule: Present Industry Code
    # ========================================================================

    def validate_present_industry(self, df: pd.DataFrame):
        """
        Rule: Coding for present industry must be a valid code that can be found in SSIC 2025
        Severity: Error
        """
        self.logger.info("Validating present industry codes...")

        # Adjust column name based on actual data
        industry_col = self._find_column(
            df,
            [
                'present_industry',
                'current_industry',
                'industry_present',
                'INDUSTRY_PRESENT',
            ],
        )

        if industry_col is None:
            self.logger.warning("Present industry column not found")
            return

        for idx, row in df.iterrows():
            code = row.get(industry_col)

            # Skip if code is empty (might be valid for unemployed persons)
            if pd.isna(code) or str(code).strip() == '':
                continue

            if not self.ref_loader.is_valid_ssic(code):
                self.validation_results.append(ValidationResult(
                    row_index=idx,
                    validation_type="SSIC_PRESENT_INDUSTRY",
                    severity="Error",
                    message=(
                        "Coding for present industry must be a valid code that can be found"
                        " in SSIC 2025."
                    ),
                    field_name=industry_col,
                    field_value=str(code),
                    household_id=row.get('household_id', None),
                ))

    # ========================================================================
    # Validation Rule: Last Industry Code
    # ========================================================================

    def validate_last_industry(self, df: pd.DataFrame):
        """
        Rule: Coding for last industry must be a valid code that can be found in SSIC 2025
        Severity: Error (646), Routing (1284)
        """
        self.logger.info("Validating last industry codes...")

        industry_col = self._find_column(df, ['last_industry', 'industry_last', 'previous_industry', 'INDUSTRY_LAST'])

        if industry_col is None:
            self.logger.warning("Last industry column not found")
            return

        # Additional columns to determine severity
        employment_status_col = self._find_column(
            df,
            [
                'employment_status',
                'emp_status',
                'EMPLOYMENT_STATUS',
            ],
        )

        for idx, row in df.iterrows():
            code = row.get(industry_col)

            # Skip if code is empty
            if pd.isna(code) or str(code).strip() == '':
                continue

            if not self.ref_loader.is_valid_ssic(code):
                # Determine severity based on employment status or other criteria
                # This logic should be adjusted based on business rules
                severity = self._determine_last_industry_severity(row, employment_status_col)

                self.validation_results.append(ValidationResult(
                    row_index=idx,
                    validation_type="SSIC_LAST_INDUSTRY",
                    severity=severity,
                    message="Coding for last industry must be a valid code that can be found in SSIC 2025.",
                    field_name=industry_col,
                    field_value=str(code),
                    household_id=row.get('household_id', None)
                ))

    def _determine_last_industry_severity(self, row: pd.Series, employment_status_col: Optional[str]) -> str:
        """Determine severity for last industry validation"""
        # Example logic - adjust based on actual business rules
        if employment_status_col and pd.notna(row.get(employment_status_col)):
            emp_status = str(row.get(employment_status_col)).strip()
            # If person is currently unemployed, use routing; otherwise error
            if emp_status in ['U', 'UNEMPLOYED', '3']:
                return "Routing"
        return "Error"

    # ========================================================================
    # Validation Rule: Field of Study
    # ========================================================================

    def validate_field_of_study(self, df: pd.DataFrame):
        """
        Rule: Field of study for highest academic qualification attained must be a valid SSEC 2020 code
        Severity: Routing
        """
        self.logger.info("Validating field of study codes...")

        fos_col = self._find_column(df, ['field_of_study', 'fos', 'FOS', 'qualification_field', 'WHE_FOS'])

        if fos_col is None:
            self.logger.warning("Field of study column not found")
            return

        for idx, row in df.iterrows():
            code = row.get(fos_col)

            # Skip if code is empty
            if pd.isna(code) or str(code).strip() == '':
                continue

            if not self.ref_loader.is_valid_ssec(code):
                self.validation_results.append(ValidationResult(
                    row_index=idx,
                    validation_type="SSEC_FIELD_OF_STUDY",
                    severity="Routing",
                    message=(
                        "Field of study for highest academic qualification attained must be a valid "
                        "SSEC 2020 code."
                    ),
                    field_name=fos_col,
                    field_value=str(code),
                    household_id=row.get('household_id', None)
                ))

    # ========================================================================
    # Validation Rule: Last Occupation Code
    # ========================================================================

    def validate_last_occupation(self, df: pd.DataFrame):
        """
        Rule: Coding for last occupation must be a valid code that can be found in SSOC 2024
        Severity: Routing
        """
        self.logger.info("Validating last occupation codes...")

        occ_col = self._find_column(
            df,
            [
                'last_occupation',
                'occupation_last',
                'previous_occupation',
                'OCCUPATION_LAST',
            ],
        )

        if occ_col is None:
            self.logger.warning("Last occupation column not found")
            return

        for idx, row in df.iterrows():
            code = row.get(occ_col)

            # Skip if code is empty
            if pd.isna(code) or str(code).strip() == '':
                continue

            if not self.ref_loader.is_valid_ssoc(code):
                self.validation_results.append(ValidationResult(
                    row_index=idx,
                    validation_type="SSOC_LAST_OCCUPATION",
                    severity="Routing",
                    message=(
                        "Coding for last occupation must be a valid code that can be found in SSOC 2024."
                    ),
                    field_name=occ_col,
                    field_value=str(code),
                    household_id=row.get('household_id', None)
                ))

    # ========================================================================
    # Validation Rule: Employment Status
    # ========================================================================

    def validate_employment_status(self, df: pd.DataFrame):
        """
        Rule: Employment status must be a valid code
        Severity: Routing
        """
        self.logger.info("Validating employment status codes...")

        emp_status_col = self._find_column(df, ['employment_status', 'emp_status', 'EMPLOYMENT_STATUS'])

        if emp_status_col is None:
            self.logger.warning("Employment status column not found")
            return

        for idx, row in df.iterrows():
            code = row.get(emp_status_col)

            # Skip if code is empty
            if pd.isna(code) or str(code).strip() == '':
                continue

            code_str = str(code).strip().upper()

            if self.config.valid_employment_status is not None and code_str not in self.config.valid_employment_status:
                self.validation_results.append(ValidationResult(
                    row_index=idx,
                    validation_type="EMPLOYMENT_STATUS",
                    severity="Routing",
                    message="Employment status must be a valid code.",
                    field_name=emp_status_col,
                    field_value=str(code),
                    household_id=row.get('household_id', None)
                ))

    # ========================================================================
    # Validation Rule: Household Reference Person
    # ========================================================================

    def validate_household_reference_person(self, df: pd.DataFrame):
        """
        Rule: A household must have 1 household reference person
        Severity: Error
        """
        self.logger.info("Validating household reference person counts...")

        household_col = self._find_column(df, ['household_id', 'hh_id', 'HOUSEHOLD_ID'])
        ref_person_col = self._find_column(df, ['reference_person', 'ref_person', 'is_reference', 'REFERENCE_PERSON'])

        if household_col is None or ref_person_col is None:
            self.logger.warning("Household ID or reference person column not found")
            return

        # Group by household and count reference persons
        household_ref_counts = df.groupby(household_col)[ref_person_col].apply(
            lambda x: x.astype(str).str.upper().isin(['1', 'Y', 'YES', 'TRUE']).sum()
        )

        # Find households with != 1 reference person
        invalid_households = household_ref_counts[household_ref_counts != 1]

        for hh_id, count in invalid_households.items():
            # Get all rows for this household
            hh_rows = df[df[household_col] == hh_id]

            for idx in hh_rows.index:
                self.validation_results.append(ValidationResult(
                    row_index=idx,
                    validation_type="HOUSEHOLD_REFERENCE_PERSON",
                    severity="Error",
                    message=f"A household must have 1 household reference person. Found {count} for household {hh_id}.",
                    field_name=ref_person_col,
                    field_value=str(df.loc[idx, ref_person_col]),
                    household_id=str(hh_id)
                ))

    # ========================================================================
    # Validation Rule: Language-Ethnicity Consistency
    # ========================================================================

    def validate_language_ethnicity_consistency(self, df: pd.DataFrame):
        """
        Rule: Chinese language/dialect should only be spoken in households with Chinese members
        Severity: Warning
        """
        self.logger.info("Validating language-ethnicity consistency...")

        household_col = self._find_column(df, ['household_id', 'hh_id', 'HOUSEHOLD_ID'])
        ethnicity_col = self._find_column(df, ['ethnicity', 'ethnic_group', 'ETHNICITY'])
        lang1_col = self._find_column(df, ['language_most_frequent', 'language1', 'primary_language', 'LANGUAGE_1'])
        lang2_col = self._find_column(df, ['language_second_frequent', 'language2', 'secondary_language', 'LANGUAGE_2'])

        if not all([household_col, ethnicity_col, lang1_col]):
            self.logger.warning("Required columns for language-ethnicity validation not found")
            return

        # Group by household to check if any member is Chinese
        household_ethnicities = df.groupby(household_col)[ethnicity_col].apply(
            lambda x: any(
                str(val).strip().upper() in (self.config.chinese_ethnicity_codes or set())
                for val in x if pd.notna(val)
            )
        )

        # Check each person's language
        for idx, row in df.iterrows():
            hh_id = row.get(household_col)

            if pd.isna(hh_id):
                continue

            has_chinese_member = household_ethnicities.get(hh_id, False)

            # Check primary language
            lang1 = str(row.get(lang1_col, '')).strip().upper()
            if not has_chinese_member and lang1 in (self.config.chinese_languages or set()):
                self.validation_results.append(ValidationResult(
                    row_index=idx,
                    validation_type="LANGUAGE_ETHNICITY_PRIMARY",
                    severity="Warning",
                    message=(
                        "None of the members in this household are Chinese. Are you sure the language "
                        "or dialect that this person most frequently speaks at home is Mandarin or a "
                        "Chinese dialect?"
                    ),
                    field_name=lang1_col,
                    field_value=lang1,
                    household_id=str(hh_id)
                ))

            # Check secondary language if column exists
            if lang2_col:
                lang2 = str(row.get(lang2_col, '')).strip().upper()
                if not has_chinese_member and lang2 in (self.config.chinese_languages or set()):
                    self.validation_results.append(ValidationResult(
                        row_index=idx,
                        validation_type="LANGUAGE_ETHNICITY_SECONDARY",
                        severity="Warning",
                        message=(
                            "None of the members in this household are Chinese. Are you sure the language "
                            "or dialect that this person second most frequently speaks at home is Mandarin or "
                            "a Chinese dialect?"
                        ),
                        field_name=lang2_col,
                        field_value=lang2,
                        household_id=str(hh_id)
                    ))

    # ========================================================================
    # Validation Rule: Postal Code
    # ========================================================================

    def validate_postal_code(self, df: pd.DataFrame):
        """
        Rule: Please fill in a valid Singapore postal code for your workplace address
        Severity: Routing
        """
        self.logger.info("Validating postal codes...")

        postal_col = self._find_column(df, ['workplace_postal_code', 'postal_code', 'postcode', 'POSTAL_CODE'])

        if postal_col is None:
            self.logger.warning("Postal code column not found")
            return

        # Singapore postal code: 6 digits
        postal_pattern = re.compile(r'^\d{6}$')

        for idx, row in df.iterrows():
            postal = row.get(postal_col)

            # Skip if empty (might be valid for non-working persons)
            if pd.isna(postal) or str(postal).strip() == '':
                continue

            postal_str = str(postal).strip()

            if not postal_pattern.match(postal_str):
                self.validation_results.append(ValidationResult(
                    row_index=idx,
                    validation_type="POSTAL_CODE",
                    severity="Routing",
                    message="Please fill in a valid Singapore postal code for your workplace address.",
                    field_name=postal_col,
                    field_value=postal_str,
                    household_id=row.get('household_id', None)
                ))

    # ========================================================================
    # Validation Rule: Conditional Free Text Fields
    # ========================================================================

    def validate_free_text_fields(self, df: pd.DataFrame):
        """
        Rule: Others free text must not be blank if WHE_HQA = 799 (Others) was selected
        Severity: Error
        """
        self.logger.info("Validating conditional free text fields...")

        hqa_col = self._find_column(df, ['WHE_HQA', 'highest_qualification', 'qualification', 'HQA'])
        hqa_text_col = self._find_column(df, ['WHE_HQA_TEXT', 'qualification_others', 'hqa_others', 'HQA_TEXT'])

        if hqa_col is None or hqa_text_col is None:
            self.logger.warning("Required columns for free text validation not found")
            return

        for idx, row in df.iterrows():
            hqa_code = str(row.get(hqa_col, '')).strip()
            hqa_text = str(row.get(hqa_text_col, '')).strip()

            # If "Others" option (799) is selected, text must not be blank
            if hqa_code == '799' and (pd.isna(row.get(hqa_text_col)) or hqa_text == ''):
                self.validation_results.append(ValidationResult(
                    row_index=idx,
                    validation_type="FREE_TEXT_REQUIRED",
                    severity="Error",
                    message="Others free text must not be blank if WHE_HQA = 799 (Others) was selected.",
                    field_name=hqa_text_col,
                    field_value="<blank>",
                    household_id=row.get('household_id', None)
                ))

    # ========================================================================
    # Additional Requested Validations
    # ========================================================================

    def _parse_numeric(self, value: object) -> Optional[float]:
        """Try to parse a numeric value from a cell. Returns float or None."""
        if value is None:
            return None
        try:
            # Remove common non-numeric characters
            s = str(value).strip()
            if s == "":
                return None
            # Remove currency symbols and commas
            s = re.sub(r"[^0-9.\-]", "", s)
            if s == "":
                return None
            return float(s)
        except Exception:
            return None

    def validate_oaw_income_low(self, df: pd.DataFrame):
        """
        Rule: If respondent is an Own-Account Worker (OAW) and reported monthly income < $200,
        flag a Warning asking to confirm the low income.
        Severity: Warning
        """
        self.logger.info("Validating OAW low incomes...")

        # Possible column names
        job_type_col = self._find_column(
            df,
            [
                'employment_type',
                'job_type',
                'occupation_type',
                'OWN_ACCOUNT_WORKER',
                'oaw_flag',
                'is_oaw',
            ],
        )
        income_col = self._find_column(
            df,
            [
                'monthly_income',
                'gross_monthly_income',
                'gmi',
                'monthly_gross_income',
                'income',
                'income_monthly',
            ],
        )

        if income_col is None:
            self.logger.debug("No income column found for OAW check; skipping")
            return

        for idx, row in df.iterrows():
            income_val = self._parse_numeric(row.get(income_col))
            if income_val is None:
                continue

            is_oaw = False
            if job_type_col:
                jt = str(row.get(job_type_col, '')).strip().upper()
                if (
                    jt in (
                        'OAW',
                        'OWN ACCOUNT WORKER',
                        'OWN-ACCOUNT WORKER',
                        'OWN_ACCOUNT_WORKER',
                    )
                    or ('OWN' in jt and 'ACCOUNT' in jt)
                ):
                    is_oaw = True
            else:
                # fallback: some datasets may indicate OAW with a column name itself
                # or by occupation keywords
                pass

            if is_oaw and income_val < 200:
                self.validation_results.append(ValidationResult(
                    row_index=idx,
                    validation_type="OAW_MONTHLY_INCOME_LOW",
                    severity="Warning",
                    message="Are you sure the monthly income earned from this OAW job is less than $200",
                    field_name=income_col,
                    field_value=str(row.get(income_col)),
                    household_id=row.get('household_id', None)
                ))

    def validate_others_interviewer_remarks(self, df: pd.DataFrame):
        """
        Rule: When an 'Others' option is selected, interviewer remarks must be present and at least 10 characters.
        Severity: Error
        """
        self.logger.info("Validating 'Others' interviewer remarks...")

        # Candidate columns that might hold 'Others' selections
        candidate_cols = [
            c
            for c in df.columns
            if 'other' in str(c).lower()
            or 'others' in str(c).lower()
            or 'other_specify' in str(c).lower()
        ]
        # Typical remark columns
        remarks_cols = [self._find_column(df, names) for names in [
            ['interviewer_remarks', 'remarks', 'note', 'interviewer_note'],
            ['WHE_HQA_TEXT', 'qualification_others', 'hqa_others', 'HQA_TEXT'],
            ['other_text', 'others_text', 'other_specify', 'specify_others']
        ]]
        remarks_cols = [c for c in remarks_cols if c]

        if not candidate_cols:
            # Try common selection columns like 'WHE_HQA'
            candidate_cols = [c for c in df.columns if str(c).upper() in ('WHE_HQA', 'HQA')]

        if not candidate_cols:
            self.logger.debug("No 'Others' candidate columns found; skipping")
            return

        for idx, row in df.iterrows():
            for col in candidate_cols:
                val = row.get(col)
                if pd.isna(val):
                    continue
                sval = str(val).strip().upper()
                # treat numeric code 799 or textual 'OTHERS' as selection
                if sval == '799' or 'OTHER' in sval:
                    # check remarks
                    remark_found = False
                    for rc in remarks_cols:
                        rtext = str(row.get(rc, '')).strip()
                        if pd.notna(rtext) and len(rtext) >= 10:
                            remark_found = True
                            break
                    if not remark_found:
                        self.validation_results.append(ValidationResult(
                            row_index=idx,
                            validation_type="OTHERS_INTERVIEWER_REMARKS",
                            severity="Error",
                            message=(
                                "Others' was specified, interviewer has not indicated any remarks or has "
                                "remarks with less than 10 characters. Please confirm that the 'Others' "
                                "option cannot be grouped into the options provided."
                            ),
                            field_name=col,
                            field_value=str(val),
                            household_id=row.get('household_id', None)
                        ))

    def validate_overseas_income_high(self, df: pd.DataFrame):
        """
        Rule: If last drawn gross monthly income from most recent overseas work experience is >= S$200,000,
        flag a Warning asking to confirm monthly/annual and currency.
        Severity: Warning
        """
        self.logger.info("Validating very high overseas incomes...")

        income_cols = [
            'last_overseas_income',
            'last_overseas_gmi',
            'overseas_income',
            'overseas_gmi',
            'last_overseas_gross_income',
        ]
        col = self._find_column(df, income_cols)
        if col is None:
            self.logger.debug("No overseas income column found; skipping")
            return

        for idx, row in df.iterrows():
            income_val = self._parse_numeric(row.get(col))
            if income_val is None:
                continue
            if income_val >= 200000:
                self.validation_results.append(ValidationResult(
                    row_index=idx,
                    validation_type="OVERSEAS_INCOME_VERY_HIGH",
                    severity="Warning",
                    message=(
                        "Are you sure the last drawn gross monthly income from the most recent overseas "
                        "work experience was S$200,000 or more? Please check whether the income reported "
                        "is monthly or annual, and whether it is in Singapore dollars. Amend accordingly."
                    ),
                    field_name=col,
                    field_value=str(row.get(col)),
                    household_id=row.get('household_id', None)
                ))

    def validate_multiple_jobs(self, df: pd.DataFrame):
        """
        Rule: If respondent is currently holding more than 1 job, flag a Warning to confirm.
        Severity: Warning
        """
        self.logger.info("Validating multiple jobs flag...")

        jobs_col = self._find_column(
            df,
            [
                'num_jobs',
                'number_of_jobs',
                'jobs_count',
                'no_of_jobs',
                'number_jobs',
                'multiple_jobs',
            ],
        )
        if jobs_col is None:
            # try boolean indicator
            jobs_col = self._find_column(df, ['holding_more_than_one_job', 'has_multiple_jobs', 'multiple_job_flag'])

        if jobs_col is None:
            self.logger.debug("No jobs count/flag column found; skipping")
            return

        for idx, row in df.iterrows():
            val = row.get(jobs_col)
            if pd.isna(val):
                continue
            # if boolean-like
            sval = str(val).strip().upper()
            if sval in ('Y', 'YES', 'TRUE'):
                trigger = True
            else:
                num = self._parse_numeric(val)
                trigger = (num is not None and num > 1)

            if trigger:
                self.validation_results.append(ValidationResult(
                    row_index=idx,
                    validation_type="MULTIPLE_JOBS",
                    severity="Warning",
                    message="Please confirm that respondent is currently holding more than 1 job",
                    field_name=jobs_col,
                    field_value=str(val),
                    household_id=row.get('household_id', None)
                ))

    # ========================================================================
    # Helper Methods
    # ========================================================================

    def _find_column(self, df: pd.DataFrame, possible_names: List[str]) -> Optional[str]:
        """Find column name from a list of possible names (case-insensitive).

        Returns the original column name from the dataframe if found, otherwise None.
        """
        df_columns_lower = {str(col).lower(): col for col in df.columns}

        for name in possible_names:
            if name.lower() in df_columns_lower:
                return df_columns_lower[name.lower()]

        return None

    def validate_gmi_against_hqa_ssoc(self, df: pd.DataFrame):
        """
        Use an optional reference table mapping (HQA x SSOC) -> expected GMI ranges to flag
        Gross Monthly Income values that fall outside expected bounds.
        """
        # Ensure mapping is loaded
        try:
            self.ref_loader.load_hqa_ssoc_gmi_mapping()
        except Exception:
            pass

        map_obj = getattr(self.ref_loader, 'hqa_ssoc_gmi_map', None)
        if not map_obj:
            self.logger.debug("No HQA/SSOC→GMI mapping available; skipping GMI table-based checks")
            return

        # find relevant columns
        hqa_col = self._find_column(
            df,
            ['WHE_HQA', 'highest_qualification', 'qualification', 'HQA'],
        )
        ssoc_col = self._find_column(
            df,
            [
                'last_occupation',
                'occupation_last',
                'previous_occupation',
                'SSOC',
                'last_occupation_code',
            ],
        )
        gmi_col = self._find_column(
            df,
            ['gmi', 'gross_monthly_income', 'monthly_income', 'monthly_gross_income'],
        )

        if hqa_col is None or ssoc_col is None or gmi_col is None:
            self.logger.debug("Missing HQA/SSOC/GMI columns for table-based GMI checks; skipping")
            return

        for idx, row in df.iterrows():
            hqa = str(row.get(hqa_col, '')).strip()
            ssoc = str(row.get(ssoc_col, '')).strip()
            gmi = self._parse_numeric(row.get(gmi_col))
            if gmi is None:
                continue

            # lookup order: exact (hqa, ssoc), (hqa, ''), ('', ssoc)
            candidate_keys = [(hqa, ssoc), (hqa, ''), ('', ssoc)]
            found = False
            for key in candidate_keys:
                if key in map_obj:
                    gmi_min, gmi_max = map_obj[key]
                    found = True
                    break

            if not found:
                continue

            if gmi < gmi_min or (gmi_max is not None and gmi > gmi_max):
                self.validation_results.append(ValidationResult(
                    row_index=idx,
                    validation_type="GMI_VS_HQA_SSOC_RANGE",
                    severity="Warning",
                    message=(
                        "Reported Gross Monthly Income appears outside the expected range for the "
                        "reported Highest Qualification and occupation. Please confirm the income value "
                        "is correct and in the expected time unit (monthly) and currency."
                    ),
                    field_name=gmi_col,
                    field_value=str(row.get(gmi_col)),
                    household_id=row.get('household_id', None)
                ))


# ============================================================================
# Report Generator
# ============================================================================

class ValidationReportGenerator:
    """Generate validation reports in various formats"""

    def __init__(self, logger: logging.Logger):
        self.logger = logger

    def generate_summary_report(self, results: List[ValidationResult]) -> pd.DataFrame:
        """Generate summary report similar to the provided format"""
        summary_data = []

        # Group by validation type and severity
        for result in results:
            summary_data.append({
                'validation_type': result.validation_type,
                'severity': result.severity,
                'message': result.message
            })

        if not summary_data:
            self.logger.info("No validation issues found")
            return pd.DataFrame()

        df_summary = pd.DataFrame(summary_data)

        # Create pivot table
        pivot = df_summary.pivot_table(
            index='message',
            columns='severity',
            aggfunc='size',
            fill_value=0
        )

        # Add Grand Total column
        pivot['Grand Total'] = pivot.sum(axis=1)

        # Sort by Grand Total descending
        pivot = pivot.sort_values('Grand Total', ascending=False)

        return pivot

    def generate_detailed_report(self, results: List[ValidationResult]) -> pd.DataFrame:
        """Generate detailed validation report"""
        if not results:
            return pd.DataFrame()

        data = []
        for result in results:
            data.append({
                'Row Index': result.row_index,
                'Household ID': result.household_id,
                'Validation Type': result.validation_type,
                'Severity': result.severity,
                'Field Name': result.field_name,
                'Field Value': result.field_value,
                'Message': result.message
            })

        return pd.DataFrame(data)

    def save_reports(self, results: List[ValidationResult], output_prefix: str = "validation_report"):
        """Save validation reports to Excel files"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Summary repor
        summary_df = self.generate_summary_report(results)
        if not summary_df.empty:
            summary_file = f"{output_prefix}_summary_{timestamp}.xlsx"
            summary_df.to_excel(summary_file)
            self.logger.info(f"Summary report saved to {summary_file}")

        # Detailed repor
        detailed_df = self.generate_detailed_report(results)
        if not detailed_df.empty:
            detailed_file = f"{output_prefix}_detailed_{timestamp}.xlsx"
            detailed_df.to_excel(detailed_file, index=False)
            self.logger.info(f"Detailed report saved to {detailed_file}")

        return summary_df, detailed_df


# ============================================================================
# Main Execution
# ============================================================================

def main():
    """Main execution function"""

    # Setup logging
    logger = setup_logging()
    logger.info("=" * 80)
    logger.info("Data Validation System Started")
    logger.info("=" * 80)

    # Initialize configuration
    config = ValidationConfig()

    # Load reference data
    ref_loader = ReferenceDataLoader(config, logger)
    if not ref_loader.load_all_references():
        logger.error("Failed to load reference data. Exiting.")
        return

    # Load input data to validate
    # ADJUST THIS PATH to your actual input file
    input_file = "data_to_validate.xlsx"

    try:
        logger.info(f"Loading input data from {input_file}")
        df_input = pd.read_excel(input_file)
        logger.info(f"Loaded {len(df_input)} records with {len(df_input.columns)} columns")
    except FileNotFoundError:
        logger.error(f"Input file {input_file} not found")
        return
    except Exception as e:
        logger.error(f"Error loading input file: {e}")
        return

    # Initialize validator
    validator = DataValidator(config, ref_loader, logger)

    # Run validation
    results = validator.validate_dataframe(df_input)

    # Generate reports
    report_generator = ValidationReportGenerator(logger)
    summary_df, detailed_df = report_generator.save_reports(results)

    # Display summary
    if not summary_df.empty:
        logger.info("\n" + "=" * 80)
        logger.info("VALIDATION SUMMARY")
        logger.info("=" * 80)
        print(summary_df.to_string())
    else:
        logger.info("\n" + "=" * 80)
        logger.info("No validation issues found!")
        logger.info("=" * 80)

    logger.info("\nValidation process completed successfully")


if __name__ == "__main__":
    main()
