from flask import Flask, render_template, request, jsonify
import yaml
from datetime import datetime, timedelta

app = Flask(__name__)

# Load the activities from a YAML file
with open('activities.yaml', 'r') as file:
    data = yaml.safe_load(file)
    activities = data['activities']

def get_last_thursday(year, month):
    """Return the last Thursday of a given month."""
    last_day = datetime(year, month + 1, 1) - timedelta(days=1)
    offset = (last_day.weekday() - 3) % 7  # Thursday is 3 in Python's weekday()
    last_thursday = last_day - timedelta(days=offset)
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

            if duration == 0:
                end_date = current_date
            else:
                end_date = current_date + timedelta(days=duration - 1)

            if task_name == 'BoD Approval':
                # Ensure BoD Approval falls on the last Thursday
                end_date = get_last_thursday(end_date.year, end_date.month)

            end_date_str = end_date.strftime('%Y-%m-%d')

            calculated_dates.append((phase, task_name, start_date_str, end_date_str, duration))
            current_date = end_date + timedelta(days=1)

    return render_template('index.html', calculated_dates=calculated_dates, start_date=start_date)

@app.route('/export', methods=['POST'])
def export():
    return jsonify({'status': 'success', 'message': 'Exported successfully!'})

if __name__ == '__main__':
    app.run(debug=True)