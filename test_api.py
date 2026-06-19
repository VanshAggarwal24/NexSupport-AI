import json, requests, sys
url = 'http://127.0.0.1:5000/api/chat'
payload = {"messages": [{"role": "user", "content": "Hello"}]}
try:
    resp = requests.post(url, json=payload, timeout=10)
    print('Status:', resp.status_code)
    print('Headers:', resp.headers)
    print('Text:', resp.text)
except Exception as e:
    print('Error:', e, file=sys.stderr)
