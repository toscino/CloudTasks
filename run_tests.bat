@echo off
call .venv\Scripts\activate
python -m pytest tests/ -v --ignore=tests/test_app.py
