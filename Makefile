.PHONY: venv run build docker

venv:
	python -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -r requirements.txt

run:
	python main.py

docker:
	docker build -t confexp:dev .

# local pyinstaller build (optional; pyinstaller not in requirements)
build:
	pip install pyinstaller && pyinstaller --onefile --name confexp main.py
