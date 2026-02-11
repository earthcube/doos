#!/usr/bin/env python3
"""
FAIR Practices Assessment - Save Tool
Saves interview responses and assessment report to structured files.
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any


def validate_assessment_data(data: Dict[str, Any]) -> bool:
    """Validate that required fields are present in the assessment data."""
    required_keys = ['participant_info', 'responses', 'assessment']

    for key in required_keys:
        if key not in data:
            print(f"Error: Missing required key '{key}'", file=sys.stderr)
            return False

    # Validate participant_info
    participant_required = ['role', 'career_stage', 'research_area', 'fair_familiarity']
    for key in participant_required:
        if key not in data['participant_info']:
            print(f"Warning: Missing participant info '{key}'", file=sys.stderr)

    # Validate assessment
    assessment_required = ['maturity_level', 'strengths', 'recommendations', 'observations']
    for key in assessment_required:
        if key not in data['assessment']:
            print(f"Warning: Missing assessment '{key}'", file=sys.stderr)

    return True


def generate_text_report(data: Dict[str, Any]) -> str:
    """Generate a human-readable text report from the assessment data."""
    report_lines = []

    # Header
    report_lines.append("=" * 80)
    report_lines.append("FAIR PRACTICES ASSESSMENT REPORT")
    report_lines.append("=" * 80)
    report_lines.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")

    # Participant Information
    report_lines.append("PARTICIPANT INFORMATION")
    report_lines.append("-" * 80)
    participant = data.get('participant_info', {})
    report_lines.append(f"Role: {participant.get('role', 'Not provided')}")
    report_lines.append(f"Career Stage: {participant.get('career_stage', 'Not provided')}")
    report_lines.append(f"Research Area: {participant.get('research_area', 'Not provided')}")
    report_lines.append(f"FAIR Familiarity: {participant.get('fair_familiarity', 'Not provided')}")
    report_lines.append("")

    # Assessment Summary
    assessment = data.get('assessment', {})
    report_lines.append("OVERALL ASSESSMENT")
    report_lines.append("-" * 80)
    report_lines.append(f"FAIR Maturity Level: {assessment.get('maturity_level', 'Not assessed')}")
    report_lines.append("")

    # Strengths
    report_lines.append("KEY STRENGTHS")
    report_lines.append("-" * 80)
    strengths = assessment.get('strengths', [])
    if strengths:
        for i, strength in enumerate(strengths, 1):
            report_lines.append(f"{i}. {strength}")
    else:
        report_lines.append("No strengths identified.")
    report_lines.append("")

    # Recommendations
    report_lines.append("PRIORITY RECOMMENDATIONS")
    report_lines.append("-" * 80)
    recommendations = assessment.get('recommendations', [])
    if recommendations:
        for i, rec in enumerate(recommendations, 1):
            report_lines.append(f"{i}. {rec}")
    else:
        report_lines.append("No recommendations provided.")
    report_lines.append("")

    # Detailed Observations
    report_lines.append("DETAILED OBSERVATIONS BY FAIR PRINCIPLE")
    report_lines.append("-" * 80)
    observations = assessment.get('observations', {})

    for principle in ['findability', 'accessibility', 'interoperability', 'reusability', 'implementation']:
        if principle in observations:
            report_lines.append(f"\n{principle.upper()}")
            report_lines.append(observations[principle])
    report_lines.append("")

    # Detailed Responses
    report_lines.append("=" * 80)
    report_lines.append("DETAILED INTERVIEW RESPONSES")
    report_lines.append("=" * 80)
    report_lines.append("")

    responses = data.get('responses', {})
    for section_name, questions in responses.items():
        report_lines.append(f"\n{section_name.upper()}")
        report_lines.append("-" * 80)
        for question_id, answer in questions.items():
            report_lines.append(f"\n{question_id}:")
            if isinstance(answer, list):
                for item in answer:
                    report_lines.append(f"  - {item}")
            else:
                report_lines.append(f"  {answer}")
        report_lines.append("")

    return "\n".join(report_lines)


def save_assessment(data: Dict[str, Any], output_dir: str = ".") -> tuple[str, str]:
    """
    Save assessment data to both JSON and text formats.

    Args:
        data: Assessment data dictionary
        output_dir: Directory to save files to

    Returns:
        Tuple of (json_path, text_path)
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate timestamp for filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON file
    json_filename = f"fair_assessment_{timestamp}.json"
    json_path = output_path / json_filename

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    # Save text report
    text_filename = f"fair_assessment_{timestamp}.txt"
    text_path = output_path / text_filename

    report = generate_text_report(data)
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(report)

    return str(json_path), str(text_path)


def main():
    """Main function to handle command-line execution."""
    if len(sys.argv) < 2:
        print("Usage: save_fair_assessment.py <json_data> [output_dir]", file=sys.stderr)
        print("\nExpects JSON data as first argument.", file=sys.stderr)
        sys.exit(1)

    # Parse input data
    try:
        data = json.loads(sys.argv[1])
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON data: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate data
    if not validate_assessment_data(data):
        print("Error: Invalid assessment data structure", file=sys.stderr)
        sys.exit(1)

    # Get output directory
    output_dir = sys.argv[2] if len(sys.argv) > 2 else "."

    # Save files
    try:
        json_path, text_path = save_assessment(data, output_dir)

        # Output success message with file paths
        result = {
            "status": "success",
            "json_file": json_path,
            "text_file": text_path,
            "message": "Assessment saved successfully"
        }
        print(json.dumps(result, indent=2))

    except Exception as e:
        print(f"Error saving assessment: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
