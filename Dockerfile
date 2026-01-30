# Use official Python runtime
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Environment variables (to be provided via docker run or docker-compose)
ENV ZSXQ_COOKIE=""
ENV DINGTALK_WEBHOOK=""
ENV DINGTALK_SECRET=""
ENV AI_API_KEY=""
ENV AI_BASE_URL="https://api.deepseek.com"

# Run the application
CMD ["python", "main.py"]
