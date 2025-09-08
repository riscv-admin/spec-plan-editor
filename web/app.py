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
        data = request.json
        start_date = data['start_date']

    calculated_dates = []
    current_date = datetime.strptime(start_date, '%Y-%m-%d')

    for phase, tasks in activities.items():
        for task in tasks:
            task_name, duration = task
            start_date_str = current_date.strftime('%Y-%m-%d')

            # Compute end_date
            if task_name == 'BoD Approval':
                # Resolve after we have prev_end_date; placeholder for now
                end_date = current_date
            elif duration == 0:
                # Show milestone on the current day but DO NOT consume time
                end_date = current_date
            else:
                end_date = current_date + timedelta(days=duration - 1)

            # Special handling for BoD Approval (unchanged logic, just clearer)
            if task_name == 'BoD Approval':
                prev_end_str = calculated_dates[-1][3]
                prev_end_date = datetime.strptime(prev_end_str, '%Y-%m-%d')
                min_date = prev_end_date + timedelta(days=10)

                current_last_thursday = get_last_thursday(min_date.year, min_date.month)
                if current_last_thursday < min_date:
                    next_month = min_date.month + 1
                    next_year = min_date.year + (1 if next_month > 12 else 0)
                    if next_month > 12:
                        next_month = 1
                    current_last_thursday = get_last_thursday(next_year, next_month)

                end_date = current_last_thursday

            end_date_str = end_date.strftime('%Y-%m-%d')
            calculated_dates.append((phase, task_name, start_date_str, end_date_str, duration))

            # Advance start **only** if the task consumed time
            if task_name == 'BoD Approval' or duration > 0:
                current_date = end_date + timedelta(days=1)
            # else: keep current_date as-is (zero-duration no-op)

    return render_template('index.html', calculated_dates=calculated_dates, start_date=start_date)

@app.route('/export', methods=['POST'])
def export():
    return jsonify({'status': 'success', 'message': 'Exported successfully!'})

if __name__ == '__main__':
    app.run(debug=True)