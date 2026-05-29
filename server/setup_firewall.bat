@echo off
echo Adding Windows Firewall rule for Barcode Scanner License Server (port 5000)...
netsh advfirewall firewall add rule name="Barcode Scanner License Server" ^
    dir=in action=allow protocol=TCP localport=5000
echo.
echo Done. Port 5000 is now open.
echo You can now reach the server from other devices on the same network.
pause
