#!/usr/bin/env bash
# Build step for Linux hosts (for example Render or Railway). UNTESTED on any hosting provider.
set -o errexit
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py createcachetable
python manage.py seed_data
