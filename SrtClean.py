import sys
import json
import os
import re
import requests


def get_exe_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def load_config():
    json_path = os.path.join(get_exe_dir(), 'SrtClean.json')
    if not os.path.exists(json_path):
        print(f'[錯誤] 找不到設定檔: {json_path}')
        input('\n按 Enter 結束...')
        sys.exit(1)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    api_url = data.get('apiUrl', '').rstrip('/')
    system_prompt = data.get('prompt', '')
    model = data.get('model', 'gpt-4o-mini')
    api_key = data.get('apiKey', 'no-key')
    reasoning_effort = data.get('reasoning_effort', None)
    reasoning_tokens = data.get('reasoning_tokens', None)
    retry_output = [s.strip() for s in data.get('retryOutput', []) if isinstance(s, str) and s.strip()]

    try:
        words_per_op = int(data.get('wordsPerOp', 0) or 0)
    except (TypeError, ValueError):
        words_per_op = 0
    if words_per_op < 0:
        words_per_op = 0

    if not api_url:
        print('[錯誤] SrtClean.json 缺少 apiUrl')
        input('\n按 Enter 結束...')
        sys.exit(1)

    return Config(api_url, system_prompt, model, api_key, reasoning_effort,
                  reasoning_tokens, retry_output, words_per_op)


def call_llm(cfg, text):
    url = cfg.api_url + '/v1/chat/completions'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {cfg.api_key}',
    }
    payload = {
        'model': cfg.model,
        'messages': [
            {'role': 'system', 'content': cfg.system_prompt},
            {'role': 'user', 'content': text},
        ],
        'stream': False,
    }
    if cfg.reasoning_effort is not None:
        payload['reasoning_effort'] = cfg.reasoning_effort
    if cfg.reasoning_tokens is not None:
        payload['reasoning_tokens'] = cfg.reasoning_tokens
    resp = requests.post(url, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    return data['choices'][0]['message']['content'].strip()


def parse_srt(content):
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    blocks = []
    for raw_block in re.split(r'\n{2,}', content.strip()):
        lines = raw_block.strip().split('\n')
        if len(lines) < 3:
            continue
        try:
            index = int(lines[0].strip())
            timestamp = lines[1].strip()
            text = '\n'.join(lines[2:])
            blocks.append({'index': index, 'timestamp': timestamp, 'text': text})
        except ValueError:
            blocks.append({'index': None, 'raw': raw_block})
    return blocks


def rebuild_srt(blocks):
    lines = []
    new_index = 1
    for block in blocks:
        if block.get('index') is not None:
            lines.append(str(new_index))
            lines.append(block['timestamp'])
            lines.append(block['text'])
            lines.append('')
            new_index += 1
        else:
            lines.append(block.get('raw', ''))
            lines.append('')
    return '\n'.join(lines).rstrip('\n') + '\n'


def is_retry_output(text, retry_output):
    return any(text == s for s in retry_output)


def process_srt(file_path, api_url, system_prompt, model, api_key, reasoning_effort, retry_output):
    print(f'處理: {file_path}')

    content = None
    used_encoding = 'utf-8'
    for enc in ('utf-8-sig', 'utf-8', 'cp950', 'big5', 'gbk', 'latin-1'):
        try:
            with open(file_path, 'r', encoding=enc) as f:
                content = f.read()
            used_encoding = enc
            break
        except (UnicodeDecodeError, LookupError):
            continue

    if content is None:
        print('  [錯誤] 無法讀取檔案（不支援的編碼）')
        return

    blocks = parse_srt(content)
    valid_blocks = [b for b in blocks if b.get('index') is not None]
    total = len(valid_blocks)
    print(f'  共 {total} 條字幕，開始處理...')

    done = 0
    for block in blocks:
        if block.get('index') is None:
            continue
        done += 1
        original = block['text'].strip()
        if not original:
            continue
        try:
            cleaned = call_llm(api_url, system_prompt, model, api_key, reasoning_effort, original)
            if retry_output and is_retry_output(cleaned, retry_output):
                print(f'  [{done}/{total}] [重試] LLM 輸出命中 retryOutput，重試一次...')
                retry = call_llm(api_url, system_prompt, model, api_key, reasoning_effort, original)
                if is_retry_output(retry, retry_output):
                    print(f'  [{done}/{total}] [跳過] 重試仍命中 retryOutput，保留原文')
                    continue
                cleaned = retry
            block['text'] = cleaned
            orig_preview = original.replace('\n', ' ')[:50]
            clean_preview = cleaned.replace('\n', ' ')[:50]
            print(f'  [{done}/{total}] \n {orig_preview!r} -> \n {clean_preview!r}')
        except Exception as e:
            print(f'  [{done}/{total}] [錯誤] {e}，保留原文')

    output = rebuild_srt(blocks)
    write_enc = 'utf-8-sig' if used_encoding == 'utf-8-sig' else 'utf-8'
    with open(file_path, 'w', encoding=write_enc, newline='') as f:
        f.write(output)

    print(f'  完成: {file_path}')


def main():
    if len(sys.argv) < 2:
        print('SrtClean — 使用 LLM 修飾 SRT 字幕文本')
        print('用法: 將 .srt 檔案拖曳到此程式上')
        print('      或: SrtClean.exe file1.srt file2.srt ...')
        print()
        print('設定檔格式 (SrtClean.json):')
        print('  {')
        print('    "apiUrl": "http://192.168.1.1:8080",')
        print('    "prompt": "給 LLM 的系統提示詞，用來修飾 srt 文本",')
        print('    "model": "gpt-4o-mini",')
        print('    "apiKey": "your-api-key",')
        print('    "reasoning_effort": "low"')
        print('  }')
        input('\n按 Enter 結束...')
        sys.exit(0)

    api_url, system_prompt, model, api_key, reasoning_effort, retry_output = load_config()
    effort_info = f'  reasoning_effort: {reasoning_effort}' if reasoning_effort else ''
    print(f'API: {api_url}  模型: {model}{effort_info}')
    print()

    srt_files = [f for f in sys.argv[1:] if f.lower().endswith('.srt')]

    if not srt_files:
        print('[錯誤] 未提供任何 .srt 檔案')
        input('\n按 Enter 結束...')
        sys.exit(1)

    for file_path in srt_files:
        if not os.path.exists(file_path):
            print(f'[錯誤] 找不到檔案: {file_path}')
            continue
        process_srt(file_path, api_url, system_prompt, model, api_key, reasoning_effort, retry_output)
        print()

    input('全部完成。按 Enter 結束...')


if __name__ == '__main__':
    main()
