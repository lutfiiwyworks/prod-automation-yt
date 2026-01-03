FROM python:3.10-slim

WORKDIR /app

# system deps + rclone
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    fontconfig \
    libgl1 \
    libglib2.0-0 \
    ca-certificates \
    curl \
    unzip \
    && curl -fsSL https://rclone.org/install.sh | bash \
    && rm -rf /var/lib/apt/lists/*

# fonts
COPY fonts /usr/share/fonts/truetype/custom
RUN fc-cache -fv

# python deps
COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt


COPY api /app

ENV PYTHONPATH=/app
ENV TZ=Asia/Jakarta

CMD ["uvicorn", "api.app:app", "--host", "0.0.0.0", "--port", "8000"]
