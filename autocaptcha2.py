import requests, time, io, base64, hashlib, random, json, os
from PIL import Image, ImageOps, ImageFilter
from google import genai
from dotenv import load_dotenv

# === ISI PAKE APIKEY MU, NGISINYA DI FILE .env ===
load_dotenv()
API_KEYS = [
    os.getenv("GEMINI_KEY1"),
    os.getenv("GEMINI_KEY2"),
    os.getenv("GEMINI_KEY3"),
    os.getenv("GEMINI_KEY4"),
    os.getenv("GEMINI_KEY5")
]
client = None
key_index = 0

# === KONFIGURASI AKUN ===
EMAIL = "" # === ISI EMAIL AKUN CAPTCHAMONEY.ID MU ===
PASSWORD = "" # === ISI PASSWORD NYA ===
USER_AGENT = "" # === ISI USER_AGENT MU. CARANYA KETIK AE "user agent" DI BROWSER ===
TARGET_POINT = 100000 # === INI TARGET POIN NYA, KALAU DAH TERCAPAI NANTI OTOMATIS MATI SENDIRI BOT NYA ===
ERROR_LOG_FILE = "captcha_error.json"

# === URL API ===
LOGIN_URL = "https://captchamoney.id/api/login.php"
USER_URL = "https://captchamoney.id/api/userinfo.php"
CAPTCHA_URL = "https://captchamoney.id/api/captcha_generate.php"
SUBMIT_URL = "https://captchamoney.id/api/captcha_submit.php"

# === FINGERPRINT ===
def generate_fingerprint():
    base = f"{random.random()}{time.time()}"
    return hashlib.sha1(base.encode()).hexdigest()

# === SESSION ===
session = requests.Session()
session.headers.update({
    "User-Agent": USER_AGENT,
    "Accept": "application/json"
})

# === LOGIN ===
def login():
    payload = {
        "email": EMAIL,
        "password": PASSWORD,
        "device_fingerprint": generate_fingerprint()
    }
    res = session.post(LOGIN_URL, data=payload)
    try:
        data = res.json()
        if data.get("status") == "success":
            print(f"[✅] Login berhasil!")
            return True
        else:
            print(f"[❌] Login gagal: {data.get('message')}")
            return False
    except Exception as e:
        print(f"[⚠️] Gagal parsing JSON saat login: {e}")
        print(res.text)
        return False

# === AMBIL DATA USER ===
def get_user_data():
    try:
        res = session.get(USER_URL)
        if res.ok:
            data = res.json()
            points = int(data.get("points", 0))
            daily_count = int(data.get("total_scratch", 0))
            return points, daily_count, 500
    except Exception as e:
        print(f"[⚠️] Gagal ambil data user: {e}")
    return 0, 0, 500

# === CAPTCHA ===
def download_captcha():
    try:
        res = session.get(CAPTCHA_URL)
        data = res.json()
        if data.get("status") == "success":
            b64_img = data.get("image", "").split(",")[-1]
            return Image.open(io.BytesIO(base64.b64decode(b64_img)))
        else:
            raise ValueError("Respon image captcha tidak valid.")
    except Exception as e:
        print(f"[⚠️] Gagal download captcha: {e}")
        return None

def process_image(image):
    image = image.convert("L")
    image = image.resize((image.width * 2, image.height * 2), Image.BICUBIC)
    image = image.filter(ImageFilter.MedianFilter(size=3))
    image = image.point(lambda x: 0 if x < 130 else 255, '1')
    return image

def log_error_image(image_pil, reason):
    buffer = io.BytesIO()
    image_pil.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
    entry = {
        "timestamp": int(time.time()),
        "reason": reason,
        "image_base64": encoded
    }
    try:
        with open(ERROR_LOG_FILE, "a") as f:
            json.dump(entry, f)
            f.write("\n")
    except Exception as e:
        print(f"[⚠️] Gagal menyimpan log error: {e}")

# === GEMINI LOGIC ===
def switch_api_key():
    global client, key_index
    if key_index >= len(API_KEYS):
        print("[🚫] Semua API Key telah digunakan!")
        return False
    try:
        client = genai.Client(api_key=API_KEYS[key_index])
        print(f"[🔁] Menggunakan API Key #{key_index + 1}")
        return True
    except Exception as e:
        print(f"[⚠️] Gagal menggunakan API Key ke-{key_index + 1}: {e}")
        key_index += 1
        return switch_api_key()

def gemini_ocr(image_pil):
    global key_index
    try:
        buffer = io.BytesIO()
        image_pil.save(buffer, format="PNG")
        img_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"text": "Tolong baca isi captcha ini. Isinya hanya huruf kapital dan angka. Tidak ada spasi."},
                        {"inline_data": {"mime_type": "image/png", "data": img_base64}}
                    ]
                }
            ]
        )
        hasil = response.text.strip()
        return ''.join(filter(str.isalnum, hasil)).upper()

    except Exception as e:
        print(f"[❌] Gagal OCR dengan Gemini: {e}")
        key_index += 1
        if switch_api_key():
            return gemini_ocr(image_pil)
        else:
            log_error_image(image_pil, reason=str(e))
            return ""

# === SUBMIT CAPTCHA ===
def submit_captcha(code):
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    data = {"captcha": code}
    res = session.post(SUBMIT_URL, data=data, headers=headers)
    return res.json()

# === MAIN LOOP ===
if switch_api_key() and login():
    while True:
        try:
            total_points, daily_count, max_count = get_user_data()
            print(f"\n[💼] Poin: {total_points} | Captcha: {daily_count}/{max_count}")

            if total_points >= TARGET_POINT:
                print(f"[🎯] Target {TARGET_POINT} poin tercapai!")
                break

            if daily_count >= max_count:
                print("[⚠️] Batas captcha harian tercapai!")
                break

            img = download_captcha()
            if not img:
                print("[❌] Gagal ambil captcha.")
                time.sleep(5)
                continue

            processed = process_image(img)
            code = gemini_ocr(processed)

            if not code or not code.isalnum():
                print(f"[❌] Captcha gagal dibaca: '{code}' → disimpan.")
                log_error_image(processed, reason="OCR gagal atau hasil tidak valid")
                continue

            print(f"[📩] Submit captcha: {code}")
            res = submit_captcha(code)

            if res.get("status") == "success":
                print(f"[✅] +{res.get('reward', 0)} poin! (Kupon: {res.get('kupon', 0)})")
            elif res.get("status") == "fail":
                print(f"[❌] Captcha salah: {res.get('message')}")
                log_error_image(processed, reason="Captcha salah oleh server")
            else:
                print(f"[⚠️] Submit gagal: {res}")

            time.sleep(5)

        except KeyboardInterrupt:
            print("\n[🛑] Dihentikan manual.")
            break
        except Exception as e:
            print(f"[⚠️] Error: {e}")
            time.sleep(5)
else:
    print("[🚫] Gagal login atau tidak ada API Key yang valid.")
