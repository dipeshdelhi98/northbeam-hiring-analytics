FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY pipeline pipeline
COPY metrics metrics
COPY api api
COPY web web
COPY data/landing data/landing
COPY tests tests
# Build the warehouse into the image and refuse to ship if the controls don't tie.
RUN python -m pipeline.run && python -m pytest -q tests/test_controls.py \
    && rm -rf data/landing tests
ENV NB_LANDING_DIR=/nonexistent
EXPOSE 8000
USER nobody
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
