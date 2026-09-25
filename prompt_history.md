使用 python3
寫一個 SrtDelete 程式，打包成 exe
讀取程式所在資料夾的 SrtDelete.json ，該內容為 ["{使用者打算刪除的 srt 內容}","..."]
修改目標檔案 {xxx}.srt
可接受拖曳檔案到該 exe 上啟動

擴充 SrtDelete.json:
```
{
	setting: {
		enableRegex: true
	},
	deleteTarget: [
		"..."
	]
}
```
實作 regex 支援

修改 SrtDelete.json:
```
{
	deleteTargetRegex: [
		"..."
	],
	deleteTarget: [
		"..."
	]
}
```
並修改實作

判斷下一個字幕是否時間有重疊，如果有，則把此字幕的結尾改為下一個字幕的開頭避免重疊。


使用 python3
寫一個 SrtClean 程式，打包成 exe
讀取程式所在資料夾的 SrtClean.json ，該內容為
```json
{
    "apiUrl": "http://192.168.1.1:8080/",
	"prompt": "給 LLM 的系統提示詞，用來修飾 srt 文本"
}
```
修改目標檔案 {xxx}.srt
使用 apiUrl 呼叫 LLM (openAI like)，每一句之間的呼叫不保留上下文
將 LLM 輸出結果替換到 srt 上
可接受拖曳檔案到該 exe 上啟動

SrtClean.json 新增 reasoning_effort 欄位，並實作

SrtClean.json 新增 欄位:
```json
{
  "retryOutput": ["I’m sorry, but I can’t help with that.", "..."]
}
```
當 LLM output 出這些句子時，重試一次。如果出現同樣結果，保留原文



1. 實作拆分句子功能，將每則字幕拆成 N 個字一組，一次處理一組，處理完再組合
  - SrtClean.json 新增 欄位: wordsPerOp
2. SrtClean.json 新增 欄位: reasoning_tokens ，對應到 api call 的設定中