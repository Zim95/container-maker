FROM python:3.11-slim

# Create the directory
RUN mkdir app
COPY . app/
WORKDIR app

# install dependencies
RUN apt-get update && apt-get install -y build-essential
RUN pip install -r requirements.txt

# install container maker spec
RUN pip install container-maker-spec/

# Copy entrypoint script
COPY ./dockerfiles/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose ports for both services
EXPOSE 8888
EXPOSE 50051

# Use the entrypoint script
ENTRYPOINT ["/entrypoint.sh"]

