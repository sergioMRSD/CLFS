import pandas as pd
from datetime import datetime
import numpy as np
import glob
import os

################################################################################
## 1. CONFIGURATION
## Update these variables to match your file paths and column names.
################################################################################

# ### CUSTOMIZE ###
INPUT_FOLDER_PATH = r'C:\path\to\your\input_folder'  # Path to the folder containing your Excel/CSV files
OUTPUT_FOLDER_PATH = r'C:\path\to\your\output_folder' # Path to save the final combined report
HEADER_ROW_INDEX = 5 # The Excel/CSV file's header is on row 6, which is index 5

# ##############################################################################
# ### CUSTOMIZE ### - ASSUMED COLUMN NAMES (All Batches)
# You MUST update these variable values to match the column names in your
# 'tidy_df' (long format) DataFrame.
# ##############################################################################

# --- Household Level ---
COL_RESPONSE_ID = 'Response ID'
COL_NUM_MEMBERS = 'No. of Household Members'

# --- Person Level (Generic) ---
COL_MEMBER_ID = 'Member_ID' # This will be created during restructuring
COL_AGE = 'Age' # This will be calculated from DOB
COL_DOB = 'Date of Birth (DD/MM/YYYY)'
COL_DOB_DT = 'Date of Birth (datetime)' # We will create this
COL_SEX = 'Sex'
COL_RACE = 'Race'
COL_ID_TYPE = 'Identification Type'
COL_STAYING_WHERE = 'Where are you currently staying?'
COL_MARITAL_STATUS = 'Marital Status'
COL_RELATIONSHIP = 'Relationship to Household Reference Person' # Crucial for restructuring

# --- Employment ---
COL_LABOUR_STATUS = 'Labour Force Status'
COL_EMPLOYMENT_STATUS = 'Employment Status as of last week'
COL_JOB_TITLE = 'Job Title'
# Use specific columns for occupation codes if they exist, otherwise assume Job Title holds it
COL_OCCUPATION_CODE = 'Job Title' # Or update if a dedicated SSOC column exists
COL_INDUSTRY = 'Establishment Industry working last week?'
COL_FULL_PART_TIME = 'Full Time or Part Time?'
COL_REASON_PART_TIME = 'Reason that working part time rather than full time?'
COL_WILLING_WORK_MORE = 'Willing to work additional hours?'
COL_AVAILABLE_WORK_MORE = 'Available for additional work?'
COL_USUAL_HOURS = 'Usual hours of work'
COL_EXTRA_HOURS = 'Extra Hours worked'
COL_ABSENCE_HOURS = 'Hours of absence'
COL_TYPE_OF_EMPLOYMENT = 'Type of Employment?'
COL_EVER_WORKED = 'Ever worked before?'

# --- Absence Checkbox (From Rule, not in column list) ---
COL_ABSENCE_UNABLE = 'ASSUMED_Absence_Hours_Unable_Checkbox' # Still assumed

# --- Job Search / Not Working ---
COL_REASON_NOT_WORKING = 'Main Reason for not working & not looking for job?'
COL_UNEMPLOYMENT_WEEKS = 'How long have you been looking for a job? (in weeks)'
COL_LEFT_LAST_JOB = 'When did you leave your last Job?'
COL_LOOKING_FOR_WORK_STATUS = 'While currently looking for work, are you:'
COL_JOB_SUBMITTED_APPLICATIONS = 'During your most recent job search, did you submit any job applications for full-time positions that were either permanent or fixed-term contracts of 1 year or more?'
COL_JOB_OFFERS_RECEIVED = 'Have you received any job offers for full-time positions that were either permanent or fixed-term contracts lasting 1 year or more?'
COL_JOB_APPLICATIONS_COUNT = 'How many have you submitted?'
COL_JOB_OFFERS_COUNT = 'How many have you received?'

# --- Education ---
COL_EDU_STATUS = 'Current Educational Status'
COL_HIGHEST_ACADEMIC_QUAL = 'Highest Academic Qualification'
COL_HIGHEST_ACADEMIC_ATTAINED_IN = 'Highest Academic Attained in?'
COL_VOCATIONAL_QUAL = 'Highest Vocational/Skills Qualifications?'

# --- Assumed Columns (Not in list, but implied by rules) ---
COL_SSOC_TWIN_CODE = 'ASSUMED_SSOC_2020_Twin_Code_Column' # Still assumed
# Check if NRIC/FIN is actually Contact Number or needs separate column
COL_NRIC = 'Contact Number' # Or update if a dedicated NRIC/FIN column exists
COL_MEMBER_NO = 'ASSUMED_Member_No_Column' # Still assumed unless tied to Member_ID logic

# --- Other ---
COL_GMI = 'GMI'
COL_REMARKS = 'Remark'


################################################################################
## 2. HELPER FUNCTIONS
## Reusable functions for common tasks like calculating age.
################################################################################

def calculate_age(dob_datetime):
    """Calculates age in years from a datetime object."""
    if pd.isna(dob_datetime):
        return None
    today = datetime.today()
    # Ensure dob_datetime is a datetime object before accessing attributes
    if isinstance(dob_datetime, pd.Timestamp):
        try:
            age = today.year - dob_datetime.year - ((today.month, today.day) < (dob_datetime.month, dob_datetime.day))
            return age
        except AttributeError:
             print(f"Warning: Could not calculate age for value {dob_datetime}. It might not be a valid date.")
             return None
    else:
        # Handle cases where conversion might have failed upstream
        # print(f"Warning: calculate_age received non-datetime value: {dob_datetime}")
        return None


def get_person_by_relationship(household_df, relationship):
    """Helper to find a person by relationship. Returns first match or None."""
    # Ensure the relationship column exists before filtering
    if COL_RELATIONSHIP not in household_df.columns:
        # print(f"Warning: Column '{COL_RELATIONSHIP}' not found in household DataFrame.")
        return None
    # Handle potential NaN values in the relationship column before comparison
    person = household_df[household_df[COL_RELATIONSHIP].astype(str) == str(relationship)]
    if not person.empty:
        return person.iloc[0]
    return None

def get_people_by_relationship(household_df, relationships_list):
    """Helper to find all people matching a list of relationships."""
    # Ensure the relationship column exists before filtering
    if COL_RELATIONSHIP not in household_df.columns:
        # print(f"Warning: Column '{COL_RELATIONSHIP}' not found in household DataFrame.")
        return pd.DataFrame() # Return empty DataFrame
    # Handle potential NaN values before using isin
    return household_df[household_df[COL_RELATIONSHIP].fillna('NA').isin(relationships_list)]


################################################################################
## 3. DATA LOADING AND RESTRUCTURING
## This section handles reading the data and transforming it into a tidy format.
################################################################################

def load_and_clean_data(file_path, header_index):
    """
    Loads the Excel or CSV file and performs initial cleaning.
    Dynamically chooses reader based on file extension.
    """
    try:
        file_name = os.path.basename(file_path)
        file_ext = os.path.splitext(file_name)[1].lower()

        if file_ext == '.xlsx' or file_ext == '.xls':
            df = pd.read_excel(file_path, header=header_index, dtype=str) # Read all as string initially
            print(f"✅ Excel file '{file_name}' loaded successfully.")
        elif file_ext == '.csv':
            # Try with default utf-8 first, fallback to latin1 if it fails
            try:
                # Read all as string to avoid type inference issues, especially with IDs/numbers
                df = pd.read_csv(file_path, header=header_index, encoding='utf-8', on_bad_lines='skip', dtype=str, low_memory=False)
            except UnicodeDecodeError:
                print(f"⚠️ UTF-8 decoding failed for '{file_name}', trying latin1 encoding...")
                df = pd.read_csv(file_path, header=header_index, encoding='latin1', on_bad_lines='skip', dtype=str, low_memory=False)
            print(f"✅ CSV file '{file_name}' loaded successfully.")
        else:
            print(f"⚠️ Skipping file '{file_name}': Unknown file extension '{file_ext}'.")
            return None

    except FileNotFoundError:
        print(f"❌ ERROR: The file at '{file_path}' was not found.")
        return None
    except Exception as e:
        print(f"❌ ERROR: Failed to load file '{file_path}'. Reason: {e}")
        return None

    # Clean up column names (remove leading/trailing spaces)
    df.columns = df.columns.str.strip()

    # Convert DOB column to datetime objects for calculations
    # Use errors='coerce' to handle any unparseable dates gracefully
    if COL_DOB in df.columns:
        # Attempt conversion, replace unparseable with NaT (Not a Time)
        df[COL_DOB_DT] = pd.to_datetime(df[COL_DOB], format='%d-%b-%y', errors='coerce') # Adjusted format based on sample: 1-Jan-93

        # Fallback for DD/MM/YYYY if the first format fails for some rows
        mask_failed = df[COL_DOB_DT].isna() & df[COL_DOB].notna()
        if mask_failed.any():
            print(f"   Info: Retrying DOB parsing with DD/MM/YYYY for {mask_failed.sum()} rows in {file_name}...")
            df.loc[mask_failed, COL_DOB_DT] = pd.to_datetime(df.loc[mask_failed, COL_DOB], format='%d/%m/%Y', errors='coerce')

        failed_count = df[COL_DOB_DT].isna().sum() - df[COL_DOB].isna().sum() # Count newly failed conversions
        if failed_count > 0:
             print(f"⚠️ Warning: Could not parse {failed_count} non-empty DOB values in {file_name} using formats 'D-Mon-YY' or 'DD/MM/YYYY'. Age calculations may be affected.")
    else:
        print(f"⚠️ Warning: Column '{COL_DOB}' not found in {file_name}. Age calculations will fail for this file.")
        df[COL_DOB_DT] = pd.NaT # Create the column anyway

    return df


def restructure_data(df_wide):
    """
    Transforms the data from a wide format (one row per household with repeating member columns)
    to a long format (one row per person). Attempts to dynamically identify column blocks.
    """
    print("⏳ Restructuring data from wide to long format...")
    all_members_data = []

    # --- Configuration for Restructuring ---
    first_person_start_col = 'Full Name'
    subsequent_person_start_col = 'Relationship to Household Reference Person'
    # Define household columns (usually at the start and maybe 'Remark' at the end)
    household_cols_start = [
        'Response ID', 'Timestamp', 'Download Status', 'Survey Code',
        'No. of Household Members'
    ]
    household_cols_end = ['Remark'] # Remark seems to be consistently at the very end

    # Filter columns to only those present in the DataFrame
    household_cols_start = [col for col in household_cols_start if col in df_wide.columns]
    household_cols_end = [col for col in household_cols_end if col in df_wide.columns]
    household_cols_all = household_cols_start + household_cols_end

    # --- Identify Column Blocks ---
    try:
        # Find all occurrences of the start columns
        # Note: pandas may add .1, .2, .3 suffixes to duplicate column names when reading
        first_person_indices = [i for i, col in enumerate(df_wide.columns) if col == first_person_start_col]
        subsequent_person_indices = [i for i, col in enumerate(df_wide.columns) 
                                    if col.startswith(subsequent_person_start_col)]

        if not first_person_indices:
            raise ValueError(f"Cannot find the starting column '{first_person_start_col}' for the first person.")

        first_p1_start_index = first_person_indices[0]

        # Determine the block for Person 1
        # It ends just before the first 'Relationship...' column (if it exists)
        first_p2_start_index = subsequent_person_indices[0] if subsequent_person_indices else -1

        if first_p2_start_index != -1:
            person_1_cols = df_wide.columns[first_p1_start_index:first_p2_start_index].tolist()
        else:
            # Only one person's data found, goes up to 'Remark' column (if exists)
            remark_index = df_wide.columns.get_loc(household_cols_end[0]) if household_cols_end else len(df_wide.columns)
            person_1_cols = df_wide.columns[first_p1_start_index:remark_index].tolist()

        base_generic_cols = person_1_cols # These are the target column names

        # Determine block size for subsequent persons by finding distance between "Relationship..." columns
        num_cols_per_extra_person = 0
        if len(subsequent_person_indices) >= 2:
            # Calculate distance between first two "Relationship..." columns
            num_cols_per_extra_person = subsequent_person_indices[1] - subsequent_person_indices[0]
            print(f"   Identified {len(person_1_cols)} cols for Person 1, {num_cols_per_extra_person} cols per subsequent person.")
        elif len(subsequent_person_indices) == 1:
            # Only one "Relationship..." found - calculate distance to Remark or end
            p2_start = subsequent_person_indices[0]
            remark_index = df_wide.columns.get_loc(household_cols_end[0]) if household_cols_end else len(df_wide.columns)
            num_cols_per_extra_person = remark_index - p2_start
            print(f"   Identified {len(person_1_cols)} cols for Person 1, {num_cols_per_extra_person} cols for Person 2 (only 1 subsequent person detected).")

    except Exception as e:
        print(f"❌ ERROR identifying column blocks: {e}. Cannot restructure.")
        # Return original df with placeholder Member_ID
        df_return = df_wide.copy()
        df_return[COL_MEMBER_ID] = 1
        return df_return

    # --- Process Each Row ---
    for index, row_wide in df_wide.iterrows():
        household_base_data = row_wide[household_cols_all]
        expected_num_members = row_wide.get('No. of Household Members', 1)
        
        # Try to convert to int
        try:
            expected_num_members = int(expected_num_members) if pd.notna(expected_num_members) else 1
        except:
            expected_num_members = 1

        # Detect actual number of member blocks with data (including beyond expected)
        # We scan all subsequent person blocks and count any block that has data, plus Person 1 if present
        remark_index = df_wide.columns.get_loc(household_cols_end[0]) if household_cols_end else len(df_wide.columns)
        actual_members_count = 0
        # Person 1 considered present if start col has data
        p1_has_data = pd.notna(row_wide.get(first_person_start_col))
        if p1_has_data:
            actual_members_count = 1
        # Count subsequent blocks with any data (relationship or any non-null field)
        if subsequent_person_indices and num_cols_per_extra_person > 0:
            for start_col_index in subsequent_person_indices:
                end_col_index = min(start_col_index + num_cols_per_extra_person, remark_index)
                member_cols_detect = df_wide.columns[start_col_index:end_col_index].tolist()
                if not member_cols_detect:
                    continue
                member_block = row_wide[member_cols_detect]
                rel_in_block = [c for c in member_cols_detect if c.startswith(subsequent_person_start_col)]
                rel_val_detect = member_block.get(rel_in_block[0]) if rel_in_block else None
                has_block_data = member_block.notna().any()
                if pd.notna(rel_val_detect) or has_block_data:
                    actual_members_count += 1

        # Process Member 1
        member_1_data = row_wide[person_1_cols]
        # Check if Person 1 has actual data (e.g., non-empty Full Name)
        if pd.isna(member_1_data.get(first_person_start_col)):
             print(f"   Skipping row index {index}: First person's '{first_person_start_col}' is empty.")
             continue # Skip this household row if P1 is empty

        member_1_series = pd.concat([household_base_data, member_1_data])
        member_1_series[COL_MEMBER_ID] = 1
        member_1_series[COL_RELATIONSHIP] = 'Reference Person' # Set relationship for P1
        # Add detected members count for household-level checks
        member_1_series['Detected Members (Auto)'] = actual_members_count
        all_members_data.append(member_1_series)

        # Process Members 2+ using ALL "Relationship..." column positions
        if subsequent_person_indices and num_cols_per_extra_person > 0:
            for member_num in range(2, expected_num_members + 1):
                # Find which "Relationship..." column corresponds to this member
                # Person 2 is at subsequent_person_indices[0]
                # Person 3 is at subsequent_person_indices[1], etc.
                person_index = member_num - 2  # 0-based index into subsequent_person_indices
                
                if person_index < len(subsequent_person_indices):
                    # Use the actual column position from subsequent_person_indices
                    start_col_index = subsequent_person_indices[person_index]
                    end_col_index = start_col_index + num_cols_per_extra_person
                else:
                    # Calculate position based on pattern
                    start_col_index = subsequent_person_indices[0] + (person_index * num_cols_per_extra_person)
                    end_col_index = start_col_index + num_cols_per_extra_person

                # Check bounds
                if start_col_index >= len(df_wide.columns):
                    break
                
                # Ensure we don't go past Remark or end of file
                remark_index = df_wide.columns.get_loc(household_cols_end[0]) if household_cols_end else len(df_wide.columns)
                end_col_index = min(end_col_index, remark_index)
                
                member_cols = df_wide.columns[start_col_index:end_col_index].tolist()
                
                if not member_cols:
                    break
                
                member_data = row_wide[member_cols]

                # Check if this member block actually has data
                # Find the relationship column (might have .1, .2, .3 suffix)
                rel_col_in_block = [c for c in member_cols if c.startswith(subsequent_person_start_col)]
                rel_val = member_data.get(rel_col_in_block[0]) if rel_col_in_block else None
                # Find any non-null value in the block
                has_data = member_data.notna().any()
                
                if pd.isna(rel_val) and not has_data:
                    # Completely empty block, stop processing
                    break

                member_series = pd.concat([household_base_data, member_data])
                member_series[COL_MEMBER_ID] = member_num
                # Add detected members count for household-level checks
                member_series['Detected Members (Auto)'] = actual_members_count

                # Rename columns: Map member_cols to base_generic_cols
                # Person 2+ has 70 columns: [Relationship, Full Name.1, Sex.1, ..., (last col).1]
                # Person 1 has 69 columns: [Full Name, Sex, ..., Relationship]
                # The structure is: Person 1 ends with Relationship, Person 2+ starts with Relationship
                # So: Person 2+ col[0] = Relationship → maps to COL_RELATIONSHIP
                #     Person 2+ col[1] = Full Name.1 → maps to Person 1 col[0] = Full Name
                #     Person 2+ col[2] = Sex.1 → maps to Person 1 col[1] = Sex
                #     ...
                #     Person 2+ col[69] = (last).1 → maps to Person 1 col[68] = Relationship (skip this)
                rename_map = {}
                for i, col_original in enumerate(member_cols):
                    if col_original.startswith(subsequent_person_start_col):
                        # First column is "Relationship to HRP"
                        rename_map[col_original] = COL_RELATIONSHIP
                    elif i > 0 and (i - 1) < len(base_generic_cols):
                        # Map Person 2+ col[1..69] to Person 1 col[0..68]
                        # But skip Person 1's last column (Relationship) if present
                        target_col = base_generic_cols[i - 1]
                        if not target_col.startswith(subsequent_person_start_col):
                            rename_map[col_original] = target_col

                member_series = member_series.rename(index=rename_map)
                all_members_data.append(member_series)

    # --- Combine and Finalize ---
    if not all_members_data:
        print("❌ ERROR: No member data could be extracted during restructuring.")
        # Return empty df with expected columns based on P1 + household + meta
        expected_cols = household_cols_all + [COL_MEMBER_ID, COL_RELATIONSHIP] + base_generic_cols
        return pd.DataFrame(columns=list(dict.fromkeys(expected_cols))) # Keep unique cols in order

    tidy_df = pd.DataFrame(all_members_data)

    # Reorder columns to a standard format (Household, Meta, Person)
    # Include helper column for household-level checks if present
    final_cols_order = household_cols_all + ['Detected Members (Auto)'] + [COL_MEMBER_ID, COL_RELATIONSHIP] + base_generic_cols
    # Ensure only unique columns present in the final DataFrame are selected
    final_cols_order_present = [col for col in list(dict.fromkeys(final_cols_order)) if col in tidy_df.columns]
    tidy_df = tidy_df[final_cols_order_present]


    # Drop rows that might be entirely empty except for household info and Member ID
    # Check for empty 'Relationship' - all valid members should have this field
    if COL_RELATIONSHIP in tidy_df.columns:
        tidy_df = tidy_df[tidy_df[COL_RELATIONSHIP].notna()]
    # Tidy DF might have duplicate columns if renaming failed, drop them
    tidy_df = tidy_df.loc[:,~tidy_df.columns.duplicated()]


    print(f"✅ Restructuring complete. Created {len(tidy_df)} person records.")
    return tidy_df


################################################################################
## 4. VALIDATION RULE FUNCTIONS
## All 176+ functions are pasted here.
################################################################################

################################################################################
## BATCH 1: VALIDATION FUNCTIONS (1-44)
##
## Instructions:
## 1. Copy these functions into your main 'main_validator.py' script.
## 2. CUSTOMIZE the column names in the section below to match your data.
## 3. Add the function names to the 'per_person_rules' or
##    'per_household_rules' lists in your 'run_validations' function.
##
################################################################################


# ##############################################################################
# ### CUSTOMIZE ### - ASSUMED COLUMN NAMES
# You MUST update these variable values to match the column names in your
# 'tidy_df' (long format) DataFrame.
# ##############################################################################

# --- Person Identifiers ---
COL_AGE = 'Age'                  # The calculated age of the person
COL_SEX = 'Sex'                  # e.g., 'Male', 'Female'
COL_RACE = 'Race'                # e.g., 'Chinese', 'Malay', 'Indian'
COL_MARITAL_STATUS = 'Marital Status' # e.g., 'Single', 'Married'
COL_ID_TYPE = 'Identification Type'   # e.g., 'Singapore Citizen', 'PR', 'Employment Pass'

# --- Household Structure ---
COL_RELATIONSHIP = 'Relationship to Household Reference Person' # e.g., 'Reference Person', 'Parent', 'Child'

# --- Location ---
COL_STAY_LOCATION = 'Where are you currently staying?' # e.g., 'In Singapore', 'Outside Singapore overseas'

# --- Employment & Occupation ---
COL_LABOUR_STATUS = 'Labour Force Status'        # e.g., 'Employed', 'Unemployed', 'Not in Labour Force'
COL_EMPLOYMENT_STATUS = 'Employment Status as of last week' # e.g., 'Employee', 'Own Account Worker', 'Employer'
COL_JOB_TITLE = 'Job Title'                    # e.g., 'Private Hire Driver', 'Civil Engineer'
# ### NOTE ###: Rules (e.g. 8-9, 85-89) imply an Occupation Code (SSOC).
# Your list has 'Job Title'. I will assume this column holds either
# text (like 'Private Hire Driver') OR a code (like '52119').
# This may need to be adjusted if 'Job Title' is text-only and
# another column holds the SSOC code.
COL_OCCUPATION_CODE = 'Job Title'
COL_INDUSTRY = 'Establishment Industry working last week?' # e.g., 'Construction', 'Financial Services'
COL_ABSENCE_HOURS = 'Hours of absence'
# ### NOTE ###: Rule 4 mentions a checkbox. Your column list does not
# include it. I am using a placeholder name.
# You MUST update this or adjust the logic in 'check_absence_hours'.
COL_ABSENCE_UNABLE = 'ASSUMED_Checkbox_for_Absence_Hours'
COL_PART_TIME_REASON = 'Reason that working part time rather than full time?'
COL_WILLING_TO_WORK_ADDITIONAL_HOURS = 'Willing to work additional hours?'
COL_AVAILABLE_FOR_ADDITIONAL_WORK = 'Available for additional work?'
COL_TYPE_OF_EMPLOYMENT = 'Type of Employment?' # e.g., 'Casual/On-call'

# --- Education ---
COL_HIGHEST_ACADEMIC_QUAL = 'Highest Academic Qualification' # e.g., 'Secondary', 'Degree'
COL_EDU_STATUS = 'Current Educational Status'      # e.g., 'Enrolled', 'Not Enrolled'

# --- Not in Labour Force ---
COL_REASON_NOT_WORKING = 'Main Reason for not working & not looking for job?'

# --- Unemployment ---
COL_UNEMPLOYMENT_WEEKS = 'How long have you been looking for a job? (in weeks)'


# ##############################################################################
# ### BATCH 1 FUNCTIONS
# ##############################################################################

# ---
# Rule 1 & 164 (Duplicate): A household must have 1 household reference person.
# Rule Type: Per-Household
# ---
def check_household_ref_person_count(household_df):
    errors = []
    ref_persons = household_df[household_df[COL_RELATIONSHIP] == 'Reference Person']
    
    if len(ref_persons) == 0:
        errors.append({'Error': 'Household has no Reference Person.'})
    elif len(ref_persons) > 1:
        errors.append({'Error': 'Household has more than one Reference Person.'})
    return errors

# ---
# Rule: Check if number of members matches declared household size
# Rule Type: Per-Household
# ---
def check_household_member_count(household_df):
    errors = []
    # Get expected number of members from the first row (should be the same for all rows in the household)
    expected = household_df.iloc[0].get(COL_NUM_MEMBERS)
    try:
        expected = int(expected)
    except Exception:
        expected = None
    actual = len(household_df)
    if expected is not None and actual != expected:
        errors.append({'Error': f"Household member count mismatch: declared {expected}, found {actual}."})
    return errors

# ---
# Rule 2 & 3: A private hire driver should be 30-74 years old and Singapore citizen.
# Rule Type: Per-Person
# ---
def check_private_hire_driver(row):
    errors = []
    # ### CUSTOMIZE ###: Update 'Private Hire Driver' text if needed
    if row.get(COL_JOB_TITLE) == 'Private Hire Driver':
        age = row.get(COL_AGE)
        id_type = row.get(COL_ID_TYPE)
        
        # ### CUSTOMIZE ###: Update 'Singapore Citizen' text if needed
        if id_type != 'Singapore Citizen':
            errors.append({'Error': f'Private Hire Driver must be a Singapore Citizen (ID Type: {id_type}).'})
        
        if age is not None:
            if age < 30:
                errors.append({'Error': f'Private Hire Driver is only {age} (must be >= 30).'})
            if age >= 75:
                errors.append({'Error': f'Private Hire Driver is {age} (must be < 75).'})
    return errors

# ---
# Rule 4: Absence hours... not blank, negative or more than 168 hours...
# Rule Type: Per-Person
# ---
def check_absence_hours(row):
    errors = []
    absence_hours = row.get(COL_ABSENCE_HOURS)
    unable_to_provide = row.get(COL_ABSENCE_UNABLE, False) # Assumes a checkbox column

    if pd.isna(absence_hours) and not unable_to_provide:
        errors.append({'Error': 'Absence hours is blank and "unable to provide" is not checked.'})
    elif pd.notna(absence_hours):
        # Convert to numeric to handle both string and int values
        try:
            hours_numeric = float(absence_hours)
            if not (0 <= hours_numeric <= 168):
                errors.append({'Error': f'Absence hours must be between 0 and 168, but was {absence_hours}.'})
        except (ValueError, TypeError):
            errors.append({'Error': f'Absence hours "{absence_hours}" is not a valid number.'})
    return errors

# ---
# Rule 5: Admin Data - DOB is wrong, please amend accordingly.
# Rule Type: Per-Person
# ---
def check_admin_dob_wrong(row):
    # This rule implies manual review or comparison against an external 'Admin Data' source
    # which we don't have. This function serves as a placeholder.
    # If you have an 'Admin_DOB' column, you could compare:
    # if row.get(COL_DOB) != row.get('Admin_DOB'):
    #     errors.append({'Error': 'DOB does not match Admin Data. Please review.'})
    return [] # Placeholder

# ---
# Rule 6: Are you sure a civil engineering/building construction labourer is not working in the construction industry?
# Rule Type: Per-Person
# ---
def check_construction_labourer_industry(row):
    errors = []
    # ### CUSTOMIZE ###: Update job titles and industry text
    job_titles = ['Civil Engineering Labourer', 'Building Construction Labourer']
    industry = row.get(COL_INDUSTRY)
    
    if row.get(COL_JOB_TITLE) in job_titles and industry != 'Construction':
        errors.append({'Error': f'Job is {row.get(COL_JOB_TITLE)} but industry is not Construction.'})
    return errors

# ---
# Rule 7: Are you sure a Employment Pass... holder is in an institutional unit... or outside Singapore...
# Rule Type: Per-Person
# ---
def check_pass_holder_location(row):
    errors = []
    # ### CUSTOMIZE ###: Update ID types and location text
    pass_types = ['Employment Pass', 'S Pass', 'Work Permit', 'Training Pass']
    locations = ['Institutional Unit', 'Outside Singapore overseas']
    
    if row.get(COL_ID_TYPE) in pass_types and row.get(COL_STAY_LOCATION) in locations:
        errors.append({'Error': f'Pass holder ({row.get(COL_ID_TYPE)}) has unusual location: {row.get(COL_STAY_LOCATION)}.'})
    return errors

# ---
# Rule 8 & 9: Are you sure a hawker/stall holder (excluding prepared food...) is working in the food courts...
# Rule Type: Per-Person
# ---
def check_hawker_industry(row):
    errors = []
    # ### CUSTOMIZE ###: This check is best done with Occupation Codes
    # Assuming '52119' is 'Hawker (excluding prepared food)'
    # Assuming '4781' is 'Food courts, coffee shops...'
    
    occ_code = str(row.get(COL_OCCUPATION_CODE))
    ind_code = str(row.get(COL_INDUSTRY)) # Assuming industry can also be a code
    
    if occ_code == '52119' and ind_code.startswith('4781'):
        errors.append({'Error': 'Occupation 52119 (Hawker excl. food) in Industry 4781 (Food courts). Check if 52120.'})
    return errors

# ---
# Rule 10: Are you sure a legislator... is not working in the central bank or provident funding industry?
# Rule Type: Per-Person
# ---
def check_legislator_industry(row):
    errors = []
    # ### CUSTOMIZE ###: Update job titles and industries
    job_titles = ['Legislator', 'Senior Government Official', 'Stat Board Official']
    industries = ['Central Bank', 'Provident Funding']
    
    if row.get(COL_JOB_TITLE) in job_titles and row.get(COL_INDUSTRY) not in industries:
        errors.append({'Error': f'Job is {row.get(COL_JOB_TITLE)} but industry is not Central Bank/Provident Funding.'})
    return errors

# ---
# Rule 11: Are you sure a male respondent is working part-time to look after his own children...
# Rule Type: Per-Person
# ---
def check_male_part_time_reason_childcare(row):
    errors = []
    # ### CUSTOMIZE ###: Update reason text
    reason = 'Care for own children aged 12 & below'
    
    if row.get(COL_SEX) == 'Male' and row.get(COL_PART_TIME_REASON) == reason:
        errors.append({'Error': 'Male respondent working part-time for childcare. Please verify.'})
    return errors

# ---
# Rule 12: Are you sure a married household reference person has a partner staying in the same household?
# Rule Type: Per-Household
# ---
def check_married_hrp_has_partner(household_df):
    errors = []
    hrp = household_df[household_df[COL_RELATIONSHIP] == 'Reference Person']
    
    if hrp.empty:
        return errors # Handled by rule 1
        
    hrp = hrp.iloc[0]
    
    # ### CUSTOMIZE ###: Update 'Married' status and partner relationships
    if hrp.get(COL_MARITAL_STATUS) == 'Married':
        partners = household_df[household_df[COL_RELATIONSHIP].isin(['Partner', 'Husband/Wife'])]
        if partners.empty:
            errors.append({'Error': 'Married HRP has no partner/spouse listed in the household.'})
    return errors

# ---
# Rule 13: Are you sure a person aged > 26 years is still a student on vacation job...
# Rule Type: Per-Person
# ---
def check_age_vs_student_job(row):
    errors = []
    age = row.get(COL_AGE)
    # ### CUSTOMIZE ###: Update labour statuses
    student_job_statuses = ['Student on vacation job', 'Paid internship', 'Awaiting examination results', 'Awaiting NS call-up']
    
    if age is not None and age > 26 and row.get(COL_LABOUR_STATUS) in student_job_statuses:
        errors.append({'Error': f'Person aged {age} has student-related labour status: {row.get(COL_LABOUR_STATUS)}.'})
    return errors

# ---
# Rule 14: Are you sure a person aged 15 has highest academic qualification is Secondary?
# Rule Type: Per-Person
# ---
def check_age_15_qualification(row):
    errors = []
    age = row.get(COL_AGE)
    # ### CUSTOMIZE ###: Update qualification text
    qual = 'Secondary' 
    
    if age == 15 and row.get(COL_HIGHEST_ACADEMIC_QUAL) == qual:
        errors.append({'Error': 'Person aged 15 has Secondary qualification. Please verify.'})
    return errors

# ---
# Rule 15: Are you sure a person in this occupation is in casual/on-call employment?
# Rule Type: Per-Person
# ---
def check_occupation_vs_casual(row):
    # This rule requires a list of occupations that are RARELY casual/on-call
    # ### CUSTOMIZE ###: Populate this list
    errors = []
    non_casual_jobs = ['Senior Government Official', 'Managing Director', 'Surgeon']
    
    if row.get(COL_JOB_TITLE) in non_casual_jobs and row.get(COL_TYPE_OF_EMPLOYMENT) == 'Casual/On-call':
        errors.append({'Error': f'Job is {row.get(COL_JOB_TITLE)} but employment type is Casual/On-call. Please verify.'})
    return [] # Placeholder

# ---
# Rule 16: Are you sure a person less than 18 years old is not enrolled in school?
# Rule Type: Per-Person
# ---
def check_age_vs_schooling(row):
    errors = []
    age = row.get(COL_AGE)
    # ### CUSTOMIZE ###: Update "not enrolled" statuses
    not_enrolled_statuses = ['Not Enrolled', 'Completed Education'] 

    if age is not None and age < 18 and row.get(COL_EDU_STATUS) in not_enrolled_statuses:
        errors.append({'Error': f'Person is {age} years old but is not enrolled in school (Status: {row.get(COL_EDU_STATUS)}).'})
    return errors

# ---
# Rule 17: Are you sure a person who is outside Singapore... is the household reference person?
# Rule Type: Per-Person
# ---
def check_household_hrp_location(household_df): # Renamed and takes household_df
    errors = []
    hrp = get_person_by_relationship(household_df, 'Reference Person')
    if hrp is None: return errors # No HRP found, another rule handles this

    # ### CUSTOMIZE ###: Update location text
    locations = ['Institutional Unit', 'Outside Singapore overseas for more than 6 months'] # Adjusted text
    current_location = str(hrp.get(COL_STAYING_WHERE,'')).strip()

    if current_location in locations:
        errors.append({'Error': f'Household Reference Person location is "{current_location}".'})
    return errors

# ---
# Rule 18: Are you sure a person working part-time... pursuing... studies is available for additional work?
# Rule Type: Per-Person
# ---
def check_pt_student_available(row):
    errors = []
    # ### CUSTOMIZE ###: Update reason and availability text
    reason = 'Pursuing full-time/part-time studies'
    availability = 'Yes' 
    
    if row.get(COL_PART_TIME_REASON) == reason and row.get(COL_AVAILABLE_FOR_ADDITIONAL_WORK) == availability:
        errors.append({'Error': 'Part-time student says they are available for additional work. Please verify.'})
    return errors

# ---
# Rule 19: Are you sure a person working part-time... pursuing... studies is willing to work additional hours?
# Rule Type: Per-Person
# ---
def check_pt_student_willing(row):
    errors = []
    # ### CUSTOMIZE ###: Update reason and willingness text
    reason = 'Pursuing full-time/part-time studies'
    willingness = 'Yes'
    
    if row.get(COL_PART_TIME_REASON) == reason and row.get(COL_WILLING_TO_WORK_ADDITIONAL_HOURS) == willingness:
        errors.append({'Error': 'Part-time student says they are willing to work additional hours. Please verify.'})
    return errors

# ---
# Rule 20: Are you sure a person who worked in this OCCUPATION is at this AGE and with this EDUCATION?
# Rule Type: Per-Person
# ---
def check_occupation_age_education_matrix(row):
    # This is a complex rule requiring an external "valid combinations" matrix.
    # Example: Flag if a 'Surgeon' (Job) is < 30 (Age) and has 'Secondary' (Education)
    # ### CUSTOMIZE ###: This check needs to be built out with your specific business logic.
    # job = row.get(COL_JOB_TITLE)
    # age = row.get(COL_AGE)
    # qual = row.get(COL_HIGHEST_ACADEMIC_QUAL)
    # if job == 'Surgeon' and age < 30 and qual == 'Secondary':
    #     errors.append({'Error': 'Unlikely Age/Education/Occupation combo: Surgeon, <30, Secondary.'})
    return [] # Placeholder

# ---
# Rule 21: Are you sure a person working part-time because he/she could not find a full-time job is not willing to work additional hours...
# Rule Type: Per-Person
# ---
def check_pt_no_full_time_willingness(row):
    errors = []
    # ### CUSTOMIZE ###: Update reason and willingness text
    reason = 'Could not find a full-time job'
    willingness = 'No'
    
    if row.get(COL_PART_TIME_REASON) == reason and row.get(COL_WILLING_TO_WORK_ADDITIONAL_HOURS) == willingness:
        errors.append({'Error': 'Works part-time (could not find full-time) but is NOT willing to work more hours. Please verify.'})
    return errors

# ---
# Rule 22: Are you sure a self-employed person is in these industries?
# Rule Type: Per-Person
# ---
def check_self_employed_industry(row):
    # This rule implies a list of *unlikely* industries for self-employed.
    # ### CUSTOMIZE ###: Populate this list
    errors = []
    unlikely_industries = ['Public Administration', 'Foreign Armed Forces']
    
    if row.get(COL_EMPLOYMENT_STATUS) == 'Own Account Worker' and row.get(COL_INDUSTRY) in unlikely_industries:
        errors.append({'Error': f'Self-employed (Own Account Worker) in unlikely industry: {row.get(COL_INDUSTRY)}.'})
    return [] # Placeholder

# ---
# Rule 23: Are you sure a tertiary educated person aged below 40 is not working... because... no suitable work available...
# Rule Type: Per-Person
# ---
def check_tertiary_under_40_not_working_reason(row):
    errors = []
    age = row.get(COL_AGE)
    # ### CUSTOMIZE ###: Update qualifications, status, and reasons
    tertiary_quals = ['Degree', 'Diploma', 'Masters', 'PhD']
    not_working_status = 'Not in Labour Force'
    unlikely_reasons = ['No suitable work available', 'Lacks necessary qualifications/skills']
    
    if (row.get(COL_HIGHEST_ACADEMIC_QUAL) in tertiary_quals and
        age is not None and age < 40 and
        row.get(COL_LABOUR_STATUS) == not_working_status and
        row.get(COL_REASON_NOT_WORKING) in unlikely_reasons):
        errors.append({'Error': f'Tertiary educated person < 40 not working due to: {row.get(COL_REASON_NOT_WORKING)}. Please verify.'})
    return errors

# ---
# Rule 24: Are you sure age difference between... is less than 15 years?
# Rule Type: Per-Household
# ---
def check_various_age_gaps_lt_15(household_df):
    errors = []
    # This rule is complex and relies on specific relationship codes/text.
    # ### CUSTOMIZE ###: Update relationship text
    relationships = {
        'HRP': household_df[household_df[COL_RELATIONSHIP] == 'Reference Person'],
        'SPOUSE': household_df[household_df[COL_RELATIONSHIP] == 'Husband/Wife'],
        'SON': household_df[household_df[COL_RELATIONSHIP] == 'Son'],
        'SON_IN_LAW': household_df[household_df[COL_RELATIONSHIP] == 'Son-in-law'],
        'PARENT_IN_LAW': household_df[household_df[COL_RELATIONSHIP] == 'Parent-in-law'],
        'GRANDSON': household_df[household_df[COL_RELATIONSHIP] == 'Grandson'],
    }
    
    # Helper to check pairs
    def check_gap(person1_df, person2_df, p1_name, p2_name):
        if not person1_df.empty and not person2_df.empty:
            p1_age = person1_df.iloc[0].get(COL_AGE)
            p2_age = person2_df.iloc[0].get(COL_AGE)
            if p1_age is not None and p2_age is not None and abs(p1_age - p2_age) < 15:
                errors.append({'Error': f'Age gap between {p1_name} (Age {p1_age}) and {p2_name} (Age {p2_age}) is < 15 years.'})

    # (i) parents-in-law and husband/wife of HRP
    check_gap(relationships['PARENT_IN_LAW'], relationships['SPOUSE'], 'Parent-in-law', 'Spouse')
    # (ii) son and grandson
    check_gap(relationships['SON'], relationships['GRANDSON'], 'Son', 'Grandson')
    # (iii) son-in-law and grandson
    check_gap(relationships['SON_IN_LAW'], relationships['GRANDSON'], 'Son-in-law', 'Grandson')
    
    return errors

# ---
# Rule 25: Are you sure age difference between child and household reference person is less than 15 years?
# Rule Type: Per-Household
# ---
def check_hrp_child_age_gap(household_df):
    errors = []
    hrp = household_df[household_df[COL_RELATIONSHIP] == 'Reference Person']
    if hrp.empty:
        return errors
        
    hrp_age = hrp.iloc[0].get(COL_AGE)
    if hrp_age is None:
        return errors
        
    # ### CUSTOMIZE ###: Update 'Child' relationship text
    children = household_df[household_df[COL_RELATIONSHIP] == 'Child']
    for _, child in children.iterrows():
        child_age = child.get(COL_AGE)
        if child_age is not None and (hrp_age - child_age) < 15:
            errors.append({'Error': f'Age gap between HRP (Age {hrp_age}) and Child (Age {child_age}) is < 15 years.'})
    return errors

# ---
# Rule 26: Are you sure age difference between the parents to the household reference person is more than 15 years?
# Rule Type: Per-Household
# ---
def check_hrp_parent_age_gap(household_df):
    errors = []
    # ### CUSTOMIZE ###: Update 'Parent' relationship text
    parents = household_df[household_df[COL_RELATIONSHIP] == 'Parent']
    
    if len(parents) == 2:
        age1 = parents.iloc[0].get(COL_AGE)
        age2 = parents.iloc[1].get(COL_AGE)
        if age1 is not None and age2 is not None and abs(age1 - age2) > 15:
            errors.append({'Error': f'Age gap between HRP\'s parents (Age {age1}, {age2}) is > 15 years.'})
    return errors

# ---
# Rule 27: Are you sure an own account worker is working as a managing director...
# Rule Type: Per-Person
# ---
def check_own_account_worker_job_title(row):
    errors = []
    # ### CUSTOMIZE ###: Update status and job titles
    status = 'Own Account Worker'
    unlikely_jobs = ['Managing Director', 'Chief Executive', 'General Manager']
    
    if row.get(COL_EMPLOYMENT_STATUS) == status and row.get(COL_JOB_TITLE) in unlikely_jobs:
        errors.append({'Error': f'Person is {status} but job is {row.get(COL_JOB_TITLE)}. Please verify.'})
    return errors

# ---
# Rule 28: Are you sure an own account worker is working in this occupation?
# Rule Type: Per-Person
# ---
def check_own_account_worker_occupation(row):
    # This rule is vague and requires a list of disallowed occupations.
    # ### CUSTOMIZE ###: Populate this list
    errors = []
    disallowed_occ = ['Police Officer', 'Government Clerk'] # Example
    
    if (row.get(COL_EMPLOYMENT_STATUS) == 'Own Account Worker' and 
        row.get(COL_OCCUPATION_CODE) in disallowed_occ):
        errors.append({'Error': 'Own Account Worker in unlikely occupation. Please verify.'})
    return [] # Placeholder

# ---
# Rule 29: Are you sure employment status for babysitter is not Own Account Worker?
# Rule Type: Per-Person
# ---
def check_babysitter_employment_status(row):
    errors = []
    # ### CUSTOMIZE ###: Update job title and status
    if (row.get(COL_JOB_TITLE) == 'Babysitter' and 
        row.get(COL_EMPLOYMENT_STATUS) != 'Own Account Worker'):
        errors.append({'Error': f'Babysitter employment status is {row.get(COL_EMPLOYMENT_STATUS)}, not Own Account Worker.'})
    return errors

# ---
# Rule 30: Are you sure employment status for cleaners, labourers... is Employer?
# Rule Type: Per-Person
# ---
def check_cleaner_labourer_employment_status(row):
    errors = []
    # ### CUSTOMIZE ###: Update job titles (or use occupation codes)
    job_group = ['Cleaner', 'Labourer', 'Related Worker'] # This is very broad, codes are better
    
    if (row.get(COL_JOB_TITLE) in job_group and 
        row.get(COL_EMPLOYMENT_STATUS) == 'Employer'):
        errors.append({'Error': f'Job is {row.get(COL_JOB_TITLE)} but employment status is Employer. Please verify.'})
    return errors

# ---
# Rule 31: Are you sure employment status of a person working as Management Executive is not Employee?
# Rule Type: Per-Person
# ---
def check_mgmt_exec_employment_status(row):
    errors = []
    # ### CUSTOMIZE ###: Update job title and status
    if (row.get(COL_JOB_TITLE) == 'Management Executive' and 
        row.get(COL_EMPLOYMENT_STATUS) != 'Employee'):
        errors.append({'Error': f'Management Executive status is {row.get(COL_EMPLOYMENT_STATUS)}, not Employee.'})
    return errors

# ---
# Rule 32 & 33: Are you sure household reference person and child are not of the same Identification Type?
# Rule Type: Per-Household
# ---
def check_hrp_child_id_type(household_df):
    errors = []
    hrp = household_df[household_df[COL_RELATIONSHIP] == 'Reference Person']
    if hrp.empty:
        return errors
        
    hrp_id = hrp.iloc[0].get(COL_ID_TYPE)
    # ### CUSTOMIZE ###: Update SC/PR values
    hrp_is_scpr = hrp_id in ['Singapore Citizen', 'Permanent Resident']
    
    children = household_df[household_df[COL_RELATIONSHIP] == 'Child']
    for _, child in children.iterrows():
        child_id = child.get(COL_ID_TYPE)
        child_is_scpr = child_id in ['Singapore Citizen', 'Permanent Resident']
        
        if child_is_scpr and not hrp_is_scpr:
            errors.append({'Error': f'Child is SC/PR (ID: {child_id}) but HRP is not (ID: {hrp_id}).'})
        if not child_is_scpr and hrp_is_scpr:
            errors.append({'Error': f'HRP is SC/PR (ID: {hrp_id}) but Child is not (ID: {child_id}).'})
    return errors

# ---
# Rule 34: Are you sure household reference person and his/her parent(s) are not of the same race?
# Rule Type: Per-Household
# ---
def check_hrp_parent_race(household_df):
    errors = []
    hrp = household_df[household_df[COL_RELATIONSHIP] == 'Reference Person']
    if hrp.empty:
        return errors
        
    hrp_race = hrp.iloc[0].get(COL_RACE)
    if hrp_race is None:
        return errors
        
    parents = household_df[household_df[COL_RELATIONSHIP] == 'Parent']
    for _, parent in parents.iterrows():
        parent_race = parent.get(COL_RACE)
        if parent_race is not None and parent_race != hrp_race:
            errors.append({'Error': f'HRP race ({hrp_race}) is different from Parent race ({parent_race}).'})
    return errors

# ---
# Rule 35: Are you sure household reference person and his/her wife/husband have different marital status?
# Rule Type: Per-Household
# ---
def check_hrp_spouse_marital_status(household_df):
    errors = []
    hrp = household_df[household_df[COL_RELATIONSHIP] == 'Reference Person']
    spouse = household_df[household_df[COL_RELATIONSHIP] == 'Husband/Wife']
    
    if not hrp.empty and not spouse.empty:
        hrp_status = hrp.iloc[0].get(COL_MARITAL_STATUS)
        spouse_status = spouse.iloc[0].get(COL_MARITAL_STATUS)
        
        if hrp_status is not None and spouse_status is not None and hrp_status != spouse_status:
            errors.append({'Error': f'HRP marital status ({hrp_status}) is different from Spouse status ({spouse_status}).'})
    return errors

# ---
# Rule 36: Are you sure household reference person is less than 18 years old?
# Rule Type: Per-Person
# ---
def check_household_hrp_age_lt_18(household_df): # Renamed and takes household_df
    errors = []
    hrp = get_person_by_relationship(household_df, 'Reference Person')
    if hrp is None: return errors

    age = hrp.get(COL_AGE) # Get age from the found HRP row (Series)

    if age is not None and age < 18:
        errors.append({'Error': f'Household Reference Person is aged {age} (< 18). Please verify.'})
    return errors

# ---
# Rule 37: Are you sure main reason for being outside... is housework... for respondent who is a male?
# Rule Type: Per-Person
# ---
def check_male_not_working_reason_housework(row):
    errors = []
    # ### CUSTOMIZE ###: Update status and reason text
    status = 'Not in Labour Force'
    reasons = ['Doing housework', 'Looking after children']
    
    if (row.get(COL_SEX) == 'Male' and
        row.get(COL_LABOUR_STATUS) == status and
        row.get(COL_REASON_NOT_WORKING) in reasons):
        errors.append({'Error': f'Male is Not in Labour Force due to: {row.get(COL_REASON_NOT_WORKING)}. Please verify.'})
    return errors

# ---
# Rule 38: Are you sure main reason... is [Care for own children aged 12 and below] when the individual does not have a child aged 12 years and below?
# Rule Type: Per-Household (but checks for a specific person)
# ---
def check_not_working_reason_childcare(household_df):
    # This rule is complex. It checks a person's reason, then scans the household for their children.
    # This assumes we can identify a person's *own* children, which might not be possible
    # just from 'Relationship to HRP'. This is a placeholder.
    # A simpler check (less accurate) would be if *anyone* in the household is <= 12.
    
    errors = []
    # ### CUSTOMIZE ###: Update reason text
    reason = 'Care for own children aged 12 and below'
    
    # Find all people in the household who gave this reason
    respondents = household_df[household_df[COL_REASON_NOT_WORKING] == reason]
    
    if respondents.empty:
        return errors

    # Check if *any* child <= 12 exists in the household
    # ### CUSTOMIZE ###: This is a simplification.
    has_young_child = any(household_df[COL_AGE] <= 12)
    
    if not has_young_child:
        for index, respondent in respondents.iterrows():
            errors.append({
                'Error': 'Reason is "Care for children <= 12", but no children <= 12 found in household.',
                'Member_ID': respondent.get('Member_ID') # Flag the specific person
            })
    return errors
# 
# ---
# Rule 39: Are you sure male aged 25-45 years cannot find suitable work or need not work...
# Rule Type: Per-Person
# ---
def check_male_25_45_not_working_reason(row):
    errors = []
    age = row.get(COL_AGE)
    # ### CUSTOMIZE ###: Update status and reason text
    status = 'Not in Labour Force'
    reasons = ['No suitable work available', 'Sufficient financial support']
    if (
        row.get(COL_SEX) == 'Male'
        and (age is not None and 25 <= age <= 45)
        and row.get(COL_LABOUR_STATUS) == status
        and row.get(COL_REASON_NOT_WORKING) in reasons
    ):
        errors.append({
            'Error': (
                f'Male aged 25-45 is Not in Labour Force due to: '
                f"{row.get(COL_REASON_NOT_WORKING)}. Please verify."
            )
        })
    return errors
    reasons = ['No suitable work available', 'Sufficient financial support']
    if (
        row.get(COL_SEX) == 'Male'
        and (age is not None and 25 <= age <= 45)
        and row.get(COL_LABOUR_STATUS) == status
        and row.get(COL_REASON_NOT_WORKING) in reasons
    ):
        errors.append({
            'Error': (
                f'Male aged 25-45 is Not in Labour Force due to: '
                f"{row.get(COL_REASON_NOT_WORKING)}. Please verify."
            )
        })
    return errors
    reasons = ['No suitable work available', 'Sufficient financial support']
    if (row.get(COL_SEX) == 'Male' and
        (age is not None and 25 <= age <= 45) and
        row.get(COL_LABOUR_STATUS) == status and
        row.get(COL_REASON_NOT_WORKING) in reasons):
        errors.append({'Error': f'Male aged 25-45 is Not in Labour Force due to: {row.get(COL_REASON_NOT_WORKING)}. Please verify.'})
    return errors
    reasons = ['No suitable work available', 'Sufficient financial support']
    if (row.get(COL_SEX) == 'Male' and
        (age is not None and 25 <= age <= 45) and
        row.get(COL_LABOUR_STATUS) == status and
        row.get(COL_REASON_NOT_WORKING) in reasons):
        errors.append({'Error': f'Male aged 25-45 is Not in Labour Force due to: {row.get(COL_REASON_NOT_WORKING)}. Please verify.'})
    return errors
    reasons = ['No suitable work available', 'Sufficient financial support']
    
    if (row.get(COL_SEX) == 'Male' and
        (age is not None and 25 <= age <= 45) and
        row.get(COL_LABOUR_STATUS) == status and
        row.get(COL_REASON_NOT_WORKING) in reasons):
        errors.append({'Error': f'Male aged 25-45 is Not in Labour Force due to: {row.get(COL_REASON_NOT_WORKING)}. Please verify.'})
    return errors

# ---
# Rule 40: Are you sure marital status of BOTH parents is different?
# Rule Type: Per-Household
# ---
def check_hrp_parents_marital_status(household_df):
    errors = []
    # ### CUSTOMIZE ###: Update 'Parent' relationship text
    parents = household_df[household_df[COL_RELATIONSHIP] == 'Parent']
    
    if len(parents) == 2:
        status1 = parents.iloc[0].get(COL_MARITAL_STATUS)
        status2 = parents.iloc[1].get(COL_MARITAL_STATUS)
        if status1 is not None and status2 is not None and status1 != status2:
            errors.append({'Error': f'HRP\'s parents have different marital status: {status1} and {status2}.'})
    return errors

# ---
# Rule 41: Are you sure marital status of parent is single?
# Rule Type: Per-Household
# ---
def check_hrp_parent_is_single(household_df):
    errors = []
    # ### CUSTOMIZE ###: Update 'Parent' and 'Single' text
    parents = household_df[household_df[COL_RELATIONSHIP] == 'Parent']
    
    for _, parent in parents.iterrows():
        if parent.get(COL_MARITAL_STATUS) == 'Single':
            errors.append({'Error': 'HRP\'s parent has marital status "Single". Please verify.'})
    return errors

# ---
# Rule 42: Are you sure marital status of person aged less than or equal to 21 years is not 'single'?
# Rule Type: Per-Person
# ---
def check_age_le_21_marital_status(row):
    errors = []
    age = row.get(COL_AGE)
    
    if (age is not None and age <= 21 and
        row.get(COL_MARITAL_STATUS) != 'Single'):
        errors.append({'Error': f'Person aged {age} has marital status "{row.get(COL_MARITAL_STATUS)}", not Single.'})
    return errors

# ---
# Rule 43: Are you sure Parent is younger than household reference person (i.e. Age)?
# Rule Type: Per-Household
# ---
def check_hrp_parent_age_inversion(household_df):
    errors = []
    hrp = household_df[household_df[COL_RELATIONSHIP] == 'Reference Person']
    if hrp.empty:
        return errors
        
    hrp_age = hrp.iloc[0].get(COL_AGE)
    if hrp_age is None:
        return errors
        
    parents = household_df[household_df[COL_RELATIONSHIP] == 'Parent']
    for _, parent in parents.iterrows():
        parent_age = parent.get(COL_AGE)
        if parent_age is not None and parent_age < hrp_age:
            errors.append({'Error': f'Parent (Age {parent_age}) is younger than HRP (Age {hrp_age}).'})
    return errors

# ---
# Rule 44: Are you sure parent/parent-in-law is less than 30 years old?
# Rule Type: Per-Household
# ---
def check_parent_age_lt_30(household_df):
    errors = []
    # ### CUSTOMIZE ###: Update relationship text
    parents = household_df[household_df[COL_RELATIONSHIP].isin(['Parent', 'Parent-in-law'])]
    
    for _, parent in parents.iterrows():
        age = parent.get(COL_AGE)
        if age is not None and age < 30:
            errors.append({'Error': f'Parent/Parent-in-law (Rel: {parent.get(COL_RELATIONSHIP)}) is aged {age} (< 30). Please verify.'})
    return errors



################################################################################
## BATCH 2: VALIDATION FUNCTIONS (45-88)
##
## Instructions:
## 1. Copy these functions into your main 'main_validator.py' script.
## 2. CUSTOMIZE the column names in the section below to match your data.
## 3. Add the function names to the 'per_person_rules' or
##    'per_household_rules' lists in your 'run_validations' function.
##
################################################################################


# ##############################################################################
# ### CUSTOMIZE ### - ASSUMED COLUMN NAMES (Batch 2)
# You MUST update these variable values to match the column names in your
# 'tidy_df' (long format) DataFrame. Many are inherited from Batch 1.
# ##############################################################################

# --- Person Identifiers (from Batch 1) ---
COL_AGE = 'Age'
COL_SEX = 'Sex'
COL_ID_TYPE = 'Identification Type'
COL_MARITAL_STATUS = 'Marital Status'
COL_RACE = 'Race'

# --- Household Structure (from Batch 1) ---
COL_RELATIONSHIP = 'Relationship to Household Reference Person'

# --- Employment & Occupation (from Batch 1) ---
COL_LABOUR_STATUS = 'Labour Force Status'
COL_EMPLOYMENT_STATUS = 'Employment Status as of last week'
COL_JOB_TITLE = 'Job Title'
COL_OCCUPATION_CODE = 'Job Title' # Assumed to hold SSOC code
COL_INDUSTRY = 'Establishment Industry working last week?'
COL_PART_TIME_REASON = 'Reason that working part time rather than full time?'

# --- Education (from Batch 1) ---
COL_HIGHEST_ACADEMIC_QUAL = 'Highest Academic Qualification'
COL_EDU_STATUS = 'Current Educational Status'

# --- Unemployment (from Batch 1) ---
COL_UNEMPLOYMENT_WEEKS = 'How long have you been looking for a job? (in weeks)'

# --- NEW COLUMNS for Batch 2 ---
COL_EVER_WORKED = 'Ever worked before?'
COL_LEFT_LAST_JOB = 'When did you leave your last Job?'
COL_USUAL_HOURS = 'Usual hours of work'
COL_HIGHEST_ACADEMIC_ATTAINED_IN = 'Highest Academic Attained in?'
COL_VOCATIONAL_QUAL = 'Highest Vocational/Skills Qualifications?'
COL_EXTRA_HOURS = 'Extra Hours worked'
# ### NOTE ###: Rules 85-89 imply a *second* SSOC code column exists,
# but it is not in your list. I am using a placeholder.
# You MUST update this or adjust the logic.
COL_SSOC_TWIN_CODE = 'ASSUMED_SSOC_2020_Twin_Code_Column'


# ##############################################################################
# ### BATCH 2 FUNCTIONS
# ##############################################################################

# ---
# Rule 45: Are you sure person has been unemployed for 52 weeks and longer?
# Rule Type: Per-Person
# ---
def check_unemployment_duration_52_weeks(row):
    errors = []
    weeks = row.get(COL_UNEMPLOYMENT_WEEKS)
    if pd.notna(weeks) and weeks >= 52:
        errors.append({'Error': f'Person has been unemployed for {weeks} weeks (>= 52). Please verify.'})
    return errors

# ---
# Rule 46: Are you sure person is a single parent/grandparent?
# Rule Type: Per-Household
# ---
def check_single_parent_grandparent(household_df):
    errors = []
    # ### CUSTOMIZE ###: Update status and relationship text
    single_statuses = ['Single', 'Widowed', 'Divorced']
    child_rels = ['Child', 'Grandchild']
    
    for index, person in household_df.iterrows():
        is_single = person.get(COL_MARITAL_STATUS) in single_statuses
        if not is_single:
            continue
            
        # Check if this person is a parent/grandparent of anyone ELSE in the household
        # This is complex logic. A simpler check is to see if they are
        # single AND have a child/grandchild relationship *to the HRP*.
        # A true check requires mapping all relationships, which is not
        # feasible without knowing all relationship codes.
        
        # Simple Check: Is this person single AND has a child in the house?
        has_child_in_hh = not household_df[household_df[COL_RELATIONSHIP].isin(child_rels)].empty
        
        if is_single and has_child_in_hh:
            # This is a weak check. It flags *any* single person in a house with children.
            # A better check might be:
            is_parent_of_hrp = person.get(COL_RELATIONSHIP) == 'Parent'
            is_single_parent_of_hrp = is_parent_of_hrp and len(household_df[household_df[COL_RELATIONSHIP] == 'Parent']) == 1
            
            if is_single_parent_of_hrp:
                 errors.append({'Error': f'Person (Parent of HRP) may be a single parent. Please verify.', 'Member_ID': person.get('Member_ID')})
    return [] # Placeholder - This rule is too ambiguous

# ---
# Rule 47: Are you sure person is aged 100 years and above?
# Rule Type: Per-Person
# ---
def check_age_100_plus(row):
    errors = []
    age = row.get(COL_AGE)
    if age is not None and age >= 100:
        errors.append({'Error': f'Person is aged {age} (>= 100). Please verify.'})
    return errors

# ---
# Rule 48: Are you sure person working in a managerial or professional job only has primary or lower qualifications?
# Rule Type: Per-Person
# ---
def check_manager_qualification(row):
    errors = []
    # ### CUSTOMIZE ###: Update job titles and qualifications
    managerial_jobs = ['Manager', 'Director', 'Professional', 'Surgeon', 'Lawyer'] # Use codes if possible
    lower_quals = ['Primary', 'Lower Secondary']
    
    job = row.get(COL_JOB_TITLE)
    qual = row.get(COL_HIGHEST_ACADEMIC_QUAL)
    
    # Skip if job is missing/NaN
    if pd.isna(job) or job == '' or job is None:
        return errors
    
    # Simple text check (adjust as needed)
    if any(m in str(job) for m in managerial_jobs) and qual in lower_quals:
        errors.append({'Error': f'Job is "{job}" but qualification is "{qual}". Please verify.'})
    return errors

# ---
# Rule 49: Are you sure Singaporean male aged > 30 years has never worked before?
# Rule Type: Per-Person
# ---
def check_sg_male_gt_30_never_worked(row):
    errors = []
    age = row.get(COL_AGE)
    # ### CUSTOMIZE ###: Update ID type, sex, and ever-worked text
    if (row.get(COL_ID_TYPE) == 'Singapore Citizen' and
        row.get(COL_SEX) == 'Male' and
        (age is not None and age > 30) and
        row.get(COL_EVER_WORKED) == 'No'):
        errors.append({'Error': 'Singaporean male aged > 30 has never worked. Please verify.'})
    return errors

# ---
# Rule 50: Are you sure Singaporean or PR with degree qualifications is working in a clerical job?
# Rule Type: Per-Person
# ---
def check_scpr_degree_clerical_job(row):
    errors = []
    # ### CUSTOMIZE ###: Update ID types, qualifications, and job titles/codes
    id_types = ['Singapore Citizen', 'Permanent Resident']
    qual = 'Degree'
    clerical_jobs = ['Clerk', 'Admin Assistant'] # Use codes if possible
    
    if (row.get(COL_ID_TYPE) in id_types and
        row.get(COL_HIGHEST_ACADEMIC_QUAL) == qual and
        row.get(COL_JOB_TITLE) in clerical_jobs):
        errors.append({'Error': f'SC/PR with Degree is working as "{row.get(COL_JOB_TITLE)}". Please verify.'})
    return errors

# ---
# Rule 51: Are you sure Singaporean or PR with university & above qualifications is working in craftsmen & cleaning related job?
# Rule Type: Per-Person
# ---
def check_scpr_uni_craft_job(row):
    errors = []
    # ### CUSTOMIZE ###: Update ID types, qualifications, and job titles/codes
    id_types = ['Singapore Citizen', 'Permanent Resident']
    quals = ['Degree', 'Masters', 'PhD'] # Assuming 'University & above'
    craft_jobs = ['Cleaner', 'Labourer', 'Craftsman'] # Use codes if possible
    
    if (row.get(COL_ID_TYPE) in id_types and
        row.get(COL_HIGHEST_ACADEMIC_QUAL) in quals and
        row.get(COL_JOB_TITLE) in craft_jobs):
        errors.append({'Error': f'SC/PR with {row.get(COL_HIGHEST_ACADEMIC_QUAL)} is working as "{row.get(COL_JOB_TITLE)}". Please verify.'})
    return errors

# ---
# Rule 52: Are you sure Son/Daughter is older than household reference person?
# Rule Type: Per-Household
# ---
def check_hrp_child_age_inversion(household_df):
    errors = []
    hrp = household_df[household_df[COL_RELATIONSHIP] == 'Reference Person']
    if hrp.empty: return errors
    hrp_age = hrp.iloc[0].get(COL_AGE)
    if hrp_age is None: return errors
        
    children = household_df[household_df[COL_RELATIONSHIP].isin(['Son', 'Daughter', 'Child'])]
    for _, child in children.iterrows():
        child_age = child.get(COL_AGE)
        if child_age is not None and child_age > hrp_age:
            errors.append({'Error': f'Child (Age {child_age}) is older than HRP (Age {hrp_age}).'})
    return errors

# ---
# Rule 53: Are you sure the age difference between the household reference person and son-in-law/daughter-in-law is less than 15 years?
# Rule Type: Per-Household
# ---
def check_hrp_inlaw_age_gap(household_df):
    errors = []
    hrp = household_df[household_df[COL_RELATIONSHIP] == 'Reference Person']
    if hrp.empty: return errors
    hrp_age = hrp.iloc[0].get(COL_AGE)
    if hrp_age is None: return errors
        
    inlaws = household_df[household_df[COL_RELATIONSHIP].isin(['Son-in-law', 'Daughter-in-law'])]
    for _, inlaw in inlaws.iterrows():
        inlaw_age = inlaw.get(COL_AGE)
        if inlaw_age is not None and abs(hrp_age - inlaw_age) < 15:
            errors.append({'Error': f'Age gap between HRP (Age {hrp_age}) and {inlaw.get(COL_RELATIONSHIP)} (Age {inlaw_age}) is < 15 years.'})
    return errors

# ---
# Rule 54: Are you sure the certificate was not obtained in Singapore?
# Rule Type: Per-Person
# ---
def check_cert_location(row):
    errors = []
    # Safe normalize value
    val = row.get(COL_HIGHEST_ACADEMIC_ATTAINED_IN)
    if pd.isna(val):
        return errors
    text = str(val).strip()
    if text.lower() in ['', 'nan', 'na', 'n/a', 'none']:
        return errors
    # If it's clearly Singapore/local, no error; otherwise flag to verify (matching current messaging)
    if text.lower() not in ['singapore', 'local'] and 'polytechnic' in text.lower():
        errors.append({'Error': f'Highest Academic Attained in: "{text}". Please verify this is not Singapore.'})
    return errors

# ---
# Rule 55: Are you sure the child's race is neither that of the father nor mother?
# Rule Type: Per-Household
# ---
def check_child_parent_race_mismatch(household_df):
    errors = []
    # Placeholder – requires family linkage (father/mother/child) mapping.
    return errors

# ---
# Rule 56: Are you sure the current labour force status of a Student's Pass holder who is working is valid?
# Rule Type: Per-Person
# ---
def check_student_pass_labour_status(row):
    errors = []
    valid_student_statuses = [
        'Schooling but currently working in vacation job',
        'Schooling but currently undergoing paid internship',
        'Working while awaiting examination results',
        'Working while schooling'
    ]
    if (row.get(COL_ID_TYPE) == 'Student Pass' and
        row.get(COL_LABOUR_STATUS) == 'Employed' and
        row.get(COL_EMPLOYMENT_STATUS) not in valid_student_statuses):
        errors.append({'Error': f'Student Pass holder is Employed, but status is "{row.get(COL_EMPLOYMENT_STATUS)}". Please verify.'})
    return errors

# ---
# Rule 57: Are you sure the education institution awarding the ITE or related qualification is not ITE?
# Rule Type: Per-Person
# ---
def check_ite_institution(row):
    errors = []
    qual = row.get(COL_HIGHEST_ACADEMIC_QUAL)
    inst = row.get(COL_HIGHEST_ACADEMIC_ATTAINED_IN)
    if 'ITE' in str(qual) and 'ITE' not in str(inst):
        errors.append({'Error': f'Qualification is {qual} but institution is {inst} (not ITE). Please verify.'})
    return errors

# ---
# Rule 58: Are you sure the educational attainment of person aged 15 years is GCE 'N' level or higher?
# Rule Type: Per-Person
# ---
def check_age_15_qualification_level(row):
    errors = []
    age = row.get(COL_AGE)
    higher_quals = ['GCE N level', 'GCE O level', 'Secondary', 'GCE A level', 'Diploma', 'Degree']
    if age == 15 and row.get(COL_HIGHEST_ACADEMIC_QUAL) in higher_quals:
        errors.append({'Error': f'Person aged 15 has qualification "{row.get(COL_HIGHEST_ACADEMIC_QUAL)}". Please verify.'})
    return errors

# ---
# Rule 59: Are you sure the Pass holder is currently not working (i.e. unemployed)?
# Rule Type: Per-Person
# ---
def check_pass_holder_unemployed(row):
    errors = []
    pass_types = ['Employment Pass', 'S Pass', 'Work Permit', 'Training Pass']
    if (row.get(COL_ID_TYPE) in pass_types and row.get(COL_LABOUR_STATUS) == 'Unemployed'):
        errors.append({'Error': f'Pass holder ({row.get(COL_ID_TYPE)}) is Unemployed. Please verify.'})
    return errors

# ---
# Rule 60: Are you sure the foreigner who is working in Singapore is not an employee?
# Rule Type: Per-Person
# ---
def check_foreigner_not_employee(row):
    errors = []
    id_type = row.get(COL_ID_TYPE)
    is_foreigner = id_type not in ['Singapore Citizen', 'Permanent Resident']
    if (is_foreigner and row.get(COL_LABOUR_STATUS) == 'Employed' and row.get(COL_EMPLOYMENT_STATUS) != 'Employee'):
        errors.append({'Error': f'Foreigner ({id_type}) is Employed but status is "{row.get(COL_EMPLOYMENT_STATUS)}", not Employee. Please verify.'})
    return errors

# ---
# Rule 61 & 62: Health workers typically in Health & Social Services industry.
# Rule Type: Per-Person
# ---
def check_health_worker_industry(row):
    errors = []
    health_jobs = ['Health Services Manager', 'Medical Doctor', 'Nursing Professional', 'Dentist', 'Physiotherapist']
    health_industry = 'Health & Social Services'
    if (row.get(COL_JOB_TITLE) in health_jobs and row.get(COL_INDUSTRY) != health_industry):
        errors.append({'Error': f'Job is {row.get(COL_JOB_TITLE)} but industry is "{row.get(COL_INDUSTRY)}", not Health.'})
    return errors
# ---
# Rule 63: Are you sure the highest educational attainment of person aged = 18 is degree and above?
# Rule Type: Per-Person
# ---
def check_age_18_qualification_degree(row):
    errors = []
    age = row.get(COL_AGE)
    # ### CUSTOMIZE ###: Update qualifications
    degree_quals = ['Degree', 'Masters', 'PhD']
    
    if age == 18 and row.get(COL_HIGHEST_ACADEMIC_QUAL) in degree_quals:
        errors.append({'Error': f'Person aged 18 has qualification "{row.get(COL_HIGHEST_ACADEMIC_QUAL)}". Please verify.'})
    return errors

# ---
# Rule 64: Are you sure the highest educational attainment of person aged 18 and below is diploma related qualification?
# Rule Type: Per-Person
# ---
def check_age_le_18_qualification_diploma(row):
    errors = []
    age = row.get(COL_AGE)
    # ### CUSTOMIZE ###: Update qualifications
    diploma_quals = ['Diploma', 'Polytechnic Diploma']
    
    if (age is not None and age <= 18 and
        row.get(COL_HIGHEST_ACADEMIC_QUAL) in diploma_quals):
        errors.append({'Error': f'Person aged {age} has qualification "{row.get(COL_HIGHEST_ACADEMIC_QUAL)}". Please verify.'})
    return errors

# ---
# Rule 65: Are you sure the hours worked for a part-timer is 35 hours or more?
# Rule Type: Per-Person
# ---
def check_part_timer_hours(row):
    errors = []
    # ### CUSTOMIZE ###: Update part-time text
    hours = row.get(COL_USUAL_HOURS)
    
    if (row.get('Full Time or Part Time?') == 'Part Time' and
        pd.notna(hours) and hours >= 35):
        errors.append({'Error': f'Person is "Part Time" but works {hours} hours (>= 35). Please verify.'})
    return errors

# ---
# Rule 66: Are you sure the household reference person and husband/wife are of the same sex?
# Rule Type: Per-Household
# ---
def check_hrp_spouse_same_sex(household_df):
    errors = []
    hrp = household_df[household_df[COL_RELATIONSHIP] == 'Reference Person']
    spouse = household_df[household_df[COL_RELATIONSHIP] == 'Husband/Wife']
    
    if not hrp.empty and not spouse.empty:
        hrp_sex = hrp.iloc[0].get(COL_SEX)
        spouse_sex = spouse.iloc[0].get(COL_SEX)
        
        if hrp_sex is not None and hrp_sex == spouse_sex:
            errors.append({'Error': f'HRP ({hrp_sex}) and Spouse ({spouse_sex}) are of the same sex. Amend relationship to "Partner".'})
    return errors

# ---
# Rule 67: Are you sure the identification type is dependant pass?
# Rule Type: Per-Person
# ---
def check_id_type_dependant_pass(row):
    errors = []
    # This rule flags *all* Dependant Pass holders for review.
    # ### CUSTOMIZE ###: Update ID type text
    if row.get(COL_ID_TYPE) == 'Dependant Pass':
        errors.append({'Error': 'ID Type is "Dependant Pass". Please verify this is correct (not Social Visit Pass).'})
    return errors

# ---
# Rule 68: Are you sure the industry of a Judge, Government associate professionals... is not in the public administration & defence?
# Rule Type: Per-Person
# ---
def check_judge_govt_industry(row):
    errors = []
    # ### CUSTOMIZE ###: Update job titles and industry
    job_titles = ['Judge', 'Government Associate Professional', 'Police Officer', 'Narcotics Officer', 'Prison Officer']
    industry = 'Public Administration & Defence'
    
    if (row.get(COL_JOB_TITLE) in job_titles and
        row.get(COL_INDUSTRY) != industry):
        errors.append({'Error': f'Job is {row.get(COL_JOB_TITLE)} but industry is "{row.get(COL_INDUSTRY)}", not {industry}.'})
    return errors

# ---
# Rule 69: Are you sure the industry of a primary school teacher is not primary school?
# Rule Type: Per-Person
# ---
def check_primary_teacher_industry(row):
    errors = []
    # ### CUSTOMIZE ###: Update job title and industry
    if (row.get(COL_JOB_TITLE) == 'Primary School Teacher' and
        row.get(COL_INDUSTRY) != 'Primary School'): # Or 'Education'
        errors.append({'Error': f'Job is Primary School Teacher but industry is "{row.get(COL_INDUSTRY)}".'})
    return errors

# ---
# Rule 70: Are you sure the industry of a secondary school teacher is not secondary school?
# Rule Type: Per-Person
# ---
def check_secondary_teacher_industry(row):
    errors = []
    # ### CUSTOMIZE ###: Update job title and industry
    if (row.get(COL_JOB_TITLE) == 'Secondary School Teacher' and
        row.get(COL_INDUSTRY) != 'Secondary School'): # Or 'Education'
        errors.append({'Error': f'Job is Secondary School Teacher but industry is "{row.get(COL_INDUSTRY)}".'})
    return errors

# ---
# Rule 71: Are you sure the industry of an education and training institution manager or relief teacher is not Education industry?
# Rule Type: Per-Person
# ---
def check_education_manager_industry(row):
    errors = []
    # ### CUSTOMIZE ###: Update job titles and industry
    job_titles = ['Education and Training Institution Manager', 'Relief Teacher']
    
    if (row.get(COL_JOB_TITLE) in job_titles and
        row.get(COL_INDUSTRY) != 'Education'):
        errors.append({'Error': f'Job is {row.get(COL_JOB_TITLE)} but industry is "{row.get(COL_INDUSTRY)}", not Education.'})
    return errors

# ---
# Rule 72: Are you sure the industry of this person is not in financial & insurance services?
# Rule Type: Per-Person
# ---
def check_finance_job_industry(row):
    errors = []
    # ### CUSTOMIZE ###: Update job titles (codes are better) and industry
    finance_jobs = ['Financial Analyst', 'Insurance Agent', 'Bank Teller']
    finance_industry = 'Financial & Insurance Services'
    
    if (row.get(COL_JOB_TITLE) in finance_jobs and
        row.get(COL_INDUSTRY) != finance_industry):
        errors.append({'Error': f'Job is {row.get(COL_JOB_TITLE)} but industry is "{row.get(COL_INDUSTRY)}", not Finance.'})
    return errors

# ---
# Rule 73: Are you sure the main reason for working part-time... is to care for own children... when the individual does not have a child aged 12 years and below...
# Rule Type: Per-Household
# ---
def check_pt_reason_childcare_no_child(household_df):
    # This is logicially identical to Rule 38, but for Part-Time Reason.
    errors = []
    # ### CUSTOMIZE ###: Update reason text
    reason = 'Care for own children aged 12 and below' # Check this text against part-time reasons
    
    respondents = household_df[household_df[COL_PART_TIME_REASON] == reason]
    if respondents.empty:
        return errors

    has_young_child = any(household_df[COL_AGE] <= 12)
    
    if not has_young_child:
        for index, respondent in respondents.iterrows():
            errors.append({
                'Error': 'PT reason is "Care for children <= 12", but no children <= 12 found in household.',
                'Member_ID': respondent.get('Member_ID')
            })
    return errors

# ---
# Rule 74: Are you sure the person aged > 35 years is still pursuing full-time / part-time study...
# Rule Type: Per-Person
# ---
def check_age_gt_35_studying(row):
    errors = []
    age = row.get(COL_AGE)
    # ### CUSTOMIZE ###: Update education statuses
    studying_statuses = ['Pursuing full-time study', 'Pursuing part-time study', 'Awaiting start of academic year']
    
    if (age is not None and age > 35 and
        row.get(COL_EDU_STATUS) in studying_statuses):
        errors.append({'Error': f'Person aged {age} has student status: "{row.get(COL_EDU_STATUS)}". Please verify.'})
    return errors

# ---
# Rule 75: Are you sure the person works 1 hour every week?
# Rule Type: Per-Person
# ---
def check_usual_hours_one(row):
    errors = []
    hours = row.get(COL_USUAL_HOURS)
    if pd.notna(hours) and hours == 1:
        errors.append({'Error': 'Usual hours of work is 1. Please verify.'})
    return errors

# ---
# Rule 76: Are you sure the respondent on student's pass is aged above 25 years?
# Rule Type: Per-Person
# ---
def check_student_pass_age_gt_25(row):
    errors = []
    age = row.get(COL_AGE)
    if (row.get(COL_ID_TYPE) == 'Student Pass' and
        age is not None and age > 25):
        errors.append({'Error': f'Person on Student Pass is aged {age} (> 25). Please verify.'})
    return errors

# ---
# Rule 77: Are you sure the vocational/WSQ certificate was not obtained in Singapore?
# Rule Type: Per-Person
# ---
def check_vocational_cert_location(row):
    errors = []
    # This rule is vague. It could refer to 'Highest Academic Attained in?'
    # or a different column for vocational qualifications.
    # ### CUSTOMIZE ###: Update 'Singapore' text
    qual = row.get(COL_VOCATIONAL_QUAL)
    inst = row.get(COL_HIGHEST_ACADEMIC_ATTAINED_IN) # Assuming same institution column
    
    # Skip if qual or inst is missing/NaN/empty
    if pd.isna(qual) or pd.isna(inst) or qual == '' or inst == '' or qual is None or inst is None or inst == 'NA':
        return errors
    
    # Only flag if vocational qual contains WSQ AND institution is NOT Singapore/Local
    if 'WSQ' in str(qual) and inst not in ['Singapore', 'Local']:
        errors.append({'Error': f'Vocational/WSQ cert obtained in "{inst}". Please verify this is not Singapore.'})
    return errors

# ---
# Rule 78: Are you sure this person left his last job more than 40 years ago?
# Rule Type: Per-Person
# ---
def check_left_last_job_40_years(row):
    errors = []
    # This rule is tricky. 'When did you leave your last Job?' could be a date or text.
    # Assuming it's text like "More than 40 years ago"
    # ### CUSTOMIZE ###: Update text
    if row.get(COL_LEFT_LAST_JOB) == 'More than 40 years ago':
        errors.append({'Error': 'Person left last job > 40 years ago. Please verify.'})
    return errors

# ---
# Rule 79: Certificate (under Highest Academic Qualification) is awarded by the Polytechnics...
# Rule Type: Per-Person
# ---
def check_poly_cert_institution(row):
    errors = []
    # ### CUSTOMIZE ###: Update qual and institution text
    qual = row.get(COL_HIGHEST_ACADEMIC_QUAL)
    inst = row.get(COL_HIGHEST_ACADEMIC_ATTAINED_IN)
    
    if 'Polytechnic' in str(inst) and 'Certificate' in str(qual):
        if 'ITE' in str(inst) or 'University' in str(inst): # Simplified check
            errors.append({'Error': f'Polytechnic Certificate (Academic) awarded by {inst}. Please verify.'})
    return errors

# ---
# Rule 80: Certificate (under vocational qualification) is 'LaSalle-SIA Diploma'...
# Rule Type: Per-Person
# ---
def check_lasalle_diploma(row):
    errors = []
    # ### CUSTOMIZE ###: Update qual and institution text
    qual = row.get(COL_VOCATIONAL_QUAL)
    inst = row.get(COL_HIGHEST_ACADEMIC_ATTAINED_IN) # Assuming same institution col
    
    if qual == 'LaSalle-SIA Diploma' and 'LaSalle' not in str(inst):
        errors.append({'Error': 'Vocational Qual is LaSalle-SIA Diploma but institution is not LaSalle.'})
    return errors

# ---
# Rule 81: Certificate (under vocational qualification) is 'NAFA Diploma'...
# Rule Type: Per-Person
# ---
def check_nafa_diploma(row):
    errors = []
    # ### CUSTOMIZE ###: Update qual and institution text
    qual = row.get(COL_VOCATIONAL_QUAL)
    inst = row.get(COL_HIGHEST_ACADEMIC_ATTAINED_IN) # Assuming same institution col
    
    if qual == 'NAFA Diploma' and 'NAFA' not in str(inst):
        errors.append({'Error': 'Vocational Qual is NAFA Diploma but institution is not NAFA.'})
    return errors

# ---
# Rule 82: Employment status for Babysitter should be Own Account Worker.
# Rule Type: Per-Person
# ---
# This is a duplicate of Rule 29. You can call the same function:
# check_babysitter_employment_status(row)

# ---
# Rule 83: Employment status of Legislator, Senior Government... should be Employee.
# Rule Type: Per-Person
# ---
def check_legislator_employment_status(row):
    errors = []
    # ### CUSTOMIZE ###: Update job titles
    job_titles = ['Legislator', 'Senior Government Official', 'Stat Board Official', 'Judge', 'Government Associate Professional', 'Police Officer', 'Narcotics Officer', 'Prison Officer']
    
    if (row.get(COL_JOB_TITLE) in job_titles and
        row.get(COL_EMPLOYMENT_STATUS) != 'Employee'):
        errors.append({'Error': f'Job is {row.get(COL_JOB_TITLE)} but status is "{row.get(COL_EMPLOYMENT_STATUS)}", not Employee.'})
    return errors

# ---
# Rule 84: Extra hours worked per week should not be blank, negative or more than 168 hours.
# Rule Type: Per-Person
# ---
def check_extra_hours(row):
    errors = []
    extra_hours = row.get(COL_EXTRA_HOURS)
    
    # This rule is slightly different from absence hours (no checkbox).
    # Assumes blank is okay if 'Worked extra hours?' is 'No'.
    if row.get('Worked extra hours?') == 'Yes':
        if pd.isna(extra_hours):
            errors.append({'Error': 'Indicated extra hours worked, but "Extra Hours worked" is blank.'})
        elif not (0 <= extra_hours <= 168):
            errors.append({'Error': f'Extra hours must be between 0 and 168, but was {extra_hours}.'})
    return errors

# ---
# Rule 85: For this RELH, check that DOB is input correctly. Are you sure Age is less than 15?
# Rule Type: Per-Person
# ---
def check_relh_age_lt_15(row):
    errors = []
    age = row.get(COL_AGE)
    # This rule is vague. "RELH" could mean specific relationships.
    # ### CUSTOMIZE ###: Update this list
    rels_to_check = ['Parent', 'Parent-in-law', 'Spouse', 'Partner']
    
    if (row.get(COL_RELATIONSHIP) in rels_to_check and
        age is not None and age < 15):
        errors.append({'Error': f'Relationship is {row.get(COL_RELATIONSHIP)} but age is {age} (< 15). Please verify DOB.'})
    return errors

# ---
# Rule 86: For this SSOC 2024 code 13210 please select the following SSOC2020 codes: 13210/13291
# Rule Type: Per-Person
# ---
# def check_ssoc_13210(row):
#     errors = []
#     # ### CUSTOMIZE ###: Requires a "twin code" column.
#     if (str(row.get(COL_OCCUPATION_CODE)) == '13210' and
#         str(row.get(COL_SSOC_TWIN_CODE)) not in ['13210', '13291']):
#         errors.append({'Error': 'SSOC 2024 is 13210, but twin code is not 13210 or 13291.'})
#     return errors

# ---
# Rule 87: For this SSOC 2024 code 13410...
# Rule Type: Per-Person
# ---
# def check_ssoc_13410(row):
#     errors = []
#     if (str(row.get(COL_OCCUPATION_CODE)) == '13410' and
#         str(row.get(COL_SSOC_TWIN_CODE)) not in ['13459', '13410']):
#         errors.append({'Error': 'SSOC 2024 is 13410, but twin code is not 13459 or 13410.'})
#     return errors

# ---
# Rule 88: For this SSOC 2024 code 24132...
# Rule Type: Per-Person
# ---
# def check_ssoc_24132(row):
#     errors = []
#     if (str(row.get(COL_OCCUPATION_CODE)) == '24132' and
#         str(row.get(COL_SSOC_TWIN_CODE)) not in ['33492', '24132']):
#         errors.append({'Error': 'SSOC 2024 is 24132, but twin code is not 33492 or 24132.'})
#     return errors


# ##############################################################################
# ### BATCH 3 FUNCTIONS
# ##############################################################################

# ---
# Rule 89: For this SSOC 2024 code 25123...
# Rule Type: Per-Person
# ---
# def check_ssoc_25123(row):
#     errors = []
#     if (str(row.get(COL_OCCUPATION_CODE)) == '25123' and
#         str(row.get(COL_SSOC_TWIN_CODE)) not in ['21662', '21669', '25123']):
#         errors.append({'Error': 'SSOC 2024 is 25123, but twin code is not 21662, 21669, or 25123.'})
#     return errors

# ---
# Rule 90: For this SSOC 2024 code 73160...
# Rule Type: Per-Person
# ---
def check_ssoc_73160(row):
    errors = []
    if (str(row.get(COL_OCCUPATION_CODE)) == '73160' and
        str(row.get(COL_SSOC_TWIN_CODE)) not in ['71323', '73160']):
        errors.append({'Error': 'SSOC 2024 is 73160, but twin code is not 71323 or 73160.'})
    return errors

# ---
# Rule 91: Highest Vocational Qualification and Institution... NITEC/master NITEC...
# Rule Type: Per-Person
# ---
def check_nitec_institution(row):
    errors = []
    # ### CUSTOMIZE ###: Update qual and institution text
    qual = str(row.get(COL_VOCATIONAL_QUAL))
    inst = str(row.get(COL_HIGHEST_ACADEMIC_ATTAINED_IN)) # Assuming same col
    
    nitec_quals = ['NITEC', 'Master NITEC']
    disallowed_insts = ['University', 'Polytechnic', 'SkillsFuture Singapore', 'WDA', 'NAFA', 'LASALLE']
    
    if any(q in qual for q in nitec_quals) and any(i in inst for i in disallowed_insts):
        errors.append({'Error': f'Qualification is {qual} but institution is {inst}, which is disallowed.'})
    return errors

# ---
# Rule 92: Household reference person is a work permit holder but his/her husband/wife...
# Rule Type: Per-Household
# ---
def check_hrp_work_permit_family_pass(household_df):
    errors = []
    hrp = household_df[household_df[COL_RELATIONSHIP] == 'Reference Person']
    if hrp.empty: return errors
    
    # ### CUSTOMIZE ###: Update ID type text
    if hrp.iloc[0].get(COL_ID_TYPE) == 'Work Permit':
        family = household_df[household_df[COL_RELATIONSHIP].isin(['Husband/Wife', 'Child', 'Parent', 'Parent-in-law'])]
        disallowed_passes = ['Social Visit Pass', 'Dependant Pass']
        
        for _, member in family.iterrows():
            if member.get(COL_ID_TYPE) in disallowed_passes:
                errors.append({'Error': f'HRP is Work Permit holder, but {member.get(COL_RELATIONSHIP)} is on {member.get(COL_ID_TYPE)}.'})
    return errors

# ---
# Rule 93: Household reference person is married. Pls check if his/her wife/husband is staying in the same household...
# Rule Type: Per-Household
# ---
def check_married_hrp_has_spouse_in_hh(household_df):
    # This is a duplicate/variation of Rule 12
    errors = []
    hrp = household_df[household_df[COL_RELATIONSHIP] == 'Reference Person']
    if hrp.empty: return errors
    hrp = hrp.iloc[0]
    
    # ### CUSTOMIZE ###: Update 'Married' status
    if hrp.get(COL_MARITAL_STATUS) == 'Married':
        spouses = household_df[household_df[COL_RELATIONSHIP].isin(['Partner', 'Husband/Wife'])]
        if spouses.empty:
            errors.append({'Error': 'Married HRP has no spouse/partner listed in household. Please verify.'})
    return errors

# ---
# Rule 94: Household reference person is single/widowed/divorced and should not have a husband/wife.
# Rule Type: Per-Household
# ---
def check_single_hrp_no_spouse(household_df):
    errors = []
    hrp = household_df[household_df[COL_RELATIONSHIP] == 'Reference Person']
    if hrp.empty: return errors
    hrp = hrp.iloc[0]
    
    # ### CUSTOMIZE ###: Update statuses
    single_statuses = ['Single', 'Widowed', 'Divorced']
    
    if hrp.get(COL_MARITAL_STATUS) in single_statuses:
        spouses = household_df[household_df[COL_RELATIONSHIP].isin(['Partner', 'Husband/Wife'])]
        if not spouses.empty:
            errors.append({'Error': f'HRP is {hrp.get(COL_MARITAL_STATUS)} but a spouse/partner is listed in household.'})
    return errors

# ---
# Rule 95-99: Duration of unemployment vs. when person left last job.
# Rule Type: Per-Person
# ---
def check_unemployment_duration_vs_left_job(row):
    errors = []
    weeks = row.get(COL_UNEMPLOYMENT_WEEKS)
    left_job = row.get(COL_LEFT_LAST_JOB) # This is text, e.g., "1 month to less than 2 months ago"
    
    if pd.isna(weeks) or pd.isna(left_job):
        return errors

    # ### CUSTOMIZE ###: Update these text values to match your data exactly
    if left_job == '1 month to less than 2 months ago' and weeks >= 8:
        errors.append({'Error': f'Left job 1-2 months ago, but unemployment is {weeks} weeks (>= 8).'})
    elif left_job == '2 months to less than 3 months ago' and weeks >= 12:
        errors.append({'Error': f'Left job 2-3 months ago, but unemployment is {weeks} weeks (>= 12).'})
    elif left_job == '4 months to less than 5 months ago' and weeks >= 21:
        errors.append({'Error': f'Left job 4-5 months ago, but unemployment is {weeks} weeks (>= 21).'})
    elif left_job == '5 months to less than 6 months ago' and weeks >= 26:
        errors.append({'Error': f'Left job 5-6 months ago, but unemployment is {weeks} weeks (>= 26).'})
    elif left_job == '7 months to less than 8 months ago' and weeks >= 34:
        errors.append({'Error': f'Left job 7-8 months ago, but unemployment is {weeks} weeks (>= 34).'})
    
    return errors

# ---
# Rule 100: Industry of Singapore Armed Forces Personnel should be Armed Forces, Police or Civil Defence.
# Rule Type: Per-Person
# ---
def check_saf_industry(row):
    errors = []
    # ### CUSTOMIZE ###: Update job title and industry
    job = 'Singapore Armed Forces Personnel'
    valid_industries = ['Armed Forces', 'Police', 'Civil Defence']
    
    if row.get(COL_JOB_TITLE) == job and row.get(COL_INDUSTRY) not in valid_industries:
        errors.append({'Error': f'Job is {job} but industry is "{row.get(COL_INDUSTRY)}".'})
    return errors

# ---
# Rule 101: Industry of university, polytechnic & other higher education teachers...
# Rule Type: Per-Person
# ---
def check_university_teacher_industry(row):
    errors = []
    # ### CUSTOMIZE ###: Update job titles and industry codes
    job_titles = ['University Teacher', 'Polytechnic Teacher', 'Higher Education Teacher']
    ind_code = str(row.get(COL_INDUSTRY)) # Assuming industry is a code
    
    if row.get(COL_JOB_TITLE) in job_titles:
        if not (ind_code.startswith('85301') or ind_code.startswith('85509')): # Simplified
            errors.append({'Error': f'Job is {row.get(COL_JOB_TITLE)} but industry code is {ind_code}.'})
    return errors

# ---
# Rule 102: It is rare for someone aged below 20 to be working in such occupations.
# Rule Type: Per-Person
# ---
def check_age_lt_20_occupation(row):
    errors = []
    age = row.get(COL_AGE)
    
    # ### CUSTOMIZE ###: Populate this list with senior job titles/codes
    senior_jobs = ['Managing Director', 'Chief Executive', 'Surgeon', 'Lawyer', 'Senior Government Official']
    
    if age is not None and age < 20 and row.get(COL_JOB_TITLE) in senior_jobs:
        errors.append({'Error': f'Person is aged {age} (< 20) but job is "{row.get(COL_JOB_TITLE)}". Please verify.'})
    return errors

# ---
# Rule 103: Job offer received but no application submitted - please verify
# Rule Type: Per-Person
# ---
def check_job_offer_no_application(row):
    errors = []
    # ### CUSTOMIZE ###: Update 'Yes'/'No' text values
    submitted_apps = row.get(COL_JOB_SUBMITTED_APPLICATIONS)
    received_offers = row.get(COL_JOB_OFFERS_RECEIVED)
    
    if received_offers == 'Yes' and submitted_apps == 'No':
        errors.append({'Error': 'Received job offer(s) but submitted no applications. Please verify.'})
    return errors

# ---
# Rule 104: Marital status of Husband/Wife should be married or separated.
# Rule Type: Per-Person
# ---
def check_spouse_marital_status(row):
    errors = []
    # ### CUSTOMIZE ###: Update relationship and status text
    valid_statuses = ['Married', 'Separated']
    
    if (row.get(COL_RELATIONSHIP) == 'Husband/Wife' and
        row.get(COL_MARITAL_STATUS) not in valid_statuses):
        errors.append({'Error': f'Relationship is Husband/Wife but marital status is "{row.get(COL_MARITAL_STATUS)}".'})
    return errors

# ---
# Rule 105: NIE Diploma (under vocational qualification) should be awarded by NIE...
# Rule Type: Per-Person
# ---
def check_nie_diploma_institution(row):
    errors = []
    # ### CUSTOMIZE ###: Update qual and institution text
    qual = row.get(COL_VOCATIONAL_QUAL)
    inst = row.get(COL_HIGHEST_ACADEMIC_ATTAINED_IN) # Assuming same col
    
    if 'NIE Diploma' in str(qual) and 'NIE' not in str(inst):
        errors.append({'Error': f'Vocational Qual is {qual} but institution is {inst} (not NIE).'})
    return errors

# ---
# Rule 106: NRIC has a different HREFPIN in the previous month.
# Rule Type: Per-Person (Requires Previous Month Data)
# ---
def check_nric_hprefpin_change(row):
    # ### PLACEHOLDER ###
    # This check requires loading and merging data from the previous month.
    # The 'row' object would need to contain 'NRIC_current' and 'NRIC_previous'.
    # if row.get(COL_NRIC) != row.get('NRIC_previous'):
    #     errors.append({'Error': 'NRIC has changed from previous month. Please verify.'})
    return []

# ---
# Rule 107: Nursery farm worker or supervisor is referring to someone working in a place where young plants...
# Rule Type: Per-Person
# ---
def check_nursery_farm_worker_occupation(row):
    errors = []
    # ### CUSTOMIZE ###: Update job titles/codes
    job_titles = ['Nursery Farm Worker', 'Nursery Supervisor']
    
    if row.get(COL_JOB_TITLE) in job_titles:
        errors.append({'Error': f'Job is "{row.get(COL_JOB_TITLE)}". Verify this is for plants, not childcare.'})
    return errors

# ---
# Rule 108: 'Others' was selected, please see if it can be recoded.
# Rule Type: Per-Person
# ---
def check_others_selected(row):
    errors = []
    # This rule is too vague. It needs to know *which* "Others" column.
    # Example for 'Main Reason for not working':
    if row.get(COL_REASON_NOT_WORKING) == 'Others':
        errors.append({'Error': 'Reason not working is "Others". Please review remarks to recode if possible.'})
    return errors

# ---
# Rule 109: 'Others' was specified, interviewer has not indicated any remarks or has remarks with less than 10 characters.
# Rule Type: Per-Person
# ---
def check_others_specified_remarks(row):
    errors = []
    remarks = str(row.get(COL_REMARKS, '')) # Get remarks, default to empty string
    
    # This rule is vague. It needs to know *which* "Others" column to check.
    # Example for 'Main Reason for not working':
    if row.get(COL_REASON_NOT_WORKING) == 'Others' and len(remarks) < 10:
        errors.append({'Error': 'Reason not working is "Others" but remarks are missing or too short (< 10 chars).'})
    return errors

# ---
# Rule 110: Person aged > 16 years and is currently pursuing full-time study; his educational attainment should not be below primary qualification.
# Rule Type: Per-Person
# ---
def check_age_gt_16_student_qualification(row):
    errors = []
    age = row.get(COL_AGE)
    # ### CUSTOMIZE ###: Update status and qual text
    status = 'Pursuing full-time study'
    below_primary_quals = ['Below Primary', 'No Qualification'] 
    
    if (age is not None and age > 16 and
        row.get(COL_EDU_STATUS) == status and
        row.get(COL_HIGHEST_ACADEMIC_QUAL) in below_primary_quals):
        errors.append({'Error': f'Full-time student aged {age} has qualification "{row.get(COL_HIGHEST_ACADEMIC_QUAL)}".'})
    return errors

# ---
# Rule 111: Person aged > 20 years and is currently pursuing full-time study; his educational attainment should not be below secondary qualification.
# Rule Type: Per-Person
# ---
def check_age_gt_20_student_qualification(row):
    errors = []
    age = row.get(COL_AGE)
    # ### CUSTOMIZE ###: Update status and qual text
    status = 'Pursuing full-time study'
    below_secondary_quals = ['Below Primary', 'No Qualification', 'Primary']
    
    if (age is not None and age > 20 and
        row.get(COL_EDU_STATUS) == status and
        row.get(COL_HIGHEST_ACADEMIC_QUAL) in below_secondary_quals):
        errors.append({'Error': f'Full-time student aged {age} has qualification "{row.get(COL_HIGHEST_ACADEMIC_QUAL)}".'})
    return errors

# ---
# Rule 112 & 113: Person with NRIC /FIN beginning with 'S' or 'T' should be a SC/PR.
# Rule Type: Per-Person
# ---
def check_nric_s_t_is_scpr(row):
    errors = []
    nric = str(row.get(COL_NRIC, ''))
    # ### CUSTOMIZE ###: Update ID type text
    valid_types = ['Singapore Citizen', 'Permanent Resident']
    
    if (nric.startswith('S') or nric.startswith('T')) and (row.get(COL_ID_TYPE) not in valid_types):
        errors.append({'Error': f'NRIC starts with {nric[0]} but ID Type is "{row.get(COL_ID_TYPE)}".'})
    return errors

# ---
# Rule 114: Please check SSOC with Employment Status.
# Rule Type: Per-Person
# ---
def check_ssoc_with_employment_status(row):
    # This is a general rule, similar to 28, 29, 30, 31.
    # It requires a lookup table of valid/invalid combinations.
    # ### PLACEHOLDER ###
    return []

# ---
# Rule 115: Please confirm in system if DOB is input correctly as Age is 0.
# Rule Type: Per-Person
# ---
def check_age_0_dob(row):
    errors = []
    if row.get(COL_AGE) == 0:
        errors.append({'Error': 'Person is aged 0. Please verify DOB is correct.'})
    return errors

# ---
# Rule 116: Please enter digits without commas or decimals.
# Rule Type: Per-Person
# ---
def check_digits_no_commas(row):
    # This is a data-entry validation, not a post-collection check.
    # The data will already be a number (float/int) if read by pandas.
    # This rule is likely not applicable at this stage.
    return []

# ---
# Rule 117: Please verify identification type of this person. Foreign children of Singapore citizens/Permanent residents...
# Rule Type: Per-Household
# ---
def check_foreign_child_id_type(household_df):
    errors = []
    # ### CUSTOMIZE ###: Update ID types
    scpr_id_types = ['Singapore Citizen', 'Permanent Resident']
    
    # Find all HRPs who are SC/PR
    hrp = household_df[household_df[COL_RELATIONSHIP] == 'Reference Person']
    if hrp.empty: return errors
    
    if hrp.iloc[0].get(COL_ID_TYPE) in scpr_id_types:
        # Find their children
        children = household_df[household_df[COL_RELATIONSHIP] == 'Child']
        for _, child in children.iterrows():
            if child.get(COL_ID_TYPE) == 'Dependant Pass':
                errors.append({'Error': 'Child of SC/PR HRP is on "Dependant Pass". Please verify (should be Social Visit Pass?).', 'Member_ID': child.get('Member_ID')})
    return errors

# ---
# Rule 118: Please verify identification type of this person. Foreign husband/wife of Singapore citizens/Permanent residents...
# Rule Type: Per-Household
# ---
def check_foreign_spouse_id_type(household_df):
    errors = []
    # ### CUSTOMIZE ###: Update ID types
    scpr_id_types = ['Singapore Citizen', 'Permanent Resident']
    
    hrp = household_df[household_df[COL_RELATIONSHIP] == 'Reference Person']
    if hrp.empty: return errors
    
    if hrp.iloc[0].get(COL_ID_TYPE) in scpr_id_types:
        spouses = household_df[household_df[COL_RELATIONSHIP] == 'Husband/Wife']
        for _, spouse in spouses.iterrows():
            if spouse.get(COL_ID_TYPE) == 'Dependant Pass':
                errors.append({'Error': 'Spouse of SC/PR HRP is on "Dependant Pass". Please verify (should be Social Visit Pass?).', 'Member_ID': spouse.get('Member_ID')})
    return errors

# ---
# Rule 119: Please verify unemployment duration of respondent.
# Rule Type: Per-Person
# ---
def check_unemployment_duration_vs_time_since_last_job(row):
    # This rule is vague and likely a variation of 95-99.
    # It implies 'unemployment weeks' should be <= time since leaving job.
    # This requires converting 'When did you leave your last Job?' to weeks.
    # ### PLACEHOLDER ###
    return []

# ---
# Rule 120: R. is below 17 years old and has more than an O level education but is not in full-time studies.
# Rule Type: Per-Person
# ---
def check_age_lt_17_olevel_not_student(row):
    errors = []
    age = row.get(COL_AGE)
    # ### CUSTOMIZE ###: Update quals and status
    post_olevel_quals = ['GCE A level', 'Diploma', 'Degree']
    status = row.get(COL_EDU_STATUS)
    
    if (age is not None and age < 17 and
        row.get(COL_HIGHEST_ACADEMIC_QUAL) in post_olevel_quals and
        status != 'Pursuing full-time study'):
        errors.append({'Error': f'Person aged {age} has {row.get(COL_HIGHEST_ACADEMIC_QUAL)} but is not in full-time study.'})
    return errors

# ---
# Rule 121: R. is unemployed and 15-19 years old but is not enrolled in school/course/not awaiting NS callup while looking for work.
# Rule Type: Per-Person
# ---
def check_unemployed_15_19_not_student(row):
    errors = []
    age = row.get(COL_AGE)
    # ### CUSTOMIZE ###: Update statuses
    valid_looking_statuses = ['Enrolled in school/course', 'Awaiting NS callup']
    
    if (row.get(COL_LABOUR_STATUS) == 'Unemployed' and
        (age is not None and 15 <= age <= 19) and
        row.get(COL_LOOKING_FOR_WORK_STATUS) not in valid_looking_statuses):
        errors.append({'Error': f'Unemployed person aged {age} has looking-for-work status "{row.get(COL_LOOKING_FOR_WORK_STATUS)}".'})
    return errors

# ---
# Rule 122: R. is unemployed and 20-24 years old with upper secondary education but is not enrolled in school/course/not awaiting NS callup...
# Rule Type: Per-Person
# ---
def check_unemployed_20_24_upper_sec_not_student(row):
    errors = []
    age = row.get(COL_AGE)
    # ### CUSTOMIZE ###: Update quals and statuses
    quals = ['Upper Secondary', 'GCE A level'] # Define 'Upper secondary'
    valid_looking_statuses = ['Enrolled in school/course', 'Awaiting NS callup']
    
    if (row.get(COL_LABOUR_STATUS) == 'Unemployed' and
        (age is not None and 20 <= age <= 24) and
        row.get(COL_HIGHEST_ACADEMIC_QUAL) in quals and
        row.get(COL_LOOKING_FOR_WORK_STATUS) not in valid_looking_statuses):
        errors.append({'Error': f'Unemployed person aged {age} with {row.get(COL_HIGHEST_ACADEMIC_QUAL)} has looking-for-work status "{row.get(COL_LOOKING_FOR_WORK_STATUS)}".'})
    return errors

# ---
# Rule 123-130: Checks for changes from the previous month.
# Rule Type: Per-Person (Requires Previous Month Data)
# ---
def check_changes_from_previous_month(row):
    # This is a single placeholder for all "change" rules (123-130).
    # You would implement separate functions for each logic.
    # ### PLACEHOLDER ###
    # if row.get('UnemploymentDuration_current') > row.get('UnemploymentDuration_previous') + 5:
    #    errors.append({'Error': 'Unemployment duration increased by >= 5 weeks.'})
    # if row.get(COL_EDU_STATUS) != row.get('EDU_STATUS_previous'):
    #    errors.append({'Error': 'Educational status has changed. Please verify.'})
    return []

# ---
# Rule 131-132: Routing checks (e.g., -A10-, -A14-).
# Rule Type: Per-Person
# ---
# def check_routing_logic(row):
#     # This validates the survey's skip logic.
#     # e.g., If Q5='No', then Q6, Q7, Q8 must be blank.
#     # This is highly specific to your survey flow.
#     # ### PLACEHOLDER ###
#     # Example: If 'Have you ever retired' = 'No', 'What age retire' should be blank
#     if row.get('Have you ever retired from any job?') == 'No' and pd.notna(row.get('What age retire?')):
#         errors.append({'Error': 'Routing Error: Answered "No" to retired, but "What age retire?" is filled.'})
#     return []


################################################################################
## BATCH 4: VALIDATION FUNCTIONS (133-176)
##
## Instructions:
## 1. Copy these functions into your main 'main_validator.py' script.
## 2. CUSTOMIZE the column names in the section below to match your data.
## 3. Add the function names to the 'per_person_rules' or
##    'per_household_rules' lists in your 'run_validations' function.
##
################################################################################


# ##############################################################################
# ### CUSTOMIZE ### - ASSUMED COLUMN NAMES (Batch 4)
# You MUST update these variable values to match the column names in your
# 'tidy_df' (long format) DataFrame. Many are inherited from Batch 1-3.
# ##############################################################################

# --- From Previous Batches ---
COL_AGE = 'Age'
COL_ID_TYPE = 'Identification Type'
COL_MARITAL_STATUS = 'Marital Status'
COL_RELATIONSHIP = 'Relationship to Household Reference Person'
COL_EMPLOYMENT_STATUS = 'Employment Status as of last week'
COL_JOB_TITLE = 'Job Title'
COL_OCCUPATION_CODE = 'Job Title' # Assumed to hold SSOC code
COL_HIGHEST_ACADEMIC_QUAL = 'Highest Academic Qualification'
COL_TYPE_OF_EMPLOYMENT = 'Type of Employment?'
COL_UNEMPLOYMENT_WEEKS = 'How long have you been looking for a job? (in weeks)'
COL_LEFT_LAST_JOB = 'When did you leave your last Job?'

# --- NEW COLUMNS for Batch 4 ---
# ### NOTE ###: Rule 134 implies an SSOC twin code column.
COL_SSOC_TWIN_CODE = 'ASSUMED_SSOC_2020_Twin_Code_Column'
# ### NOTE ###: Rule 144 implies an NRIC/FIN column.
COL_NRIC = 'ASSUMED_NRIC_FIN_Column'
# ### NOTE ###: Rule 145 implies a GMI (Gross Monthly Income) column.
COL_GMI = 'GMI'
# ### NOTE ###: Rule 146 implies DOB and NRIC columns.
COL_DOB = 'Date of Birth (DD/MM/YYYY)'
# ### NOTE ###: Rule 147 implies a Member Number column.
COL_MEMBER_NO = 'ASSUMED_Member_No_Column'


# ##############################################################################
# ### BATCH 4 FUNCTIONS
# ##############################################################################

# ---
# Rule 133-143: More Routing checks.
# Rule Type: Per-Person
# # ---
# def check_routing_logic_batch_2(row):
#     # This is a continuation of the routing placeholders.
#     # You must implement the specific skip logic for your survey.
#     # e.g., check_routing_B1, check_routing_B2_OCC, etc.
#     # ### PLACEHOLDER ###
    
#     # Example for Rule 'Routing -JS_SUBMIT-':
#     # This might mean: If 'During your most recent job search...' == 'No',
#     # then 'How many have you submitted?' should be blank.
#     errors = []
#     if (row.get('During your most recent job search, did you submit any job applications...?') == 'No' and
#         pd.notna(row.get('How many have you submitted?'))):
#         errors.append({'Error': 'Routing Error: Answered "No" to submitting applications, but "How many" is filled.'})
#     return errors

# ---
# Rule 144: There are duplicated NRIC in the survey, please seek Ops assistance to resolve this.
# Rule Type: Global (Applied *before* household checks)
# ---
def check_duplicate_nric(full_tidy_df):
    errors = []
    if COL_NRIC not in full_tidy_df.columns:
         errors.append({'Error': f"Global Rule Error: Column '{COL_NRIC}' not found for duplicate check."})
         return errors

    # Drop empty values first
    nrics = full_tidy_df[full_tidy_df[COL_NRIC].notna() & (full_tidy_df[COL_NRIC] != '')][COL_NRIC]

    # Find unique duplicated values
    duplicates = nrics[nrics.duplicated()].unique()

    for nric_val in duplicates:
        # Find all rows with this duplicated value
        dup_rows = full_tidy_df[full_tidy_df[COL_NRIC] == nric_val]
        response_ids = dup_rows[COL_RESPONSE_ID].unique().tolist()
        member_ids = dup_rows[COL_MEMBER_ID].unique().tolist()

        errors.append({
            'Error': f'Duplicate {COL_NRIC} found: {nric_val}.',
            'Response IDs': str(response_ids),
            'Member IDs': str(member_ids)
        })
    return errors

# ---
# Rule 145: There are high income difference from previous month...
# Rule Type: Per-Person (Requires Previous Month Data)
# ---
def check_high_income_difference(row):
    # ### PLACEHOLDER ###
    # Requires merged row with 'GMI_current' and 'GMI_previous'.
    # current_gmi = row.get(COL_GMI)
    # prev_gmi = row.get('GMI_previous')
    # if pd.notna(current_gmi) and pd.notna(prev_gmi):
    #     if abs(current_gmi - prev_gmi) > 1000: # ### CUSTOMIZE ###: Define "high"
    #         errors.append({'Error': 'High income difference from previous month.'})
    return []

# ---
# Rule 146: There are more than one response with the same DOB and same last 5 characters in their NRIC.
# Rule Type: Global (Applied *before* household checks)
# ---
def check_duplicate_dob_nric_partial(full_tidy_df):
    errors = []
    if COL_NRIC not in full_tidy_df.columns or COL_DOB not in full_tidy_df.columns: # Check COL_DOB too
         missing_cols = [col for col in [COL_NRIC, COL_DOB] if col not in full_tidy_df.columns]
         errors.append({'Error': f"Global Rule Error: Column(s) '{', '.join(missing_cols)}' not found for partial duplicate check."})
         return errors

    # Create a copy to avoid modifying the original DataFrame
    df_copy = full_tidy_df[[COL_DOB, COL_NRIC, COL_RESPONSE_ID, COL_MEMBER_ID]].copy()

    # Ensure DOB is string for consistent comparison if needed, or rely on datetime objects if parsed
    # df_copy[COL_DOB] = df_copy[COL_DOB].astype(str) # Optional: if DOB format varies

    # Create 'nric_last5', handle potential errors if COL_NRIC is not string
    try:
        df_copy['nric_last5'] = df_copy[COL_NRIC].astype(str).str.strip().str[-5:]
    except Exception as e:
        errors.append({'Error': f"Global Rule Error: Could not extract last 5 chars from '{COL_NRIC}'. Reason: {e}"})
        return errors

    # Define key columns and remove rows where key info is missing
    key_cols = [COL_DOB, 'nric_last5']
    df_copy.dropna(subset=key_cols, inplace=True)
    df_copy = df_copy[df_copy['nric_last5'] != ''] # Exclude empty last 5

    # Find rows that are part of a duplicate group based on key_cols
    duplicates_mask = df_copy.duplicated(subset=key_cols, keep=False)
    duplicates_df = df_copy[duplicates_mask]

    if not duplicates_df.empty:
        # Group by the duplicate keys to report each unique duplication once
        grouped = duplicates_df.groupby(key_cols)
        for name, group in grouped:
            dob_val, nric5_val = name
            response_ids = group[COL_RESPONSE_ID].unique().tolist()
            member_ids = group[COL_MEMBER_ID].unique().tolist()
            errors.append({
                'Error': f'Potential duplicate found: DOB "{dob_val}" and {COL_NRIC} ending in "{nric5_val}".',
                'Response IDs': str(response_ids),
                'Member IDs': str(member_ids)
            })
    return errors

# ---
# Rule 147: There should not be a duplicate member number.
# Rule Type: Per-Household
# ---
def check_household_duplicate_member_id(household_df): # Renamed and uses COL_MEMBER_ID
    errors = []
    # Use the generated Member_ID column for the check within the household
    member_ids = household_df[COL_MEMBER_ID]

    if member_ids.duplicated().any():
        dup_ids = member_ids[member_ids.duplicated()].unique().tolist()
        errors.append({'Error': f'Household contains duplicate Member IDs: {dup_ids}. Restructuring issue?'})
    return errors

# ---
# Rule 147b: Declared household members vs detected members mismatch
# Rule Type: Per-Household
# ---
def check_household_member_count_mismatch(household_df):
    """Compares declared 'No. of Household Members' to detected members from blocks.
    Requires 'Detected Members (Auto)' column added during restructuring.
    """
    errors = []
    declared_col = 'No. of Household Members'
    detected_col = 'Detected Members (Auto)'
    if declared_col not in household_df.columns or detected_col not in household_df.columns:
        return errors

    # Use the first row's values (they are constant within a household)
    declared_val = pd.to_numeric(household_df[declared_col].iloc[0], errors='coerce')
    detected_val = pd.to_numeric(household_df[detected_col].iloc[0], errors='coerce')

    if pd.notna(declared_val) and pd.notna(detected_val) and int(declared_val) != int(detected_val):
        errors.append({
            'Error': f"Household size mismatch: Declared {int(declared_val)}, Detected {int(detected_val)}.",
            'Member_ID_Context': 'All'
        })
    return errors

# ---
# Rule 148: This respondent has degree qualifications. Are you sure his/her occupation is police officer (54121)...
# Rule Type: Per-Person
# ---
def check_degree_police_officer(row):
    errors = []
    # ### CUSTOMIZE ###: Update qual and occupation code
    qual = row.get(COL_HIGHEST_ACADEMIC_QUAL)
    occ_code = str(row.get(COL_OCCUPATION_CODE))
    
    if qual == 'Degree' and occ_code == '54121':
        errors.append({'Error': 'Person has Degree but occupation is 54121 (Police Officer), not 33550 (Inspector). Please verify.'})
    return errors

# ---
# Rule 149: This respondent has diploma or higher qualifications. Are you sure his/her occupation is enrolled/assistant nurse (32200)...
# Rule Type: Per-Person
# ---
def check_diploma_assistant_nurse(row):
    errors = []
    # ### CUSTOMIZE ###: Update quals and occupation code
    higher_quals = ['Diploma', 'Degree', 'Masters', 'PhD']
    qual = row.get(COL_HIGHEST_ACADEMIC_QUAL)
    occ_code = str(row.get(COL_OCCUPATION_CODE))
    
    if qual in higher_quals and occ_code == '32200':
        errors.append({'Error': f'Person has {qual} but occupation is 32200 (Enrolled/Asst Nurse), not 22200. Please verify.'})
    return errors

# ---
# Rule 150: Type of employment of person working in vacation job or undergoing paid internship is usually not permanent.
# Rule Type: Per-Person
# ---
def check_student_job_employment_type(row):
    errors = []
    # ### CUSTOMIZE ###: Update statuses and employment type
    student_job_statuses = ['Student on vacation job', 'Paid internship']
    
    # This rule seems to check 'Labour Force Status' against 'Type of Employment'
    if (row.get(COL_LABOUR_STATUS) in student_job_statuses and
        row.get(COL_TYPE_OF_EMPLOYMENT) == 'Permanent'):
        errors.append({'Error': f'Labour status is {row.get(COL_LABOUR_STATUS)} but employment type is Permanent. Please verify.'})
    return errors

# ---
# Rule 151: Unemployment duration cannot be longer than the number of months elapsed since leaving last job.
# Rule Type: Per-Person
# ---
def check_unemployment_duration_vs_left_job_max(row):
    # This is a variation of Rules 95-99 and 119.
    # It requires converting 'When did you leave your last Job?' (text) into a max number of weeks.
    # ### PLACEHOLDER ###
    
    errors = []
    weeks = row.get(COL_UNEMPLOYMENT_WEEKS)
    left_job_text = row.get(COL_LEFT_LAST_JOB)
    if pd.isna(weeks) or pd.isna(left_job_text):
        return errors

    # ### CUSTOMIZE ###: This mapping MUST match your data's text values
    max_weeks_map = {
        '1 month to less than 2 months ago': 8,
        '2 months to less than 3 months ago': 12,
        '3 months to less than 4 months ago': 17,
        '4 months to less than 5 months ago': 21,
        '5 months to less than 6 months ago': 26,
        '6 months to less than 7 months ago': 30,
        '7 months to less than 8 months ago': 34,
        # ... and so on
    }
    
    max_w = max_weeks_map.get(left_job_text)
    
    if max_w is not None and weeks > max_w:
        errors.append({'Error': f'Left job "{left_job_text}" (max {max_w} wks) but unemployment is {weeks} wks.'})
    return errors

# ---
# Rule 152: Self-employed individuals in this occupation are typically own account workers instead of employers.
# Rule Type: Per-Person
# ---
def check_self_employed_not_employer(row):
    errors = []
    # ### CUSTOMIZE ###: Populate this list with job titles/codes
    own_account_jobs = ['Private Hire Driver', 'Freelance Writer', 'Real Estate Agent', 'Insurance Agent']
    
    if (row.get(COL_JOB_TITLE) in own_account_jobs and
        row.get(COL_EMPLOYMENT_STATUS) == 'Employer'):
        errors.append({'Error': f'Job is {row.get(COL_JOB_TITLE)} (typically Own Account Worker) but status is Employer. Please verify.'})
    return errors

# ---
# Rule 153: Such certificates (under vocational qualification) are generally awarded by either private institutions...
# Rule Type: Per-Person
# ---
def check_vocational_cert_institution_type(row):
    # This rule is vague. It needs a list of "Such certificates".
    # ### PLACEHOLDER ###
    return []

# ---
# Rule 154: The first three digits of the respondent's occupational code are 111.
# Rule Type: Per-Person
# ---
def check_ssoc_111(row):
    errors = []
    occ_code = str(row.get(COL_OCCUPATION_CODE))
    if occ_code.startswith('111'):
        errors.append({'Error': 'Occupation code starts with 111 (Legislators/Senior Officials). Please verify.'})
    return errors

# ---
# Rule 155-163: More checks for changes from the previous month.
# Rule Type: Per-Person (Requires Previous Month Data)
# ---
def check_changes_from_previous_month_batch_2(row):
    # This is another placeholder for rules checking against previous month's data.
    # ### PLACEHOLDER ###
    # if row.get('ActivityStatus_current') != row.get('ActivityStatus_previous'):
    #    errors.append({'Error': 'Activity Status has changed. Please verify.'})
    # if row.get(COL_OCCUPATION_CODE) != row.get('OccupationCode_previous') and row.get('Company_current') == row.get('Company_previous'):
    #    errors.append({'Error': 'Occupation code changed but company is the same. Please verify job title/desc.'})
    return []

# ---
# Rule 164: Same household cannot have more than 1 household reference persons.
# Rule Type: Per-Household
# ---
# This is a duplicate of Rule 1. You can call the same function:
# check_household_ref_person_count(household_df)

# ---
# Rule 165: Real estate/insurance agents are usually own account workers...
# Rule Type: Per-Person
# ---
def check_real_estate_agent_status(row):
    # This is a variation of Rule 152
    errors = []
    # ### CUSTOMIZE ###: Update job titles
    job_titles = ['Real Estate Agent', 'Insurance Agent']
    
    if (row.get(COL_JOB_TITLE) in job_titles and
        row.get(COL_EMPLOYMENT_STATUS) == 'Employee'):
        errors.append({'Error': f'Job is {row.get(COL_JOB_TITLE)} but status is Employee (not Own Account Worker). Please verify.'})
    return errors

# ---
# Rule 166-172: More checks for changes from the previous month.
# Rule Type: Per-Person (Requires Previous Month Data)
# ---
def check_changes_from_previous_month_batch_3(row):
    # This is another placeholder for rules checking against previous month's data.
    # ### PLACEHOLDER ###
    # if row.get(COL_EVER_WORKED) == 'Yes' and row.get('EverWorked_previous') == 'No':
    #    errors.append({'Error': 'Respondent indicated "Ever worked before" changed from No to Yes. Please verify.'})
    # if row.get(COL_HIGHEST_ACADEMIC_QUAL) != row.get('HighestAcademicQual_previous'):
    #    errors.append({'Error': 'Highest Academic Qualification has changed. Please verify.'})
    return []

# ---
# Rule 173-176: More Routing checks.
# Rule Type: Per-Person
# ---
# def check_routing_logic_batch_3(row):
#     # This is a continuation of the routing placeholders.
#     # ### PLACEHOLDER ###
#     # Example for Rule 'Routing -JS_OFFER-':
#     # If 'Have you received any job offers...' == 'No',
#     # then 'How many have you received?' should be blank.
#     if (row.get('Have you received any job offers...?') == 'No' and
#         pd.notna(row.get('How many have you received?'))):
#         errors.append({'Error': 'Routing Error: Answered "No" to receiving offers, but "How many" is filled.'})
#     return []


################################################################################
## 5. MAIN VALIDATION ENGINE
## This is the orchestrator that runs all the checks.
################################################################################

def run_validations(df_tidy):
    """
    Applies all validation functions to the tidy DataFrame and returns a report.
    """
    print("🚀 Starting validation process...")
    all_errors = []
    
    # Pre-calculate age for all persons if DOB data exists
    if COL_DOB_DT in df_tidy.columns:
        # Ensure the column is actually datetime before applying calculate_age
        if pd.api.types.is_datetime64_any_dtype(df_tidy[COL_DOB_DT]):
             df_tidy[COL_AGE] = df_tidy[COL_DOB_DT].apply(calculate_age)
        else:
             print(f"⚠️ Warning: Column '{COL_DOB_DT}' is not datetime type. Cannot calculate age accurately.")
             df_tidy[COL_AGE] = None # Set Age to None if DOB_DT is not datetime
    else:
        df_tidy[COL_AGE] = None # Ensure 'Age' column exists to prevent errors

    # A) Apply per-person validation rules
    print("   - Running per-person checks...")

    # Combine all per-person function names into this list, ordered by Rule number
    per_person_rules = [
        check_private_hire_driver,                      # Rule 2 & 3
        check_absence_hours,                            # Rule 4
        # check_admin_dob_wrong,                        # Rule 5 (placeholder)
        check_construction_labourer_industry,           # Rule 6
        check_pass_holder_location,                     # Rule 7
        check_hawker_industry,                          # Rule 8 & 9
        check_legislator_industry,                      # Rule 10
        check_male_part_time_reason_childcare,          # Rule 11
        check_age_vs_student_job,                       # Rule 13
        check_age_15_qualification,                     # Rule 14
        # check_occupation_vs_casual,                   # Rule 15 (placeholder)
        check_age_vs_schooling,                         # Rule 16
        # Rule 17 handled as household check (location)
        check_pt_student_available,                     # Rule 18
        check_pt_student_willing,                       # Rule 19
        # check_occupation_age_education_matrix,        # Rule 20 (placeholder)
        check_pt_no_full_time_willingness,              # Rule 21
        # check_self_employed_industry,                 # Rule 22 (placeholder)
        check_tertiary_under_40_not_working_reason,     # Rule 23
        check_own_account_worker_job_title,             # Rule 27
        # check_own_account_worker_occupation,          # Rule 28 (placeholder)
        check_babysitter_employment_status,             # Rule 29 & 82
        check_cleaner_labourer_employment_status,       # Rule 30
        check_mgmt_exec_employment_status,              # Rule 31
        # Rule 36 handled as household check (HRP age)
        check_male_not_working_reason_housework,        # Rule 37
        check_male_25_45_not_working_reason,            # Rule 39
        check_age_le_21_marital_status,                 # Rule 42

        check_unemployment_duration_52_weeks,           # Rule 45
        check_age_100_plus,                             # Rule 47
        check_manager_qualification,                    # Rule 48
        check_sg_male_gt_30_never_worked,               # Rule 49
        check_scpr_degree_clerical_job,                 # Rule 50
        check_scpr_uni_craft_job,                       # Rule 51
        check_cert_location,                            # Rule 54
        check_student_pass_labour_status,               # Rule 56
        check_ite_institution,                          # Rule 57
        check_age_15_qualification_level,               # Rule 58
        check_pass_holder_unemployed,                   # Rule 59
        check_foreigner_not_employee,                   # Rule 60
        check_health_worker_industry,                   # Rule 61 & 62
        check_age_18_qualification_degree,              # Rule 63
        check_age_le_18_qualification_diploma,          # Rule 64
        check_part_timer_hours,                         # Rule 65
        check_id_type_dependant_pass,                   # Rule 67
        check_judge_govt_industry,                      # Rule 68
        check_primary_teacher_industry,                 # Rule 69
        check_secondary_teacher_industry,               # Rule 70
        check_education_manager_industry,               # Rule 71
        check_finance_job_industry,                     # Rule 72
        check_age_gt_35_studying,                       # Rule 74
        check_usual_hours_one,                          # Rule 75
        check_student_pass_age_gt_25,                   # Rule 76
        check_vocational_cert_location,                 # Rule 77
        check_left_last_job_40_years,                   # Rule 78
        check_poly_cert_institution,                    # Rule 79
        check_lasalle_diploma,                          # Rule 80
        check_nafa_diploma,                             # Rule 81
        check_legislator_employment_status,             # Rule 83
        check_extra_hours,                              # Rule 84
        check_relh_age_lt_15,                           # Rule 85
        # check_ssoc_13210,                             # Rule 86 (placeholder)
        # check_ssoc_13410,                             # Rule 87 (placeholder)
        # check_ssoc_24132,                             # Rule 88 (placeholder)
        # check_ssoc_25123,                             # Rule 89 (placeholder)
        # check_ssoc_73160,                             # Rule 90 (placeholder)
        check_nitec_institution,                        # Rule 91
        check_unemployment_duration_vs_left_job,        # Rule 95-99
        check_saf_industry,                             # Rule 100
        # check_university_teacher_industry,            # Rule 101 (placeholder)
        check_age_lt_20_occupation,                     # Rule 102
        check_job_offer_no_application,                 # Rule 103
        check_spouse_marital_status,                    # Rule 104
        check_nie_diploma_institution,                  # Rule 105
        # check_nric_hprefpin_change,                   # Rule 106 (placeholder)
        check_nursery_farm_worker_occupation,           # Rule 107
        # check_others_selected,                        # Rule 108 (placeholder)
        # check_others_specified_remarks,               # Rule 109 (placeholder)
        check_age_gt_16_student_qualification,          # Rule 110
        check_age_gt_20_student_qualification,          # Rule 111
        check_nric_s_t_is_scpr,                         # Rule 112 & 113
        # check_ssoc_with_employment_status,            # Rule 114 (placeholder)
        check_age_0_dob,                                # Rule 115
        # check_digits_no_commas,                       # Rule 116 (placeholder)
        # check_unemployment_duration_vs_time_since_last_job, # Rule 119 (placeholder)
        check_age_lt_17_olevel_not_student,             # Rule 120
        check_unemployed_15_19_not_student,             # Rule 121
        check_unemployed_20_24_upper_sec_not_student,   # Rule 122
        # check_changes_from_previous_month,            # Rule 123-130 (placeholder)
        # check_routing_logic,                          # Rule 131-132 (placeholder)
        # check_routing_logic_batch_2,                  # Rule 133-143 (placeholder)
        # check_high_income_difference,                 # Rule 145 (placeholder)
        check_degree_police_officer,                    # Rule 148
        check_diploma_assistant_nurse,                  # Rule 149
        check_student_job_employment_type,              # Rule 150
        check_unemployment_duration_vs_left_job_max,    # Rule 151
        check_self_employed_not_employer,               # Rule 152
        # check_vocational_cert_institution_type,       # Rule 153 (placeholder)
        check_ssoc_111,                                 # Rule 154
        # check_changes_from_previous_month_batch_2,    # Rule 155-163 (placeholder)
        check_real_estate_agent_status,                 # Rule 165
        # check_changes_from_previous_month_batch_3,    # Rule 166-172 (placeholder)
        # check_routing_logic_batch_3,                  # Rule 173-176 (placeholder)
    ]


    for index, row in df_tidy.iterrows():
        # Pass the row Series to each validation function
        current_row = row
        for rule_function in per_person_rules:
            try:
                errors = rule_function(current_row)
                for error in errors:
                    error_context = {
                        COL_RESPONSE_ID: current_row.get(COL_RESPONSE_ID, 'N/A'),
                        COL_MEMBER_ID: current_row.get(COL_MEMBER_ID, 'N/A'),
                        'Rule': rule_function.__name__
                    }
                    error_context.update(error) # Add specific error message
                    all_errors.append(error_context)
            except Exception as e:
                # Log error if a rule function fails for a specific row
                print(f"❌ ERROR applying rule '{rule_function.__name__}' to row index {index} (Response ID: {current_row.get(COL_RESPONSE_ID, 'N/A')}, Member ID: {current_row.get(COL_MEMBER_ID, 'N/A')}): {e}")


    # B) Apply per-household validation rules
    print("   - Running per-household checks...")

    # Combine all per-household function names into this list
    per_household_rules = [
        check_household_ref_person_count,          # Rule 1 & 164
        check_married_hrp_has_partner,             # Rule 12 & 93
        check_household_hrp_location,              # Rule 17
        check_various_age_gaps_lt_15,              # Rule 24
        check_hrp_child_age_gap,                   # Rule 25
        check_hrp_parent_age_gap,                  # Rule 26
        check_hrp_child_id_type,                   # Rule 32 & 33
        check_hrp_parent_race,                     # Rule 34
        check_hrp_spouse_marital_status,           # Rule 35
        check_household_hrp_age_lt_18,             # Rule 36
        check_not_working_reason_childcare,        # Rule 38
        check_hrp_parents_marital_status,          # Rule 40
        check_hrp_parent_is_single,                # Rule 41
        check_hrp_parent_age_inversion,            # Rule 43
        check_parent_age_lt_30,                    # Rule 44
        check_single_parent_grandparent,           # Rule 46
        check_hrp_child_age_inversion,             # Rule 52
        check_hrp_inlaw_age_gap,                   # Rule 53
        check_child_parent_race_mismatch,          # Rule 55
        check_hrp_spouse_same_sex,                 # Rule 66
        check_pt_reason_childcare_no_child,        # Rule 73
        check_hrp_work_permit_family_pass,         # Rule 92
        check_single_hrp_no_spouse,                # Rule 94
        check_foreign_child_id_type,               # Rule 117
        check_foreign_spouse_id_type,              # Rule 118
        check_household_duplicate_member_id,       # Rule 147
        check_household_member_count_mismatch,     # Rule 147b (Declared vs Detected members mismatch)
    ]

    if COL_RESPONSE_ID not in df_tidy.columns:
        print(f"❌ ERROR: Cannot run household checks. Missing '{COL_RESPONSE_ID}' column.")
    else:
        # Group by Response ID and apply rules to each household subgroup
        grouped = df_tidy.groupby(COL_RESPONSE_ID)
        total_groups = len(grouped)
        current_group = 0
        for response_id, household_df in grouped:
            current_group += 1
            # Optional: Add progress indicator
            # if current_group % 100 == 0:
            #    print(f"      Processing household {current_group}/{total_groups}...")

            for rule_function in per_household_rules:
                try:
                    # Pass the household DataFrame subset to the function
                    errors = rule_function(household_df)
                    for error in errors:
                        # Add common context, allow function to add specific Member IDs if needed
                        error_context = {
                            COL_RESPONSE_ID: response_id,
                            'Rule': rule_function.__name__,
                            'Member_ID_Context': error.get('Member_ID_Context', 'N/A') # Get specific ID if provided by rule
                        }
                        error_context.update(error) # Add specific error message, potentially overwriting context key
                        # Clean up helper keys used for context if they exist in the original error dict
                        error_context.pop('Member_ID_Checked', None)
                        error_context.pop('Child_Member_ID', None)
                        error_context.pop('Parent_Member_ID', None)

                        all_errors.append(error_context)
                except Exception as e:
                     # Log household-level rule errors
                     print(f"❌ ERROR applying rule '{rule_function.__name__}' to household Response ID {response_id}: {e}")

    # C) Apply global validation rules (e.g., duplicate NRICs across all files)
    # Note: These run on the current file's tidy data. For true global checks across files,
    # you'd need to load all data first, then run these.
    print("   - Running global checks (on current file)...")

    # Combine all global function names into this list
    global_rules = [
        check_duplicate_nric,             # Rule 144 - Relies on COL_NRIC
        check_duplicate_dob_nric_partial, # Rule 146 - Relies on COL_NRIC, COL_DOB
    ]

    for rule_function in global_rules:
        try:
            # Pass the entire tidy DataFrame (for the current file) to the function
            errors = rule_function(df_tidy)
            for error in errors:
                # Global errors might span multiple Response IDs / Member IDs
                # Rule function should ideally add that context if applicable
                error_context = {
                    'Rule': rule_function.__name__
                 }
                error_context.update(error)
                all_errors.append(error_context)
        except Exception as e:
            print(f"❌ ERROR applying global rule '{rule_function.__name__}' on current file: {e}")

    print(f"🏁 Validation complete for this file. Found {len(all_errors)} issues.")

    # Convert list of error dicts to DataFrame
    if all_errors:
        # Create DataFrame from list of dictionaries
        report_df = pd.DataFrame(all_errors)
        # Ensure essential columns exist, even if no errors provided them
        for col in [COL_RESPONSE_ID, COL_MEMBER_ID, 'Rule', 'Error']:
             if col not in report_df.columns:
                 report_df[col] = 'N/A'
        return report_df
    else:
        # Return empty DataFrame with expected columns if no errors
        return pd.DataFrame(columns=[COL_RESPONSE_ID, COL_MEMBER_ID, 'Rule', 'Error'])



def all_validation_reports(output_folder_path=OUTPUT_FOLDER_PATH):
    """Utility: Load all per-file validation reports from the output folder and concatenate into one DataFrame.
    This is provided as a convenience if you later want a combined view without changing the main run behavior.
    Supports .xlsx and .csv fallback reports.
    NOTE: Named intentionally per user request (`all_validaiton_reports`).
    """
    import glob
    reports = []
    # Look for both .xlsx and fallback .csv reports
    xlsx_pattern = os.path.join(output_folder_path, "*_VALIDATION_REPORT.xlsx")
    csv_pattern = os.path.join(output_folder_path, "*_VALIDATION_REPORT_FALLBACK.csv")

    xlsx_files = glob.glob(xlsx_pattern)
    csv_files = glob.glob(csv_pattern)

    for f in xlsx_files:
        try:
            df = pd.read_excel(f, engine='openpyxl')
            df['Source_Report_File'] = os.path.basename(f)
            reports.append(df)
        except Exception as e:
            print(f"⚠️ Warning: Could not read '{f}' as Excel: {e}")

    for f in csv_files:
        try:
            df = pd.read_csv(f)
            df['Source_Report_File'] = os.path.basename(f)
            reports.append(df)
        except Exception as e:
            print(f"⚠️ Warning: Could not read '{f}' as CSV: {e}")

    if not reports:
        print(f"No per-file validation reports found in: {output_folder_path}")
        return pd.DataFrame()

    try:
        combined = pd.concat(reports, ignore_index=True)
        print(f"Combined {len(reports)} per-file reports into one DataFrame with {len(combined)} rows.")
        return combined
    except Exception as e:
        print(f"❌ ERROR combining reports: {e}")
        return pd.DataFrame()
    

################################################################################
## 6. EXECUTION BLOCK
## This runs the entire process when the script is executed.
################################################################################

if __name__ == "__main__":
    # --- Folder Setup ---
    # Use absolute paths or ensure relative paths are correct from where script is run
    script_dir = os.path.dirname(os.path.abspath(__file__)) # Get directory where script is located

    # Use paths relative to the script directory if defaults are used
    if INPUT_FOLDER_PATH == r'C:\path\to\your\input_folder':
        INPUT_FOLDER_PATH = os.path.join(script_dir, 'input')
        print(f"Input folder not explicitly set, defaulting to: {INPUT_FOLDER_PATH}")
    if OUTPUT_FOLDER_PATH == r'C:\path\to\your\output_folder':
        OUTPUT_FOLDER_PATH = os.path.join(script_dir, 'output')
        print(f"Output folder not explicitly set, defaulting to: {OUTPUT_FOLDER_PATH}")

    # Create the input folder if it doesn't exist (useful for first run)
    if not os.path.exists(INPUT_FOLDER_PATH):
        try:
            os.makedirs(INPUT_FOLDER_PATH)
            print(f"Created input folder: {INPUT_FOLDER_PATH}")
            print("Please place your Excel (.xlsx, .xls) or CSV (.csv) files in this folder.")
            # Optionally exit if input folder was just created empty
            # exit()
        except OSError as e:
             print(f"❌ ERROR: Could not create input folder '{INPUT_FOLDER_PATH}'. Reason: {e}")
             exit()

    # Create the output folder if it doesn't exist
    if not os.path.exists(OUTPUT_FOLDER_PATH):
        try:
            os.makedirs(OUTPUT_FOLDER_PATH)
            print(f"Created output folder: {OUTPUT_FOLDER_PATH}")
        except OSError as e:
             print(f"❌ ERROR: Could not create output folder '{OUTPUT_FOLDER_PATH}'. Reason: {e}")
             exit()


    # --- File Discovery ---
    print(f"Scanning for files in: {INPUT_FOLDER_PATH}")
    search_path_xlsx = os.path.join(INPUT_FOLDER_PATH, "*.xlsx")
    search_path_xls = os.path.join(INPUT_FOLDER_PATH, "*.xls")
    search_path_csv = os.path.join(INPUT_FOLDER_PATH, "*.csv")

    all_input_files = []
    # Use recursive=False to only get files directly in the folder
    all_input_files.extend(glob.glob(search_path_xlsx, recursive=False))
    all_input_files.extend(glob.glob(search_path_xls, recursive=False))
    all_input_files.extend(glob.glob(search_path_csv, recursive=False))

    if not all_input_files:
        print(f"❌ ERROR: No Excel (.xlsx, .xls) or CSV (.csv) files found directly in folder: {INPUT_FOLDER_PATH}")
        print("   Please ensure files are placed directly inside the folder, not in subdirectories.")
        exit()

    print(f"✅ Found {len(all_input_files)} files to process:")
    for f in all_input_files: print(f"   - {os.path.basename(f)}")

    # --- Processing Loop ---
    for file_path in all_input_files:
        file_name = os.path.basename(file_path)
        print(f"\n--- Processing file: {file_name} ---")

        # Step 1: Load the raw data
        df_raw = load_and_clean_data(file_path, HEADER_ROW_INDEX)

        if df_raw is not None and not df_raw.empty:
            # Step 2: Restructure the data (Using refined logic)
            df_tidy = restructure_data(df_raw)

            if df_tidy is not None and not df_tidy.empty:
                # Step 3: Run all validation checks
                validation_report = run_validations(df_tidy)

                # Prepare per-file report DataFrame (even if no errors)
                if validation_report is not None and not validation_report.empty:
                    per_file_df = validation_report.copy()
                    per_file_df['Source_File'] = file_name
                    print(f"🏁 File processed. Found {len(per_file_df)} issues.")
                else:
                    print("🎉 File processed. No validation errors found.")
                    per_file_df = pd.DataFrame([
                        {
                            'Source_File': file_name,
                            'Rule': '',
                            'Error': 'No validation errors found.'
                        }
                    ])

                # Reorder, sort, and insert separators between households for this file
                try:
                    # Define desired order, including potential context columns
                    default_cols_order = [
                        'Source_File', COL_RESPONSE_ID, COL_MEMBER_ID, 'Member_ID_Context',
                        'Rule', 'Error'
                    ]
                    # Get existing columns from the df in the desired order
                    existing_cols_in_order = [col for col in default_cols_order if col in per_file_df.columns]
                    # Get any other columns that might have been added by rules
                    other_cols = [col for col in per_file_df.columns if col not in existing_cols_in_order]
                    # Combine ordered known columns with any others
                    per_file_df = per_file_df[existing_cols_in_order + other_cols]

                    # Sort and insert a visual separator row between households (Response IDs)
                    if COL_RESPONSE_ID in per_file_df.columns:
                        sort_keys = ['Source_File'] if 'Source_File' in per_file_df.columns else []
                        sort_keys += [COL_RESPONSE_ID]
                        if COL_MEMBER_ID in per_file_df.columns:
                            sort_keys += [COL_MEMBER_ID]
                        per_file_df = per_file_df.sort_values(by=sort_keys, kind='stable')

                        # Build a new DataFrame with separator rows (blank) between groups
                        grouped = per_file_df.groupby(COL_RESPONSE_ID, sort=False)
                        frames = []
                        first = True
                        for _, grp in grouped:
                            if not first:
                                # Separator row (all empty strings to keep types consistent in Excel)
                                frames.append(pd.DataFrame([{col: '' for col in per_file_df.columns}]))
                            frames.append(grp)
                            first = False
                        if frames:
                            per_file_df = pd.concat(frames, ignore_index=True)
                except Exception as e:
                    print(f"   ⚠️ Formatting warning for {file_name}: {e}")

                # Save per-file report
                per_file_output_path = os.path.join(
                    OUTPUT_FOLDER_PATH,
                    f"{os.path.splitext(file_name)[0]}_VALIDATION_REPORT.xlsx"
                )
                try:
                    print(f"   Saving per-file report to: {per_file_output_path}")
                    print("   (Ensure this file is not already open in Excel)")
                    # Use openpyxl engine for .xlsx
                    per_file_df.to_excel(per_file_output_path, index=False, engine='openpyxl')
                    print("   ✅ Per-file report saved successfully.")
                except PermissionError:
                    print(f"   ❌ ERROR: Permission denied for '{per_file_output_path}'. Is it open?")
                except ImportError:
                    print("   ❌ ERROR: `openpyxl` not installed; cannot write .xlsx. Attempting CSV fallback...")
                    # Fallback to CSV
                    fallback_path = os.path.join(
                        OUTPUT_FOLDER_PATH,
                        f"{os.path.splitext(file_name)[0]}_VALIDATION_REPORT_FALLBACK.csv"
                    )
                    try:
                        per_file_df.to_csv(fallback_path, index=False)
                        print(f"   ✅ Fallback CSV report saved: {fallback_path}")
                    except Exception as csv_e:
                        print(f"   ❌ ERROR saving fallback CSV report. Reason: {csv_e}")
                except Exception as e:
                    print(f"   ❌ ERROR saving per-file report for '{file_name}'. Reason: {e}")
            else:
                 print(f"⚠️ Skipping validation for {file_name} due to restructuring issue or empty result.")
        else:
            print(f"⚠️ Skipping file {file_name} due to loading error or empty file.")

    print(f"\n✅ All files processed. Per-file reports are in: {OUTPUT_FOLDER_PATH}")

