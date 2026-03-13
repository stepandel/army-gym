.PHONY: install ingest serve watch

install:
	pip install -r requirements.txt

ingest:
	python ingest_all.py

ingest-harbor:
	python ingest.py

ingest-langsmith:
	python ingest_langsmith.py

serve: ingest
	streamlit run app.py

watch:
	python ingest_all.py && streamlit run app.py
