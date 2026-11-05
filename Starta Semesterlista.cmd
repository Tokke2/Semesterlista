@echo off
rem Compatibility entry point. Use the VBS file directly to avoid CMD flashing.
start "" "%SystemRoot%\System32\wscript.exe" //NoLogo "%~dp0Starta Semesterlista.vbs"
