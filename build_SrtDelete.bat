@echo off
chcp 65001 > nul
echo 正在打包 SrtDelete.exe ...

pyinstaller --onefile --console --name SrtDelete SrtDelete.py

if %errorlevel% neq 0 (
    echo.
    echo [錯誤] 打包失敗，請確認已安裝 pyinstaller: pip install pyinstaller
    pause
    exit /b 1
)

echo.
echo 打包完成！輸出位置: dist\SrtDelete.exe
echo 請將 SrtDelete.json 放在與 SrtDelete.exe 相同的資料夾中。
pause
