FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

RUN apt-get update && apt-get install -y cron && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod 0644 crontab
RUN crontab crontab

CMD ["cron", "-f"]