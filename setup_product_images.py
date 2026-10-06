import os
import urllib.request
from PIL import Image, ImageDraw, ImageFont

PRODUCT_IMAGES = {
    "espresso.jpg": "https://images.unsplash.com/photo-1510591509098-f4fdc6d0ff04?w=500&auto=format&fit=crop&q=80",
    "americano.jpg": "https://images.unsplash.com/photo-1551030173-122aabc4489c?w=500&auto=format&fit=crop&q=80",
    "latte.jpg": "https://images.unsplash.com/photo-1534778101976-62847782c213?w=500&auto=format&fit=crop&q=80",
    "cappuccino.jpg": "https://images.unsplash.com/photo-1572442388796-11668a67e53d?w=500&auto=format&fit=crop&q=80",
    "coldbrew.jpg": "https://images.unsplash.com/photo-1517701550927-30cf4ba1dba5?w=500&auto=format&fit=crop&q=80",
    "turkkahvesi.jpg": "https://images.unsplash.com/photo-1589396575653-c09c794ff6a6?w=500&auto=format&fit=crop&q=80",
    "portakalsuyu.jpg": "https://images.unsplash.com/photo-1613478223719-2ab802602423?w=500&auto=format&fit=crop&q=80",
    "kruvasan.jpg": "https://images.unsplash.com/photo-1555507036-ab1f4038808a?w=500&auto=format&fit=crop&q=80",
    "cheesecake.jpg": "https://images.unsplash.com/photo-1533134242443-d4fd215305ad?w=500&auto=format&fit=crop&q=80",
    "sandvic.jpg": "https://images.unsplash.com/photo-1528735602780-2552fd46c7af?w=500&auto=format&fit=crop&q=80",
}

def generate_fallback_image(filename, text, target_dir):
    img = Image.new('RGB', (400, 300), color=(30, 41, 59))
    draw = ImageDraw.Draw(img)
    draw.rectangle([10, 10, 390, 290], outline=(56, 189, 248), width=3)
    draw.text((40, 140), text, fill=(255, 255, 255))
    filepath = os.path.join(target_dir, filename)
    img.save(filepath, 'JPEG', quality=85)
    print(f"Generated fallback: {filename}")

def setup_product_images():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    img_dir = os.path.join(base_dir, "static", "images")
    os.makedirs(img_dir, exist_ok=True)
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for filename, url in PRODUCT_IMAGES.items():
        filepath = os.path.join(img_dir, filename)
        if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
            print(f"Already exists: {filename}")
            continue
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp, open(filepath, 'wb') as f:
                f.write(resp.read())
            print(f"Downloaded: {filename}")
        except Exception as e:
            print(f"Download failed for {filename} ({e}), creating placeholder...")
            title = filename.replace('.jpg', '').capitalize()
            generate_fallback_image(filename, title, img_dir)

if __name__ == '__main__':
    setup_product_images()
