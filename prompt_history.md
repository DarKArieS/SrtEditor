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