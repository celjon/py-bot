import os

# Единый путь к базе данных для всего проекта
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
DB_PATH = os.path.join(DATA_DIR, 'bothub.db')

# Создаем директорию если нужно
os.makedirs(DATA_DIR, exist_ok=True)

def get_db_path() -> str:
    """Получить путь к базе данных"""
    return DB_PATH