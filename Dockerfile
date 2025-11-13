# Use Python 3.10 or higher
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p uploads

COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 5025

# Use the entrypoint script
CMD ["./entrypoint.sh"]