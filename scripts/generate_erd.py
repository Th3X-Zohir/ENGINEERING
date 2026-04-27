import django
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from eralchemy2 import render_er
render_er('postgresql+psycopg2://workmanager_user:workmanager123@localhost/workmanager_db', 'docs/erd.png')
print("ERD saved to docs/erd.png")