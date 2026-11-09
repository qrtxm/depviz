"""Заменитель программы d2 для тестов: копирует вход в выходной файл."""

import shutil
import sys

if __name__ == "__main__":
    shutil.copyfile(sys.argv[1], sys.argv[2])
