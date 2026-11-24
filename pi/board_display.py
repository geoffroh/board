#!/usr/bin/env python3
"""Show Board progress on a Pimoroni Display HAT Mini (320x240 LCD).

Signs in to Supabase as the board's user, counts cards per column, and draws
one square per card, coloured by column (red = not started ... green = done).

    python board_display.py                  # drive the screen
    python board_display.py --preview a.png  # draw to a file instead (no Pi needed)
    python board_display.py --demo --preview a.png   # sample data, no sign-in

Settings come from environment variables, or a board.env file next to this
script. See board.env.example.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

from PIL import Image, ImageDraw, ImageFont

W, H = 320, 240
BG, TEXT, DIM = (17, 20, 24), (232, 234, 237), (139, 146, 155)
# Colour stops from "not started" to "done". Four columns use these directly;
# other column counts are spread evenly along them.
STOPS = [(255, 69, 58), (255, 128, 0), (255, 214, 10), (48, 209, 88)]
FONT_PATHS = {
    True: "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    False: "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
}


def load_env_file():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "board.env")
    if not os.path.exists(path):
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            os.environ.setdefault(key.strip(), value)


def setting(name, default=None):
    value = os.environ.get(name, default)
    if value is None:
        sys.exit("Missing setting %s. Copy board.env.example to board.env and fill it in." % name)
    return value


def parse_columns(text):
    columns = []
    for part in text.split(","):
        col_id, _, name = part.strip().partition(":")
        if col_id:
            columns.append((col_id.strip(), (name or col_id).strip()))
    return columns


def colour_for(index, count):
    if count <= 1:
        return STOPS[-1]
    pos = index / (count - 1) * (len(STOPS) - 1)
    low = min(int(pos), len(STOPS) - 2)
    t = pos - low
    return tuple(round(a + (b - a) * t) for a, b in zip(STOPS[low], STOPS[low + 1]))


def font(size, bold=False):
    try:
        return ImageFont.truetype(FONT_PATHS[bold], size)
    except OSError:
        return ImageFont.load_default(size)


class Supabase:
    def __init__(self, url, key, email, password):
        self.url = url.rstrip("/")
        if self.url.endswith("/rest/v1"):
            self.url = self.url[: -len("/rest/v1")]
        self.key, self.email, self.password = key, email, password
        self.token, self.expires = None, 0

    def _call(self, method, path, body=None, token=None):
        headers = {"apikey": self.key, "Content-Type": "application/json"}
        if token:
            headers["Authorization"] = "Bearer " + token
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.url + path, data=data, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=20) as res:
            return json.load(res)

    def _sign_in(self):
        try:
            session = self._call("POST", "/auth/v1/token?grant_type=password",
                                 {"email": self.email, "password": self.password})
        except urllib.error.HTTPError as err:
            # Show Supabase's own explanation, e.g. "Invalid API key".
            detail = err.read().decode("utf-8", "replace")[:300]
            hint = "check SUPABASE_KEY" if err.code == 401 else "check BOARD_EMAIL and BOARD_PASSWORD"
            raise RuntimeError("Sign-in failed (HTTP %d, %s): %s" % (err.code, hint, detail)) from None
        self.token = session["access_token"]
        self.expires = time.time() + session.get("expires_in", 3600)

    def statuses(self):
        """The status of every card, as a list of column ids."""
        if not self.token or time.time() > self.expires - 60:
            self._sign_in()
        try:
            rows = self._call("GET", "/rest/v1/cards?select=status", token=self.token)
        except urllib.error.HTTPError as err:
            if err.code != 401:
                raise
            self._sign_in()
            rows = self._call("GET", "/rest/v1/cards?select=status", token=self.token)
        return [row["status"] for row in rows]


def count_cards(statuses, columns):
    ids = [col_id for col_id, _ in columns]
    counts = [0] * len(ids)
    for status in statuses:
        # A card in a column this screen doesn't know about counts as not started.
        counts[ids.index(status) if status in ids else 0] += 1
    return counts


def render(title, columns, counts, offline=False):
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    n = len(columns)
    colours = [colour_for(i, n) for i in range(n)]
    total = sum(counts)
    done = counts[-1] if counts else 0

    # Header: title on the left, percentage done on the right.
    percent = "%d%%" % round(100 * done / total) if total else "0%"
    big = font(20, bold=True)
    pw = d.textlength(percent, font=big)
    d.text((W - 12 - pw, 9), percent, font=big, fill=colours[-1])
    shown = title
    while shown and d.textlength(shown, font=big) > W - 36 - pw:
        shown = shown[:-1]
    d.text((12, 9), shown if shown == title else shown.rstrip() + "…", font=big, fill=TEXT)

    # Thin stacked bar: each column's share of the board.
    x, bar_w = 12.0, W - 24
    d.rectangle((12, 40, 12 + bar_w, 45), fill=(40, 45, 52))
    for count, colour in zip(reversed(counts), reversed(colours)):  # done first, like the grid
        if total and count:
            w = bar_w * count / total
            d.rectangle((round(x), 40, round(x + w), 45), fill=colour)
            x += w

    # One square per card, done first, so green spreads from the top left.
    gx, gy, gw, gh = 12, 58, W - 24, 116
    if total:
        size = 30
        while size > 4 and (gw // size) * (gh // size) < total:
            size -= 1
        per_row = max(1, gw // size)
        gap = max(1, size // 7)
        order = [c for i in reversed(range(n)) for c in [colours[i]] * counts[i]]
        for i, colour in enumerate(order[: per_row * max(1, gh // size)]):
            cx, cy = gx + (i % per_row) * size, gy + (i // per_row) * size
            d.rounded_rectangle((cx, cy, cx + size - gap - 1, cy + size - gap - 1),
                                radius=max(1, size // 6), fill=colour)
    else:
        d.text((gx, gy + 40), "No cards yet", font=font(16), fill=DIM)

    # Footer: a count and a name for each column.
    cell = (W - 24) / max(1, n)
    num, small = font(22, bold=True), font(11)
    for i, ((_, name), count) in enumerate(zip(columns, counts)):
        cx = 12 + i * cell
        d.text((cx, 184), str(count), font=num, fill=colours[i])
        label = name
        while label and d.textlength(label, font=small) > cell - 4:
            label = label[:-1]
        d.text((cx, 212), label, font=small, fill=DIM)

    if offline:
        d.ellipse((W - 10, H - 10, W - 4, H - 4), fill=STOPS[0])
    return img


def open_display():
    import st7789  # only needed on the Pi

    disp = st7789.ST7789(
        width=W, height=H,
        rotation=int(os.environ.get("BOARD_ROTATION", "180")),
        port=0, cs=1, dc=9, backlight=13,
        # Lower this if the picture glitches on a long ribbon cable.
        spi_speed_hz=int(os.environ.get("BOARD_SPI_MHZ", "30")) * 1000 * 1000,
        offset_left=0, offset_top=0,
    )
    disp.begin()
    return disp


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--preview", metavar="FILE", help="draw once to an image file and exit")
    parser.add_argument("--demo", action="store_true", help="use sample data, no sign-in")
    args = parser.parse_args()

    load_env_file()
    title = os.environ.get("BOARD_TITLE", "Board")
    columns = parse_columns(os.environ.get(
        "BOARD_COLUMNS", "todo:To do,doing:In progress,review:Review,done:Done"))
    poll = max(10, int(os.environ.get("BOARD_POLL_SECONDS", "60")))

    if args.demo:
        fetch = lambda: ["todo"] * 19 + ["doing"] * 5 + ["review"] * 3 + ["done"] * 6
    else:
        fetch = Supabase(setting("SUPABASE_URL"), setting("SUPABASE_KEY"),
                         setting("BOARD_EMAIL"), setting("BOARD_PASSWORD")).statuses

    if args.preview:
        render(title, columns, count_cards(fetch(), columns)).save(args.preview)
        print("wrote", args.preview)
        return

    disp = open_display()
    counts, shown = [0] * len(columns), None
    while True:
        offline = False
        try:
            counts = count_cards(fetch(), columns)
        except Exception as err:  # keep the last picture up and try again
            offline = True
            print("could not fetch cards:", err, file=sys.stderr, flush=True)
        if (counts, offline) != shown:
            disp.display(render(title, columns, counts, offline))
            shown = (list(counts), offline)
        time.sleep(poll)


if __name__ == "__main__":
    main()
