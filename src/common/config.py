import os

INGRESS_HOST: str = os.getenv('INGRESS_HOST', 'localhost')

REPO_NAME: str = os.getenv('REPO_NAME')
REPO_PASSWORD: str = os.getenv('REPO_PASSWORD')
