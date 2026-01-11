FROM python:3.11-slim

WORKDIR /app

# Install git if needed for myPyllant or other dependencies
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run unbuffered for logs
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
