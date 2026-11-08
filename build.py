#!/usr/bin/env python3
"""Builds jflib.org into _site/ with the Python standard library only.

    python build.py                                        # the pages alone, for working on them
    python build.py --docs DIR --gallery DIR --preview     # what the workflow publishes for now
    python build.py --check ...                            # build, then check the result

--docs is the output of `python build_rs.py site` in JFLib, --gallery its build/web/gallery with
the scalar and SIMD variants. --preview keeps search engines away and shows the preview note.

Languages: English pages are src/pages/*.html and go to the root. A translation is
src/i18n/LANG/PAGE.html in the same format and goes to LANG/PAGE.html; a page without one is
built there in English with a note. src/i18n/strings.json translates the layout ({{t:English}})
and the texts of site.js.
"""
import argparse
import html
import json
import os
import re
import shutil
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
VOID = frozenset("area base br col embed hr img input link meta source track wbr use".split())
PREVIEW_NOTE = "Preview. Kritzel, jfWord and the Build Manager are still shown in German."
ROBOTS_OPEN = "User-agent: *\nAllow: /\n"
ROBOTS_CLOSED = "User-agent: *\nDisallow: /\n"
SITE_URL = "https://jflib.org/"
LANGS = (("en", "English"), ("de", "Deutsch"), ("fr", "Français"), ("it", "Italiano"), ("es", "Español"))
JS_KEYS = ("Feature Gallery", "Running in your browser as WebAssembly", "Close", "Feature Gallery, running live",
           "The gallery could not be loaded here. This is what it looks like:", "A picture of the Feature Gallery.",
           "Picture viewer", "Previous picture", "Next picture", "Zoom out", "Zoom in", "Fit to the screen", "Fit",
           "Enlarge: ", "Line {n} of {m}", "Pause", "Play")
NAV = ("features", "apps", "compare", "roadmap")


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


def translator(strings, lang):
    table = strings.get(lang, {})

    def t(key):
        if lang != "en" and key not in table:
            raise SiteError(f"src/i18n/strings.json: {lang} has no text for {key!r}")
        return table.get(key, key)
    return t


def localize_links(text):
    """A page in LANG/ keeps its links to other pages, so they stay in its language; everything
    else (pictures, fonts, styles, docs, gallery) lies one folder up."""
    def one(url):
        if re.match(r"[a-z][a-z0-9+.-]*:|#|/|\.\./", url):
            return url
        path = url.split("#")[0].split("?")[0]
        if path.endswith(".html") and "/" not in path:
            return url
        return "../" + url

    def attr(m):
        name, value = m.group(1), m.group(2)
        if name == "srcset":
            value = ", ".join(" ".join([one(part.split()[0])] + part.split()[1:]) for part in value.split(","))
        else:
            value = one(value)
        return f'{name}="{value}"'
    return re.sub(r'\b(href|src|srcset)="([^"]*)"', attr, text)


def lang_menu(page, lang, base, done):
    rows = []
    for code, name in LANGS:
        href = base + ("" if code == "en" else code + "/") + page
        here = ' aria-current="true"' if code == lang else ""
        rows.append(f'<li><a href="{href}" hreflang="{code}" lang="{code}" data-lang="{code}"{here}>{name}</a></li>')
    label = dict(LANGS)[lang]
    return ('<details class="lang"><summary aria-label="{{t:Language}}: %s"><svg viewBox="0 0 24 24" aria-hidden="true"><use href="#i-globe"/></svg>'
            '<span>%s</span></summary><ul>%s</ul></details>' % (label, lang.upper(), "".join(rows)))


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
    strings = json.loads((SRC / "i18n" / "strings.json").read_text(encoding="utf-8"))
    robots = '<meta name="robots" content="noindex">\n' if preview else ""
    pages = sorted((SRC / "pages").glob("*.html"))
    translated = {code: {p.name for p in (SRC / "i18n" / code).glob("*.html")} for code, _ in LANGS[1:]}
    for code in translated:
        for name in translated[code]:
            if not (SRC / "pages" / name).is_file():
                raise SiteError(f"src/i18n/{code}/{name}: there is no English page of that name")
    for lang, _ in LANGS:
        t = translator(strings, lang)
        base = "" if lang == "en" else "../"
        folder = out if lang == "en" else out / lang
        folder.mkdir(exist_ok=True)
        note = '<span class="draft">%s</span>\n    ' % html.escape(t("@preview")) if preview else ""
        licence = t("@licence").format(
            mit='<a href="https://github.com/JFLibrary/JFLib/blob/main/LICENSE-MIT">%s</a>' % html.escape(t("MIT License")),
            apache='<a href="https://github.com/JFLibrary/JFLib/blob/main/LICENSE-APACHE">%s</a>' % html.escape(t("Apache License 2.0")))
        for path in pages:
            own = lang == "en" or path.name in translated[lang]
            source = path if lang == "en" or not own else SRC / "i18n" / lang / path.name
            fields, body = page_parts(source)
            body = (body.replace("{{apps-rail}}", apps_rail(apps))
                        .replace("{{apps-list}}", apps_list(apps))
                        .replace("{{contact}}", contact_line(config, preview)))
            done = ["en"] + [c for c, _ in LANGS[1:] if path.name in translated[c]]
            alternates = ""
            if len(done) > 1:
                alternates = "".join('<link rel="alternate" hreflang="%s" href="%s%s%s">\n' % (
                    c, SITE_URL, "" if c == "en" else c + "/", path.name) for c in done)
                alternates += '<link rel="alternate" hreflang="x-default" href="%s%s">\n' % (SITE_URL, path.name)
            js = {k: t(k) for k in JS_KEYS} if lang != "en" else {}
            if lang == "en":
                hints = {c: [strings[c]["@hint"], strings[c]["@hint-go"], c + "/" + path.name, strings[c]["Close"]] for c in done[1:]}
                if hints:
                    js["hints"] = hints
            text = layout
            for nav in NAV:
                text = text.replace("{{current-%s}}" % nav, ' aria-current="page"' if fields.get("nav") == nav else "")
            untranslated = "" if own else '<p class="untranslated"><span class="wrap">%s</span></p>\n' % html.escape(t("@untranslated"))
            text = (text.replace("{{lang-menu}}", lang_menu(path.name, lang, base, done))
                        .replace("{{title}}", html.escape(fields["title"]))
                        .replace("{{description}}", html.escape(fields["description"], quote=True))
                        .replace("{{robots}}", robots)
                        .replace("{{alternates}}", alternates)
                        .replace("{{lang}}", lang if own else "en")
                        .replace("{{base}}", base)
                        .replace("{{licence}}", licence)
                        .replace("{{preview-note}}", note)
                        .replace("{{untranslated}}", untranslated)
                        .replace("{{js-strings}}", '<script type="application/json" id="strings">%s</script>\n' % json.dumps(js, ensure_ascii=False).replace("</", "<\\/"))
                        .replace("{{main}}", body.rstrip("\n")))
            text = re.sub(r"\{\{t:([^}]*)\}\}", lambda m: html.escape(t(m.group(1)), quote=True), text)
            if lang != "en":
                text = localize_links(text)
            (folder / path.name).write_text(text, encoding="utf-8", newline="\n")
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
        for key in ("href", "src", "srcset"):
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
    pages = sorted(out.glob("*.html")) + sorted(p for code, _ in LANGS[1:] for p in (out / code).glob("*.html"))
    for p in pages:
        s = Scan()
        text = p.read_text(encoding="utf-8")
        s.feed(text)
        rel = p.relative_to(out).as_posix()
        scans[rel] = s
        problems += [f"{rel}: {m}" for m in s.problems]
        if s.stack:
            problems.append(f"{rel}: never closed: {' '.join(s.stack)}")
        if "{{" in text:
            problems.append(f"{rel}: a placeholder is left: " + re.search(r"\{\{[^}]*\}\}", text).group(0))
        if re.search(r'(?:src|href)="https?://[^"]+\.(?:js|css|woff2?)"', text) or "fonts.googleapis" in text:
            problems.append(f"{rel}: loads a script, style or font from another host")
    used = set()
    links = 0
    for name, s in scans.items():
        for tag, target in s.links:
            if re.match(r"[a-z][a-z0-9+.-]*:", target):
                continue
            links += 1
            path, _, frag = target.partition("#")
            path = path.split("?")[0]
            path = os.path.normpath(os.path.join(os.path.dirname(name), path)).replace("\\", "/") if path else name
            if path.startswith("..") :
                problems.append(f"{name}: link out of the site: {target}")
                continue
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
    if docs:
        problems += check_docs_links(out)
    return problems, len(pages), links


def check_docs_links(out):
    """The docs check their own links in JFLib; what leads out of docs/ to this site is checked here."""
    problems = []
    base = out / "docs"
    pattern = re.compile(r'(?:href|src)="(\.\./[^"#?]*)|url\((\.\./[^)#?]*)\)')
    for path in sorted(base.rglob("*")):
        if path.suffix not in (".html", ".css"):
            continue
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            target = match.group(1) or match.group(2)
            full = Path(os.path.normpath(path.parent / target))
            inside = full == base or base in full.parents
            if not inside and not full.is_file():
                problems.append(f"{path.relative_to(out).as_posix()}: broken link out of the docs: {target}")
    return problems


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
