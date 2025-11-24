from PIL import Image, ImageDraw, ImageFont


def ttf_to_ascii(text, font_path, font_size, char_set):
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        raise RuntimeError("Error: Could not load font from {font_path}")

    # Figure out text dimensions
    dummy_img = Image.new("L", (1, 1))
    dummy_draw = ImageDraw.Draw(dummy_img)
    bbox = dummy_draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]

    if width == 0 or height == 0:
        return ""

    # Create actual image
    img = Image.new("L", (width, height), color=255)
    draw = ImageDraw.Draw(img)
    draw.text((-bbox[0], -bbox[1]), text, font=font, fill=0)

    pixels = img.getdata()
    lines = []
    char_range = len(char_set) - 1

    for i in range(height):
        line = []
        for j in range(width):
            pixel_value = pixels[i * width + j]
            # Invert the pixel value because 0 is black and 255 is white.
            # We want darker pixels to map to denser ASCII characters.
            inverted_pixel = 255 - pixel_value
            index = int(inverted_pixel / 255 * char_range)
            line.append(char_set[index])
        lines.append("".join(line))

    return "\n".join(lines)
