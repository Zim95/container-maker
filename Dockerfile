FROM python:3.11-slim

# Create the directory
RUN mkdir app
COPY . app/
WORKDIR app

# install dependencies
RUN apt-get update && apt-get install -y build-essential
RUN pip install -r requirements.txt

# run code
CMD ["python", "app.py", "--use_ssl", "true"]
