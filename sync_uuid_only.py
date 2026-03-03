#!/usr/bin/env python3
# /opt/sync/sync_api_only.py
"""
Синхронизация через API добавления клиентов
Не трогает настройки инбаунда!
"""

import requests
import json
import time
import sys

def log(message):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}")
    sys.stdout.flush()

def login_xui(url, username, password):
    """Авторизация в 3x-ui"""
    try:
        session = requests.Session()
        # Получаем CSRF
        session.get(f"{url}/login", timeout=5)
        
        # Логинимся
        response = session.post(
            f"{url}/login",
            data={"username": username, "password": password},
            timeout=10
        )
        
        if response.status_code == 200:
            return session
    except:
        pass
    return None

def get_existing_clients(session, url, inbound_id):
    """Получает существующих клиентов из инбаунда"""
    try:
        # Получаем инбаунд
        resp = session.get(f"{url}/panel/api/inbounds/list")
        inbounds = resp.json().get('obj', [])
        
        for inbound in inbounds:
            if str(inbound.get('id')) == str(inbound_id):
                settings = json.loads(inbound.get('settings', '{}'))
                return {c.get('id'): c for c in settings.get('clients', [])}
    except:
        pass
    return {}

def add_client_via_api(session, url, inbound_id, client_data):
    """
    Добавляет клиента через API метод
    POST /panel/api/inbounds/addClient
    """
    try:
        # API для добавления клиента
        api_url = f"{url}/panel/api/inbounds/addClient"
        
        # Подготовка данных
        payload = {
            "id": inbound_id,
            "settings": json.dumps({"clients": [client_data]})
        }
        
        response = session.post(api_url, json=payload, timeout=10)
        
        if response.status_code == 200:
            return True, "Успешно"
        else:
            return False, f"HTTP {response.status_code}: {response.text}"
            
    except Exception as e:
        return False, str(e)


def force_activate_client(session, url, email, inbound_id):
    """
    Принудительная активация клиента путем обновления трафика
    """
    try:
        # URL для обновления трафика
        update_url = f"{url}/panel/api/inbounds/updateClientTraffic/{email}"
        
        # Отправляем 0 байт (или 1 байт для верности)
        payload = {
            "upload": 0,      # 0 байт загрузки
            "download": 0      # 0 байт скачивания
        }
        
        response = session.post(update_url, json=payload, timeout=5)
        
        if response.status_code == 200:
            # Проверяем, что запись создалась
            check_url = f"{url}/panel/api/inbounds/getClientTraffics/{email}"
            check_response = session.get(check_url)
            
            if check_response.status_code == 200:
                return True, "Клиент активирован"
            else:
                return False, "Не удалось проверить активацию"
        else:
            return False, f"Ошибка HTTP {response.status_code}"
            
    except Exception as e:
        return False, str(e)



def sync_with_api():
    """Синхронизация через API добавления"""
    log("🔄 Синхронизация через API")
    
    # КОНФИГУРАЦИЯ
    servers = [
        {
            "name": "Главный сервер",
            "url": "https://PANEL_URL",
            "username": "user",
            "password": "password",
            "inbound_id": N,
            "is_master": True
        },
        {
            "name": "Сервер 2",
            "url": "https://PANEL_URL",
            "username": "user",
            "password": "password",
            "inbound_id": N,
            "is_master": False
        }
    ]
    
    # Получаем клиентов с главного
    master = next((s for s in servers if s['is_master']), None)
    if not master:
        return
    
    master_session = login_xui(master['url'], master['username'], master['password'])
    if not master_session:
        return
    
    try:
        # Получаем клиентов с главного
        existing_master = get_existing_clients(master_session, master['url'], master['inbound_id'])
        master_clients = list(existing_master.values())
        
        log(f"📊 Клиентов на главном: {len(master_clients)}")
        
        # Slave серверы
        slaves = [s for s in servers if not s['is_master']]
        
        for slave in slaves:
            log(f"\n📡 Синхронизация на {slave['name']}")
            
            slave_session = login_xui(slave['url'], slave['username'], slave['password'])
            if not slave_session:
                continue
            
            try:
                # Получаем существующих клиентов на slave
                existing_slave = get_existing_clients(slave_session, slave['url'], slave['inbound_id'])
                log(f"  Текущих клиентов: {len(existing_slave)}")
                
                # Добавляем отсутствующих через API
                added = 0
                skipped = 0
                errors = 0
                
                for client in master_clients:
                    client_uuid = client.get('id')
                    client_email = client.get('email', 'без email')
                    
                    if not client_uuid:
                        log(f"  ⚠️  У клиента нет UUID: {client_email}")
                        continue
                    
                    # Проверяем, есть ли уже такой клиент
                    if client_uuid in existing_slave:
                        skipped += 1
                        log(f"  ⏭️  Уже есть: {client_email}")
                        continue
                    
                    # Подготавливаем данные для API
                    client_data = {
                        "id": client.get('id'),
                        "email": client.get('email'),
                        "flow": client.get('flow', ''),
                        "limitIp": client.get('limitIp', 0),
                        "totalGB": client.get('totalGB', 0),
                        "expiryTime": client.get('expiryTime', 0),
                        "enable": client.get('enable', True),
                        "tgId": client.get('tgId', ''),
                        "subId": client.get('subId', '')
                    }
                    
                    # Добавляем через API
                    success, message = add_client_via_api(
                        slave_session, 
                        slave['url'], 
                        slave['inbound_id'],
                        client_data
                    )
                    
                    if success:
                        added += 1
                        log(f"  ✅ Добавлен: {client_email}")
                        act_success, act_msg = force_activate_client(
                            slave_session, 
                            slave['url'], 
                            client_email,
                            slave['inbound_id']
                        )
                    else:
                        errors += 1
                        log(f"  ❌ Ошибка {client_email}: {message[:50]}")
                    
                    # Небольшая пауза между запросами
                    time.sleep(0.5)
                
                # Итоги
                log(f"  📊 Итог: Добавлено={added}, Пропущено={skipped}, Ошибок={errors}")
                
            except Exception as e:
                log(f"  ❌ Ошибка на {slave['name']}: {e}")
            
            time.sleep(1)
        
        log("\n🎉 Синхронизация завершена через API")
        
    except Exception as e:
        log(f"❌ Критическая ошибка: {e}")

def main():
    """Для systemd"""
    INTERVAL = 300  # 5 минут
    
    while True:
        try:
            sync_with_api()
            log(f"⏳ Следующая синхронизация через {INTERVAL} секунд")
            time.sleep(INTERVAL)
        except KeyboardInterrupt:
            log("👋 Остановка")
            break
        except Exception as e:
            log(f"💥 Ошибка: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()
