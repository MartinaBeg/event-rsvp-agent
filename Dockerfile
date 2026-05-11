FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src

RUN pip install .

# Mount your workbook at /data/rsvp.xlsx and set EXCEL_PATH=/data/rsvp.xlsx.
VOLUME ["/data"]
ENV EXCEL_PATH=/data/rsvp.xlsx

CMD ["python", "-m", "icp_agent"]
