FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py assistants.py brief.py chart.py chat.py handoff_schema.py handoffs.py handover.py muse.py onboarding.py rules.py sam.py store.py timed.py tools.py trust.py vision.py voice.py workflow.py workspace.py ./
COPY data ./data
COPY static ./static
ENV PYTHONUNBUFFERED=1
# One process: every request must see the same in-memory SQLite. Threads give concurrency.
CMD exec gunicorn --workers 1 --threads 8 --timeout 120 --bind 0.0.0.0:${PORT:-8080} app:app
