@echo off
rem Hourly refresh: re-download station TOA5 files, then rebuild the Tableau CSVs.
rem Run by the Windows scheduled task "PermafrostTicker Hourly Refresh".
set ROOT=%~dp0
set PY=C:\Users\aymane.ahajjam\AppData\Local\Programs\Python\Python312\python.exe
set LOG=%ROOT%refresh.log
echo ==== %DATE% %TIME% ==== >> "%LOG%"
"%PY%" -I "%ROOT%station_data_survey\download.py" >> "%LOG%" 2>&1
"%PY%" -I "%ROOT%station_data_survey\build_tableau_extract.py" "%ROOT%station_data_survey" >> "%LOG%" 2>&1
