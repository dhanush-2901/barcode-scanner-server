@echo off
echo Installing dependencies...
pip install -r requirements.txt
echo.

echo ============================================================
echo   YOUR PC's IP ADDRESS (use this in app\build.gradle):
echo ============================================================
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    set ip=%%a
    goto :show
)
:show
echo   http:%ip%:5000
echo ============================================================
echo.
echo   In app\build.gradle, set:
echo   buildConfigField "String", "LICENSE_SERVER_URL", '"http:%ip%:5000"'
echo.
echo   Then rebuild the APK so devices use this address.
echo ============================================================
echo.
echo Starting server...
python app.py
pause
