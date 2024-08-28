# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Install any dependencies specified in requirements.txt
RUN pip install --no-cache-dir Flask pandas requests PyGithub gunicorn apscheduler PyYAML

# Copy the rest of the application code into the container
COPY . .

# Expose port 5031 to allow external access to the Flask app
EXPOSE 5032

# Command to run the Flask application with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5032", "app:app"]