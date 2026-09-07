FROM python:3.12.8-bookworm
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src src
COPY packages packages
COPY apps apps
COPY services services
COPY scripts scripts
COPY evals evals
COPY migrations migrations
RUN pip install --no-cache-dir .
EXPOSE 8080
CMD ["python", "scripts/tf.py", "demo"]
