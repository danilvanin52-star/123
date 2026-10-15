#!/usr/bin/env python3
"""Безопасная проверка STEAM.RU: ТОЛЬКО GET, покупок и списаний нет."""
from __future__ import annotations
import getpass
import os
import sys
from pathlib import Path
from decimal import Decimal

sys.path.insert(0, str(Path(__file__).resolve().parent / 'plugins'))
from steamru_stars_engine import SteamClient, ApiFailure, D


def main():
    print('STEAM.RU — проверка API без покупок (GET /account и каталог).')
    print('Ни одного POST /orders выполнено НЕ будет. Ключи не записываются в файлы.')
    key = os.environ.get('STEAMRU_API_KEY') or getpass.getpass('Вставь api_key (ввод скрыт): ').strip()
    secret = os.environ.get('STEAMRU_API_SECRET') or getpass.getpass('Вставь api_secret (ввод скрыт): ').strip()
    if not key or not secret:
        print('Нет api_key или api_secret. Если секрет утерян, перевыпусти ПАРУ ключ/секрет в кабинете.')
        return 2
    try:
        api = SteamClient(key, secret)
        acc = api.account()  # GET /account, официальный health-check
        bal = acc.get('balance')
        print('\n✓ Авторизация успешна; баланс USD:', bal if bal is not None else 'не сообщён')
        info = api.request('GET', '/catalog/services/telegram-stars/products')
        if info.get('service') != 'telegram-stars':
            raise RuntimeError('Каталог вернул другой сервис')
        print('✓ Telegram Stars — продукты, доступные ключу:')
        found=False
        for p in info.get('products', []):
            pid=p.get('product_id'); lo=p.get('min_count'); hi=p.get('max_count')
            price=p.get('price_usd'); fields=p.get('fields', [])
            print(f'  product_id={pid}; цена=${price}/звезда; лимиты={lo}..{hi}; поля={fields}')
            if str(pid)=='55':
                found=True
                if price is not None and lo is not None and hi is not None and int(lo)<=50<=int(hi):
                    for stars in (50, 100, 150):
                        if int(lo) <= stars <= int(hi):
                            print(f'  → {stars} звёзд стоят ${D(price)*stars} (без покупки)')
                    print(f'  На один тест 50 Stars расчётный баланс: ${D(price)*50 + Decimal("0.25")} с резервом $0.25.')
                    print('  Сверь минимальную сумму пополнения сервиса; курс RUB считай по факту зачисления USD.')
        print('✓ Проверка завершена. НИЧЕГО не куплено.')
        if not found:
            print('ВНИМАНИЕ: product_id=55 отсутствует. Не включай LIVE до сверки конфига!')
        return 0
    except ApiFailure as e:
        print('✗ API-ошибка:', e.code, '(HTTP', e.status, ')')
        print('Ничего не покупалось. Если 401 — проверь пару ключ/секрет и HMAC-подпись.')
        return 1
    except Exception as e:
        print('✗ Подключение не удалось:', type(e).__name__)
        print('Ничего не покупалось; секреты не отправляй в чат.')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
