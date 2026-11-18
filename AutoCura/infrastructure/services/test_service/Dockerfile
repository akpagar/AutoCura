FROM python:3.11-slim

WORKDIR /app
COPY server.py .

ENV PORT=9000
EXPOSE 9000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:9000/health', timeout=2)" || exit 1

CMD ["python", "server.py"]
