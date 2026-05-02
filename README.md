# SrtDelete

批次刪除 SRT 字幕檔中指定條目的工具，支援精確比對與正規表達式。

## 使用方式

1. 將 `SrtDelete.exe` 與 `SrtDelete.json` 放在同一個資料夾
2. 編輯 `SrtDelete.json`，填入要刪除的字幕文字
3. 將一個或多個 `.srt` 檔案拖曳到 `SrtDelete.exe` 上執行

也可以透過命令列執行：

```
SrtDelete.exe file1.srt file2.srt ...
```

## 設定檔 SrtDelete.json

```json
{
    "deleteTargetRegex": [
        "^字幕由.+提供$",
        "\\[.*?\\]"
    ],
    "deleteTarget": [
        "廣告字幕",
        "贊助商訊息"
    ]
}
```

### `deleteTarget`

精確比對陣列。字幕文字去除前後空白後，與條目完全相同才刪除。

### `deleteTargetRegex`

正規表達式陣列。使用 `re.search()` 比對，字幕文字中只要有符合的子字串即刪除。

```json
{
    "deleteTargetRegex": [
        "\\[.*?\\]",
        "^字幕由.+提供$",
        "\\d{4}-\\d{2}-\\d{2}"
    ]
}
```

> 無效的正規表達式會印出警告並略過，不影響其他條目的執行。

兩個欄位可同時使用，任一命中即刪除。

## 執行範例

```
已載入 3 個刪除條目（Regex 模式）

處理: C:\subtitle\movie.srt
  刪除: [00:01:23,000 --> 00:01:25,000] 字幕由 XXX 提供
  刪除: [00:45:10,500 --> 00:45:12,000] [掌聲]
  完成: 共 1024 條，刪除 2 條，保留 1022 條

全部完成。按 Enter 結束...
```

## 注意事項

- 直接修改原始 `.srt` 檔案，操作前請自行備份
- 刪除後會自動重新編號剩餘字幕
- 支援編碼：UTF-8 BOM、UTF-8、CP950、Big5、GBK

## 重新打包

需要 Python 3 與 PyInstaller：

```
pip install pyinstaller
```

執行 `build_SrtDelete.bat`，或手動執行：

```
python -m PyInstaller --onefile --console --name SrtDelete SrtDelete.py
```

輸出位置：`dist\SrtDelete.exe`
