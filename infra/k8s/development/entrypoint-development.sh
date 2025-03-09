#!/bin/bash

# Start Jupyter notebook in the background using Poetry
poetry run jupyter notebook --ip 0.0.0.0 --no-browser --allow-root &

# Run the main application using Poetry
poetry run python app.py --use_ssl true
