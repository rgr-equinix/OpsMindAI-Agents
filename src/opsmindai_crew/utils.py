"""Utility functions for incident management and file organization."""

import os
from datetime import datetime
from typing import Optional


def get_incident_output_folder(incident_id: str, base_output_dir: str = "outputs") -> str:
    """
    Get the output folder path for a specific incident.
    
    Args:
        incident_id: The incident identifier
        base_output_dir: Base directory for all outputs (default: "outputs")
    
    Returns:
        Path to the incident-specific output folder
    """
    # Clean incident ID to be filesystem-safe
    clean_incident_id = incident_id.replace("/", "_").replace("\\", "_").replace(":", "_")
    
    # Create folder structure: outputs/INCIDENT_ID/
    incident_folder = os.path.join(base_output_dir, clean_incident_id)
    
    # Ensure the folder exists
    os.makedirs(incident_folder, exist_ok=True)
    
    return incident_folder


def get_incident_file_path(incident_id: str, filename: str, base_output_dir: str = "outputs") -> str:
    """
    Get the full file path for a file within an incident's output folder.
    
    Args:
        incident_id: The incident identifier
        filename: The filename (with extension)
        base_output_dir: Base directory for all outputs (default: "outputs")
    
    Returns:
        Full path to the file within the incident folder
    """
    incident_folder = get_incident_output_folder(incident_id, base_output_dir)
    return os.path.join(incident_folder, filename)


def list_incident_files(incident_id: str, base_output_dir: str = "outputs") -> list:
    """
    List all files in an incident's output folder.
    
    Args:
        incident_id: The incident identifier
        base_output_dir: Base directory for all outputs (default: "outputs")
    
    Returns:
        List of file paths in the incident folder
    """
    incident_folder = get_incident_output_folder(incident_id, base_output_dir)
    
    if not os.path.exists(incident_folder):
        return []
    
    files = []
    for filename in os.listdir(incident_folder):
        file_path = os.path.join(incident_folder, filename)
        if os.path.isfile(file_path):
            files.append(file_path)
    
    return files


def get_incident_summary(incident_id: str, base_output_dir: str = "outputs") -> dict:
    """
    Get a summary of all files generated for an incident.
    
    Args:
        incident_id: The incident identifier
        base_output_dir: Base directory for all outputs (default: "outputs")
    
    Returns:
        Dictionary with file summary information
    """
    files = list_incident_files(incident_id, base_output_dir)
    
    summary = {
        "incident_id": incident_id,
        "output_folder": get_incident_output_folder(incident_id, base_output_dir),
        "total_files": len(files),
        "files": []
    }
    
    for file_path in files:
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)
        modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        
        summary["files"].append({
            "filename": filename,
            "path": file_path,
            "size_bytes": file_size,
            "modified": modified_time.isoformat(),
            "type": _get_file_type(filename)
        })
    
    return summary


def _get_file_type(filename: str) -> str:
    """Determine file type based on extension."""
    ext = os.path.splitext(filename)[1].lower()
    
    type_mapping = {
        '.pdf': 'report',
        '.html': 'visualization',
        '.png': 'image',
        '.json': 'data',
        '.csv': 'data',
        '.txt': 'text',
        '.md': 'documentation'
    }
    
    return type_mapping.get(ext, 'other')
