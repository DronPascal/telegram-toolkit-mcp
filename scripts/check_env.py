#!/usr/bin/env python3
"""
Check environment variables loading
"""
import os
from dotenv import load_dotenv

print('Before loading .env:')
api_id = os.getenv('TELEGRAM_API_ID', 'NOT SET')
api_hash = os.getenv('TELEGRAM_API_HASH', 'NOT SET')
print(f'TELEGRAM_API_ID: {api_id}')
print(f'TELEGRAM_API_HASH: {api_hash[:8] if api_hash != "NOT SET" else "NOT SET"}...')

load_dotenv()

print('\nAfter loading .env:')
api_id = os.getenv('TELEGRAM_API_ID', 'NOT SET')
api_hash = os.getenv('TELEGRAM_API_HASH', 'NOT SET')
print(f'TELEGRAM_API_ID: {api_id}')
print(f'TELEGRAM_API_HASH: {api_hash[:8] if api_hash != "NOT SET" else "NOT SET"}...')

# Also check the actual .env file content
print('\n.env file content:')
try:
    with open('.env', 'r') as f:
        lines = f.readlines()
        for line in lines:
            if 'TELEGRAM_API' in line and not line.startswith('#'):
                print(f'  {line.strip()}')
except Exception as e:
    print(f'  Error reading .env: {e}')
