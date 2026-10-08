"""Render the Flask app into a static site (for GitHub Pages).

All date math runs client-side, so the rendered page is fully functional
without the server. Run from the web/ directory:

    python build_static.py [output_dir]
"""
import os
import shutil
import sys

from app import app

out_dir = sys.argv[1] if len(sys.argv) > 1 else '_site'

response = app.test_client().get('/')
if response.status_code != 200:
    sys.exit(f'Render failed with HTTP {response.status_code}')

shutil.rmtree(out_dir, ignore_errors=True)
shutil.copytree('static', os.path.join(out_dir, 'static'))
with open(os.path.join(out_dir, 'index.html'), 'wb') as file:
    file.write(response.data)

print(f'Static site written to {out_dir}/')
