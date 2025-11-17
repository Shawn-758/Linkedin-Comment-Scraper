import json
import logging
import re
import pandas as pd
from datetime import datetime, timedelta, timezone
import os

# Emojis for logging
EMOJIS = {
    "rocket": "🚀",
    "cookie": "🍪",
    "check_mark": "✅",
    "cross_mark": "❌",
    "search": "🔍",
    "document": "📄",
    "speech_bubble": "💬",
    "warning": "⚠️",
    "party_popper": "🎉",
    "disk": "💾",
    "wave": "👋",
}

def load_cookies(cookie_file_path: str) -> dict:
    """Loads cookies from a JSON file."""
    with open(cookie_file_path, "r") as f:
        cookies = json.load(f)
    return cookies

def clean_profile_url(url: str) -> str | None:
    """
    Cleans a LinkedIn profile URL to its canonical form.
    e.g., /in/john-doe-12345/ or https://www.linkedin.com/in/john-doe-12345/
    """
    if not url:
        return None
        
    match = re.search(r"\/in\/([a-zA-Z0-9-]+)", url)
    if match:
        username = match.group(1)
        return f"https://www.linkedin.com/in/{username}/"
    
    return None

def get_timestamp_from_urn(urn: str) -> datetime | None:
    """
    Extracts the precise timestamp from a LinkedIn URN.
    Logic from ollie-boyd/linkedin-post-timestamp-extractor.
    """
    try:
        # urn:li:activity:7316321711396700160
        match = re.search(r'activity:(\d+)', urn)
        if not match:
            return None

        linkedin_id = match.group(1)
        first_41_bits = bin(int(linkedin_id))[2:43]  
        timestamp_ms = int(first_41_bits, 2)
        
        # Return a timezone-aware datetime object
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)

    except Exception as e:
        logging.warning(f"Could not decode timestamp from URN {urn}: {e}")
        return None

# --- State & Checkpointing Functions ---

def load_state_json(file_path: str) -> list | dict | None:
    """Loads a JSON state file. Returns None if it doesn't exist."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        logging.warning(f"State file {file_path} is corrupt. Returning None.")
        return None

def save_state_json(data: list | dict, file_path: str):
    """Saves data to a JSON state file."""
    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save state file {file_path}: {e}")

# --- Result Output Functions ---

def load_results(output_file: str) -> list[dict]:
    """Loads existing results from a CSV or JSON file."""
    if not os.path.exists(output_file):
        return []
    
    file_format = output_file.split('.')[-1]
    
    try:
        if file_format == "csv":
            df = pd.read_csv(output_file)
            return df.to_dict('records')
        elif file_format == "json":
            with open(output_file, 'r') as f:
                return json.load(f)
    except (pd.errors.EmptyDataError, json.JSONDecodeError):
        logging.warning(f"Output file {output_file} is empty or corrupt. Starting fresh.")
        return []
    except Exception as e:
        logging.error(f"Error loading results from {output_file}: {e}. Returning empty list.")
        return []
    return []

def save_results(results: list[dict], output_file: str, file_format: str = 'csv'):
    """
    Saves the full list of dictionaries to a CSV or JSON, overwriting the file.
    """
    if not results:
        logging.warning(f"{EMOJIS['warning']} No results to save for {output_file}.")
        return

    df = pd.DataFrame(results)
    
    if "headline" in df.columns:
        df = df[["profile_url", "headline"]]
    else:
        df = df[["profile_url"]]

    try:
        if file_format == "csv":
            df.to_csv(output_file, index=False)
        elif file_format == "json":
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)
                
    except Exception as e:
        logging.error(f"{EMOJIS['cross_mark']} Failed to save final results to {output_file}: {e}")

def append_results(new_results: list[dict], output_file: str, file_format: str = 'csv'):
    """
    Appends a list of new results to an existing CSV or JSON file.
    """
    if not new_results:
        return
    
    file_exists = os.path.exists(output_file)
    
    try:
        if file_format == "csv":
            df = pd.DataFrame(new_results)
            if "headline" in df.columns:
                df = df[["profile_url", "headline"]]
            else:
                df = df[["profile_url"]]
            
            df.to_csv(output_file, mode='a', header=not file_exists, index=False)
            
        elif file_format == "json":
            existing_results = load_results(output_file)
            existing_results.extend(new_results)
            with open(output_file, 'w') as f:
                json.dump(existing_results, f, indent=2)
                
    except Exception as e:
        logging.error(f"{EMOJIS['cross_mark']} Failed to append results to {output_file}: {e}")