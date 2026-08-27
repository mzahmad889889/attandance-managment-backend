FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# build-essential: insightface compiles a C++ extension; libgl1/libglib2.0-0: opencv runtime
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Bake the buffalo_sc face model into the image so first request doesn't need a download
RUN python -c "from insightface.app import FaceAnalysis; FaceAnalysis(name='buffalo_sc', providers=['CPUExecutionProvider'])" || true

COPY . .

RUN mkdir -p uploads/workers uploads/snapshots

EXPOSE 5000

CMD ["./docker-entrypoint.sh"]
