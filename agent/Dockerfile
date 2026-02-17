FROM python:3.11-slim

WORKDIR /agent

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt /agent/requirements.txt
RUN pip install --no-cache-dir -r /agent/requirements.txt

COPY . /agent

CMD ["python", "/agent/app.py", "--http"]
