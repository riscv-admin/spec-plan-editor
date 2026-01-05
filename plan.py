# SPDX-License-Identifier: Apache-2.0

"""
Specification Plan Editor - Timeline Calculation Tool

This module calculates project timelines based on activities defined in a YAML file.
It supports different estimation modes (optimistic, most likely, pessimistic) and
can generate schedules starting from different project phases.
"""

import argparse
import csv
import calendar
import math
import re
from datetime import datetime, timedelta

import yaml
from tabulate import tabulate

# Path to the YAML file containing activity definitions
ACTIVITIES_FILE = "web/activities.yaml"

# Ordered list of project phases - defines the sequence of the specification lifecycle
PHASE_ORDER = [
    "Inception",
    "Planning",
    "Development",
    "Stabilization",
    "Freezing",
    "Ratification-Ready",
    "Publication",
]


def load_activities_from_yaml(file_path):
    """
    Load activities from a YAML configuration file.

    Args:
        file_path: Path to the YAML file containing activity definitions

    Returns:
        Dictionary of activities organized by phase
    """
    with open(file_path, "r") as file:
        data = yaml.safe_load(file)
    return data["activities"]


def normalize_phase(name):
    """
    Normalize phase names by converting to lowercase and replacing separators with spaces.

    Args:
        name: Phase name to normalize

    Returns:
        Normalized phase name (lowercase, spaces instead of underscores/hyphens)
    """
    return re.sub(r"[\s_-]+", " ", str(name).strip().lower())


# Create a lookup dictionary for phase validation (normalized name -> canonical name)
PHASE_LOOKUP = {normalize_phase(phase): phase for phase in PHASE_ORDER}


def parse_phase(value):
    """
    Parse and validate a phase name, returning the canonical phase name.

    Args:
        value: Phase name to parse and validate

    Returns:
        Canonical phase name from PHASE_ORDER

    Raises:
        ValueError: If the phase name is not valid
    """
    key = normalize_phase(value)
    if key not in PHASE_LOOKUP:
        raise ValueError(
            f"Invalid phase '{value}'. Choose one of: {', '.join(PHASE_ORDER)}"
        )
    return PHASE_LOOKUP[key]


def is_public_review_activity(name):
    """
    Check if an activity name indicates a public review period.

    Args:
        name: Activity name to check

    Returns:
        True if the activity is a public review activity
    """
    normalized = re.sub(r"\s+", " ", str(name).strip().lower())
    return normalized.startswith("public review")


def is_approval_activity(name):
    """
    Check if an activity name indicates an approval activity.

    Args:
        name: Activity name to check

    Returns:
        True if the activity name contains 'approval'
    """
    return re.search(r"approval", str(name), re.IGNORECASE) is not None


def is_governing_committee_review(name):
    """
    Check if an activity name indicates a governing committee review.

    Args:
        name: Activity name to check

    Returns:
        True if the activity is a governing committee review
    """
    return (
        re.search(r"governing[\s-]*committee[\s-]*review", str(name).lower())
        is not None
    )


def is_internal_review(name):
    """
    Check if an activity name indicates an internal review.

    Args:
        name: Activity name to check

    Returns:
        True if the activity is an internal review
    """
    return re.search(r"internal[\s-]*review", str(name).lower()) is not None


def effective_duration_for(activity_name, base_duration, estimate_mode):
    """
    Calculate the effective duration for an activity based on the estimate mode.

    Certain activities (public reviews, approvals, committee reviews) always use
    the base duration. Other activities are adjusted based on the estimate mode:
    - optimistic: 70% of base duration (minimum 1 day)
    - pessimistic: 130% of base duration
    - most_likely: base duration unchanged

    Args:
        activity_name: Name of the activity
        base_duration: Base duration in days
        estimate_mode: Estimation mode (optimistic, most_likely, or pessimistic)

    Returns:
        Effective duration in days
    """
    if base_duration == 0:
        return 0
    # Fixed duration activities - not subject to estimation adjustments
    if is_public_review_activity(activity_name):
        return base_duration
    if (
        is_approval_activity(activity_name)
        or is_governing_committee_review(activity_name)
        or is_internal_review(activity_name)
    ):
        return base_duration
    # Apply estimation mode adjustments for other activities
    if estimate_mode == "optimistic":
        return max(1, math.floor(base_duration * 0.7))
    if estimate_mode == "pessimistic":
        return math.ceil(base_duration * 1.3)
    return base_duration


def get_last_thursday(year, month):
    """
    Calculate the date of the last Thursday of a given month.

    This is used for BoD (Board of Directors) approval meetings which are
    typically scheduled on the last Thursday of the month.

    Args:
        year: Year
        month: Month (1-12)

    Returns:
        datetime object representing the last Thursday of the month
    """
    last_day = calendar.monthrange(year, month)[1]
    last_day_date = datetime(year, month, last_day)
    # Calculate days to go back to reach Thursday
    offset = (last_day_date.weekday() - calendar.THURSDAY) % 7
    return last_day_date - timedelta(days=offset)


def calculate_schedule(
    activities, start_date_str, start_from, handoff_mode, estimate_mode
):
    """
    Calculate the complete project schedule based on activities and parameters.

    Args:
        activities: Dictionary of activities organized by phase
        start_date_str: Start date in YYYY-MM-DD format
        start_from: Phase to start from (earlier phases have zero duration)
        handoff_mode: Task dependency mode ('end_to_start' or 'start_when_end')
        estimate_mode: Estimation mode (optimistic, most_likely, or pessimistic)

    Returns:
        Tuple of (calculated_dates, summary) where:
        - calculated_dates: List of tuples (phase, task, start, end, duration)
        - summary: Dictionary with total days, ratification text, and phase summary
    """
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    current_start_date = start_date
    start_from_index = PHASE_ORDER.index(start_from)
    # Gap between tasks: 1 day for end_to_start, 0 for start_when_end
    gap_days = 1 if handoff_mode == "end_to_start" else 0

    calculated_dates = []
    summary_phases = []
    overall_start = None
    overall_end = None
    last_end_date = None
    bod_end_date = None  # Track BoD approval date for ratification quarter

    # Iterate through all phases in order
    for phase in PHASE_ORDER:
        if phase not in activities:
            raise ValueError(f"Missing phase '{phase}' in {ACTIVITIES_FILE}.")

        phase_tasks = activities[phase]
        phase_start = None
        phase_end = None

        # Process each task in the current phase
        for task_name, duration in phase_tasks:
            try:
                base_duration = int(duration)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"Invalid duration for '{task_name}' in '{phase}': {duration}"
                ) from exc

            # Set duration to 0 for phases before the start_from phase
            if PHASE_ORDER.index(phase) < start_from_index:
                base_duration = 0

            # Calculate effective duration based on estimate mode
            effective_duration = effective_duration_for(
                task_name, base_duration, estimate_mode
            )

            start_date = current_start_date
            end_date = start_date
            if effective_duration != 0:
                # End date is start + duration - 1 (inclusive)
                end_date = start_date + timedelta(days=effective_duration - 1)

            # Special handling for BoD Approval: must be on last Thursday of month
            if task_name == "BoD Approval":
                # Ensure at least 10 days from last activity
                min_date = (
                    last_end_date + timedelta(days=10)
                    if last_end_date
                    else start_date
                )
                last_thursday = get_last_thursday(min_date.year, min_date.month)
                # If last Thursday of current month is too early, use next month
                if last_thursday < min_date:
                    next_month = min_date.month + 1
                    next_year = min_date.year + (1 if next_month > 12 else 0)
                    if next_month > 12:
                        next_month = 1
                    last_thursday = get_last_thursday(next_year, next_month)
                end_date = last_thursday
                bod_end_date = end_date

            # Store the calculated task dates
            calculated_dates.append(
                (
                    phase,
                    task_name,
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d"),
                    effective_duration,
                )
            )

            # Track phase boundaries
            if phase_start is None:
                phase_start = start_date
            phase_end = end_date

            # Track overall project boundaries
            if overall_start is None:
                overall_start = start_date
            overall_end = end_date
            last_end_date = end_date

            # Move to next task start date (with gap if configured)
            if task_name == "BoD Approval" or effective_duration > 0:
                current_start_date = end_date + timedelta(days=gap_days)

        # Add phase summary if it has activities
        if phase_start and phase_end:
            phase_duration = max(1, (phase_end - phase_start).days + 1)
            summary_phases.append(
                (
                    phase,
                    phase_start.strftime("%Y-%m-%d"),
                    phase_end.strftime("%Y-%m-%d"),
                    phase_duration,
                )
            )
        else:
            # Phase was skipped or has no activities
            summary_phases.append((phase, "", "", 0))

    # Calculate total project duration
    total_days = 0
    if overall_start and overall_end:
        total_days = max(1, (overall_end - overall_start).days + 1)

    # Generate ratification quarter information based on BoD approval date
    ratification_text = ""
    if bod_end_date:
        quarter = (bod_end_date.month - 1) // 3 + 1
        ratification_text = (
            f"Ratification will happen in Q{quarter}{bod_end_date.year}, "
            f"with the BoD meeting on {bod_end_date.strftime('%Y-%m-%d')}."
        )

    summary = {
        "total_days": total_days,
        "ratification_text": ratification_text,
        "phases": summary_phases,
    }
    return calculated_dates, summary


def print_summary(summary):
    """
    Print a high-level summary of the project schedule.

    Displays total duration, ratification information, and a table of phases
    with their start/end dates and durations.

    Args:
        summary: Summary dictionary from calculate_schedule
    """
    ratification_text = summary.get("ratification_text", "")
    print(f"\nTotal Duration: {summary['total_days']} days")
    if ratification_text:
        print(ratification_text)
    summary_table = [
        [phase, start_date, end_date, duration]
        for phase, start_date, end_date, duration in summary["phases"]
    ]
    headers = ["Phase", "Start Date", "End Date", "Duration (Days)"]
    print(tabulate(summary_table, headers, tablefmt="pretty"))


def print_schedule_table(calculated_dates):
    """
    Print a detailed schedule table showing all activities.

    Displays each activity with its phase, start date, end date, and duration
    in a formatted table.

    Args:
        calculated_dates: List of calculated task dates from calculate_schedule
    """
    table = []
    # Group tasks by phase in the correct order
    for phase in PHASE_ORDER:
        phase_tasks = [item for item in calculated_dates if item[0] == phase]
        table.extend(phase_tasks)
    headers = ["Phase", "Activity", "Start Date", "End Date", "Duration (Days)"]
    print(tabulate(table, headers, tablefmt="pretty"))


def build_plan_summary(calculated_dates):
    """
    Build a milestone-focused summary of the project plan.

    Extracts key milestones from the calculated schedule and formats them
    as a list of milestone labels with their target dates.

    Args:
        calculated_dates: List of calculated task dates from calculate_schedule

    Returns:
        List of [milestone_label, date] pairs for display
    """
    # Convert calculated dates into a more query-friendly format
    rows = [
        {
            "phase": phase,
            "activity": activity,
            "start": start_date,
            "end": end_date,
        }
        for phase, activity, start_date, end_date, _ in calculated_dates
    ]
    # Group rows by phase for easier lookup
    rows_by_phase = {}
    for row in rows:
        rows_by_phase.setdefault(row["phase"], []).append(row)

    def find_by_activity(activity_substr, phase_filter=None):
        """Find a row by activity name substring and optional phase filter."""
        for row in rows:
            if activity_substr in row["activity"]:
                if phase_filter is None or row["phase"] == phase_filter:
                    return row
        return None

    # Define the key milestones to extract from the schedule
    milestones = [
        {
            "label": "Inception Completed by",
            "dateType": "end",
            "phase": "Inception",
        },
        {"label": "Plan Approved by", "dateType": "end", "phase": "Planning"},
        {
            "label": "Specification Development Completed (v0.6) by",
            "dateType": "end",
            "activity": "Governing Committee Approval",
            "phase": "Development",
        },
        {
            "label": "Internal Review Start (v0.6) by",
            "dateType": "start",
            "activity": "Internal Review (14-day minimum)",
            "phase": "Development",
        },
        {
            "label": "Specification Stabilized (v0.8) by",
            "dateType": "end",
            "phase": "Stabilization",
        },
        {
            "label": "ARC Freeze Approval Request by",
            "dateType": "start",
            "phase": "Freezing",
        },
        {
            "label": "Specification Frozen (v0.9) by",
            "dateType": "end",
            "phase": "Freezing",
        },
        {
            "label": "Public Review Start (v0.9) by",
            "dateType": "start",
            "phase": "Ratification-Ready",
        },
        {
            "label": "TSC Approval (v0.99) by",
            "dateType": "end",
            "phase": "Ratification-Ready",
        },
        {
            "label": "Specification Ratified (v1.0) by",
            "dateType": "end",
            "phase": "Publication",
        },
    ]

    # Extract milestone dates from the schedule
    summary_rows = []
    for milestone in milestones:
        relevant_row = None
        activity = milestone.get("activity")
        phase = milestone.get("phase")

        # Find the relevant activity or phase
        if activity:
            relevant_row = find_by_activity(activity, milestone.get("phaseFilter"))
        elif phase:
            phase_rows = rows_by_phase.get(phase, [])
            if phase_rows:
                # Use first row for start dates, last row for end dates
                relevant_row = (
                    phase_rows[0]
                    if milestone["dateType"] == "start"
                    else phase_rows[-1]
                )

        # Special case: Specification Development uses Governing Committee Approval date
        if (
            milestone["label"]
            == "Specification Development Completed (v0.6) by"
        ):
            override_row = find_by_activity(
                "Governing Committee Approval", phase_filter="Development"
            )
            if override_row:
                relevant_row = override_row

        # Extract the appropriate date (start or end) from the relevant row
        if relevant_row:
            date_value = (
                relevant_row["start"]
                if milestone["dateType"] == "start"
                else relevant_row["end"]
            )
        else:
            date_value = "N/A"

        summary_rows.append([milestone["label"], date_value])

    return summary_rows


def print_plan_summary(summary_rows):
    """
    Print a table of key milestones and their target dates.

    Args:
        summary_rows: List of [milestone_label, date] pairs from build_plan_summary
    """
    headers = ["Plan Summary", "Date"]
    print(tabulate(summary_rows, headers, tablefmt="pretty"))


def slugify_filename(value):
    """
    Convert a string to a filesystem-safe slug.

    Converts to lowercase, replaces spaces with hyphens, removes special
    characters, and consolidates multiple hyphens.

    Args:
        value: String to slugify

    Returns:
        Slugified string safe for use in filenames
    """
    normalized = str(value).strip().lower().replace(" ", "-")
    # Remove non-alphanumeric characters (except hyphens and underscores)
    normalized = re.sub(r"[^a-z0-9_-]+", "-", normalized)
    # Consolidate multiple hyphens
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized or "phase"


def build_summary_csv_filename(start_from, estimate_mode, start_date_str):
    """
    Build a descriptive filename for the CSV export.

    Format: {phase}_{estimate_mode}_{start_date}_.csv

    Args:
        start_from: Starting phase name
        estimate_mode: Estimation mode used
        start_date_str: Start date string

    Returns:
        CSV filename string
    """
    phase_part = slugify_filename(start_from)
    estimate_part = slugify_filename(estimate_mode)
    return f"{phase_part}_{estimate_part}_{start_date_str}_.csv"


def write_plan_summary_csv(summary_rows, filename):
    """
    Write the plan summary to a CSV file.

    Args:
        summary_rows: List of [milestone_label, date] pairs
        filename: Output CSV filename
    """
    with open(filename, "w", newline="") as file:
        writer = csv.writer(file)
        for row in summary_rows:
            writer.writerow(row)


def build_parser():
    """
    Build the command-line argument parser.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description="Calculate project timelines based on web activities."
    )
    parser.add_argument(
        "--start-date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="Start date in YYYY-MM-DD format (default: today).",
    )
    parser.add_argument(
        "--start-from",
        default="Inception",
        help="Phase to start from; earlier phases are set to zero duration.",
    )
    parser.add_argument(
        "--handoff-mode",
        choices=["end_to_start", "start_when_end"],
        default="end_to_start",
        help="Task dependency mode (next day or same day).",
    )
    parser.add_argument(
        "--estimate-mode",
        choices=["most_likely", "optimistic", "pessimistic"],
        default="most_likely",
        help="Three-point estimate mode.",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Write the plan summary CSV to the current directory.",
    )
    return parser


def main():
    """
    Main entry point for the plan editor CLI.

    Parses command-line arguments, calculates the project schedule, and
    displays/exports the results based on user options.
    """
    parser = build_parser()
    args = parser.parse_args()

    # Validate and parse the start_from phase
    try:
        start_from = parse_phase(args.start_from)
    except ValueError as exc:
        print(exc)
        raise SystemExit(1)

    # Load activities and calculate schedule
    activities = load_activities_from_yaml(ACTIVITIES_FILE)
    calculated_dates, summary = calculate_schedule(
        activities,
        args.start_date,
        start_from,
        args.handoff_mode,
        args.estimate_mode,
    )
    summary_rows = build_plan_summary(calculated_dates)

    # Display results
    print_summary(summary)
    print_plan_summary(summary_rows)
    print_schedule_table(calculated_dates)

    # Export to CSV if requested
    if args.csv:
        filename = build_summary_csv_filename(
            start_from, args.estimate_mode, args.start_date
        )
        write_plan_summary_csv(summary_rows, filename)
        print(f"\nWrote plan summary CSV to {filename}")


if __name__ == "__main__":
    main()
