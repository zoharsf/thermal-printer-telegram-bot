FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    bluez \
    bluetooth \
    git \
    fonts-dejavu-core \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev

RUN git clone --depth 1 https://github.com/NaitLee/Cat-Printer cat-printer

COPY src/ src/

RUN mkdir -p /data/images

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "catprint_bot.main"]
