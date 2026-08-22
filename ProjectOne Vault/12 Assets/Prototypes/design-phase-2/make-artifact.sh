#!/usr/bin/env bash
# Regenerates artifact.html — a single self-contained copy of the prototype for
# the Claude Artifact panel. GENERATED FILE: never edit artifact.html by hand.
#
# The authoritative source is index.html + styles.css + prototype.js.
# Run this after changing any of them:
#
#   ./make-artifact.sh
#
# Two deliberate differences from the repository copy, and only two:
#   1. No <!doctype>/<html>/<head>/<body> — the Artifact host supplies them.
#   2. Inter and Instrument Serif are loaded from Google Fonts, the one external
#      host the Artifact CSP allows. The repository copy stays dependency-free
#      and uses the fallback chains declared in styles.css.
set -euo pipefail
cd "$(dirname "$0")"
python3 - <<'PYEOF'
import io, re

html = io.open('index.html', encoding='utf-8').read()
css  = io.open('styles.css', encoding='utf-8').read()
parts = ['campaign.js', 'prototype.js', 'screens.js']
js = '\n'.join(io.open(n, encoding='utf-8').read() for n in parts)

for name, src in ([('styles.css', css)] + [(n, io.open(n, encoding='utf-8').read()) for n in parts]):
    if '</style' in src.lower() or '</script' in src.lower():
        raise SystemExit('Refusing to inline %s: it contains a closing tag sequence.' % name)

body = re.search(r'<body[^>]*>(.*)</body>', html, re.S).group(1)
for n in parts:
    body = body.replace('<script src="%s"></script>' % n, '')
body = body.strip()

head = """<title>The Cutting Room</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Instrument+Serif&display=swap">
<style>
%s

/* ---------------------------------------------------------------------------
   ARTIFACT BUILD ONLY — the two production typefaces.
   apps/web loads these through next/font. The repository copy of this
   prototype takes no external dependency and uses the fallback chains above;
   here they are loaded so the direction can be reviewed in its real faces.
   --------------------------------------------------------------------------- */
:root {
  --font-sans: "Inter", ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  --font-display: "Instrument Serif", Georgia, "Times New Roman", serif;
}
</style>""" % css

out = head + "\n\n" + body + "\n\n<script>\n" + js + "\n</script>\n"
io.open('artifact.html', 'w', encoding='utf-8').write(out)
print('artifact.html regenerated: %d bytes' % len(out.encode('utf-8')))
PYEOF
