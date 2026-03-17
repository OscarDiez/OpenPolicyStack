# Use an official Python runtime as a parent image, using slim for a smaller footprint
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container at /app
COPY requirements.txt .

# Install dependencies directly
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Ensure the data directory exists so the app doesn't crash if it's missing
RUN mkdir -p /app/data

# Expose the API port (Adrian's reverse proxy will route to this)
EXPOSE 8000

# Set the environment variable for Python so it doesn't buffer outputs
ENV PYTHONUNBUFFERED=1

# Command to run the application using uvicorn
CMD ["uvicorn", "src.app:app", "--host", "0.0.0.0", "--port", "8000"]
