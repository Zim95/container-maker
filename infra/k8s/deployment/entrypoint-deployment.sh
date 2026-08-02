#!/bin/bash

# Production entrypoint - run the gRPC server directly.
# (No Jupyter notebook, no venv-path juggling, no tail -f: those are dev-only conveniences.)
poetry run python app.py --use_ssl true
