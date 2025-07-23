FROM python:3.12-slim-bookworm

COPY app /app
COPY README.md /README.md
COPY requirements.txt /requirements.txt

RUN pip install -r requirements.txt

CMD ["python", "-m", "app.app"]
