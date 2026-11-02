#!/usr/bin/env python3
"""Builds jflib.org into _site/ with the Python standard library only.

    python build.py                                        # the pages alone, for working on them
    python build.py --docs DIR --gallery DIR --preview     # what the workflow publishes for now
    python build.py --check ...                            # build, then check the result

--docs is the output of `python build_rs.py site` in JFLib, --gallery its build/web/gallery with
the scalar and SIMD variants. --preview keeps search engines away and shows the preview note.
"""
import argparse
import html
import json
import re
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
VOID = frozenset("area base br col embed hr img input link meta source track wbr use".split())
PREVIEW_NOTE = "Preview. Most screenshots still show German text until the gallery and demos are translated."
ROBOTS_OPEN = "User-agent: *\nAllow: /\n"
ROBOTS_CLOSED = "User-agent: *\nDisallow: /\n"


class SiteError(Exception):
    pass


def page_parts(path):
    head, sep, body = path.read_text(encoding="utf-8").partition("\n---\n")
    if not sep:
        raise SiteError(f"{path.name}: the page starts with its fields and a line ---")
    fields = dict(line.split(": ", 1) for line in head.splitlines())
    return fields, body


def app_action(app):
    if app.get("link"):
        return '<a class="btn" href="%s">Product page</a>' % html.escape(app["link"], quote=True)
    return None


def apps_rail(apps):
    rows = []
    for a in apps:
        action = app_action(a) or '<span class="soon">Product page coming soon</span>'
        rows.append('      <article class="app"><img src="img/%s" width="%d" height="%d" loading="lazy" alt="%s"><h3>%s</h3>'
                    '<p class="soft">%s</p>%s</article>' % (
                        a["image"], a["width"], a["height"], html.escape(a["alt"], quote=True),
                        html.escape(a["name"]), html.escape(a["text"]), action))
    return "\n".join(rows)


def apps_list(apps):
    rows = []
    for i, a in enumerate(apps):
        text = a["text"] + (" " + a["note"] if a.get("note") else "")
        chips = "".join("<span>%s</span>" % html.escape(p) for p in a["platforms"])
        action = app_action(a) or '<span class="soon-btn">Product page coming soon</span>'
        rows.append('  <article class="ap%s">\n    <div class="ap-pic"><img src="img/%s" width="%d" height="%d"%s alt="%s"></div>\n'
                    '    <div>\n      <h2>%s</h2>\n      <p>%s</p>\n'
                    '      <div class="chips platforms" aria-label="Platforms">%s</div>\n      %s\n    </div>\n  </article>' % (
                        " flip" if i % 2 else "", a["image"], a["width"], a["height"],
                        ' loading="lazy"' if i else "", html.escape(a["alt"], quote=True),
                        html.escape(a["name"]), html.escape(text), chips, action))
    return "\n\n".join(rows)


def contact_line(config, preview):
    mail = config.get("contact_email")
    if mail:
        return '<a href="mailto:%s">%s</a>' % (html.escape(mail, quote=True), html.escape(mail))
    if not preview:
        raise SiteError("site.json: the legal notice needs contact_email before the preview note goes away")
    return "<em>still to be added</em>"


def gallery_copy(src, out):
    """The browser host without its service bar, and without the threaded variant, which needs
    server headers that GitHub Pages cannot send."""
    variants = json.loads((src / "variants.json").read_text(encoding="utf-8"))
    variants.pop("threads", None)
    if "simd" not in variants or "scalar" not in variants:
        raise SiteError("--gallery: needs the scalar and SIMD builds of the gallery")
    shutil.copytree(src, out, ignore=shutil.ignore_patterns("*.threads.wasm"))
    (out / "variants.json").write_text(json.dumps(variants), encoding="utf-8")
    page = (out / "index.html").read_text(encoding="utf-8")
    link = '<link rel="stylesheet" href="host.css">'
    if link not in page or "<title>gallery</title>" not in page:
        raise SiteError("--gallery: index.html has changed, adapt gallery_copy() in build.py")
    page = page.replace(link, link + "\n<style>#hostbar{display:none!important}</style>")
    page = page.replace("<title>gallery</title>", "<title>Feature Gallery</title>")
    (out / "index.html").write_text(page, encoding="utf-8")


def build(out, docs, gallery, preview):
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    layout = (SRC / "layout.html").read_text(encoding="utf-8")
    apps = json.loads((ROOT / "apps.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "site.json").read_text(encoding="utf-8"))
    note = '<span class="draft">%s</span>\n    ' % PREVIEW_NOTE if preview else ""
    robots = '<meta name="robots" content="noindex">\n' if preview else ""
    for path in sorted((SRC / "pages").glob("*.html")):
        fields, body = page_parts(path)
        body = (body.replace("{{apps-rail}}", apps_rail(apps))
                    .replace("{{apps-list}}", apps_list(apps))
                    .replace("{{contact}}", contact_line(config, preview)))
        text = layout
        for nav in ("features", "apps"):
            text = text.replace("{{current-%s}}" % nav, ' aria-current="page"' if fields.get("nav") == nav else "")
        text = (text.replace("{{title}}", html.escape(fields["title"]))
                    .replace("{{description}}", html.escape(fields["description"], quote=True))
                    .replace("{{robots}}", robots)
                    .replace("{{preview-note}}", note)
                    .replace("{{main}}", body.rstrip("\n")))
        (out / path.name).write_text(text, encoding="utf-8", newline="\n")
    for name in ("site.css", "site.js", "favicon.svg"):
        shutil.copyfile(SRC / name, out / name)
    shutil.copytree(SRC / "img", out / "img")
    shutil.copytree(SRC / "fonts", out / "fonts")
    (out / "robots.txt").write_text(ROBOTS_CLOSED if preview else ROBOTS_OPEN, encoding="utf-8", newline="\n")
    if docs:
        shutil.copytree(docs, out / "docs", ignore=shutil.ignore_patterns(".jflib-site"))
    if gallery:
        gallery_copy(gallery, out / "gallery")


class Scan(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.ids, self.links, self.problems = [], set(), [], []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if a.get("id"):
            if a["id"] in self.ids:
                self.problems.append("id used twice: " + a["id"])
            self.ids.add(a["id"])
        for key in ("href", "src"):
            if a.get(key) and not (tag == "use" and a[key].startswith("#")):
                self.links.append((tag, a[key]))
        if tag == "img":
            for need in ("alt", "width", "height"):
                if need not in a:
                    self.problems.append(f"img without {need}: {a.get('src')}")
        if tag not in VOID:
            self.stack.append(tag)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack or self.stack[-1] != tag:
            self.problems.append(f"</{tag}> closes {self.stack[-1] if self.stack else 'nothing'} at line {self.getpos()[0]}")
            if tag in self.stack:
                while self.stack.pop() != tag:
                    pass
            return
        self.stack.pop()


def check(out, docs, gallery):
    problems, scans = [], {}
    pages = sorted(out.glob("*.html"))
    for p in pages:
        s = Scan()
        text = p.read_text(encoding="utf-8")
        s.feed(text)
        scans[p.name] = s
        problems += [f"{p.name}: {m}" for m in s.problems]
        if s.stack:
            problems.append(f"{p.name}: never closed: {' '.join(s.stack)}")
        if "{{" in text:
            problems.append(f"{p.name}: a placeholder is left: " + re.search(r"\{\{[^}]*\}\}", text).group(0))
        if re.search(r'(?:src|href)="https?://[^"]+\.(?:js|css|woff2?)"', text) or "fonts.googleapis" in text:
            problems.append(f"{p.name}: loads a script, style or font from another host")
    used = set()
    links = 0
    for name, s in scans.items():
        for tag, target in s.links:
            if re.match(r"[a-z][a-z0-9+.-]*:", target):
                continue
            links += 1
            path, _, frag = target.partition("#")
            path = path.split("?")[0] or name
            if path.startswith("docs/") and not docs or path.startswith("gallery/") and not gallery:
                continue
            if not (out / path).is_file():
                problems.append(f"{name}: broken link: {target}")
                continue
            used.add(path)
            if frag and path in scans and frag not in scans[path].ids:
                problems.append(f"{name}: no anchor: {target}")
    for js in ("gallery/index.html", "gallery/variants.json", "img/gallery-winui.png"):
        if js.startswith("gallery/") and not gallery:
            continue
        if not (out / js).is_file():
            problems.append("missing: " + js)
    for img in sorted((out / "img").iterdir()):
        if f"img/{img.name}" not in used and img.name not in (out / "site.js").read_text(encoding="utf-8"):
            problems.append("image not used by any page: " + img.name)
    css = (out / "site.css").read_text(encoding="utf-8")
    for font in re.findall(r"url\((fonts/[^)]+)\)", css):
        if not (out / font).is_file():
            problems.append("site.css: missing font: " + font)
    if gallery and (out / "gallery" / "gallery.threads.wasm").exists():
        problems.append("the threaded gallery variant was copied")
    return problems, len(pages), links


def main(argv=None):
    ap = argparse.ArgumentParser(description="builds the JFLib website")
    ap.add_argument("--out", default=str(ROOT / "_site"))
    ap.add_argument("--docs", help="output of `python build_rs.py site`")
    ap.add_argument("--gallery", help="build/web/gallery of JFLib")
    ap.add_argument("--preview", action="store_true", help="noindex, robots.txt closed, preview note in the footer")
    ap.add_argument("--check", action="store_true", help="check links, anchors, images and HTML after building")
    a = ap.parse_args(argv)
    out, docs, gallery = Path(a.out).resolve(), a.docs and Path(a.docs).resolve(), a.gallery and Path(a.gallery).resolve()
    try:
        build(out, docs, gallery, a.preview)
    except SiteError as e:
        print("build: " + str(e))
        return 1
    if a.check:
        problems, pages, links = check(out, docs, gallery)
        for p in problems:
            print("check: " + p)
        if problems:
            print(f"check: {len(problems)} problem(s)")
            return 1
        print(f"check: ok ({pages} pages, {links} local links)")
    print(f"built {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
