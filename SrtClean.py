import sys
import json
import os
import re
from collections import namedtuple

import requests


Config = namedtuple('Config', [
    'api_url', 'system_prompt', 'model', 'api_key',
    'reasoning_effort', 'reasoning_tokens', 'retry_output', 'words_per_op',
])

# 一個「字」：連續的拉丁字母/數字算一個字，CJK 或其他非空白字元各算一個 token
LATIN = r"[A-Za-zÀ-ɏ0-9]+(?:['’-][A-Za-zÀ-ɏ0-9]+)*"
TOKEN_RE = re.compile(LATIN + r"|\S")


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


def split_by_words(text, words_per_op):
    """將 text 拆成每組最多 words_per_op 個字。

    每組都是 text 的原始切片，''.join(結果) == text，
    組合回去時不會遺失任何空白或換行。
    標點會留在前一組，不會被切成下一組的開頭。
    """
    if words_per_op <= 0:
        return [text]

    tokens = list(TOKEN_RE.finditer(text))
    if not tokens:
        return [text]

    starts = [0]
    count = 0
    for i, token in enumerate(tokens):
        if token.group()[0].isalnum():
            count += 1
        if count < words_per_op or i + 1 >= len(tokens):
            continue
        # 標點留在本組，遇到下一個「字」才切開
        if tokens[i + 1].group()[0].isalnum():
            starts.append(tokens[i + 1].start())
            count = 0

    bounds = starts + [len(text)]
    return [text[bounds[i]:bounds[i + 1]] for i in range(len(bounds) - 1)]


def clean_once(cfg, text, label):
    """呼叫 LLM 修飾 text。命中 retryOutput 會重試一次，仍命中則回傳 None（保留原文）。"""
    cleaned = call_llm(cfg, text)
    if cfg.retry_output and is_retry_output(cleaned, cfg.retry_output):
        print(f'{label} [重試] LLM 輸出命中 retryOutput，重試一次...')
        cleaned = call_llm(cfg, text)
        if is_retry_output(cleaned, cfg.retry_output):
            print(f'{label} [跳過] 重試仍命中 retryOutput，保留原文')
            return None
    return cleaned


def clean_text(cfg, text, label):
    """依 wordsPerOp 拆成 N 個字一組，一次處理一組，處理完再組合。

    回傳 (組合後的文字, 失敗的組數)。失敗的組保留原文。
    """
    chunks = split_by_words(text, cfg.words_per_op)
    parts = []
    failed = 0

    for i, chunk in enumerate(chunks, 1):
        core = chunk.strip()
        if not core:
            parts.append(chunk)
            continue

        lead = chunk[:len(chunk) - len(chunk.lstrip())]
        trail = chunk[len(chunk.rstrip()):]
        chunk_label = label if len(chunks) == 1 else f'{label} ({i}/{len(chunks)})'

        try:
            cleaned = clean_once(cfg, core, chunk_label)
        except Exception as e:
            print(f'{chunk_label} [錯誤] {e}，保留原文')
            cleaned = None

        if cleaned is None:
            failed += 1
            cleaned = core
        parts.append(lead + cleaned + trail)

    result = ''.join(parts)
    if len(chunks) > 1:
        # 某一組被整段清掉時，避免留下多餘空白
        result = re.sub(r'[ \t]{2,}', ' ', result)
        result = '\n'.join(line.strip() for line in result.split('\n')).strip()

    return result, failed


def process_srt(file_path, cfg):
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

        label = f'  [{done}/{total}]'
        cleaned, failed = clean_text(cfg, original, label)
        if failed and cleaned == original:
            continue

        block['text'] = cleaned
        orig_preview = original.replace('\n', ' ')[:50]
        clean_preview = cleaned.replace('\n', ' ')[:50]
        print(f'{label} \n {orig_preview!r} -> \n {clean_preview!r}')

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
        print('    "reasoning_effort": "low",')
        print('    "retryOutput": ["很抱歉，我無法協助處理這個要求。"],')
        print('    "wordsPerOp": 20')
        print('  }')
        print()
        print('  wordsPerOp: 每則字幕拆成 N 個字一組分次處理，0 或省略表示整則一次處理')
        input('\n按 Enter 結束...')
        sys.exit(0)

    cfg = load_config()
    info = f'API: {cfg.api_url}  模型: {cfg.model}'
    if cfg.reasoning_effort:
        info += f'  reasoning_effort: {cfg.reasoning_effort}'
    if cfg.reasoning_tokens:
        info += f'  reasoning_tokens: {cfg.reasoning_tokens}'
    if cfg.words_per_op:
        info += f'  wordsPerOp: {cfg.words_per_op}'
    print(info)
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
        process_srt(file_path, cfg)
        print()

    input('全部完成。按 Enter 結束...')


if __name__ == '__main__':
    main()
