import datetime
import os
import shutil
import zipfile
from pathlib import Path


def create_backup(source_dir, backup_dir):
    """Создает бэкап указанной папки"""
    try:
        # Создаем имя папки с датой
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_name = f"backup_{timestamp}"
        backup_path = os.path.join(backup_dir, backup_name)

        ## Копируем файлы
        shutil.copytree(source_dir, backup_path)
        print(f"✅ Бэкап создан: {backup_path}")

        # Или создаем zip-архив
        zip_path = f"{backup_path}.zip"
        with zipfile.ZipFile(zip_path, "w") as zipf:
            for root, dirs, files in os.walk(source_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, source_dir)
                    zipf.write(file_path, arcname)

        print(f"📦 ZIP-архив создан: {zip_path}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    source = input("Путь к папке для бэкапа: ")
    destination = input("Куда сохранить бэкап: ")
    create_backup(source, destination)
