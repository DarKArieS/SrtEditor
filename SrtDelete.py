import sys
import json
import os
import re


def get_exe_dir():
    """取得執行檔所在資料夾"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def load_config():
    """從 SrtDelete.json 讀取刪除清單"""
    json_path = os.path.join(get_exe_dir(), 'SrtDelete.json')
    if not os.path.exists(json_path):
        print(f'[錯誤] 找不到設定檔: {json_path}')
        input('\n按 Enter 結束...')
        sys.exit(1)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if not isinstance(data, dict):
        print('[錯誤] SrtDelete.json 格式錯誤，須為 JSON 物件')
        input('\n按 Enter 結束...')
        sys.exit(1)

    raw_targets = data.get('deleteTarget', [])
    if not isinstance(raw_targets, list):
        print('[錯誤] deleteTarget 必須是陣列')
        input('\n按 Enter 結束...')
        sys.exit(1)
    patterns = [p.strip() for p in raw_targets if isinstance(p, str) and p.strip()]

    raw_regex = data.get('deleteTargetRegex', [])
    if not isinstance(raw_regex, list):
        print('[錯誤] deleteTargetRegex 必須是陣列')
        input('\n按 Enter 結束...')
        sys.exit(1)
    compiled = []
    for p in raw_regex:
        if not isinstance(p, str) or not p.strip():
            continue
        try:
            compiled.append(re.compile(p.strip()))
        except re.error as e:
            print(f'[警告] 無效的正規表達式，略過: {p!r}  ({e})')

    return patterns, compiled


def parse_srt(content):
    """將 SRT 內容解析為字幕區塊清單"""
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
            blocks.append({
                'index': index,
                'timestamp': timestamp,
                'text': text,
            })
        except ValueError:
            blocks.append({'index': None, 'raw': raw_block})

    return blocks


def parse_timestamp(ts_str):
    """將 SRT 時間字串 HH:MM:SS,mmm 轉為毫秒"""
    m = re.match(r'(\d+):(\d{2}):(\d{2}),(\d{3})', ts_str.strip())
    if not m:
        return None
    h, mn, s, ms = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4))
    return h * 3600000 + mn * 60000 + s * 1000 + ms


def format_timestamp(total_ms):
    """將毫秒轉回 SRT 時間字串 HH:MM:SS,mmm"""
    h = total_ms // 3600000
    total_ms %= 3600000
    mn = total_ms // 60000
    total_ms %= 60000
    s = total_ms // 1000
    ms = total_ms % 1000
    return f'{h:02d}:{mn:02d}:{s:02d},{ms:03d}'


def fix_overlaps(blocks):
    """若當前字幕結束時間 > 下一字幕開始時間，將結束時間縮短至下一字幕的開始時間"""
    valid = [b for b in blocks if b.get('index') is not None]
    fixed = 0
    for i in range(len(valid) - 1):
        cur_parts = valid[i]['timestamp'].split('-->')
        next_parts = valid[i + 1]['timestamp'].split('-->')
        if len(cur_parts) != 2 or len(next_parts) != 2:
            continue
        cur_end_ms = parse_timestamp(cur_parts[1])
        next_start_ms = parse_timestamp(next_parts[0])
        if cur_end_ms is None or next_start_ms is None:
            continue
        if cur_end_ms > next_start_ms:
            new_end = format_timestamp(next_start_ms)
            old_ts = valid[i]['timestamp']
            valid[i]['timestamp'] = cur_parts[0].rstrip() + ' --> ' + new_end
            print(f'  修正重疊: [{old_ts}] -> [{valid[i]["timestamp"]}]')
            fixed += 1
    return fixed


def should_delete(block, patterns, compiled):
    """判斷字幕區塊是否符合刪除條件"""
    if block.get('index') is None:
        return False
    text = block['text'].strip()
    return any(p == text for p in patterns) or any(rx.search(text) for rx in compiled)


def rebuild_srt(blocks):
    """將字幕區塊重新編號並組合成 SRT 字串"""
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


def process_srt(file_path, patterns, compiled):
    """處理單一 SRT 檔案"""
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
    total = sum(1 for b in blocks if b.get('index') is not None)

    kept = []
    deleted = 0
    for block in blocks:
        if should_delete(block, patterns, compiled):
            deleted += 1
            preview = block['text'].replace('\n', ' ')[:60]
            print(f'  刪除: [{block["timestamp"]}] {preview}')
        else:
            kept.append(block)

    overlap_fixed = fix_overlaps(kept)
    output = rebuild_srt(kept)

    write_enc = 'utf-8-sig' if used_encoding == 'utf-8-sig' else 'utf-8'
    with open(file_path, 'w', encoding=write_enc, newline='') as f:
        f.write(output)

    overlap_msg = f'，修正重疊 {overlap_fixed} 條' if overlap_fixed else ''
    print(f'  完成: 共 {total} 條，刪除 {deleted} 條，保留 {total - deleted} 條{overlap_msg}')


def main():
    if len(sys.argv) < 2:
        print('SrtDelete — 批次刪除 SRT 字幕條目')
        print('用法: 將 .srt 檔案拖曳到此程式上')
        print('      或: SrtDelete.exe file1.srt file2.srt ...')
        print()
        print('設定檔格式 (SrtDelete.json):')
        print('  {')
        print('    "setting": { "enableReg": false },')
        print('    "deleteTarget": ["要刪除的文字", "^正規表達式$"]')
        print('  }')
        input('\n按 Enter 結束...')
        sys.exit(0)

    patterns, compiled = load_config()

    if not patterns and not compiled:
        print('[警告] deleteTarget 與 deleteTargetRegex 中沒有任何刪除條目')
        input('\n按 Enter 結束...')
        sys.exit(0)

    print(f'已載入 {len(patterns)} 個精確比對、{len(compiled)} 個正規表達式條目')
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
        process_srt(file_path, patterns, compiled)
        print()

    input('全部完成。按 Enter 結束...')


if __name__ == '__main__':
    main()
