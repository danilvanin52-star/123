"""Проверка только Python и зависимостей; без аккаунтов, сети и запуска бота."""
import importlib
import importlib.metadata
import sys


def main():
    failures = []
    print("Python:", sys.version.split()[0])
    if sys.version_info < (3, 11):
        failures.append("Python 3.11 or newer is required")
    for name in ("requests", "urllib3", "requests_toolbelt", "psutil", "bs4", "colorama",
                 "telebot", "PIL", "lxml", "bcrypt", "socks"):
        try:
            importlib.import_module(name)
        except Exception as exc:
            failures.append(f"{name}: {type(exc).__name__}: {exc}")
    for package, expected in (("requests", "2.28.1"), ("requests-toolbelt", "0.10.1"),
                              ("pyTelegramBotAPI", "4.15.2")):
        try:
            actual = importlib.metadata.version(package)
            if actual != expected:
                failures.append(f"{package}: expected {expected}, installed {actual}")
        except importlib.metadata.PackageNotFoundError:
            pass  # Missing modules are reported above.
    if failures:
        print("Dependency check FAILED:")
        for message in failures:
            print(" -", message)
        return 1
    print("Dependency check OK. No accounts connected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
