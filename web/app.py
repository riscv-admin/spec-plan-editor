from flask import Flask, render_template, request, jsonify
import yaml, calendar
from datetime import datetime, timedelta

app = Flask(__name__)

# Load the activities from a YAML file
with open('activities.yaml', 'r') as file:
    data = yaml.safe_load(file)
    activities = data['activities']

def get_last_thursday(year, month):
    """Return the last Thursday of a given month."""
    # Get the last day of the month
    last_day = calendar.monthrange(year, month)[1]
    last_day_date = datetime(year, month, last_day)

    # Calculate the offset to the last Thursday
    offset = (last_day_date.weekday() - calendar.THURSDAY) % 7
    last_thursday = last_day_date - timedelta(days=offset)
    print (last_thursday)
    return last_thursday


@app.route('/', methods=['GET', 'POST'])
def index():
    start_date = datetime.today().strftime('%Y-%m-%d')

    if request.method == 'POST':
        # Process the posted data
        data = request.json
        start_date = data['start_date']

    calculated_dates = []
    current_date = datetime.strptime(start_date, '%Y-%m-%d')

    for phase, tasks in activities.items():
        for task in tasks:
            task_name, duration = task
            start_date_str = current_date.strftime('%Y-%m-%d')

            # Default end date based on duration
            if duration == 0:
                end_date = current_date
            else:
                end_date = current_date + timedelta(days=duration - 1)

            # Special handling for BoD Approval
            if task_name == 'BoD Approval':
                # Get the actual end date of the preceding task
                prev_end_str = calculated_dates[-1][3]  # end date of the last entry in calculated_dates
                prev_end_date = datetime.strptime(prev_end_str, '%Y-%m-%d')

                # Must be at least 10 days after the last approval
                min_date = prev_end_date + timedelta(days=10)

                # Find the last Thursday of that month
                current_last_thursday = get_last_thursday(min_date.year, min_date.month)

                # If that last Thursday is still before min_date, move to the next month
                if current_last_thursday < min_date:
                    next_month = min_date.month + 1
                    next_year = min_date.year
                    if next_month > 12:
                        next_month = 1
                        next_year += 1
                    current_last_thursday = get_last_thursday(next_year, next_month)

                end_date = current_last_thursday

            end_date_str = end_date.strftime('%Y-%m-%d')
            calculated_dates.append((phase, task_name, start_date_str, end_date_str, duration))

            # Next task starts the day after this one ends
            current_date = end_date + timedelta(days=1)

    return render_template('index.html', calculated_dates=calculated_dates, start_date=start_date)

@app.route('/export', methods=['POST'])
def export():
    return jsonify({'status': 'success', 'message': 'Exported successfully!'})

if __name__ == '__main__':
    app.run(debug=True)