"""Explicit local LIVE entry point. Startup checks only read the supplier API."""
import configparser
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import runpy
import sys
from steamru_instance import InstanceLock, AlreadyRunning

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'plugins'))
from steamru_stars_engine import SteamClient, D, effective_exchange_rate, STEAM_CURRENCIES, STEAM_KINDS
import steamru_stars_pricing as pricing
import steamru_stars_services as services

VARIABLES = ('STEAMRU_API_KEY', 'STEAMRU_API_SECRET', 'STEAMRU_OWNER_TG_ID', 'STEAMRU_LIVE_CONFIRM')


def startup_diagnostic(stage, *, error=None):
    """A tiny allowlist; never serialize exception text, bodies, headers or credentials."""
    report = {'stage':stage,'checked_at':datetime.now(timezone.utc).isoformat(),
              'error_type':type(error).__name__ if error else None,'real_purchases':0}
    if isinstance(error,pricing.PartnerFailure):
        report.update(partner_error_code=error.code,partner_http_status=error.status)
    if pricing.TOPUP_CLIENT is not None:
        report['partner_requests'] = list(pricing.TOPUP_CLIENT.trace)
    path = ROOT/'storage/plugins/steamru_startup_diagnostic.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def run_live():
    os.chdir(ROOT)
    os.environ.pop('STEAMRU_LIVE_CONFIRM', None)
    config_path = ROOT / 'storage/plugins/steamru_stars_config.json'
    if not config_path.exists() or not (ROOT / 'configs/_main.cfg').exists():
        print('Cardinal и плагин ещё не настроены.')
        return 2
    cfg = json.loads(config_path.read_text(encoding='utf-8'))
    if (cfg.get('mode') != 'live' or cfg.get('auto_disable_lots_on_pause') is not True
            or cfg.get('activate_lots_on_resume') is not True or not cfg.get('managed_lots')
            or not cfg.get('lot_ids_to_disable') or cfg.get('capture_initial_paid_orders') is not False
            or cfg.get('capture_paid_orders_in_dry_run') is not False):
        print('Нет настроенной безопасной конфигурации LIVE. Продажи не запущены.')
        return 2
    main_cfg = configparser.ConfigParser(delimiters=(':',), interpolation=None)
    main_cfg.read(ROOT / 'configs/_main.cfg', encoding='utf-8')
    if (main_cfg.getboolean('FunPay', 'autoRestore', fallback=True)
            or main_cfg.getboolean('FunPay', 'autoDelivery', fallback=True)):
        print('Выключи штатную автовыдачу и автовосстановление Cardinal.')
        return 2
    authorized_path = ROOT / 'storage/cache/tg_authorized_users.json'
    authorized = json.loads(authorized_path.read_text(encoding='utf-8')) if authorized_path.exists() else {}
    owner = os.environ.get('STEAMRU_OWNER_TG_ID', '')
    if not owner and len(authorized) == 1:
        owner = next(iter(authorized))
    if not owner and authorized:
        owner = input('Введи свой числовой Telegram ID из авторизованных пользователей: ').strip()
    if not owner.isdigit() or owner not in authorized:
        print('Сначала авторизуйся в своём управляющем Telegram-боте.')
        return 2
    print('LIVE: после /sr_resume бот откроет доступные лоты и будет выполнять оплаченные заказы.')
    print('Ключ и секрет вводятся скрыто, только локально. В файлы не сохраняются.')
    key = os.environ.get('STEAMRU_API_KEY') or getpass.getpass('STEAM.RU api_key: ').strip()
    secret = os.environ.get('STEAMRU_API_SECRET') or getpass.getpass('STEAM.RU api_secret: ').strip()
    stage = 'funding_config'
    try:
        rate = effective_exchange_rate(cfg['wallet_paid_rub'], cfg['wallet_credited_usd'])
        if rate != D(cfg['rub_per_usd']):
            raise ValueError('Не совпадает эффективный курс')
        api = SteamClient(key, secret)  # Startup never permits supplier POST.
        stage = 'supplier_account';startup_diagnostic(stage)
        balance = D(api.account()['balance'])
        stage = 'supplier_catalog';startup_diagnostic(stage)
        costs = []
        prices = {}
        for name in set(cfg['managed_lots'].values()):
            rule = cfg['lot_rules'][name]
            count = rule['stars_per_unit']
            if rule.get('kind') in STEAM_KINDS: count = rule['min_count']
            if rule.get('kind') in ('game_key','service_code','service_topup'):
                continue  # Key catalogue is checked in the maintenance worker before activation.
            product = (api.steam_rub_product(count) if rule.get('kind')=='steam_rub' else
                       api.steam_currency_product(rule['currency'],count) if rule.get('kind') in STEAM_KINDS else api.product('telegram-stars',55,count))
            rule['last_price_usd']=str(D(product['price_usd']))
            if rule.get('kind') in STEAM_KINDS:rule['sell_enabled']=True
            cost = D(product['price_usd']) * count
            costs.append(cost)
            prices[rule.get('kind', 'stars') + ':' + str(count)] = str(cost)
        required = min(costs) if cfg.get('catalog_sync', {}).get('enabled') else max(costs)
        if balance < required + D(cfg['min_balance_reserve_usd']):
            if not cfg.get('catalog_sync',{}).get('enabled'):
                raise ValueError('Недостаточно баланса на максимальный пакет')
            print('Баланс мал: недоступные лоты останутся выключены. Telegram и автоматическое чтение баланса работают; закупок нет.')
        print('API STEAM.RU и каталог доступны. Баланс $' + str(balance) + '. Покупок не было.')
        if cfg.get('services',{}).get('enabled'):
            stage='supplier_services_catalog';startup_diagnostic(stage)
            selected=cfg['services']['selected'];verified=[];service_error=None
            try:verified=services.catalogue(api,selected,cfg['services'].get('max_price_usd','10'))
            except Exception as exc:service_error=type(exc).__name__
            verified_map=dict(verified)
            for name in selected:
                rule=cfg['lot_rules'].get(name)
                if rule is not None:
                    rule['sell_enabled']=name in verified_map
                    if name in verified_map:
                        rule.update(last_price_usd=verified_map[name]['last_price_usd'],verified_at=verified_map[name]['verified_at'])
            pending=config_path.with_name(config_path.name+'.live-api-check.tmp')
            pending.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');pending.replace(config_path)
            service_report={'checked_at':datetime.now(timezone.utc).isoformat(),'read_only':True,
                'verified_names':list(verified_map),'unavailable_names':[n for n in selected if n not in verified_map],
                'error_type':service_error,'real_purchases':0}
            (ROOT/'storage/plugins/steamru_service_check.json').write_text(json.dumps(service_report,indent=2)+'\n',encoding='utf-8')
            print('Новые сервисы проверены через API: '+str(len(verified))+'/'+str(len(selected))+'. Недоступные товары остаются выключенными.')
        options = cfg.get('auto_pricing', {})
        if options.get('enabled') and options.get('watch_topup_rate'):
            print('Для чтения курса нужен локальный вход в partner.steam.ru. Платежей эта проверка не делает.')
            email = getpass.getpass('E-mail партнёрского кабинета (скрыто): ').strip()
            password = getpass.getpass('Пароль партнёрского кабинета (скрыто): ')
            pricing.TOPUP_CLIENT = pricing.PartnerTopupClient(email, password,
                    options.get('payment_method', 'sbp'), options.get('reference_usd', '100'))
            stage = 'partner_login_and_rate';startup_diagnostic(stage)
            quote = pricing.TOPUP_CLIENT.refresh()
            print('Текущая стоимость нового пополнения: ' + quote['effective_rub_per_usd'] + ' RUB/USD.')
            email = password = ''
        snapshot = {'verified_at': datetime.now(timezone.utc).isoformat(),
                    'balance_usd': str(balance), 'packages_usd': prices, 'read_only': True}
        (ROOT / 'storage/plugins/steamru_live_check.json').write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print('STEAM.RU проверен только чтением. Баланс $' + str(balance) + '. Покупок при запуске нет.')
    except Exception as exc:
        startup_diagnostic(stage,error=exc)
        if isinstance(exc,pricing.PartnerFailure):
            print('Ошибка чтения курса STEAM.RU: '+str(exc))
        else:
            print('Проверка LIVE не прошла на шаге '+stage+': '+type(exc).__name__+'.')
        print('Продажи не запущены. Причина записана без секретов в storage/plugins/steamru_startup_diagnostic.json.')
        return 1
    startup_diagnostic('cardinal_start')
    os.environ.update(STEAMRU_API_KEY=key, STEAMRU_API_SECRET=secret,
                      STEAMRU_OWNER_TG_ID=owner, STEAMRU_LIVE_CONFIRM='I_ACCEPT_REAL_PURCHASES')
    print('Оставь окно открытым. В Telegram отправь /sr_resume, затем /sr_status.')
    try:
        runpy.run_path(str(ROOT / 'main.py'), run_name='__main__')
    finally:
        loaded = sys.modules.get('plugins.steamru_stars')
        if loaded is not None and getattr(loaded, 'C', None) is not None:
            loaded.on_pre_stop(loaded.C)
        for name in VARIABLES:
            os.environ.pop(name, None)
    return 0


def main():
    try:
        with InstanceLock(ROOT):
            return run_live()
    except AlreadyRunning as exc:
        print(str(exc))
        return 2
    finally:
        for name in VARIABLES:
            os.environ.pop(name, None)
        if pricing.TOPUP_CLIENT is not None:
            pricing.TOPUP_CLIENT.close()
            pricing.TOPUP_CLIENT = None


if __name__ == '__main__':
    sys.exit(main())
