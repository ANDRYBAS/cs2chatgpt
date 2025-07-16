@echo off
cd /d "%~dp0"
powershell -Command "Start-Process python 'chat.py' -Verb runAs"