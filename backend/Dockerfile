FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock
COPY backend/ .
COPY data/raw/districts.json /data/districts.json
COPY data/raw/neighborhoods.json /data/neighborhoods.json
COPY data/raw/bursa-settlement-centers.json /data/settlements.json
ENV SETTLEMENT_DATA=/data/settlements.json
ENV NEIGHBORHOOD_DATA=/data/neighborhoods.json
ENV DISTRICT_DATA=/data/districts.json PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --create-home appuser
USER appuser
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed && python -m app.geography_import && python -m app.demo_seed --citywide && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
