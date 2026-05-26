FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Data volume mount point — DB and CSV output land here
RUN mkdir -p /app/data/output

CMD ["python", "scheduler.py"]
