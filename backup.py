import argparse
import datetime
import logging
import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Optional, Tuple


class BackupCreator:
    """Класс для создания резервных копий папок"""

    def __init__(self, log_level: str = "INFO"):
        """Инициализация с настройкой логирования"""
        self.setup_logging(log_level)

    def setup_logging(self, log_level: str):
        """Настройка системы логирования"""
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format="%(asctime)s - %(levelname)s - %(message)s",
            handlers=[logging.FileHandler("backup.log"), logging.StreamHandler()],
        )
        self.logger = logging.getLogger(__name__)

    def validate_paths(
        self, source_dir: str, backup_dir: str
    ) -> Tuple[bool, Optional[str]]:
        """Проверка существования путей"""
        source_path = Path(source_dir)
        backup_path = Path(backup_dir)

        if not source_path.exists():
            return False, f"Исходная папка не существует: {source_dir}"

        if not source_path.is_dir():
            return False, f"Указанный путь не является папкой: {source_dir}"

        # Создаем папку для бэкапов, если её нет
        try:
            backup_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            return False, f"Нет прав на создание папки: {backup_dir}"

        # Проверка доступного места
        if not self.check_disk_space(source_path, backup_path):
            return False, "Недостаточно места на диске для создания бэкапа"

        return True, None

    def check_disk_space(self, source_path: Path, backup_path: Path) -> bool:
        """Проверка свободного места на диске"""
        try:
            source_size = self.get_directory_size(source_path)
            free_space = shutil.disk_usage(backup_path).free

            # Требуем в 2 раза больше места для надежности (сжатие + накладные расходы)
            required_space = source_size * 2

            if free_space < required_space:
                self.logger.warning(
                    f"Мало свободного места. Требуется: {self.format_bytes(required_space)}, "
                    f"Свободно: {self.format_bytes(free_space)}"
                )
                return False
            return True
        except Exception as e:
            self.logger.warning(f"Не удалось проверить место на диске: {e}")
            return True  # Продолжаем, если не удалось проверить

    def get_directory_size(self, path: Path) -> int:
        """Вычисление размера папки"""
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(path):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                try:
                    total_size += os.path.getsize(filepath)
                except OSError:
                    continue
        return total_size

    @staticmethod
    def format_bytes(size: int) -> str:
        """Форматирование размера в читаемый вид"""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} PB"

    def create_backup(
        self,
        source_dir: str,
        backup_dir: str,
        max_backups: int = 10,
        create_zip: bool = True,
    ) -> Tuple[bool, Optional[str]]:
        """Создает бэкап указанной папки"""

        # Валидация путей
        is_valid, error_message = self.validate_paths(source_dir, backup_dir)
        if not is_valid:
            return False, error_message

        source_path = Path(source_dir)
        backup_path = Path(backup_dir)

        try:
            # Создаем имя бэкапа с датой и именем папки
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            folder_name = source_path.name
            backup_name = f"{folder_name}_backup_{timestamp}"
            backup_full_path = backup_path / backup_name

            self.logger.info(f"Начало создания бэкапа: {source_dir}")

            # Копируем файлы
            shutil.copytree(source_path, backup_full_path)
            self.logger.info(f"Создана копия папки: {backup_full_path}")

            # Создаем ZIP-архив если нужно
            if create_zip:
                zip_file_path = self.create_zip_archive(backup_full_path, source_path)
                if zip_file_path:
                    # Удаляем распакованную копию, оставляя только архив
                    shutil.rmtree(backup_full_path)
                    self.logger.info(f"ZIP-архив создан: {zip_file_path}")
                    backup_full_path = Path(zip_file_path)
                else:
                    self.logger.warning(
                        "Не удалось создать ZIP-архив, сохранена полная копия"
                    )

            # Очистка старых бэкапов
            self.cleanup_old_backups(backup_path, folder_name, max_backups)

            # Статистика
            backup_size = (
                backup_full_path.stat().st_size if backup_full_path.exists() else 0
            )
            self.logger.info(
                f"Бэкап успешно создан: {backup_full_path}\n"
                f"Размер: {self.format_bytes(backup_size)}\n"
                f"Исходная папка: {source_dir}"
            )

            return True, str(backup_full_path)

        except PermissionError as e:
            error_msg = f"Ошибка доступа: {e}"
            self.logger.error(error_msg)
            return False, error_msg
        except shutil.Error as e:
            error_msg = f"Ошибка копирования: {e}"
            self.logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Неожиданная ошибка: {e}"
            self.logger.error(error_msg, exc_info=True)
            return False, error_msg

    def create_zip_archive(
        self, source_backup_path: Path, original_source: Path
    ) -> Optional[str]:
        """Создание ZIP-архива"""
        try:
            zip_path = source_backup_path.with_suffix(".zip")

            with zipfile.ZipFile(
                zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6
            ) as zipf:
                for file_path in original_source.rglob("*"):
                    if file_path.is_file():
                        try:
                            arcname = file_path.relative_to(original_source)
                            zipf.write(file_path, arcname)
                        except Exception as e:
                            self.logger.warning(
                                f"Не удалось добавить файл {file_path}: {e}"
                            )

            return str(zip_path)
        except Exception as e:
            self.logger.error(f"Ошибка создания ZIP: {e}")
            return None

    def cleanup_old_backups(self, backup_dir: Path, folder_name: str, max_backups: int):
        """Удаление старых бэкапов, оставляя только последние max_backups"""
        try:
            # Ищем все бэкапы для данной папки
            backup_pattern = f"{folder_name}_backup_*"
            backups = sorted(
                backup_dir.glob(backup_pattern + ".zip")
                or backup_dir.glob(backup_pattern),
                key=os.path.getmtime,
                reverse=True,
            )

            # Удаляем старые бэкапы
            for backup in backups[max_backups:]:
                try:
                    if backup.is_file():
                        backup.unlink()
                    elif backup.is_dir():
                        shutil.rmtree(backup)
                    self.logger.info(f"Удален старый бэкап: {backup}")
                except Exception as e:
                    self.logger.warning(f"Не удалось удалить {backup}: {e}")

        except Exception as e:
            self.logger.warning(f"Ошибка при очистке старых бэкапов: {e}")


def main():
    """Основная функция для запуска из командной строки"""
    parser = argparse.ArgumentParser(description="Создание резервных копий папок")
    parser.add_argument("--source", "-s", help="Путь к папке для бэкапа")
    parser.add_argument("--destination", "-d", help="Куда сохранить бэкап")
    parser.add_argument(
        "--max-backups",
        "-m",
        type=int,
        default=10,
        help="Максимальное количество хранимых бэкапов (по умолчанию: 10)",
    )
    parser.add_argument(
        "--no-zip",
        action="store_true",
        help="Не создавать ZIP-архив (сохранять как папку)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Уровень логирования",
    )

    args = parser.parse_args()

    # Если аргументы не переданы, запрашиваем у пользователя
    source = args.source
    destination = args.destination

    if not source:
        source = input("Путь к папке для бэкапа: ").strip()

    if not destination:
        destination = input("Куда сохранить бэкап: ").strip()

    # Создаем экземпляр бэкапера
    backup_creator = BackupCreator(log_level=args.log_level)

    # Создаем бэкап
    success, result = backup_creator.create_backup(
        source_dir=source,
        backup_dir=destination,
        max_backups=args.max_backups,
        create_zip=not args.no_zip,
    )

    if success:
        print(f"\n✅ Бэкап успешно создан: {result}")
        return 0
    else:
        print(f"\n❌ Ошибка: {result}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
