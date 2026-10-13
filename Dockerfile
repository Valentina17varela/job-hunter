# Job Hunter in a container: Python + uv + TeX Live (latexmk). The `claude` CLI is NOT included:
# use an API key (anthropic_api) inside the container. See docs/SETUP.md#docker.
# TeX Live from apt works on amd64 and arm64 and needs no internet at run time
# (tectonic has no official arm64 Linux build); `latex.engine: auto` picks latexmk.
FROM python:3.12-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates latexmk lmodern \
      texlive-latex-base texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended \
 && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY config ./config
COPY src ./src
RUN uv pip install --system --no-cache .

# Your data lives in the mounted workspace, never in the image.
WORKDIR /workspace
ENV PYTHONUNBUFFERED=1
EXPOSE 8765
CMD ["jobhunter", "ui", "--bind", "0.0.0.0", "--port", "8765"]
