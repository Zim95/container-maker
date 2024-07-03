FROM python:3.11-slim

# Environment Variables
ENV server_threads=10
ENV address="0.0.0.0"
ENV port=50052
ENV use_ssl=true
ENV jupyter_notebook_ip="0.0.0.0"
ENV jupyter_notebook_port=8889

# Create the directory
RUN mkdir app
COPY ./container-maker-spec app/
COPY ./demo app/
COPY ./deployment/entrypoint.sh app/entrypoint.sh
COPY ./src app/
COPY app.py app/
WORKDIR app

# install dependencies
RUN apt-get update && apt-get install -y build-essential
RUN pip install -r requirements.txt

# Entrypoint
ENTRYPOINT ["/entrypoint.sh"]
