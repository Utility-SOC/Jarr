# arr_omnitool/core/utils.py
"""
Shared utility functions used across the application.
"""

import re
import csv
import logging
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def format_file_size(bytes_size: int) -> str:
    """
    Convert bytes to human-readable file size.
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def parse_release_date(date_str: str) -> Optional[datetime]:
    """
    Parse various date formats into datetime object.
    """
    if not date_str:
        return None
    
    formats = [
        '%Y-%m-%d',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%S.%f',
        '%Y-%m-%dT%H:%M:%SZ',
        '%Y-%m-%dT%H:%M:%S.%fZ',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def sanitize_filename(filename: str) -> str:
    """
    Remove or replace characters that are invalid in filenames.
    """
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    filename = re.sub(r'\s+', ' ', filename)
    filename = filename.strip()
    return filename


def compare_versions(version1: str, version2: str) -> int:
    """
    Compare two version strings.
    """
    def normalize(v):
        return [int(x) for x in re.sub(r'[^0-9.]', '', v).split('.')]
    
    try:
        v1_parts = normalize(version1)
        v2_parts = normalize(version2)
        
        max_len = max(len(v1_parts), len(v2_parts))
        v1_parts += [0] * (max_len - len(v1_parts))
        v2_parts += [0] * (max_len - len(v2_parts))
        
        if v1_parts < v2_parts:
            return -1
        elif v1_parts > v2_parts:
            return 1
        else:
            return 0
    except:
        return 0


def normalize_title(title: str) -> str:
    """
    Normalize a title for better matching.
    """
    title = title.lower()
    title = re.sub(r'^(the|a|an)\s+', '', title)
    title = re.sub(r'[^\w\s]', '', title)
    title = re.sub(r'\s+', ' ', title)
    title = title.strip()
    return title


def validate_url(url: str) -> bool:
    """
    Validate if a string is a valid URL.
    """
    if not url:
        return False
    
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """
    Truncate a string to a maximum length, adding suffix if truncated.
    """
    if len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix


def format_duration(seconds: int) -> str:
    """
    Format seconds into human-readable duration.
    """
    if seconds < 60:
        return f"{seconds}s"
    
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    
    hours = minutes // 60
    remaining_minutes = minutes % 60
    
    if remaining_minutes == 0:
        return f"{hours}h"
    
    return f"{hours}h {remaining_minutes}m"

# --- MODIFIED FUNCTION ---
def scrub_name(name: str, blacklist: list[str]) -> str:
    """
    Removes blacklist regex patterns from a name and cleans up common separators.
    """
    scrubbed_name = name
    
    # 1. Remove all blacklist patterns (case-insensitive)
    for pattern_string in blacklist:
        # This is the active part of the "enable/disable" feature.
        # We process the list given to us (which is pre-filtered).
        try:
            pattern = re.compile(pattern_string, re.IGNORECASE)
            scrubbed_name = pattern.sub("", scrubbed_name)
        except re.error as e:
            logger.warning(f"Invalid regex in blacklist, skipping: '{pattern_string}'. Error: {e}")
            pass

    # 2. Clean up common separators and artifacts left behind
    # Replace common delimiters with a space
    scrubbed_name = re.sub(r'[\.\[\]\(\)\-_{}]', ' ', scrubbed_name)
    
    # 3. Consolidate multiple spaces into one
    scrubbed_name = re.sub(r'\s+', ' ', scrubbed_name).strip()
    
    # 4. Remove leading/trailing spaces or hyphens one last time
    scrubbed_name = scrubbed_name.strip(" -")
    
    return scrubbed_name

def parse_csv_to_list(file_path: str) -> list[str]:
    """Reads the first column of a CSV into a list of strings."""
    words = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    words.append(row[0].strip())
    except Exception as e:
        logger.error(f"Failed to read CSV {file_path}: {e}")
        return []
    return words

def save_list_to_csv(file_path: str, words: list[str]):
    """Saves a list of strings as a one-column CSV."""
    try:
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for word in words:
                writer.writerow([word])
    except Exception as e:
        logger.error(f"Failed to save CSV {file_path}: {e}")