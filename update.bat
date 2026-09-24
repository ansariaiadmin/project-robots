@echo off
git pull origin main && docker compose up --build -d
pause
