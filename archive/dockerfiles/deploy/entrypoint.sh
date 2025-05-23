#!/bin/bash

# Start Jupyter notebook in the background
jupyter notebook --ip 0.0.0.0 --no-browser --allow-root &

# Start the Python application
python app.py --use_ssl true
