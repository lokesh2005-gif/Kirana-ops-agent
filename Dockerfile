FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create artifact directories
RUN mkdir -p artifacts/invoices artifacts/reports

# Default: run in webhook mode (override USE_WEBHOOK in environment for local dev)
ENV USE_WEBHOOK=true
ENV PORT=8443

EXPOSE 8443

CMD ["python", "-m", "app.telegram.bot"]
