from PIL import Image

def make_favicon():
    img_path = r"c:\Users\zians\Downloads\CELTM WEB MASTER\frontend\public\celtm-logo-cropped.png"
    out_path = r"c:\Users\zians\Downloads\CELTM WEB MASTER\frontend\src\app\favicon.ico"

    img = Image.open(img_path).convert("RGBA")

    # Create a white background
    bg = Image.new("RGBA", img.size, "WHITE")
    bg.paste(img, (0, 0), img)

    # We want a square favicon. Let's crop or pad to square.
    w, h = bg.size
    size = max(w, h)
    square_bg = Image.new("RGBA", (size, size), "WHITE")
    square_bg.paste(bg, ((size - w) // 2, (size - h) // 2))

    # Resize to icon size
    icon = square_bg.resize((64, 64), Image.Resampling.LANCZOS)

    icon.save(out_path, format="ICO", sizes=[(64, 64)])
    print("Favicon updated successfully!")

if __name__ == "__main__":
    make_favicon()
