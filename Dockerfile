FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# docker run -e WB_BOT_TOKEN=... -e STAR_PAYMENTS=1 ...
CMD ["python", "bot.py"]
