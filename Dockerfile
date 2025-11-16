# Use the official Playwright Python image
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY main.py .
COPY scraper.py .
COPY utils.py .
COPY selectors.json .

# Set the entrypoint to run the main script
ENTRYPOINT ["python", "main.py"]