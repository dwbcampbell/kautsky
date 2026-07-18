PY := .venv/bin/python
WORK ?= erfurter-programm

.PHONY: venv scrape segment translate qa site render epub clean

venv:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install anthropic beautifulsoup4 lxml pyyaml requests

scrape:
	$(PY) pipeline/01_scrape.py $(WORK)

segment:
	$(PY) pipeline/02_segment.py $(WORK)

translate:
	$(PY) pipeline/03_translate.py $(WORK) $(CHAPTERS)

qa:
	$(PY) pipeline/04_qa_check.py $(WORK)

site:
	$(PY) pipeline/05_generate_qmd.py $(WORK)

render:
	quarto render site/

epub:
	$(PY) pipeline/06_generate_epub.py $(WORK)
	quarto render works/$(WORK)/book/

clean:
	rm -rf site/_site site/.quarto works/*/book/_book works/*/book/.quarto
