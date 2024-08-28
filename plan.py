import sys
from datetime import datetime, timedelta
from tabulate import tabulate
import yaml

# Load the YAML file
def load_activities_from_yaml(file_path):
    with open(file_path, 'r') as file:
        data = yaml.safe_load(file)
    return data['activities']

# Define the path to the YAML file
yaml_file_path = 'activities.yaml'

# Load the activities from the YAML file
activities = load_activities_from_yaml(yaml_file_path)

def calculate_last_thursday(year, month):
    """Calculate the last Thursday of a given month and year."""
    last_day = datetime(year, month + 1, 1) - timedelta(days=1) if month < 12 else datetime(year, 12, 31)
    offset = (last_day.weekday() - 3) % 7
    return last_day - timedelta(days=offset)

def calculate_quarter(date):
    """Calculate the quarter for a given date."""
    month = date.month
    year = date.year % 100  # Get last two digits of the year
    quarter = (month - 1) // 3 + 1
    return f"Q{quarter}{year:02d}"

def get_last_day_of_quarter(year, quarter):
    """Get the last day of the specified quarter."""
    if quarter == 1:
        return datetime(year, 3, 31)
    elif quarter == 2:
        return datetime(year, 6, 30)
    elif quarter == 3:
        return datetime(year, 9, 30)
    elif quarter == 4:
        return datetime(year, 12, 31)
    else:
        raise ValueError("Invalid quarter. Choose from Q1, Q2, Q3, or Q4.")

def get_ratification_position_in_quarter(bod_approval_end_date, quarter_start, quarter_end):
    """Determine where the BoD Approval date falls within the quarter."""
    quarter_duration = (quarter_end - quarter_start).days
    days_into_quarter = (bod_approval_end_date - quarter_start).days

    if days_into_quarter < quarter_duration * 0.25:
        return "beginning of"
    elif days_into_quarter < quarter_duration * 0.5:
        return "first half of"
    elif days_into_quarter < quarter_duration * 0.75:
        return "middle of"
    else:
        return "end of"

def calculate_dates_reverse(ratification_quarter, path):
    """Calculate dates in reverse given a target ratification quarter."""
    year = int("20" + ratification_quarter[2:4])
    quarter = int(ratification_quarter[1])

    if quarter == 1:
        quarter_start = datetime(year, 1, 1)  # Start of the year for Q1
    else:
        quarter_start = get_last_day_of_quarter(year, quarter - 1) + timedelta(days=1)

    quarter_end = get_last_day_of_quarter(year, quarter)
    last_thursday = calculate_last_thursday(quarter_end.year, quarter_end.month)

    current_date = last_thursday
    calculated_dates = []
    summary = {}
    total_days = 0

    # Store phases in a list to reverse the order after processing
    summary_list = []

    for phase in ["Ratification-Ready", "Freeze", "Development", "Plan"]:
        phase_activities = activities[phase] if phase != "Inception" else activities["Inception"][path]
        phase_tasks = []
        phase_duration = 0

        for task_name, duration in reversed(phase_activities):
            if duration == 0:
                continue  # Skip tasks with a duration of 0 days

            if task_name == "BoD Approval":
                start_date = end_date = last_thursday
            else:
                end_date = current_date
                start_date = end_date - timedelta(days=duration - 1)
                current_date = start_date - timedelta(days=1)  # Set current date to the day before the start date for the next task in reverse
                phase_duration += duration

            phase_tasks.insert(0, (phase, task_name, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), duration))

        calculated_dates.extend(phase_tasks)
        summary_list.insert(0, (phase, phase_tasks[0][2], phase_tasks[-1][3], phase_duration))  # Collect summary data in forward order
        total_days += phase_duration

    summary["total_days"] = total_days
    summary["ratification_quarter"] = ratification_quarter
    summary["phases"] = summary_list

    # Calculate where the BoD Approval falls within the quarter
    bod_approval_end_date = last_thursday
    ratification_position = get_ratification_position_in_quarter(bod_approval_end_date, quarter_start, quarter_end)
    summary["ratification_position"] = f"Ratification will happen in the {ratification_position} {ratification_quarter}."

    # Check if the total duration exceeds the available time in the quarter
    earliest_possible_start_date = current_date + timedelta(days=1)  # Adjusted for final start date
    if earliest_possible_start_date < datetime.now():
        print(f"Warning: The plan cannot fit within the target quarter {ratification_quarter}.")
        print("Recalculating the schedule to fit the earliest possible start date...\n")
        earliest_start_date = datetime.now().strftime("%Y-%m-%d")
        return calculate_dates_forward(earliest_start_date, path), summary

    return calculated_dates, summary

def calculate_dates_forward(start_date_str, path, replan_phase=None):
    start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
    current_date = start_date
    calculated_dates = []
    phases = ["Inception", "Plan", "Development", "Freeze", "Ratification-Ready"]
    summary = {}
    summary_list = []
    bod_approval_end_date = None

    if replan_phase:
        for phase in phases:
            if phase == replan_phase:
                break
            if phase == "Inception":
                calculated_dates.extend([(phase, task_name, None, None, None) for task_name, _ in activities["Inception"][path]])
            else:
                calculated_dates.extend([(phase, task_name, None, None, None) for task_name, _ in activities[phase]])

        phases = phases[phases.index(replan_phase):]

    total_days = 0
    ratification_quarter = None

    for phase in phases:
        phase_activities = activities[phase] if phase != "Inception" else activities["Inception"][path]
        phase_tasks = []
        phase_duration = 0

        for task_name, duration in phase_activities:
            if duration == 0:
                continue  # Skip tasks with a duration of 0 days

            if task_name == "BoD Approval":
                last_thursday = calculate_last_thursday(current_date.year, current_date.month)
                start_date = end_date = last_thursday
                bod_approval_end_date = end_date  # Track the BoD Approval end date
            else:
                start_date = current_date
                end_date = start_date + timedelta(days=duration - 1)
                current_date = end_date  # Set current date to end_date for next task
                phase_duration += duration

            phase_tasks.append((phase, task_name, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"), duration))

        calculated_dates.extend(phase_tasks)
        summary_list.append((phase, phase_tasks[0][2], phase_tasks[-1][3], phase_duration))
        total_days += phase_duration

        if phase == "Ratification-Ready":
            phase_end_date = end_date  # Ensure phase_end_date is defined
            ratification_quarter = calculate_quarter(phase_end_date)

    summary["total_days"] = total_days
    summary["ratification_quarter"] = ratification_quarter

    if bod_approval_end_date:
        quarter = int(ratification_quarter[1])
        quarter_start = get_last_day_of_quarter(bod_approval_end_date.year, quarter - 1) + timedelta(days=1) if quarter > 1 else datetime(bod_approval_end_date.year, 1, 1)
        quarter_end = get_last_day_of_quarter(bod_approval_end_date.year, quarter)
        ratification_position = get_ratification_position_in_quarter(bod_approval_end_date, quarter_start, quarter_end)
        summary["ratification_position"] = f"Ratification will happen in the {ratification_position} {ratification_quarter}."
    else:
        summary["ratification_position"] = ""

    summary["phases"] = summary_list
    return calculated_dates, summary

def print_summary(summary):
    ratification = summary.get("ratification_quarter", "N/A")
    ratification_position = summary.get("ratification_position", "")
    print(f"\nTotal Duration: {summary['total_days']} days | Ratification: {ratification} | {ratification_position}")
    summary_table = []
    for phase, start_date, end_date, duration in summary["phases"]:
        summary_table.append([
            phase,
            start_date,
            end_date,
            duration
        ])
    headers = ["Phase", "Start Date", "End Date", "Duration (Days)"]
    print(tabulate(summary_table, headers, tablefmt="pretty"))

def print_schedule_table(calculated_dates):
    table = []
    phases_order = ["Inception", "Plan", "Development", "Freeze", "Ratification-Ready"]
    for phase in phases_order:
        phase_tasks = [item for item in calculated_dates if item[0] == phase]
        table.extend(phase_tasks)
    headers = ["Phase", "Activity", "Start Date", "End Date", "Duration (Days)"]
    print(tabulate(table, headers, tablefmt="pretty"))

def print_help():
    help_message = """
Usage: python script_name.py <path> [OPTIONS]

Script to calculate project timelines based on the path ('regular' or 'fast-track').

Modes of Operation:
  1. Default Mode (Forward Calculation):
     - This mode calculates the project timeline starting from today's date or a specified start date.
     - Usage: python script_name.py <path>
     - Example: python script_name.py regular

  2. Reverse Mode:
     - This mode calculates the project timeline in reverse, starting from a target ratification quarter.
     - Requires the --reverse and --target-quarter options.
     - Usage: python script_name.py <path> --reverse --target-quarter=<Q1XX>
     - Example: python script_name.py regular --reverse --target-quarter=Q425

  3. Replan Mode:
     - This mode recalculates the project timeline starting from a specified phase (e.g., 'Development').
     - Optionally, a new start date can be provided.
     - Usage: python script_name.py <path> --replan=<phase> [--start-date=<YYYY-MM-DD>]
     - Example: python script_name.py fast-track --replan=Freeze
     - Example: python script_name.py regular --replan=Development --start-date=2024-11-01

Options:
  --reverse                Run the script in reverse mode to backtrack from a target ratification quarter.
  --target-quarter=<Q1XX>  Specify the target ratification quarter (e.g., Q425 for Q4 of 2025).
  --replan=<phase>         Recalculate the timeline starting from the specified phase.
  --start-date=<YYYY-MM-DD>  Provide a specific start date for forward or replan mode.
  --help                   Display this help message.

Examples:
  1. Default Mode:
     python script_name.py regular

  2. Reverse Mode:
     python script_name.py regular --reverse --target-quarter=Q425

  3. Replan Mode:
     python script_name.py fast-track --replan=Development --start-date=2024-10-01
    """
    print(help_message)

if __name__ == "__main__":
    if len(sys.argv) < 2 or "--help" in sys.argv:
        print_help()
        sys.exit(0)

    replan_phase = None
    start_date_str = datetime.now().strftime("%Y-%m-%d")  # Default to current date
    target_quarter = None

    for arg in sys.argv:
        if arg.startswith("--replan"):
            replan_phase = arg.split("=")[1]
        if arg.startswith("--start-date"):
            start_date_str = arg.split("=")[1]
        if arg.startswith("--target-quarter"):
            target_quarter = arg.split("=")[1]

    path = sys.argv[1].lower()

    if path not in ["regular", "fast-track"]:
        print("Invalid path. Choose either 'regular' or 'fast-track'.")
        sys.exit(1)

    if "--reverse" in sys.argv:
        if not target_quarter:
            print("Error: --reverse requires --target-quarter to be specified.")
            sys.exit(1)
        calculated_dates, summary = calculate_dates_reverse(target_quarter, path)
    else:
        calculated_dates, summary = calculate_dates_forward(start_date_str, path, replan_phase)

    print_summary(summary)
    print_schedule_table(calculated_dates)
