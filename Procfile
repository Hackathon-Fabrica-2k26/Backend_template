release: python src/manage.py migrate --noinput
web: gunicorn --chdir src config.wsgi --bind 0.0.0.0:$PORT
worker: celery -A src.config worker -l info --concurrency=4
