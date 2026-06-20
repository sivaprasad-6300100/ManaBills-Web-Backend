import os
from dotenv import load_dotenv  # ← add

from django.core.wsgi import get_wsgi_application

load_dotenv()  # ← add, before os.environ.setdefault

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()