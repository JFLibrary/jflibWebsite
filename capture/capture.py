#!/usr/bin/env python3
"""Takes the website's screenshots and GIFs from a built JFLib, without opening a window.

    python capture/capture.py --jflib ../JFLib            # everything into src/img/
    python capture/capture.py --jflib ../JFLib --only gallery-kde dock

The JFLib checkout should be at the commit in jflib.lock, with these builds in it:

    python build_rs.py all --target win
    python build_rs.py app gallery --target win --style winui,classic,macos,kde,jfoffice,backupcraft
    python build_rs.py app Kritzel --target win --style classic --out build/kritzel-classic
    python build_rs.py new hello --title "Hello"      # with the click counter from JFLib's README as
    python build_rs.py app hello --target win         # its src/main.rs, for the start page's example

Kritzel, jfWord and the Build Manager have no English texts yet, so their pictures are not here.
Windows only, because the pictures should all look the same, and the GIFs need ffmpeg. Every
picture is a script (see "The script language" in JFLib's docs/GUIDE.md) run headless: the app draws
into memory on a virtual clock, so a run gives the same picture every time.
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
IMG = ROOT / "src" / "img"
SAMPLE = HERE / "sample-drawing.png"
POINTER = HERE / "pointer.png"
LAB = "apps/JFNetworker/assets/labs/01-campus-vlan.jfnet"


class Shot:
    """One picture: the app, how it starts, and script lines to bring it into the right state."""

    def __init__(self, name, exe, size, lines=(), args=(), theme="light", scale=100, crop=None, env=None, window=None, script=None):
        self.name, self.exe, self.size, self.lines, self.args = name, exe, size, list(lines), list(args)
        self.theme, self.scale, self.crop, self.env, self.window = theme, scale, crop, env or {}, window
        self.script = script        # a script from the JFLib checkout to run first, without its own shots


class Reel:
    """One GIF: a script that takes a frame after each step, with the pointer drawn in afterwards,
    because the app does not draw one. still: the frame for people who ask for reduced motion."""

    def __init__(self, name, exe, size, args=(), theme="light", side=None):
        self.name, self.exe, self.size, self.args, self.theme = name, exe, size, list(args), theme
        self.lines, self.frames, self.at, self.still = [], [], None, 0
        self.side = side                    # a second window, drawn right of the main one
        self.width = int(size.split("x")[0])

    def cmd(self, line):
        self.lines.append(line)
        return self

    def snap(self, ms):
        self.lines.append("shot frames/%03d.png" % len(self.frames))
        if self.side:
            self.lines.append("shot frames/%03ds.png window %d" % (len(self.frames), self.side))
        self.frames.append((ms, self.at))
        return self

    def go(self, x, y, steps=8, ms=40):
        x0, y0 = self.at or (x, y)
        for i in range(1, steps + 1):
            self.at = (round(x0 + (x - x0) * i / steps), round(y0 + (y - y0) * i / steps))
            if self.at[0] < self.width:     # beyond it the pointer is over the second window
                self.lines.append("move %d,%d" % self.at)
            self.snap(ms)
        return self

    def down(self):
        return self.cmd("down %d,%d" % self.at)

    def up(self):
        return self.cmd("up %d,%d" % self.at)

    def keep(self):
        self.still = len(self.frames) - 1
        return self


class Player:
    """The test page's script player: a picture after each command that does something, with the
    pointer where that command acted. Expectations take no picture; the page shows them passed."""

    def __init__(self, name, exe, size, steps, crop):
        self.name, self.exe, self.size, self.steps, self.crop = name, exe, size, steps, crop


# (line, where the pointer is after it); None: an expectation
FORM = Player("uis-form", "win/winui/gallery", "1000x700", [
    ("click #700", (144, 564)),
    ('type "Ada Lovelace"', (144, 564)),
    ('expect #700 text "Ada Lovelace"', None),
    ('click "Option A"', (66, 328)),
    ('expect checkbox:"Option A" unchecked', None),
    ('click "Blue"', (464, 328)),
    ('expect radio:"Blue" checked', None),
    ("drag 105,446 186,446 12", (186, 446)),
    ("expect #140 value 84", None),
    ("key tab up up", (186, 446)),
    ("expect #141 focused", None),
    ("expect #141 value 14", None),
    ("theme dark", (186, 446)),
], crop=(0, 0, 1000, 620))


def gallery(style):
    return f"win/{style}/gallery"


INSPECTOR = 2147422208
SIDE_GAP = 16
INSPECT_PICKED = ["inspect on", "wait 100", "inspect select #101", "move 450,330", "wait 100"]
INSPECT_EDITED = ["inspect on", "inspect tab look", "inspect set accent #E8590C", "inspect set radius 8", "move 450,330", "wait 100"]

SHOTS = [
    Shot("gallery-winui", gallery("winui"), "1000x700"),
    Shot("gallery-winui-dark", gallery("winui"), "1000x700", theme="dark"),
    Shot("gallery-macos", gallery("macos"), "1000x700"),
    Shot("gallery-kde", gallery("kde"), "1000x700"),
    Shot("gallery-classic", gallery("classic"), "1000x700"),
    Shot("gallery-jfoffice", gallery("jfoffice"), "1000x700"),
    Shot("gallery-backupcraft", gallery("backupcraft"), "1000x700"),
    Shot("gallery-rtl", gallery("winui"), "1000x700", args=["--lang", "ar"], env={"jfgui_FONT_FALLBACK": "1"}),
    Shot("pocket", "win/androidGallery", "390x844", scale=200),
    Shot("paintcraft", "win/PaintCraft", "1280x800", args=[str(SAMPLE)], theme="dark"),
    Shot("kritzel-winui", "win/Kritzel", "1280x800", script="apps/Kritzel/tests/readme.uis"),
    Shot("kritzel-classic", "kritzel-classic/win/Kritzel", "1280x800", script="apps/Kritzel/tests/readme.uis"),
    Shot("backupcraft-dark", "win/BackupCraft", "1280x800", args=["--fixture", "--page", "jobs"], theme="dark", lines=["wait 50"]),
    Shot("jfnetworker", "win/JFNetworker", "1400x880", args=["--open", LAB], theme="dark", lines=["wait 300"]),
    Shot("feature-charts", "win/datagallery", "1440x960"),
    Shot("feature-high-contrast", "win/datagallery", "1440x960", args=["--contrast", "high"]),
    Shot("feature-richtext", "win/editortest", "1000x700", crop=(0, 0, 1000, 565)),
    Shot("feature-code-editor", "win/editortest", "1000x680", theme="dark", lines=['click tab:"Code"', "wait 50"]),
    Shot("feature-svg", "win/svgtest", "1040x820"),
    Shot("feature-spellcheck", "win/spelltest", "640x560", lines=["wait 200", "rclick 70,136", "wait 200"], crop=(0, 0, 640, 436)),
    Shot("feature-font-dialog", "win/fontpicktest", "900x640", theme="dark", lines=['click "Font…"', "wait 100"], window=184878562),
    Shot("feature-text-scale", gallery("winui"), "1000x700", args=["--text-scale", "150"]),
    Shot("mdview", "win/mdviewtest", "1100x660"),
    Shot("audio", "win/audiotest", "900x640"),
    Shot("settings", "win/prefstest", "1000x720", crop=(0, 335, 1000, 385)),
    Shot("terminal", "win/JFNetworker", "1280x900", args=["--open", LAB], theme="dark",
         lines=["wait 300", "drag 630,671 630,380 8", 'dblclick listitem:"R1"', "wait 300", 'type "\\n"', "wait 100", 'type "enable\\n"', "wait 100",
                'type "show ip interface brief\\n"', "wait 200"], crop=(266, 410, 670, 465)),
    Shot("example-counter", "win/hello", "480x300", lines=['click "Click me"', 'click "Click me"', "wait 50"]),
    # the inspector's page: the tool window has the id 2147422208
    Shot("inspector-widgets", gallery("winui"), "1000x700", lines=INSPECT_PICKED, window=INSPECTOR),
    Shot("inspector-frame", gallery("winui"), "1000x700", lines=INSPECT_PICKED + ["inspect tab frame", "wait 50"], window=INSPECTOR),
    Shot("inspector-colors", gallery("winui"), "1000x700", lines=["inspect on", "inspect tab colors", "wait 100"], window=INSPECTOR),
    Shot("inspector-appearance", gallery("winui"), "1000x700", lines=INSPECT_EDITED, window=INSPECTOR),
    Shot("inspector-appearance-app", gallery("winui"), "1000x700", lines=INSPECT_EDITED),
    Shot("inspector-outlines", gallery("winui"), "1000x700", lines=["inspect on", "inspect option outlines on", "wait 100"]),
    Shot("inspector-order", gallery("winui"), "1000x700", lines=["inspect on", "inspect option order on", "wait 100"]),
    Shot("inspector-repaints", gallery("winui"), "1000x700", lines=["inspect on", "inspect option dirty on", 'click "Toggle"', "wait 30"]),
]


def reels():
    r = {}

    insp = Reel("feature-inspector", gallery("winui"), "900x520")
    insp.at = (700, 300)
    insp.cmd("inspect arm").cmd("move 700,300").cmd("key f12").cmd("wait 50")
    # jumps: on the way between widgets the overlay would mark the whole page
    for x, y in ((62, 201), (142, 201), (432, 201), (34, 329), (357, 329), (536, 329), (106, 445)):
        insp.go(x, y, steps=1, ms=1100)
        if (x, y) == (142, 201):
            insp.keep()
    r["inspector"] = insp

    # the pick: a button in the tool window, then a click into the app selects instead of acting
    pick = Reel("inspector-pick", gallery("winui"), "1000x700", side=INSPECTOR)
    tool = 1000 + SIDE_GAP
    pick.at = (720, 600)
    pick.cmd("inspect on").cmd("move 720,600").cmd("wait 100").snap(1000)
    pick.go(tool + 32, 54, steps=10).snap(300)
    pick.cmd("window %d" % INSPECTOR).cmd('click button:"Pick"').cmd("window main").cmd("wait 50").snap(700)
    pick.go(393, 329, steps=12).cmd("wait 50").snap(1000)
    pick.cmd("click 393,329").cmd("wait 100").snap(2200).keep()
    pick.go(tool + 329, 92, steps=10).cmd("inspect tab look").cmd("wait 50").snap(900)
    pick.go(tool + 240, 295, steps=6).cmd("inspect set accent #E8590C").cmd("wait 50").snap(2600)
    r["pick"] = pick

    # the page shows these same lines as the script
    test = Reel("uis-test", "win/template", "480x300")
    test.at = (300, 240)
    test.cmd("move 300,240").snap(500)
    test.go(60, 120, steps=10).snap(300)
    test.cmd('click "Click me"').snap(700)
    test.cmd('click "Click me"').cmd('expect text:"Clicks: 2" exists').snap(900).keep()
    test.go(135, 120, steps=6).snap(300)
    test.cmd('click "Reset"').cmd('expect text:"Clicks: 0" exists').snap(1200)
    r["uis"] = test

    dock = Reel("feature-docking", "win/docktest", "960x640", theme="dark")
    dock.at = (500, 300)
    dock.cmd("move 500,300").go(745, 66, steps=10).snap(300).down().cmd("wait 1100").snap(200)
    dock.go(500, 260, steps=10).go(140, 200, steps=10).snap(300)
    dock.go(130, 328, steps=6).snap(900).keep()
    dock.go(460, 545, steps=10).snap(700)
    dock.go(130, 328, steps=10).snap(300).up().snap(1400)
    r["dock"] = dock

    dnd = Reel("feature-dragdrop", "win/dndtest", "720x440")
    dnd.at = (300, 260)
    dnd.cmd("move 300,260").go(52, 105, steps=8).snap(300).down().snap(100)
    dnd.go(200, 110, steps=8).go(330, 120, steps=6).snap(800).keep()
    dnd.up().snap(1400)
    r["dnd"] = dnd

    diagram = Reel("feature-diagram", "win/diagramtest", "1100x760")
    diagram.at = (800, 560)
    diagram.cmd("move 800,560").go(470, 164, steps=10).snap(300).down().snap(100)
    diagram.go(620, 330, steps=14).snap(500).keep()
    diagram.go(330, 440, steps=14).snap(500).go(470, 164, steps=14).up().snap(1400)
    r["diagram"] = diagram
    return r


def run_app(exe, args, work, env, timeout=90):
    full = dict(os.environ)
    full.update(env)
    p = subprocess.run([str(exe)] + args, cwd=work, env=full, capture_output=True, text=True, errors="replace", timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"{exe.name} exit {p.returncode}: {(p.stdout + p.stderr).strip()[-400:]}")


def common_args(size, theme, scale=100, extra=()):
    """English unless the picture names its own language: an app reads the first --lang."""
    lang = [] if "--lang" in extra else ["--lang", "en"]
    return lang + ["--size", size, "--theme", theme, "--scale", str(scale), "--anim", "off"]


def take_shot(s, build, work):
    exe = build / (s.exe + ".exe")
    out = work / "shot.png"
    out.unlink(missing_ok=True)
    where = " window %d" % s.window if s.window else ""
    crop = " %d %d %d %d" % s.crop if s.crop else ""
    first = []
    if s.script:
        text = (build.parent / s.script).read_text(encoding="utf-8")
        first = [line for line in text.splitlines() if not line.startswith(("shot ", "quit"))]
    (work / "shot.uis").write_text("\n".join(first + s.lines + [f"shot shot.png{where}{crop}", "quit", ""]), encoding="utf-8")
    run_app(exe, common_args(s.size, s.theme, s.scale, s.args) + s.args + ["--script", "shot.uis"], work, s.env)
    shutil.copyfile(out, IMG / f"{s.name}.png")
    print(f"{s.name}: {out.stat().st_size // 1024} KB")


def take_gpu_scene(build, work):
    """The benchmark scene's last frame: too busy for a PNG."""
    subprocess.run([str(build / "win/gputest.exe"), "--bench", "200000", "--res", "1280x800", "--frames", "90", "--warmup", "30",
                    "--shot", "scene.png"], cwd=work, capture_output=True, timeout=180, check=True)
    out = IMG / "gpu-scene.jpg"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(work / "scene.png"), "-q:v", "4", str(out)], check=True)
    print(f"gpu-scene: {out.stat().st_size // 1024} KB")


def take_reel(r, build, work):
    frames = work / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir()
    (work / "reel.uis").write_text("\n".join(r.lines + ["quit", ""]), encoding="utf-8")
    run_app(build / (r.exe + ".exe"), common_args(r.size, r.theme) + r.args + ["--script", "reel.uis"], work, {}, timeout=180)
    listing = []
    for i, (ms, at) in enumerate(r.frames):
        src = frames / ("%03d.png" % i)
        if r.side:
            both = frames / ("c%03d.png" % i)
            h = int(r.size.split("x")[1])
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-i", str(frames / ("%03ds.png" % i)), "-filter_complex",
                            "[1]pad=iw+%d:%d:%d:0:color=0xD5D8E0[s];[0][s]hstack" % (SIDE_GAP, h, SIDE_GAP), str(both)], check=True)
            src = both
        if at:
            drawn = frames / ("p%03d.png" % i)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-i", str(POINTER), "-filter_complex",
                            "overlay=%d:%d" % at, str(drawn)], check=True)
            src = drawn
        listing.append(f"file '{src.as_posix()}'\nduration {ms / 1000:.3f}\n")
        if i == r.still:
            shutil.copyfile(src, IMG / f"{r.name}-still.png")
    listing.append(f"file '{src.as_posix()}'\n")          # the concat demuxer ignores the last duration otherwise
    (work / "reel.txt").write_text("".join(listing), encoding="utf-8")
    out = IMG / f"{r.name}.gif"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(work / "reel.txt"), "-vf",
                    "split[a][b];[a]palettegen=max_colors=160:stats_mode=full[p];[b][p]paletteuse=dither=none:diff_mode=rectangle",
                    "-fps_mode", "vfr", "-loop", "0", str(out)], check=True)
    total = sum(ms for ms, _ in r.frames) / 1000
    print(f"{r.name}: {len(r.frames)} frames, {total:.1f} s, {out.stat().st_size // 1024} KB")


def take_player(pl, build, work):
    frames = work / "frames"
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir()
    lines, n = [], 0
    for line, at in pl.steps:
        lines.append(line)
        if at:
            lines.append("shot frames/%03d.png %d %d %d %d" % ((n,) + pl.crop))
            n += 1
    (work / "player.uis").write_text("\n".join(lines + ["quit", ""]), encoding="utf-8")
    run_app(build / (pl.exe + ".exe"), common_args(pl.size, "light") + ["--script", "player.uis"], work, {})
    n = 0
    for line, at in pl.steps:
        if not at:
            continue
        out = IMG / ("%s-%d.png" % (pl.name, n + 1))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(frames / ("%03d.png" % n)), "-i", str(POINTER), "-filter_complex",
                        "overlay=%d:%d" % at, str(out)], check=True)
        n += 1
    print(f"{pl.name}: {n} pictures")


def main(argv=None):
    ap = argparse.ArgumentParser(description="takes the website's screenshots and GIFs")
    ap.add_argument("--jflib", required=True, help="a JFLib checkout with its builds")
    ap.add_argument("--only", nargs="*", help="names of pictures or GIFs (default: all)")
    a = ap.parse_args(argv)
    build = Path(a.jflib).resolve() / "build"
    want = set(a.only or [])
    failed = []
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        # relative paths such as the lab live in the checkout
        for s in SHOTS:
            s.args = [str(Path(a.jflib).resolve() / x) if x == LAB else x for x in s.args]
            if want and s.name not in want:
                continue
            try:
                take_shot(s, build, work)
            except (RuntimeError, OSError, subprocess.SubprocessError) as e:
                failed.append(s.name)
                print(f"{s.name}: FAILED {e}")
        if not want or "gpu-scene" in want:
            try:
                take_gpu_scene(build, work)
            except (OSError, subprocess.SubprocessError) as e:
                failed.append("gpu-scene")
                print(f"gpu-scene: FAILED {e}")
        if not want or FORM.name in want:
            try:
                take_player(FORM, build, work)
            except (RuntimeError, OSError, subprocess.SubprocessError) as e:
                failed.append(FORM.name)
                print(f"{FORM.name}: FAILED {e}")
        for key, r in reels().items():
            if want and key not in want and r.name not in want:
                continue
            try:
                take_reel(r, build, work)
            except (RuntimeError, OSError, subprocess.SubprocessError) as e:
                failed.append(r.name)
                print(f"{r.name}: FAILED {e}")
    if failed:
        print("failed: " + " ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
