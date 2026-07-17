FROM jsfrnc/mt5-docker-api:latest

# Install required packages
RUN pip install --no-cache-dir requests uvicorn fastapi websockets

# Fix: add wine_version to DefaultSettings (missing in base image)
RUN sed -i 's/required_packages = \[/wine_version = "wine-11.0"\n        required_packages = [/' /app/Metatrader/start.py

# Verify fix
RUN grep -n "wine_version" /app/Metatrader/start.py

ENV API_PORT=8000
ENV VNC_PORT=3000
ENV VNC_PASSWORD=alphastack

EXPOSE 3000 8000
