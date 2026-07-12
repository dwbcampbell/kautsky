PY := .venv/bin/python

.PHONY: venv scrape segment translate qa site render clean

venv:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install anthropic beautifulsoup4 lxml pyyaml requests

scrape:
	$(PY) pipeline/01_scrape.py

segment:
	$(PY) pipeline/02_segment.py

translate:
	$(PY) pipeline/03_translate.py

qa:
	$(PY) pipeline/04_qa_check.py

site:
	$(PY) pipeline/05_generate_qmd.py

render:
	quarto render site/

clean:
	rm -rf site/_site site/.quarto
