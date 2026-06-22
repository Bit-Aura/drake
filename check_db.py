import urllib.request
import json

def check():
    try:
        req = urllib.request.Request("http://127.0.0.1:8001/api/v1/overview")
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            data = json.loads(resp.read().decode())
            print("API Overview Response:")
            print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"Error querying API: {e}")

if __name__ == "__main__":
    check()
