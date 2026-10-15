@echo off
setlocal EnableExtensions
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
chcp 65001 >nul
cd /d "%~dp0"
if not exist "requirements.txt" goto missing_project
if not exist "check_install.py" goto missing_helper
if exist ".venv\Scripts\python.exe" goto install_packages
python --version
if errorlevel 1 goto missing_python
echo.
echo Создаю отдельное окружение Python в папке проекта...
python -m venv ".venv"
if errorlevel 1 goto failed

:install_packages
echo.
echo Устанавливаю зависимости Cardinal. Нужен доступ к интернету.
".venv\Scripts\python.exe" -m pip install -r "requirements.txt"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip check
if errorlevel 1 goto failed
".venv\Scripts\python.exe" check_install.py
if errorlevel 1 goto failed
echo.
echo УСТАНОВКА УСПЕШНА. Закрой это окно и запусти Start.bat.
pause
exit /b 0

:missing_project
echo Не найден requirements.txt. Полностью распакуй проект и помести исправление рядом с main.py.
pause
exit /b 1

:missing_helper
echo Не найден check_install.py. Скопируй все три файла исправления в папку проекта.
pause
exit /b 1

:missing_python
echo Не найден рабочий Python. Установи Python 3.11 или новее и добавь его в PATH.
pause
exit /b 1

:failed
echo.
echo УСТАНОВКА НЕ ЗАВЕРШЕНА. Текст ошибки остаётся выше.
echo Start.bat пока не запускай. Ключи и пароли в тексте ошибки скрывай.
pause
exit /b 1
