"""认证二维码的终端展示。"""

from io import BytesIO

from PIL import Image


def print_qr(data):
    """Sample exact QR modules from the first finder row, retaining a quiet zone."""
    im = Image.open(BytesIO(data)).convert("L")
    pixels = im.load()
    bounds = im.point(lambda p: 255 if p < 128 else 0).getbbox()
    if not bounds:
        return
    left, top, right, bottom = bounds
    end = left
    while end < right and pixels[end, top] < 128:
        end += 1
    module = (end - left) / 7
    size = round((right - left) / module) if module else 0
    if size < 21 or size > 177 or (size - 21) % 4:
        print("终端二维码无法排版，请打开二维码图片扫码。")
        return
    rows = []
    for y in range(-4, size + 4):
        row = []
        for x in range(-4, size + 4):
            black = (0 <= x < size and 0 <= y < size and
                     pixels[min(right - 1, round(left + (x + .5) * module)),
                            min(bottom - 1, round(top + (y + .5) * module))] < 128)
            row.append(black)
        rows.append(row)
    if len(rows) % 2:
        rows.append([False] * len(rows[0]))
    chars = {(False, False): " ", (True, False): "▀", (False, True): "▄", (True, True): "█"}
    for y in range(0, len(rows), 2):
        print("\033[30;107m" + "".join(chars[a, b] for a, b in zip(rows[y], rows[y + 1])) + "\033[0m")
