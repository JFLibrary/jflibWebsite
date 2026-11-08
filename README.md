# jflibWebsite

The source of [jflib.org](https://jflib.org), the website of the [JFLib](https://github.com/JFLibrary/JFLib) GUI library.

```sh
python build.py --check     # the pages alone -> _site/
```

| Path | Contents |
| --- | --- |
| `src/pages/` | The pages: fields, a line `---`, then the content of `<main>` |
| `src/layout.html` | Head, top bar and footer of every page |
| `src/i18n/` | `strings.json` translates the layout and the texts of `site.js`; `LANG/PAGE.html` is a page translated into German, French, Italian or Spanish, built to `LANG/PAGE.html` (a page without one is built there in English with a note) |
| `src/site.css`, `src/site.js` | Look and behaviour, no libraries |
| `src/img/`, `src/fonts/` | Screenshots, and the fonts with their licences |
| `apps.json` | Name, text, picture and product page link of every app, used by the start page and the Apps page |
| `site.json` | The contact address on the legal pages |
| `jflib.lock` | The JFLib commit that docs and gallery are built from |
| `build.py` | Puts it together into `_site/`; `--check` checks links, anchors, images and HTML |
| `.github/workflows/pages.yml` | Builds every push, publishes `main` |
| `capture/` | Takes the screenshots and GIFs in `src/img/` from a built JFLib; run by hand on Windows, the results are checked in |

Python's standard library is all `build.py` needs. To include docs and gallery, build them in a JFLib
checkout at the commit in `jflib.lock` and pass them in:

```sh
python build_rs.py site --out DOCS
python build_rs.py app gallery --target web --web-mode scalar
python build_rs.py app gallery --target web --web-mode simd
python build.py --docs DOCS --gallery JFLIB/build/web/gallery --preview --check
```

To move the site to a newer JFLib, put the new commit into `jflib.lock`. The workflow then builds
docs and gallery once and keeps them under that commit. The threaded gallery variant is left out,
because it needs server headers GitHub Pages cannot send.

`--preview` asks search engines to stay away and shows a note in the footer. The workflow uses it
until the site is launched.
