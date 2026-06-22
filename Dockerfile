FROM python:3.12-slim

# StormLib (von RichChk mitgeliefert) braucht keine extra System-Libs auf glibc-Basis.
# 'slim' (Debian) ist glibc -> kompatibel mit der mitgelieferten StormLib .so.

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SC_TRANSPORT=http \
    SC_HOST=0.0.0.0 \
    SC_PORT=8000 \
    SC_MAPS_DIR=/data/maps

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY starcraft_mcp /app/starcraft_mcp
COPY selftest.py /app/selftest.py

# Karten-Volume (Basis-Karten, WAVs, fertige Missionen).
RUN mkdir -p /data/maps
VOLUME ["/data/maps"]

EXPOSE 8000

# Streamable-HTTP-Endpunkt unter http://0.0.0.0:8000/mcp
CMD ["python", "-m", "starcraft_mcp.server"]
