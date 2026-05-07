FROM mcr.microsoft.com/playwright/python:v1.51.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright browsers are pre-installed in the base image; only install chromium
RUN playwright install chromium

COPY . .

EXPOSE 8080

CMD ["python", "main.py"]
