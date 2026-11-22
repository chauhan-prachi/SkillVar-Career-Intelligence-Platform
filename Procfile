web: gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2
release: python manage.py migrate --noinput && python manage.py createcachetable && python manage.py seed_data
