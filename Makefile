# Variables
VENV_NAME=venv
PYTHON=${VENV_NAME}/bin/python3
PIP=${VENV_NAME}/bin/pip3
DATABASE_PATH := $(shell ${PYTHON} -c "from src.web_crawler.config import DATABASE_PATH; print(DATABASE_PATH)")

# Detect OS
ifeq ($(OS),Windows_NT)
    PYTHON=${VENV_NAME}/Scripts/python3
    PIP=${VENV_NAME}/Scripts/pip3
    ACTIVATE=.\\${VENV_NAME}\\Scripts\\activate
else
    ACTIVATE=source ${VENV_NAME}/bin/activate
endif

.PHONY: all venv clean test run activate inspect clear-db

# Default target
all: venv

# Create virtual environment (only needed once)
venv:
	test -d ${VENV_NAME} || python3 -m venv ${VENV_NAME}
	${PIP} install --upgrade pip
	${PIP} install requests beautifulsoup4 pytest black fastapi uvicorn python-dotenv google-generativeai pyperclip


# Show activation command
activate:
	@echo "To activate the virtual environment, run:"
	@echo "${ACTIVATE}"

# Clean up everything (including venv)
clean: clear-db
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf **/__pycache__
	rm -rf .pytest_cache
	rm -rf ${VENV_NAME}

# Run tests
test:
	${PYTHON} -m pytest tests/

# Run crawler (using proper module path)
crawl:
	${PYTHON} -m src.web_crawler $(ARGS)

# Inspect crawler output (for debugging and seeing db contents)
inspect:
	python -m src.web_crawler.crawler inspect

# Run the API server
run-api:
	${PYTHON} -m uvicorn src.web_crawler.api:app --reload --host 0.0.0.0 --port 8000

# Clear the database
clear-db:
	@echo "Clearing database..."
	@rm -f ${DATABASE_PATH}
	@echo "Database cleared!"