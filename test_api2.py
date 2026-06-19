import json, requests, sys
url = 'http://127.0.0.1:5000/api/chat'
payload = {"message": "Hello", "history": []}
try:
    resp = requests.post(url, json=payload, timeout=10)
    print('Status:', resp.status_code)
    print('Response:', resp.text)
except Exception as e:
    print('Error:', e, file=sys.stderr)
