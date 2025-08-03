import requests
import hashlib
import random
import time
import json

# Konfigurasi login
# Ini buat ngetes bisa login ke akun captchamoney.id apa gak
EMAIL = ""
PASSWORD = ""
LOGIN_URL = "https://captchamoney.id/api/login.php"
USER_AGENT = ""

# Fungsi untuk membuat fingerprint acak
def generate_fingerprint():
    base = f"{random.random()}{time.time()}"
    return hashlib.sha1(base.encode()).hexdigest()

# Data login (form-data)
payload = {
    "email": EMAIL,
    "password": PASSWORD,
    "device_fingerprint": generate_fingerprint()
}

# Header
headers = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json"
}

# Buat session agar cookie login disimpan
session = requests.Session()
session.headers.update(headers)

# Kirim request login
response = session.post(LOGIN_URL, data=payload)

try:
    data = response.json()
    print("[🔄] Response JSON:")
    print(json.dumps(data, indent=2))

    if data.get("status") == "success":
        print("\n[✅] Login berhasil!")
        # Jika token atau session disimpan di cookie, bisa akses session.cookies
        print(f"[ℹ️] Cookie session: {session.cookies.get_dict()}")
    else:
        print(f"\n[❌] Login gagal: {data.get('message') or 'Tidak diketahui'}")
except Exception as e:
    print(f"[⚠️] Gagal parsing JSON: {e}")
    print(response.text)
