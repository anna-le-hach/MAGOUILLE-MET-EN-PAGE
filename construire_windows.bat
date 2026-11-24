@echo off
REM Construit "Magouille met en page.exe" dans le dossier dist
python -m pip install -r requirements.txt pyinstaller
python -m PyInstaller magouille.spec --noconfirm
echo.
echo C'est pret : dist\Magouille met en page.exe
pause
