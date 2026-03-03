#!/usr/bin/env python3
# /opt/sync/working_aggregator.py
"""
Рабочий агрегатор с обработкой ошибок
"""

from flask import Flask, Response
import requests
import base64
import logging

logging.basicConfig(level=logging.INFO)
app = Flask(__name__)

# Список серверов 3x-ui
SERVERS = [
    "https://SERVER:PORT/sub/{id}",
    "https://SERVER2:PORT/sub/{id}",
    # Добавьте другие серверы если нужно
]

@app.route('/sub/<sub_id>')
def get_combined_subscription(sub_id):
    """Объединяет подписки со всех серверов"""
    
    all_configs = []
    
    for server_template in SERVERS:
        url = server_template.replace("{id}", sub_id)
        
        try:
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                # Проверяем, что это base64
                content = response.text.strip()
                
                # Пробуем декодировать
                try:
                    decoded = base64.b64decode(content).decode('utf-8', errors='ignore')
                    
                    # Добавляем все конфиги
                    for line in decoded.split('\n'):
                        if line.strip():
                            all_configs.append(line.strip())
                            
                    print(f"✓ {url}: {len(decoded.split())} конфигов")
                    
                except:
                    # Если не base64, добавляем как есть
                    all_configs.append(content)
                    print(f"⚠️  {url}: не base64 формат")
                    
            else:
                print(f"✗ {url}: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"✗ {url}: {str(e)}")
    
    # Если ничего нет
    if not all_configs:
        print(f"❌ Нет конфигов для {sub_id}")
        return Response("No subscriptions found. Check your sub_id.", status=404)
    
    # Объединяем и кодируем
    combined = "\n".join(all_configs)
    encoded = base64.b64encode(combined.encode()).decode()
    
    print(f"✅ {sub_id}: {len(all_configs)} конфигов")
    return Response(encoded, mimetype='text/plain')

@app.route('/health')
def health():
    return "AGGREGATOR OK"

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 VPN Aggregator запущен")
    print("📍 Порт: 5000")
    print(f"📡 Серверов: {len(SERVERS)}")
    print("=" * 50)
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
