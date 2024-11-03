FROM python:3.11-slim

# Create the directory
RUN mkdir app
COPY . app/
WORKDIR app

# # Copy entrypoint script
# COPY ./dockerfiles/entrypoint-debug.sh /entrypoint.sh
# Run the existing entrypoint script in dockerfiles.
RUN chmod +x ./dockerfiles/entrypoint.sh

# install dependencies
RUN apt-get update && apt-get install -y build-essential
RUN pip install -r requirements.txt

# install container maker spec
RUN pip install container-maker-spec/

# install vim
RUN apt-get install vim

# Expose ports for both services
EXPOSE 8888
EXPOSE 50051

# Use the entrypoint script
ENTRYPOINT ["./dockerfiles/entrypoint.sh"]

