import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import PatternFill

from CLFS_validation_rules import validate_others_option


# Column name to HouseholdMember attribute mapping
COLUMN_MAPPING = {
    "full_name": "Full Name",
    "date_of_birth": "Date of Birth (DD/MM/YYYY)",
    "age": "Age",
    "contact_number": "Contact Number",
    "tenancy_of_household": "Tenancy of Household",
    "hire_foreign_domestic_workers": "Do you hire any Foreign Domestic Workers in this household?",
    "num_foreign_domestic_workers": "How many Foreign Domestic Workers do you have?",
    "foreign_domestic_workers_received_bonus": "Did your Foreign Domestic Worker(s) receive any bonus during the last 12 months (including the 13th month Annual Wage Supplement)?",
    "sex": "Sex",
    "place_of_birth": "Place of Birth",
    "identification_type": "Identification Type",
    "race": "Race",
    "where_currently_staying": "Where are you currently staying?",
    "main_reason_living_abroad": "What is your main reason for living abroad?",
    "religion": "What is your religion?",
    "marital_status": "Marital Status",
    "number_of_children": "Number of children given birth to",
    "highest_academic_qualification": "Highest Academic Qualification",
    "field_of_study_highest_academic": "Field of study of your highest academic qualification attained?",
    "place_of_study_highest_academic": "Place of study for your Highest Academic Attained in?",
    "has_vocational_skills_certificates": "Have you ever obtained any Vocational or Skills certificates/qualifications, (e.g. (WSQ) and (ESS) certificates, or formal certifications that validate knowledge and skills in a particular field)?",
    "highest_vocational_certificate": "What is the highest vocational or skills certificate/qualification obtained?",
    "field_of_study_vocational": "What is the field of study of your highest vocational or skills certificate/qualification?",
    "place_of_study_vocational": "Where is the place of study for your highest vocational or skills certificate/qualification?",
    "care_economy": "Care economy",
    "artificial_intelligence": "Artificial Intelligence",
    "digital_skills": "Digital skills (excluding Artificial Intelligence)",
    "green_economy": "Green economy",
    "industry_4_0": "Industry 4.0",
    "programmes_used_to_upgrade_skills": "Have you utilised any of the following programmes/initiatives to upgrade your skills or switch jobs?",
    "ever_retired": "Have you ever retired from any job?",
    "retirement_age": "What age retire?",
    "labour_force_status": "Labour Force Status",
    "employment_status_last_week": "Employment Status as of last week",
    "organisation_type_last_week": "The organisation that employed you last week was a/an:",
    "paid_internship_traineeship": "Was your main job last week a paid internship, traineeship or apprenticeship?",
    "reason_for_internship": "What was the main reason you were in a paid internship, traineeship, or apprenticeship?",
    "salary_paid_by_contracting_agency": "Is your salary paid by an employment/labour contracting agency (e.g., BGC Group, PERSOLKELLY)?",
    "deployed_to_another_organisation": "Are you deployed to work in another organisation that supervises your work?",
    "business_trade_type": "The business or trade you operated/helping in last week was a/an:",
    "acra_registered_business_owner": "Are you an owner/partner of an ACRA-registered business in this job?",
    "business_incorporated": "Is this business incorporated (e.g., name of business ends with private limited or its equivalent)?",
    "sets_price_for_goods_services": "Do you usually set the price for the goods or services you provide in this job?",
    "job_title": "Job Title",
    "main_tasks_duties": "Main tasks / duties",
    "skills_description": "Which of the following statements best describe your skills in relation to what is needed for your job/business?",
    "qualification_needed_for_job": "In your view, what level of qualification, if any, is needed to carry out the tasks and duties of your job/business?",
    "field_of_study_needed_for_job": "In your view, which field of study is needed to carry out the tasks and duties of your job/business?",
    "name_of_establishment_last_week": "Name of Establishment you were working last week?",
    "reasons_self_employed": "What were your reason(s) for being self-employed?",
    "prefer_to_be": "Would you prefer to be a/an",
    "reasons_for_taking_job": "What were your reason(s) for taking up this job?",
    "keen_reasons": "I was keen in this job and took it up because:",
    "not_keen_reasons": "I was not keen in this job, but still took it up because:",
    "usual_hours_of_work": "Usual hours of work",
    "reason_working_part_time": "Reason that working part time rather than full time?",
    "person_taking_care_of": "The person you are mainly taking care of is your",
    "care_recipient_age": "What is his/her age?",
    "care_recipient_disabled_ill": "Is he/she disabled/ill?",
    "main_reason_part_time": "Main reason for working part-time rather than full-time:",
    "work_full_time_if_care_services_available": "Would you work full-time if suitable care services were available and/or affordable?",
    "willing_work_additional_hours": "Willing to work additional hours?",
    "available_additional_work": "Available for additional work?",
    "actively_sought_additional_hours": "Actively sought additional hours of work in the past four weeks?",
    "gmi": "GMI",
    "bonus_received_last_12_months": "Bonus received from your job(s) during the last 12 months",
    "employed_at_least_10_months": "Employed for at least 10 months during the last 12 months?",
    "num_jobs_held_last_week": "How many jobs did you hold last week?",
    "when_began_current_employer": "When did you begin working for your current employer?",
    "type_of_employment": "Type of Employment?",
    "contract_duration": "Contract duration",
    "began_as_fixed_term": "Begin as a fixed-term contract employee in your current job?",
    "employer_gave_paid_leave": "Did your employer give you paid leave or compensation instead?",
    "employer_gave_paid_sick_leave": "Did your employer give you paid sick leave when you were on MC",
    "employer_gave_rest_day_weekly": "Did your employer give you at least one rest day each week?",
    "satisfied_current_job": "Are you satisfied with your current job?",
    "actively_looking_new_job": "Are you actively looking for a new job?",
    "how_looked_for_job_last_4_weeks": "How did you look for a job or employment during the last 4 weeks?",
    "looking_for_permanent_job": "Are you looking for a permanent job?",
    "available_start_new_job": "Are you available to start work on the new job upon quitting the current job?",
    "looking_to_better_utilise_skills": "Is the main reason for looking for a new job to better utilise your skills?",
    "num_job_changes_last_2_years": "Number of Job changes in the last 2 years",
    "when_left_last_job": "When did you leave your last job?",
    "ns_industry": "NS Industry",
    "remarks": "Remarks",
}


@dataclass
class HouseholdMember:
    # Basic Information
    full_name: str
    date_of_birth: Optional[str] = None
    age: Optional[int] = None
    contact_number: Optional[str] = None
    tenancy_of_household: Optional[str] = None
    hire_foreign_domestic_workers: Optional[str] = None
    num_foreign_domestic_workers: Optional[int] = None
    foreign_domestic_workers_received_bonus: Optional[str] = None
    sex: Optional[str] = None
    place_of_birth: Optional[str] = None
    identification_type: Optional[str] = None
    race: Optional[str] = None
    where_currently_staying: Optional[str] = None
    main_reason_living_abroad: Optional[str] = None
    religion: Optional[str] = None
    marital_status: Optional[str] = None
    number_of_children: Optional[int] = None
    
    # Education
    highest_academic_qualification: Optional[str] = None
    field_of_study_highest_academic: Optional[str] = None
    place_of_study_highest_academic: Optional[str] = None
    has_vocational_skills_certificates: Optional[str] = None
    highest_vocational_certificate: Optional[str] = None
    field_of_study_vocational: Optional[str] = None
    place_of_study_vocational: Optional[str] = None
    
    # Skills & Training
    care_economy: Optional[str] = None
    artificial_intelligence: Optional[str] = None
    digital_skills: Optional[str] = None
    green_economy: Optional[str] = None
    industry_4_0: Optional[str] = None
    programmes_used_to_upgrade_skills: Optional[str] = None
    
    # Retirement
    ever_retired: Optional[str] = None
    retirement_age: Optional[int] = None
    
    # Employment Status
    labour_force_status: Optional[str] = None
    employment_status_last_week: Optional[str] = None
    organisation_type_last_week: Optional[str] = None
    paid_internship_traineeship: Optional[str] = None
    reason_for_internship: Optional[str] = None
    salary_paid_by_contracting_agency: Optional[str] = None
    deployed_to_another_organisation: Optional[str] = None
    business_trade_type: Optional[str] = None
    acra_registered_business_owner: Optional[str] = None
    business_incorporated: Optional[str] = None
    sets_price_for_goods_services: Optional[str] = None
    
    # Current Job Details
    job_title: Optional[str] = None
    main_tasks_duties: Optional[str] = None
    skills_description: Optional[str] = None
    
    qualification_needed_for_job: Optional[str] = None
    field_of_study_needed_for_job: Optional[str] = None
    name_of_establishment_last_week: Optional[str] = None
    reasons_self_employed: Optional[str] = None
    prefer_to_be: Optional[str] = None
    reasons_for_taking_job: Optional[str] = None
    keen_reasons: Optional[str] = None
    not_keen_reasons: Optional[str] = None
    
    # Work Hours & Arrangements
    usual_hours_of_work: Optional[float] = None
    reason_working_part_time: Optional[str] = None
    person_taking_care_of: Optional[str] = None
    care_recipient_age: Optional[int] = None
    care_recipient_disabled_ill: Optional[str] = None
    main_reason_part_time: Optional[str] = None
    work_full_time_if_care_services_available: Optional[str] = None
    willing_work_additional_hours: Optional[str] = None
    available_additional_work: Optional[str] = None
    actively_sought_additional_hours: Optional[str] = None
    
    # Compensation & Benefits
    gmi: Optional[float] = None
    bonus_received_last_12_months: Optional[float] = None
    employed_at_least_10_months: Optional[str] = None
    num_jobs_held_last_week: Optional[int] = None
    when_began_current_employer: Optional[str] = None
    type_of_employment: Optional[str] = None
    contract_duration: Optional[str] = None
    began_as_fixed_term: Optional[str] = None
    employer_gave_paid_leave: Optional[str] = None
    employer_gave_paid_sick_leave: Optional[str] = None
    employer_gave_rest_day_weekly: Optional[str] = None
    
    # Job Satisfaction & Search
    satisfied_current_job: Optional[str] = None
    actively_looking_new_job: Optional[str] = None
    how_looked_for_job_last_4_weeks: Optional[str] = None
    looking_for_permanent_job: Optional[str] = None
    available_start_new_job: Optional[str] = None
    looking_to_better_utilise_skills: Optional[str] = None
    num_job_changes_last_2_years: Optional[int] = None
    
    # Previous Employment
    when_left_last_job: Optional[str] = None
    usual_hours_work_previous: Optional[float] = None
    employment_status_previous: Optional[str] = None
    type_employment_previous: Optional[str] = None
    contract_duration_previous: Optional[str] = None
    job_title_previous: Optional[str] = None
    main_tasks_duties_previous: Optional[str] = None
    establishment_name_previous: Optional[str] = None
    age_started_employment: Optional[int] = None
    breaks_in_employment: Optional[int] = None
    
    # Work Relocation
    relocated_from_singapore: Optional[str] = None
    first_relocation_experience: Optional[str] = None
    relocation_total_duration: Optional[str] = None
    how_work_stint_arose: Optional[str] = None
    job_title_relocated: Optional[str] = None
    job_industry_sector_relocated: Optional[str] = None
    last_drawn_gmi_relocated: Optional[float] = None
    company_type_relocated: Optional[str] = None
    location_of_work_relocated: Optional[str] = None
    
    # Job Search Status
    actively_looking_jobs_past_4_weeks: Optional[str] = None
    looked_for_job_last_12_months: Optional[str] = None
    want_to_work_at_present: Optional[str] = None
    already_secured_job: Optional[str] = None
    how_soon_expect_start_new_job: Optional[str] = None
    available_work_next_2_weeks: Optional[str] = None
    when_available_to_work: Optional[str] = None
    how_long_looking_for_job_weeks: Optional[int] = None
    what_doing_while_looking: Optional[str] = None
    occupation_looking_for: Optional[str] = None
    main_step_to_look_employment: Optional[str] = None
    other_steps_look_employment: Optional[str] = None
    experienced_difficulties_securing_job: Optional[str] = None
    main_difficulty_encountered: Optional[str] = None
    other_difficulties_encountered: Optional[str] = None
    
    # Work History
    ever_worked_before: Optional[str] = None
    employment_status_last_worked: Optional[str] = None
    job_title_last_worked: Optional[str] = None
    main_tasks_duties_last_worked: Optional[str] = None
    establishment_name_last_worked: Optional[str] = None
    usual_hours_work_last_worked: Optional[float] = None
    last_drawn_gmi_last_worked: Optional[float] = None
    main_reason_left_last_job: Optional[str] = None
    reason_left_elaboration: Optional[str] = None
    reason_left_temporary_nature: Optional[str] = None
    reason_left_illness_injury: Optional[str] = None
    
    # Care Responsibilities (leaving job)
    person_taking_care_of_leaving: Optional[str] = None
    care_recipient_age_leaving: Optional[int] = None
    care_recipient_disabled_leaving: Optional[str] = None
    main_reason_leaving_due_care: Optional[str] = None
    work_full_time_if_care_services_leaving: Optional[str] = None
    when_left_last_job_months: Optional[int] = None
    
    # Second Relocation Info
    relocated_from_singapore_2: Optional[str] = None
    first_relocation_experience_2: Optional[str] = None
    relocation_total_duration_2: Optional[str] = None
    how_work_stint_arose_2: Optional[str] = None
    job_title_relocated_2: Optional[str] = None
    job_industry_sector_relocated_2: Optional[str] = None
    last_drawn_gmi_relocated_2: Optional[float] = None
    company_type_relocated_2: Optional[str] = None
    location_work_relocated_2: Optional[str] = None
    
    # Not Working/Not Looking
    main_reason_not_working_not_looking: Optional[str] = None
    ever_retired_2: Optional[str] = None
    retirement_age_2: Optional[int] = None
    person_taking_care_of_2: Optional[str] = None
    care_recipient_age_2: Optional[int] = None
    care_recipient_disabled_2: Optional[str] = None
    main_reason_not_working_not_looking_detail: Optional[str] = None
    work_if_care_services_available: Optional[str] = None
    ever_worked_before_2: Optional[str] = None
    when_left_last_job_months_2: Optional[int] = None
    employment_status_last_worked_2: Optional[str] = None
    job_title_last_worked_2: Optional[str] = None
    main_tasks_duties_last_worked_2: Optional[str] = None
    establishment_name_last_worked_2: Optional[str] = None
    usual_hours_work_last_worked_2: Optional[float] = None
    
    # Future Work Plans
    intend_look_job_future: Optional[str] = None
    when_intend_look_job: Optional[str] = None
    prefer_full_time_or_part_time: Optional[str] = None
    
    # Self-Employment & Gig Work
    self_employed_last_12_months: Optional[str] = None
    self_employed_last_12_months_2: Optional[str] = None
    worked_own_business_last_12_months: Optional[str] = None
    freelance_online_platforms_last_12_months: Optional[str] = None
    held_licences_permits_last_12_months: Optional[str] = None
    did_work_related_to_licences: Optional[str] = None
    reason_holding_licence_not_working: Optional[str] = None
    
    # Income from Non-Employment Sources
    interest_from_savings_last_12_months: Optional[float] = None
    revise_interest_earned_answer: Optional[str] = None
    interest_from_savings_revised: Optional[float] = None
    dividends_interests_investments_last_12_months: Optional[float] = None
    other_income_non_employment: Optional[str] = None
    income_from_rents_last_12_months: Optional[float] = None
    allowances_contributions_last_12_months: Optional[float] = None
    other_sources_income_last_12_months: Optional[float] = None
    
    # Care Provision
    provide_care_to_individuals: Optional[str] = None
    provide_care_to_individuals_2: Optional[str] = None
    individuals_have_long_term_care_needs: Optional[str] = None
    individuals_with_long_term_care_relationship: Optional[str] = None
    how_long_providing_caregiving_support: Optional[str] = None
    expect_provide_support_6_months: Optional[str] = None
    
    # Disabilities & Difficulties
    difficulty_seeing: Optional[str] = None
    difficulty_hearing: Optional[str] = None
    difficulty_body_movement: Optional[str] = None
    difficulty_self_care: Optional[str] = None
    long_lasting_difficulties: Optional[str] = None
    
    # Work Accommodations
    job_accommodates_working_arrangements: Optional[str] = None
    job_accommodates_working_arrangements_2: Optional[str] = None
    
    # Additional Info
    ns_industry: Optional[str] = None
    remarks: Optional[str] = None


def _normalize_value(value: object) -> Optional[str]:
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text if text else None


def _get_member_column_groups(columns: list[str]) -> list[dict[str, Optional[int]]]:
    full_name_indices = [i for i, col in enumerate(columns) if col == "Full Name"]
    dob_indices = [i for i, col in enumerate(columns) if col == "Date of Birth (DD/MM/YYYY)"]

    groups: list[dict[str, Optional[int]]] = []
    for idx, full_name_idx in enumerate(full_name_indices):
        next_full_name_idx = (
            full_name_indices[idx + 1] if idx + 1 < len(full_name_indices) else len(columns)
        )
        dob_idx = next(
            (i for i in dob_indices if full_name_idx < i < next_full_name_idx),
            None,
        )
        groups.append({"full_name_idx": full_name_idx, "dob_idx": dob_idx})

    return groups


def extract_household_members(df: pd.DataFrame) -> list[list[HouseholdMember]]:
    columns = list(df.columns)
    groups = _get_member_column_groups(columns)
    households: list[list[HouseholdMember]] = []

    for _, row in df.iterrows():
        members: list[HouseholdMember] = []
        for group in groups:
            name = _normalize_value(row.iloc[group["full_name_idx"]])
            if not name:
                continue
            
            # Create member with name (required)
            member = HouseholdMember(full_name=name)
            
            # Populate all mapped attributes from the row
            for attr_name, col_name in COLUMN_MAPPING.items():
                if attr_name == "full_name":
                    # Already set
                    continue
                if col_name in columns:
                    col_idx = columns.index(col_name)
                    value = _normalize_value(row.iloc[col_idx])
                    # Try to convert to appropriate type
                    if value:
                        if attr_name in ["age", "num_foreign_domestic_workers", "number_of_children", 
                                        "retirement_age", "care_recipient_age", "num_jobs_held_last_week",
                                        "num_job_changes_last_2_years", "care_recipient_age_leaving", 
                                        "when_left_last_job_months", "care_recipient_age_2", 
                                        "when_left_last_job_months_2", "how_long_looking_for_job_weeks",
                                        "age_started_employment", "breaks_in_employment"]:
                            try:
                                value = int(float(value))
                            except (ValueError, TypeError):
                                pass
                        elif attr_name in ["gmi", "bonus_received_last_12_months", "usual_hours_of_work",
                                          "last_drawn_gmi_relocated", "usual_hours_work_previous",
                                          "usual_hours_work_last_worked", "usual_hours_work_last_worked_2",
                                          "gmi", "bonus_received_last_12_months", "usual_hours_of_work",
                                          "interest_from_savings_last_12_months", "interest_from_savings_revised",
                                          "dividends_interests_investments_last_12_months", 
                                          "income_from_rents_last_12_months", "allowances_contributions_last_12_months",
                                          "other_sources_income_last_12_months", "last_drawn_gmi_relocated_2"]:
                            try:
                                value = float(value)
                            except (ValueError, TypeError):
                                pass
                        setattr(member, attr_name, value)
            
            members.append(member)
        households.append(members)

    return households

def load_xlsx_files(folder_path="Operating_Table"):
    """
    Load all .xlsx files from the specified folder.
    
    Args:
        folder_path (str): Path to the folder containing .xlsx files
        
    Returns:
        dict: Dictionary with filenames as keys and DataFrames as values
    """
    xlsx_files = {}
    
    # Check if folder exists
    if not os.path.exists(folder_path):
        print(f"Error: Folder '{folder_path}' does not exist.")
        return xlsx_files
    
    # Find all .xlsx files in the folder
    for file in Path(folder_path).glob("*.xlsx"):
        try:
            print(f"Loading {file.name}...")
            df = pd.read_excel(file)
            xlsx_files[file.name] = df
            print(f"Successfully loaded {file.name} with {len(df)} rows and {len(df.columns)} columns")
        except Exception as e:
            print(f"Error loading {file.name}: {e}")
    
    if not xlsx_files:
        print(f"No .xlsx files found in '{folder_path}'")
    
    return xlsx_files


def create_output_directory():
    """Create output folder if it doesn't exist"""
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    return output_dir


def save_with_highlights(df: pd.DataFrame, original_file_path: str, changes: dict):
    """
    Save modified Excel file with cells highlighted in yellow where changes were made.
    
    Args:
        df: Modified DataFrame
        original_file_path: Path to original file
        changes: Dictionary with format {(row, col): (old_value, new_value)}
    """
    output_dir = create_output_directory()
    
    # Create output filename
    filename = Path(original_file_path).stem
    output_path = output_dir / f"{filename}_validated.xlsx"
    
    # Save the dataframe
    df.to_excel(output_path, index=False, engine="openpyxl")
    
    # Now apply highlights to changed cells
    wb = load_workbook(output_path)
    ws = wb.active
    
    # Yellow highlight for changed cells
    yellow_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    
    for (row_idx, col_idx), (old_val, new_val) in changes.items():
        # Excel rows are 1-indexed and we need to account for header row
        excel_row = row_idx + 2  # +1 for 1-indexing, +1 for header
        excel_col = col_idx + 1  # +1 for 1-indexing
        
        cell = ws.cell(row=excel_row, column=excel_col)
        cell.fill = yellow_fill
        cell.value = new_val
    
    wb.save(output_path)
    print(f"\n✓ Validated file saved to: {output_path}")
    return output_path


def main():
    """Main function to run the validator."""
    print("CLFS Data Validator")
    print("=" * 50)
    
    # Load all .xlsx files from Operating_Table folder
    files = load_xlsx_files()
    
    print(f"\nTotal files loaded: {len(files)}")
    
    # Display summary of loaded files
    for filename, df in files.items():
        print(f"\n{filename}:")
        print(f"  Rows: {len(df)}")
        print(f"  Columns: {len(df.columns)}")

        households = extract_household_members(df)
        total_members = sum(len(members) for members in households)
        print(f"  Households parsed: {len(households)}")
        print(f"  Household members parsed: {total_members}")
        
        # Display household member details
        print(f"\n  Household Member Details:")
        for household_idx, members in enumerate(households, 1):
            print(f"\n  Household {household_idx}:")
            for member_idx, member in enumerate(members, 1):
                print(f"    Member {member_idx}:")
                print(f"      Name: {member.full_name}")
                print(f"      DOB: {member.date_of_birth}")
                print(f"      Age: {member.age}")
                print(f"      Labour Force Status: {member.labour_force_status}")
                print(f"      Employment Status: {member.employment_status_last_week}")
                print(f"      Job Title: {member.job_title}")
        
        # Apply validation rules
        print(f"\n{'=' * 50}")
        print(f"Applying Validation Rules...")
        print(f"{'=' * 50}")
        
        # Track changes for output
        changes = {}
        modified_df = df.copy()
        
        # RULE 1: Others option validation
        print(f"\nRULE 1: Others option validation")
        print("-" * 50)
        
        rule1_issues = 0
        rule1_corrected = 0
        
        # Check place_of_birth column (one of the "Others:" columns)
        place_of_birth_col = "Place of Birth"
        if place_of_birth_col in df.columns:
            col_idx = df.columns.get_loc(place_of_birth_col)
            
            for row_idx, value in df[place_of_birth_col].items():
                if pd.isna(value):
                    continue
                
                result = validate_others_option(str(value), "place_of_birth")
                
                if result.corrected_value:
                    print(f"  ✓ Row {row_idx + 1}: {result.message}")
                    print(f"    Before: {result.original_value}")
                    print(f"    After:  {result.corrected_value}")
                    modified_df.at[row_idx, place_of_birth_col] = result.corrected_value
                    changes[(row_idx, col_idx)] = (result.original_value, result.corrected_value)
                    rule1_corrected += 1
        
        print(f"\nRULE 1 Summary: {rule1_corrected} corrected")
        
        # Save validated output if changes were made
        if changes:
            original_path = Path("Operating_Table") / filename
            save_with_highlights(modified_df, str(original_path), changes)


if __name__ == "__main__":
    main()
