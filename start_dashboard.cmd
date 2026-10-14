@echo off
rem Launch the permafrost station dashboard in the default browser (http://localhost:8501).
cd /d "%~dp0app"
"C:\Users\aymane.ahajjam\AppData\Local\Programs\Python\Python312\python.exe" -m streamlit run app.py --server.headless false --browser.gatherUsageStats false
