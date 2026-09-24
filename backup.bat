@echo off
echo Backup... && mkdir backups 2>nul && copy .env backups\ 2>nul && echo Backup done
pause
