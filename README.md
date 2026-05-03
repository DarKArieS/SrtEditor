# SrtEditor

SRT 字幕工具集，包含刪除指定條目與 LLM 文本修飾兩支程式。

---

## SrtDelete

批次刪除 SRT 字幕檔中指定條目的工具，支援精確比對與正規表達式。

### 使用方式

1. 將 `SrtDelete.exe` 與 `SrtDelete.json` 放在同一個資料夾
2. 編輯 `SrtDelete.json`，填入要刪除的字幕文字
3. 將一個或多個 `.srt` 檔案拖曳到 `SrtDelete.exe` 上執行

也可以透過命令列執行：

```
SrtDelete.exe file1.srt file2.srt ...
```

### 設定檔 SrtDelete.json

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

#### `deleteTarget`

精確比對陣列。字幕文字去除前後空白後，與條目完全相同才刪除。

#### `deleteTargetRegex`

正規表達式陣列。使用 `re.search()` 比對，字幕文字中只要有符合的子字串即刪除。

> 無效的正規表達式會印出警告並略過，不影響其他條目的執行。兩個欄位可同時使用，任一命中即刪除。

### 執行範例

```
已載入 3 個刪除條目（Regex 模式）

處理: C:\subtitle\movie.srt
  刪除: [00:01:23,000 --> 00:01:25,000] 字幕由 XXX 提供
  刪除: [00:45:10,500 --> 00:45:12,000] [掌聲]
  完成: 共 1024 條，刪除 2 條，保留 1022 條

全部完成。按 Enter 結束...
```

### 重新打包

```
pip install pyinstaller
```

執行 `build_SrtDelete.bat`，輸出位置：`dist\SrtDelete.exe`

---

## SrtClean

使用 OpenAI 相容的 LLM API 自動修飾 SRT 字幕文本，每條字幕獨立呼叫、不保留上下文。

### 使用方式

1. 將 `SrtClean.exe` 與 `SrtClean.json` 放在同一個資料夾
2. 編輯 `SrtClean.json`，填入 API 位址與系統提示詞
3. 將一個或多個 `.srt` 檔案拖曳到 `SrtClean.exe` 上執行

也可以透過命令列執行：

```
SrtClean.exe file1.srt file2.srt ...
```

### 設定檔 SrtClean.json

```json
{
    "apiUrl": "http://192.168.1.1:8080",
    "prompt": "給 LLM 的系統提示詞，用來修飾 srt 文本",
    "model": "gpt-4o-mini",
    "apiKey": "your-api-key"
}
```

| 欄位 | 必填 | 說明 |
|------|------|------|
| `apiUrl` | 是 | OpenAI 相容 API 的主機位址（不含結尾斜線），程式會呼叫 `{apiUrl}/v1/chat/completions` |
| `prompt` | 是 | LLM 的系統提示詞 |
| `model` | 否 | 模型名稱，預設 `gpt-4o-mini` |
| `apiKey` | 否 | API 金鑰，本機服務填 `no-key` 即可 |

### 執行範例

```
API: http://192.168.1.1:8080  模型: gpt-4o-mini

處理: C:\subtitle\movie.srt
  共 120 條字幕，開始處理...
  [1/120] '字幕由網友提供，禁止商業用途' -> '字幕由網友提供'
  [2/120] '這個、這個真的很好吃耶' -> '這真的很好吃'
  ...
  完成: C:\subtitle\movie.srt

全部完成。按 Enter 結束...
```

### 重新打包

```
pip install pyinstaller requests
```

執行 `build_SrtClean.bat`，輸出位置：`dist\SrtClean.exe`

---

## 注意事項

- 兩支程式皆直接修改原始 `.srt` 檔案，操作前請自行備份
- 支援編碼：UTF-8 BOM、UTF-8、CP950、Big5、GBK
- 刪除或修改後會自動重新編號剩餘字幕
