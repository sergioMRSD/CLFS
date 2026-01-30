import os
import pandas as pd
from pathlib import Path

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


if __name__ == "__main__":
    main()
