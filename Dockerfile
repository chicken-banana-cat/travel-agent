FROM python:3.12-slim

WORKDIR /app

# Copy requirements file
COPY pyproject.toml poetry.lock ./

# Install poetry
RUN pip install poetry

# Configure poetry
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --without dev --no-root

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Start the application
CMD ["uvicorn", "travel_agent.api.main:app", "--host", "0.0.0.0", "--port", "8000"] 