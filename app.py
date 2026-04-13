from flask import Flask, render_template, request, jsonify
import json, os, re, subprocess, tempfile, tkinter as tk
from tkinter import filedialog

app = Flask(__name__)
APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(APP_DIR, 'settings.json')
TD_MODULE_NAME = 'remap_lalapad_tdq'
TD_MODULE_TEMPLATE_DIR = os.path.join(APP_DIR, 'module_templates', TD_MODULE_NAME)
TD_MODULE_REQUIRED_SETTINGS = {
    'dts_root': TD_MODULE_NAME,
}
TD_MODULE_REQUIRED_BUILD = {
    'cmake': TD_MODULE_NAME,
    'kconfig': f'{TD_MODULE_NAME}/Kconfig',
}


class TDModuleConflict(RuntimeError):
    """Raised when TD module auto-install would overwrite user-managed files."""
    pass

# ---- WSL UNC パス書き込みヘルパー ----
def _wsl_unc_to_native(path_str):
    """\\\\wsl$\\Ubuntu\\home\\... -> /home/..."""
    # \\wsl$ or \\wsl.localhost で始まる UNC パスを WSL ネイティブパスに変換
    s = path_str.replace('/', '\\')
    if not (s.startswith('\\\\') and s[2:5].lower() == 'wsl'):
        return None
    # 3つ目の \ 以降がディストリ名、4つ目の \ 以降がパス
    parts = s.lstrip('\\').split('\\', 2)  # ['wsl$', 'Ubuntu', 'home\\user\\...']
    if len(parts) < 3:
        return None
    return '/' + parts[2].replace('\\', '/')


def ensure_directory(path):
    """Create a directory locally or through WSL for UNC targets."""
    path_str = str(path or '')
    if not path_str:
        return
    wsl_native = _wsl_unc_to_native(path_str)
    if wsl_native:
        result = subprocess.run(
            ['wsl', '-u', 'root', '-e', 'mkdir', '-p', wsl_native],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            raise IOError(f'wsl mkdir failed: {result.stderr.strip()}')
        return
    os.makedirs(path_str, exist_ok=True)

def write_text_file(path, content, encoding='utf-8'):
    """
    テキストファイルを書き込む。wsl$ UNC パスは
    Windows から直接 open('w') すると PermissionError になる場合があるため、
    一時ファイル経由で wsl.exe cp を使って書き込む。
    """
    path_str = str(path)
    ensure_directory(os.path.dirname(path_str))
    wsl_native = _wsl_unc_to_native(path_str)
    if wsl_native:
        # WSL UNC パス: Windows の TEMP に書いて wsl cp で転送
        with tempfile.NamedTemporaryFile('w', encoding=encoding, newline='\n',
                                         suffix='.keytmp', delete=False) as tf:
            tf.write(content)
            tmp_win = tf.name
        # C:\foo\bar.tmp → /mnt/c/foo/bar.tmp
        drive = tmp_win[0].lower()
        rest = tmp_win[2:].replace('\\', '/')
        tmp_wsl = f'/mnt/{drive}{rest}'
        try:
            result = subprocess.run(
                ['wsl', '-u', 'root', '-e', 'cp', tmp_wsl, wsl_native],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                raise IOError(f'wsl cp failed: {result.stderr.strip()}')
        finally:
            try:
                os.unlink(tmp_win)
            except OSError:
                pass
    else:
        with open(path_str, 'w', encoding=encoding, newline='\n') as f:
            f.write(content)

TD_COUNT = 32
_TD_EMPTY = {
    'single_tap': '',
    'single_hold': '',
    'double_tap': '',
    'tapping_term': 200,
    'display_name': '',
}
TD_MACRO_CONTROL_BEHAVIORS = {
    'macro_tap', 'macro_press', 'macro_release', 'macro_pause_for_release',
    'macro_wait_time', 'macro_tap_time',
    'macro_param_1to1', 'macro_param_1to2', 'macro_param_2to1', 'macro_param_2to2',
}
TD_MANAGED_BEGIN = '/* REMAP_LALAPAD_TD_BEGIN */'
TD_MANAGED_END = '/* REMAP_LALAPAD_TD_END */'
TD_HELPER_LABEL_RE = re.compile(
    r'^td\d+(?:(?:s|st|sh|dt|dh)|_(?:single|double|single_tap|single_hold|double_tap|double_hold))$'
)
TD_PUBLIC_LABEL_RE = re.compile(r'^td\d+$')

MACRO_COUNT = 16
MACRO_MANAGED_BEGIN = '/* REMAP_LALAPAD_MACRO_BEGIN */'
MACRO_MANAGED_END   = '/* REMAP_LALAPAD_MACRO_END */'
MACRO_LABEL_RE = re.compile(r'^mc\d+$')
MACRO_LABELS = {f'mc{i}' for i in range(MACRO_COUNT)}
MACRO_PAIR_ID_RE = re.compile(r'^[A-Za-z0-9_-]{1,64}$')

# US配列 文字 → ZMK keycode
_US_CHAR_MAP = {
    ' ': 'SPACE', '\t': 'TAB', '\n': 'ENTER', '\r': 'ENTER',
    '0': 'N0', '1': 'N1', '2': 'N2', '3': 'N3', '4': 'N4',
    '5': 'N5', '6': 'N6', '7': 'N7', '8': 'N8', '9': 'N9',
    '-': 'MINUS', '=': 'EQUAL', '[': 'LEFT_BRACKET', ']': 'RIGHT_BRACKET',
    '\\': 'BACKSLASH', ';': 'SEMI', "'": 'SQT', ',': 'COMMA', '.': 'PERIOD', '/': 'SLASH',
    '`': 'GRAVE',
    '!': 'LS(N1)', '@': 'LS(N2)', '#': 'LS(N3)', '$': 'LS(N4)', '%': 'LS(N5)',
    '^': 'LS(N6)', '&': 'LS(N7)', '*': 'LS(N8)', '(': 'LS(N9)', ')': 'LS(N0)',
    '_': 'LS(MINUS)', '+': 'LS(EQUAL)', '{': 'LS(LEFT_BRACKET)', '}': 'LS(RIGHT_BRACKET)',
    '|': 'LS(BACKSLASH)', ':': 'LS(SEMI)', '"': 'LS(SQT)', '<': 'LS(COMMA)',
    '>': 'LS(PERIOD)', '?': 'LS(SLASH)', '~': 'LS(GRAVE)',
    **{c: c.upper() for c in 'abcdefghijklmnopqrstuvwxyz'},
    **{c: f'LS({c})' for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'},
}


def make_default_settings():
    return {
        'firmware_folder': '',
        'keymap_path': '',
        'main_conf_path': '',
        'left_conf_path': '',
        'right_conf_path': '',
        'td_definitions': [dict(_TD_EMPTY) for _ in range(TD_COUNT)],
        'macro_definitions': make_default_macro_definitions(),
        'per_folder_macros': {},
    }

# Standard ZMK built-in behaviors (won't appear in custom palette)
BUILTIN_BEHAVIORS = {
    'kp', 'mt', 'mo', 'to', 'tog', 'lt', 'mkp', 'bt', 'out',
    'sys_reset', 'bootloader', 'trans', 'none',
    'sk', 'sl', 'caps_word', 'nkro', 'gresc', 'rgb_ug', 'ext_power',
    'key_repeat', 'soft_off', 'studio_unlock',
}
CUSTOM_DEFINITION_EXCLUDE = BUILTIN_BEHAVIORS | {'mt2', 'zip_dyn_scale', 'zip_dyn_scale_set'} | MACRO_LABELS
CUSTOM_USAGE_EXCLUDE = BUILTIN_BEHAVIORS | {'zip_dyn_scale', 'zip_dyn_scale_set'} | MACRO_LABELS


# ──────────────────────────────────────────────
# Settings
# ──────────────────────────────────────────────

def normalize_td_binding(raw):
    raw = ' '.join(str(raw or '').strip().split())
    if not raw:
        return ''
    normalized = raw if raw.startswith('&') else '&' + raw
    return repair_quantum_modified_binding(normalized)


def repair_quantum_modified_binding(raw):
    raw = ' '.join(str(raw or '').strip().split())
    if not raw.startswith('&kp '):
        return raw
    body = raw[4:]
    open_count = body.count('(')
    close_count = body.count(')')
    if open_count > close_count:
        body += ')' * (open_count - close_count)
    return '&kp ' + body


def normalize_legacy_mt_value(raw):
    raw = ' '.join(str(raw or '').strip().split())
    if not raw:
        return ''
    if raw.startswith('&'):
        return raw
    return f'&kp {raw}'


def normalize_td_definition(item):
    item = item or {}
    if any(k in item for k in ('single_tap', 'single_hold', 'double_tap', 'double_hold')):
        result = {
            'single_tap': normalize_td_binding(item.get('single_tap', '')),
            'single_hold': normalize_td_binding(item.get('single_hold', '')),
            'double_tap': normalize_td_binding(item.get('double_tap', '')),
            'tapping_term': int(item.get('tapping_term', 200) or 200),
        }
    else:
        result = {
            'single_tap': normalize_td_binding(normalize_legacy_mt_value(item.get('tap', ''))),
            'single_hold': normalize_td_binding(normalize_legacy_mt_value(item.get('hold', ''))),
            'double_tap': '',
            'tapping_term': int(item.get('tapping_term', 200) or 200),
        }
    result['tapping_term'] = max(50, min(1000, result['tapping_term']))
    result['display_name'] = str(item.get('display_name', '') or '').strip()
    return result


def normalize_td_definitions(items):
    defs = [normalize_td_definition(item) for item in (items or [])[:TD_COUNT]]
    while len(defs) < TD_COUNT:
        defs.append(dict(_TD_EMPTY))
    return defs


def td_definitions_require_module(items):
    for td in normalize_td_definitions(items):
        if td.get('single_tap') or td.get('single_hold') or td.get('double_tap'):
            return True
    return False


def _normalize_text_for_compare(content):
    return str(content).replace('\r\n', '\n').replace('\r', '\n').rstrip('\n')


def _read_text_file(path, encoding='utf-8'):
    with open(path, 'r', encoding=encoding) as f:
        return f.read()


def _td_module_conflict(target_path, detail):
    target = norm(target_path) if target_path else '(unknown path)'
    return TDModuleConflict(
        f'TD モジュール自動導入を中止しました。保護対象: {target}。{detail}'
    )


def _iter_td_module_template_files():
    for dirpath, _, filenames in os.walk(TD_MODULE_TEMPLATE_DIR):
        rel_dir = os.path.relpath(dirpath, TD_MODULE_TEMPLATE_DIR)
        for filename in sorted(filenames):
            src = os.path.join(dirpath, filename)
            rel = filename if rel_dir == '.' else os.path.join(rel_dir, filename)
            yield src, rel


def _parse_simple_yaml_mapping_line(line, path_hint, lineno):
    match = re.match(r'^([A-Za-z0-9_-]+)\s*:\s*(.*?)\s*$', line)
    if not match:
        raise _td_module_conflict(path_hint, f'line {lineno} の形式を解釈できません。')
    key = match.group(1)
    value = match.group(2)
    if value == '':
        raise _td_module_conflict(path_hint, f'line {lineno} の値が空です。')
    return key, value


def _parse_module_yml(content, path_hint):
    data = {
        'top': {},
        'build': {},
        'settings': {},
    }
    in_build = False
    in_settings = False
    for lineno, raw_line in enumerate(str(content).replace('\r\n', '\n').replace('\r', '\n').split('\n'), start=1):
        stripped = raw_line.strip()
        if not stripped or stripped.startswith('#'):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(' '))
        if indent == 0:
            in_settings = False
            if stripped == 'build:':
                in_build = True
                continue
            key, value = _parse_simple_yaml_mapping_line(stripped, path_hint, lineno)
            data['top'][key] = value
            in_build = False
            continue
        if not in_build:
            raise _td_module_conflict(path_hint, f'line {lineno} は build: の外にネストされています。')
        if indent == 2:
            if stripped == 'settings:':
                in_settings = True
                continue
            key, value = _parse_simple_yaml_mapping_line(stripped, path_hint, lineno)
            data['build'][key] = value
            in_settings = False
            continue
        if indent == 4 and in_settings:
            key, value = _parse_simple_yaml_mapping_line(stripped, path_hint, lineno)
            data['settings'][key] = value
            continue
        raise _td_module_conflict(path_hint, f'line {lineno} のインデント構造は未対応です。')
    return data


def _render_module_yml(data):
    lines = []
    for key, value in data.get('top', {}).items():
        lines.append(f'{key}: {value}')
    lines.append('build:')
    settings = data.get('settings', {})
    if settings:
        lines.append('  settings:')
        for key, value in settings.items():
            lines.append(f'    {key}: {value}')
    for key, value in data.get('build', {}).items():
        lines.append(f'  {key}: {value}')
    return '\n'.join(lines).rstrip() + '\n'


def _merge_td_module_yml(existing_text, path_hint, include_board_root=False):
    if existing_text is None:
        data = {
            'top': {},
            'build': {},
            'settings': {},
        }
        if include_board_root:
            data['settings']['board_root'] = '.'
    else:
        data = _parse_module_yml(existing_text, path_hint)

    changed = False
    settings = data['settings']
    build = data['build']

    for key, expected in TD_MODULE_REQUIRED_SETTINGS.items():
        current = settings.get(key)
        if current is None:
            settings[key] = expected
            changed = True
        elif current != expected:
            raise _td_module_conflict(path_hint, f'{key}: {current} が既に設定されているため自動追記できません。')

    for key, expected in TD_MODULE_REQUIRED_BUILD.items():
        current = build.get(key)
        if current is None:
            build[key] = expected
            changed = True
        elif current != expected:
            raise _td_module_conflict(path_hint, f'{key}: {current} が既に設定されているため自動追記できません。')

    if existing_text is not None and not changed:
        return existing_text, False
    return _render_module_yml(data), True


def plan_td_module_install(firmware_folder):
    firmware_root = norm(firmware_folder)
    if not firmware_root:
        raise _td_module_conflict('firmware_folder', 'ファームウェアフォルダが未設定です。')
    config_dir = os.path.join(firmware_root, 'config')
    boards_dir = os.path.join(firmware_root, 'boards')
    if not os.path.isdir(config_dir):
        raise _td_module_conflict(config_dir, '標準レイアウトの config/ が見つかりません。')
    if not os.path.isdir(boards_dir):
        raise _td_module_conflict(boards_dir, '標準レイアウトの boards/ が見つかりません。')

    writes = []
    module_root = os.path.join(firmware_root, TD_MODULE_NAME)
    for src, rel in _iter_td_module_template_files():
        dest = os.path.join(module_root, rel)
        template_text = _read_text_file(src)
        if os.path.exists(dest):
            current_text = _read_text_file(dest)
            if _normalize_text_for_compare(current_text) != _normalize_text_for_compare(template_text):
                raise _td_module_conflict(dest, '既存ファイルの内容がテンプレートと異なるため上書きしません。')
            continue
        writes.append((dest, template_text))

    module_yml_path = os.path.join(firmware_root, 'zephyr', 'module.yml')
    if os.path.exists(module_yml_path):
        module_yml_text = _read_text_file(module_yml_path)
        merged_text, changed = _merge_td_module_yml(module_yml_text, module_yml_path)
    else:
        merged_text, changed = _merge_td_module_yml(None, module_yml_path, include_board_root=True)
    if changed:
        writes.append((module_yml_path, merged_text))

    return {
        'status': 'installed' if writes else 'already_present',
        'writes': writes,
    }


def apply_td_module_install(plan):
    for path, content in plan.get('writes', []):
        write_text_file(path, content)


def normalize_macro_step(step):
    step = step or {}
    t = step.get('type', '')
    pair_id = str(step.get('pair_id', '') or '').strip()
    if not MACRO_PAIR_ID_RE.match(pair_id):
        pair_id = ''
    if t in ('tap', 'press', 'release'):
        key = repair_quantum_modified_binding(str(step.get('key', '')).strip())
        if not key:
            return None
        result = {'type': t, 'key': key}
        if pair_id and t in ('press', 'release'):
            result['pair_id'] = pair_id
        return result
    if t == 'wait':
        ms = max(1, min(30000, int(step.get('ms') or step.get('wait_ms') or 50)))
        return {'type': 'wait', 'ms': ms}
    if t == 'tap_time':
        ms = max(1, min(1000, int(step.get('ms') or step.get('tap_time_ms') or 10)))
        return {'type': 'tap_time', 'ms': ms}
    if t == 'pause_for_release':
        return {'type': 'pause_for_release'}
    if t == 'text':
        text = str(step.get('text', ''))
        return {'type': 'text', 'text': text} if text else None
    return None


def normalize_macro_definition(item, slot=0):
    item = item or {}
    label = str(item.get('label', f'mc{slot}')).strip() or f'mc{slot}'
    steps = [normalize_macro_step(s) for s in (item.get('steps') or [])]
    return {
        'label': label,
        'display_name': str(item.get('display_name', '')).strip(),
        'steps': [s for s in steps if s],
    }


def normalize_macro_definitions(items):
    result = []
    items = list(items or [])
    for i in range(MACRO_COUNT):
        d = normalize_macro_definition(items[i] if i < len(items) else {}, i)
        if not d['label']:
            d['label'] = f'mc{i}'
        result.append(d)
    return result


def make_default_macro_definitions():
    return [{'label': f'mc{i}', 'display_name': '', 'steps': []} for i in range(MACRO_COUNT)]


def normalize_per_folder_macros(items):
    result = {}
    if not isinstance(items, dict):
        return result
    for raw_path, macro_defs in items.items():
        path = norm(str(raw_path or '').strip())
        if not path:
            continue
        result[path] = normalize_macro_definitions(macro_defs)
    return result


def normalize_settings(settings):
    raw = settings or {}
    normalized = {**make_default_settings(), **raw}
    td_defs = raw.get('td_definitions')
    if td_defs is None and raw.get('mt_definitions') is not None:
        td_defs = raw.get('mt_definitions')
    if td_defs is None:
        td_defs = normalized.get('td_definitions')
    normalized['td_definitions'] = normalize_td_definitions(td_defs)
    normalized.pop('mt_definitions', None)
    normalized['macro_definitions'] = normalize_macro_definitions(raw.get('macro_definitions'))
    normalized['per_folder_macros'] = normalize_per_folder_macros(raw.get('per_folder_macros'))
    return normalized


def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            return normalize_settings(json.load(f))
    return normalize_settings({})


def save_settings_file(s):
    s = normalize_settings(s)
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(s, f, indent=2, ensure_ascii=False)


def norm(path):
    """Normalize path separators for the current OS."""
    return os.path.normpath(path) if path else ''


# ──────────────────────────────────────────────
# File discovery
# ──────────────────────────────────────────────

def discover_files(folder):
    """Given a firmware root folder, find all relevant config files.
    Returns a dict with keymap_path, main_conf_path, left/right_conf_path,
    and keyboard_name. Unknown paths are empty strings."""
    folder = norm(folder)
    result = {
        'firmware_folder': folder,
        'keymap_path': '',
        'main_conf_path': '',
        'left_conf_path': '',
        'right_conf_path': '',
        'keyboard_name': '',
    }

    config_dir = os.path.join(folder, 'config')
    if not os.path.isdir(config_dir):
        return result

    # Find the first .keymap file inside config/
    for fname in sorted(os.listdir(config_dir)):
        if fname.endswith('.keymap'):
            kb = fname[:-7]  # e.g. "lalapadgen2"
            result['keyboard_name'] = kb
            result['keymap_path'] = os.path.join(config_dir, fname)
            result['main_conf_path'] = os.path.join(config_dir, f'{kb}.conf')
            shields = os.path.join(config_dir, 'boards', 'shields', kb)
            result['left_conf_path']  = os.path.join(shields, f'{kb}_left.conf')
            result['right_conf_path'] = os.path.join(shields, f'{kb}_right.conf')
            break

    return result


# ──────────────────────────────────────────────
# Keymap parsing
# ──────────────────────────────────────────────

def parse_bindings(text):
    """Split a bindings block text into list of {raw} dicts."""
    text = re.sub(r'//[^\n]*', ' ', text)
    text = ' '.join(text.split())
    return [{'raw': '&' + p.strip()} for p in text.split('&') if p.strip()]


def extract_layers(content):
    """Return list of layer dicts from keymap content."""
    layers = []
    pat = re.compile(
        r'(\w+)\s*\{[^{}]*display-name\s*=\s*"([^"]*)"[^{}]*bindings\s*=\s*<([^>]*)>',
        re.DOTALL
    )
    for m in pat.finditer(content):
        layers.append({
            'name': m.group(1),
            'display_name': m.group(2),
            'bindings': parse_bindings(m.group(3)),
        })
    return layers


def extract_custom_bindings(content):
    """Collect unique custom bindings from local definitions and non-built-in usages."""
    seen = set()

    for block_name in ('behaviors', 'macros'):
        span = find_block_span(content, block_name)
        if not span:
            continue
        _, _, body_start, body_end = span
        body = content[body_start:body_end]
        for match in re.finditer(r'^\s*(\w+)\s*:', body, re.MULTILINE):
            label = match.group(1)
            if (
                label in TD_MACRO_CONTROL_BEHAVIORS
                or TD_HELPER_LABEL_RE.match(label)
                or TD_PUBLIC_LABEL_RE.match(label)
                or label in CUSTOM_DEFINITION_EXCLUDE
            ):
                continue
            seen.add('&' + label)

    pat = re.compile(r'bindings\s*=\s*<([^>]*)>', re.DOTALL)
    for block in pat.finditer(content):
        text = re.sub(r'//[^\n]*', ' ', block.group(1))
        text = ' '.join(text.split())
        for part in text.split('&'):
            part = part.strip()
            if not part:
                continue
            tokens = part.split()
            beh = tokens[0]
            if (
                beh in CUSTOM_USAGE_EXCLUDE
                or beh in TD_MACRO_CONTROL_BEHAVIORS
                or TD_HELPER_LABEL_RE.match(beh)
                or TD_PUBLIC_LABEL_RE.match(beh)
            ):
                continue
            # Normalize: keep behavior + first arg by default, but preserve both
            # hold/tap args for mt2 so the custom palette can render its label.
            if beh == 'mt2' and len(tokens) > 2:
                key = '&' + ' '.join(tokens[:3])
            else:
                key = ('&' + ' '.join(tokens[:2])) if len(tokens) > 1 else '&' + beh
            seen.add(key)
    return sorted(seen)


def extract_defines(content):
    """Extract #define NAME VALUE pairs (layer names, etc.)."""
    defines = {}
    for m in re.finditer(r'#define\s+(\w+)\s+(\S+)', content):
        defines[m.group(1)] = m.group(2)
    return defines


def find_block_span(content, block_name):
    """Return (block_start, block_end, body_start, body_end) for `name { ... };`."""
    m = re.search(rf'(^[ \t]*{re.escape(block_name)}\s*\{{)', content, re.MULTILINE)
    if not m:
        return None
    brace_start = content.find('{', m.start())
    depth = 0
    end_brace = -1
    for i in range(brace_start, len(content)):
        ch = content[i]
        if ch == '{':
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0:
                end_brace = i
                break
    if end_brace == -1:
        return None
    block_end = end_brace + 1
    while block_end < len(content) and content[block_end] in ' \t':
        block_end += 1
    if block_end < len(content) and content[block_end] == ';':
        block_end += 1
    return m.start(), block_end, brace_start + 1, end_brace


def extract_combos(content):
    """Extract combo definitions from the keymap."""
    span = find_block_span(content, 'combos')
    if not span:
        return []
    _, _, body_start, body_end = span
    body = content[body_start:body_end]
    result = []
    combo_pat = re.compile(r'(\w+)\s*\{(.*?)\n\s*\};', re.DOTALL)
    for m in combo_pat.finditer(body):
        name = m.group(1)
        combo_body = m.group(2)
        binding_match = re.search(r'bindings\s*=\s*<([^>]*)>', combo_body, re.DOTALL)
        positions_match = re.search(r'key-positions\s*=\s*<([^>]*)>', combo_body, re.DOTALL)
        layers_match = re.search(r'layers\s*=\s*<([^>]*)>', combo_body, re.DOTALL)
        timeout_match = re.search(r'timeout-ms\s*=\s*<([^>]*)>', combo_body, re.DOTALL)
        binding_raw = ' '.join((binding_match.group(1) if binding_match else '').split())
        if binding_raw and not binding_raw.startswith('&'):
            binding_raw = '&' + binding_raw
        result.append({
            'name': name,
            'binding': binding_raw or '&none',
            'key_positions': ' '.join((positions_match.group(1) if positions_match else '').split()),
            'layers': ' '.join((layers_match.group(1) if layers_match else '').split()),
            'timeout_ms': (timeout_match.group(1).strip() if timeout_match else ''),
        })
    return result


def extract_conditional_layers(content):
    """Extract conditional layer definitions from the keymap."""
    span = find_block_span(content, 'conditional_layers')
    if not span:
        return []
    _, _, body_start, body_end = span
    body = content[body_start:body_end]
    result = []
    cond_pat = re.compile(r'(\w+)\s*\{(.*?)\n\s*\};', re.DOTALL)
    for m in cond_pat.finditer(body):
        name = m.group(1)
        cond_body = m.group(2)
        if_layers_match = re.search(r'if-layers\s*=\s*<([^>]*)>', cond_body, re.DOTALL)
        then_layer_match = re.search(r'then-layer\s*=\s*<([^>]*)>', cond_body, re.DOTALL)
        result.append({
            'name': name,
            'if_layers': ' '.join((if_layers_match.group(1) if if_layers_match else '').split()),
            'then_layer': (then_layer_match.group(1).strip() if then_layer_match else ''),
        })
    return result


def _extract_property_value(node_body, prop_name):
    match = re.search(rf'{re.escape(prop_name)}\s*=\s*(.*?);', node_body, re.DOTALL)
    return match.group(1) if match else ''


def parse_phandle_array_entries(raw_value):
    entries = []
    text = re.sub(r'//[^\n]*', ' ', raw_value or '')
    for chunk in re.findall(r'<([^>]*)>', text, re.DOTALL):
        normalized = normalize_td_binding(' '.join(chunk.split()))
        if normalized:
            entries.append(normalized)
    return entries


def normalize_td_node_binding(raw):
    normalized = normalize_td_binding(raw)
    if normalized in ('&trans', '&none'):
        return ''
    return normalized


def extract_td_definitions(content):
    defs = [dict(_TD_EMPTY) for _ in range(TD_COUNT)]
    span = find_block_span(content, 'behaviors')
    if not span:
        return defs

    _, _, body_start, body_end = span
    body = content[body_start:body_end]
    node_pat = re.compile(r'^\s*(td\d+(?:s)?)\s*:\s*\w+\s*\{(.*?)^\s*\};', re.MULTILINE | re.DOTALL)
    nodes = {match.group(1): match.group(2) for match in node_pat.finditer(body)}
    helper_bindings = {}

    for label, node_body in nodes.items():
        compatible_match = re.search(r'compatible\s*=\s*"([^"]+)"', node_body)
        compatible = compatible_match.group(1) if compatible_match else ''
        if compatible != 'zmk,behavior-hold-tap':
            continue
        helper_entries = parse_phandle_array_entries(_extract_property_value(node_body, 'bindings'))
        if len(helper_entries) >= 2:
            helper_bindings[label] = helper_entries[:2]

    for slot in range(TD_COUNT):
        label = f'td{slot}'
        node_body = nodes.get(label)
        if not node_body:
            continue

        compatible_match = re.search(r'compatible\s*=\s*"([^"]+)"', node_body)
        compatible = compatible_match.group(1) if compatible_match else ''
        bindings = parse_phandle_array_entries(_extract_property_value(node_body, 'bindings'))
        term_match = re.search(r'tapping-term-ms\s*=\s*<([^>]*)>', node_body)
        term = int(term_match.group(1).strip()) if term_match else 200

        if compatible in ('zmk,behavior-tap-dance-triple', 'zmk,behavior-tap-dance-quad'):
            defs[slot] = {
                'single_tap': normalize_td_node_binding(bindings[0] if len(bindings) > 0 else ''),
                'single_hold': normalize_td_node_binding(bindings[1] if len(bindings) > 1 else ''),
                'double_tap': normalize_td_node_binding(bindings[2] if len(bindings) > 2 else ''),
                'tapping_term': term,
            }
            continue

        if compatible != 'zmk,behavior-tap-dance':
            continue

        single_tap = ''
        single_hold = ''
        double_tap = normalize_td_node_binding(bindings[1] if len(bindings) > 1 else '')
        if bindings:
            first_parts = bindings[0].split()
            helper_label = first_parts[0].lstrip('&') if first_parts else ''
            helper = helper_bindings.get(helper_label)
            if helper and len(first_parts) >= 3:
                single_hold = normalize_td_node_binding(f'{helper[0]} {first_parts[1]}')
                single_tap = normalize_td_node_binding(f'{helper[1]} {first_parts[2]}')
            else:
                single_tap = normalize_td_node_binding(bindings[0])

        defs[slot] = {
            'single_tap': single_tap,
            'single_hold': single_hold,
            'double_tap': double_tap,
            'tapping_term': term,
        }

    return defs


def _step_from_macro_binding(entry):
    """Parse a single `&macro_xxx ...` string into a step dict."""
    entry = entry.strip()
    if entry.startswith('<') and entry.endswith('>'):
        entry = entry[1:-1].strip()
    tokens = entry.split()
    if not tokens:
        return None
    first = tokens[0].lstrip('&')
    if first in ('macro_tap', 'macro_press', 'macro_release'):
        kind = first.replace('macro_', '')
        if len(tokens) >= 3 and tokens[1] == '&kp':
            return {'type': kind, 'key': '&kp ' + ' '.join(tokens[2:])}
    if first == 'macro_wait_time' and len(tokens) >= 2:
        try:
            return {'type': 'wait', 'ms': int(tokens[1])}
        except ValueError:
            pass
    if first == 'macro_tap_time' and len(tokens) >= 2:
        try:
            return {'type': 'tap_time', 'ms': int(tokens[1])}
        except ValueError:
            pass
    if first == 'macro_pause_for_release':
        return {'type': 'pause_for_release'}
    return None


def extract_macro_definitions(content):
    defs = [{'label': f'mc{i}', 'display_name': '', 'steps': []} for i in range(MACRO_COUNT)]
    span = find_block_span(content, 'macros')
    if not span:
        return defs
    _, _, body_start, body_end = span
    body = content[body_start:body_end]
    managed_pat = re.compile(
        rf'{re.escape(MACRO_MANAGED_BEGIN)}(.*?){re.escape(MACRO_MANAGED_END)}',
        re.DOTALL,
    )
    m = managed_pat.search(body)
    if not m:
        return defs
    managed = m.group(1)
    for slot in range(MACRO_COUNT):
        label = f'mc{slot}'
        node_pat = re.compile(
            rf'^\s*{re.escape(label)}\s*:\s*\w+\s*\{{(.*?)^\s*\}};',
            re.MULTILINE | re.DOTALL,
        )
        nm = node_pat.search(managed)
        if not nm:
            continue
        node_body = nm.group(1)
        bindings_match = re.search(r'bindings\s*[^;]*;', node_body, re.DOTALL)
        if not bindings_match:
            continue
        entries = re.findall(r'<([^>]*)>', bindings_match.group(0))
        steps = [s for e in entries for s in [_step_from_macro_binding(e)] if s]
        defs[slot]['steps'] = steps
    return defs


# ──────────────────────────────────────────────
# Keymap writing
# ──────────────────────────────────────────────

ROW_SIZES = [10, 10, 10, 12, 10, 6, 10]  # total = 68


def format_bindings(bindings):
    rows, i = [], 0
    for n in ROW_SIZES:
        chunk = bindings[i:i + n]
        rows.append('            ' + '  '.join(b['raw'] for b in chunk))
        i += n
    return '\n'.join(rows)


def format_combo(combo):
    lines = [f'        {combo["name"]} {{']
    timeout_ms = str(combo.get('timeout_ms', '')).strip()
    if timeout_ms:
        lines.append(f'            timeout-ms = <{timeout_ms}>;')
    lines.append(f'            bindings = <{combo["binding"]}>;')
    lines.append(f'            key-positions = <{combo["key_positions"]}>;')
    layers = str(combo.get('layers', '')).strip()
    if layers:
        lines.append(f'            layers = <{layers}>;')
    lines.append('        };')
    return '\n'.join(lines)


def update_combos(original, combos):
    combos = combos or []
    block_lines = [
        '    combos {',
        '        compatible = "zmk,combos";',
    ]
    if combos:
        block_lines.append('')
        block_lines.extend(format_combo(combo) for combo in combos if combo.get('name') and combo.get('key_positions'))
    block_lines.append('    };')
    new_block = '\n'.join(block_lines)

    span = find_block_span(original, 'combos')
    if span:
        block_start, block_end, _, _ = span
        return original[:block_start] + new_block + original[block_end:]

    keymap_pat = re.compile(r'\n\s*keymap\s*\{', re.DOTALL)
    m = keymap_pat.search(original)
    if not m:
        return original + '\n\n' + new_block + '\n'
    return original[:m.start()] + '\n\n' + new_block + original[m.start():]


def replace_bindings_block(block_text, bindings):
    """Replace the first bindings = <...> block inside a named DTS block."""
    pat = re.compile(r'(bindings\s*=\s*<)(.*?)(>)', re.DOTALL)
    m = pat.search(block_text)
    if not m:
        return block_text
    new_text = '\n' + format_bindings(bindings) + '\n            '
    return block_text[:m.start(2)] + new_text + block_text[m.end(2):]


def replace_managed_section(body, section_lines,
                             begin_marker=TD_MANAGED_BEGIN, end_marker=TD_MANAGED_END):
    managed_pat = re.compile(
        rf'\n?[ \t]*{re.escape(begin_marker)}.*?[ \t]*{re.escape(end_marker)}\n?',
        re.DOTALL,
    )
    section = ''
    if section_lines:
        payload = '\n'.join(section_lines).rstrip()
        section = '\n' + '\n'.join([
            '        ' + begin_marker,
            payload,
            '        ' + end_marker,
        ]) + '\n'
    if managed_pat.search(body):
        return managed_pat.sub(section, body, count=1)
    if not section:
        return body
    stripped = body.rstrip()
    suffix = '' if stripped.endswith('\n') else '\n'
    return stripped + suffix + section


def upsert_managed_block(content, block_name, section_lines, insert_before='keymap',
                          begin_marker=TD_MANAGED_BEGIN, end_marker=TD_MANAGED_END):
    span = find_block_span(content, block_name)
    if span:
        _, _, body_start, body_end = span
        body = content[body_start:body_end]
        tail_match = re.search(r'(\n[ \t]*)$', body)
        tail = tail_match.group(1) if tail_match else '\n'
        new_body = replace_managed_section(body, section_lines, begin_marker, end_marker)
        new_body = new_body.rstrip('\n\t ') + tail
        return content[:body_start] + new_body + content[body_end:]
    if not section_lines:
        return content
    block_lines = [f'    {block_name} {{']
    block_lines.extend(section_lines)
    block_lines.append('    };')
    new_block = '\n'.join(block_lines)
    insert_pat = re.compile(rf'\n\s*{re.escape(insert_before)}\s*\{{', re.DOTALL)
    match = insert_pat.search(content)
    if match:
        return content[:match.start()] + '\n\n' + new_block + content[match.start():]
    root_end = content.rfind('};')
    if root_end == -1:
        return content.rstrip() + '\n\n' + new_block + '\n'
    return content[:root_end] + '\n\n' + new_block + '\n' + content[root_end:]


def _split_single_param(raw):
    """Split '&behavior PARAM' into ('behavior', 'PARAM').
    Returns (None, None) for empty, 0-param, or 3+-token bindings."""
    raw = normalize_td_binding(raw)
    if not raw:
        return None, None
    parts = raw.split()
    if len(parts) == 2:
        return parts[0].lstrip('&'), parts[1]
    return None, None


def build_td_sections(td_definitions):
    return build_tdt_sections(td_definitions)
    # Structure: zmk,behavior-tap-dance (outer, #binding-cells=0) wrapping
    # zmk,behavior-hold-tap (inner, tapping-term-ms=1) as its first binding.
    #
    # Why tapping-term-ms=1 for the inner hold-tap:
    #   With the old approach (both timers = 200ms), hold required 400ms total
    #   (tap-dance 200ms + hold-tap 200ms). Setting the inner hold-tap timer to
    #   1ms means hold fires ~1ms after the tap-dance resolves (~201ms total).
    #   Single-tap still works: if the key was released before the tap-dance
    #   timer, hold-tap receives press+release immediately → HT_KEY_UP → tap.
    behaviors_lines = []
    for slot, td in enumerate(normalize_td_definitions(td_definitions)):
        state_bindings = [
            normalize_td_binding(td.get('single_tap')),
            normalize_td_binding(td.get('single_hold')),
            normalize_td_binding(td.get('double_tap')),
        ]
        if not any(state_bindings):
            continue
        term = int(td.get('tapping_term', 200) or 200)
        if behaviors_lines:
            behaviors_lines.append('')
        hold_beh, hold_param = _split_single_param(single_hold)
        tap_beh, tap_param = _split_single_param(single_tap)
        if single_hold and hold_beh is not None:
            # Inner hold-tap: tap-preferred + tapping-term-ms=20
            #
            # Why hold-preferred:
            #   When tap-dance resolves as SINGLE-TAP (key already released), press+release
            #   are invoked with the SAME timestamp (tap_dance->release_at). In
            #   on_hold_tap_binding_released the check is:
            #     event.timestamp > hold_tap->timestamp + tapping_term_ms
            #   = same_ts > same_ts + 20  → FALSE
            #   So decide_hold_tap(HT_KEY_UP) runs → hold-preferred → STATUS_TAP → tap fires ✓
            #
            #   When tap-dance resolves as HOLD (key still pressed), hold-tap press fires and:
            #   - HT_OTHER_KEY_DOWN (another key pressed while undecided) → HOLD immediately ✓
            #   - HT_TIMER_EVENT (timer fires after ~20ms) → HOLD automatically ✓
            #
            # Why tapping-term-ms=20 (not 1):
            #   hold-tap computes tapping_term_ms_left = (event.timestamp + term) - k_uptime_get().
            #   event.timestamp = tap_dance->release_at = key_press_ts + 200ms.
            #   k_uptime_get() at hold-tap press ≈ key_press_ts + 200ms + jitter (1-5ms).
            #   With term=1: tapping_term_ms_left = 1 - jitter → often negative →
            #   Z_TIMEOUT_MS(MAX(negative, 0)) = K_NO_WAIT → fires "immediately" but
            #   may behave unpredictably. term=20 gives 15-19ms positive margin.
            #
            # Why NOT hold-while-undecided:
            #   Fires the hold binding immediately on press, BEFORE the decision.
            #   For single-tap (same-timestamp press+release), hold key fires before
            #   TAP is decided → tap output is preceded by spurious hold keycode.
            ht_tap_beh = tap_beh if tap_beh is not None else 'trans'
            ht_tap_param = tap_param if tap_param is not None else '0'
            behaviors_lines.extend([
                f'        td{slot}s: td{slot}s {{',
                '            compatible = "zmk,behavior-hold-tap";',
                '            #binding-cells = <2>;',
                '            flavor = "hold-preferred";',
                '            tapping-term-ms = <20>;',
                f'            bindings = <&{hold_beh}>, <&{ht_tap_beh}>;',
                '        };',
                '',
            ])
            ht_ref = f'&td{slot}s {hold_param} {ht_tap_param}'
            td_bindings = f'<{ht_ref}>, <{double_tap}>' if double_tap else f'<{ht_ref}>'
        else:
            # No hold (or non-parseable hold): pure tap-dance.
            b0 = single_tap or '&trans'
            td_bindings = f'<{b0}>, <{double_tap}>' if double_tap else f'<{b0}>'
        behaviors_lines.extend([
            f'        td{slot}: td{slot} {{',
            '            compatible = "zmk,behavior-tap-dance";',
            '            #binding-cells = <0>;',
            f'            tapping-term-ms = <{term}>;',
            f'            bindings = {td_bindings};',
            '        };',
        ])
    return behaviors_lines, []


def build_tdq_sections(td_definitions):
    return build_tdt_sections(td_definitions)
    behaviors_lines = []
    for slot, td in enumerate(normalize_td_definitions(td_definitions)):
        state_bindings = [
            normalize_td_binding(td.get('single_tap')),
            normalize_td_binding(td.get('single_hold')),
            normalize_td_binding(td.get('double_tap')),
        ]
        if not any(state_bindings):
            continue
        term = int(td.get('tapping_term', 200) or 200)
        if behaviors_lines:
            behaviors_lines.append('')
        td_bindings = ', '.join(f'<{binding or "&trans"}>' for binding in state_bindings)
        behaviors_lines.extend([
            f'        td{slot}: td{slot} {{',
            '            compatible = "zmk,behavior-tap-dance-triple";',
            '            #binding-cells = <0>;',
            f'            tapping-term-ms = <{term}>;',
            f'            bindings = {td_bindings};',
            '        };',
        ])
    return behaviors_lines, []


def build_tdt_sections(td_definitions):
    behaviors_lines = []
    for slot, td in enumerate(normalize_td_definitions(td_definitions)):
        state_bindings = [
            normalize_td_binding(td.get('single_tap')),
            normalize_td_binding(td.get('single_hold')),
            normalize_td_binding(td.get('double_tap')),
        ]
        if not any(state_bindings):
            continue
        term = int(td.get('tapping_term', 200) or 200)
        if behaviors_lines:
            behaviors_lines.append('')
        td_bindings = ', '.join(f'<{binding or "&trans"}>' for binding in state_bindings)
        behaviors_lines.extend([
            f'        td{slot}: td{slot} {{',
            '            compatible = "zmk,behavior-tap-dance-triple";',
            '            #binding-cells = <0>;',
            f'            tapping-term-ms = <{term}>;',
            f'            bindings = {td_bindings};',
            '        };',
        ])
    return behaviors_lines, []


def update_tap_dance_nodes(original, td_definitions):
    behavior_lines, macro_lines = build_tdt_sections(td_definitions)
    result = upsert_managed_block(original, 'behaviors', behavior_lines, insert_before='macros',
                                   begin_marker=TD_MANAGED_BEGIN, end_marker=TD_MANAGED_END)
    result = upsert_managed_block(result, 'macros', macro_lines, insert_before='combos',
                                   begin_marker=TD_MANAGED_BEGIN, end_marker=TD_MANAGED_END)
    return result


def _expand_text_to_bindings(text):
    """US配列テキストをmacro_tap binding文字列のリストに展開する。"""
    result = []
    for c in text:
        code = _US_CHAR_MAP.get(c)
        if code:
            result.append(f'<&macro_tap &kp {code}>')
    return result


def _step_to_bindings(step):
    """ステップ dict → binding 文字列リスト。"""
    t = step.get('type', '')
    if t in ('tap', 'press', 'release'):
        key = step.get('key', '').strip()
        if not key:
            return []
        return [f'<&macro_{t} {key}>']
    if t == 'wait':
        return [f'<&macro_wait_time {step.get("ms", 50)}>']
    if t == 'tap_time':
        return [f'<&macro_tap_time {step.get("ms", 10)}>']
    if t == 'pause_for_release':
        return ['<&macro_pause_for_release>']
    if t == 'text':
        return _expand_text_to_bindings(step.get('text', ''))
    return []


def build_macro_sections(macro_definitions):
    lines = []
    for i, macro in enumerate(normalize_macro_definitions(macro_definitions)):
        steps = macro.get('steps', [])
        if not steps:
            continue
        all_bindings = []
        for step in steps:
            all_bindings.extend(_step_to_bindings(step))
        if not all_bindings:
            continue
        label = f'mc{i}'
        if lines:
            lines.append('')
        lines.append(f'        {label}: {label} {{')
        lines.append('            compatible = "zmk,behavior-macro";')
        lines.append('            #binding-cells = <0>;')
        for j, b in enumerate(all_bindings):
            if j == 0:
                lines.append(f'            bindings = {b}')
            else:
                lines.append(f'                     , {b}')
        lines.append('                     ;')
        lines.append('        };')
    return lines


def update_macro_nodes(original, macro_definitions):
    lines = build_macro_sections(macro_definitions or [])
    return upsert_managed_block(
        original, 'macros', lines, insert_before='combos',
        begin_marker=MACRO_MANAGED_BEGIN, end_marker=MACRO_MANAGED_END,
    )


def format_conditional_layer(item):
    lines = [f'        {item["name"]} {{']
    lines.append(f'            if-layers = <{item["if_layers"]}>;')
    lines.append(f'            then-layer = <{item["then_layer"]}>;')
    lines.append('        };')
    return '\n'.join(lines)


def update_conditional_layers(original, conditional_layers):
    items = []
    for item in conditional_layers or []:
        name = str(item.get('name', '')).strip()
        if_layers = ' '.join(str(item.get('if_layers', '')).split())
        then_layer = str(item.get('then_layer', '')).strip()
        if not name or not if_layers or not then_layer:
            continue
        items.append({
            'name': name,
            'if_layers': if_layers,
            'then_layer': then_layer,
        })

    block_lines = [
        '    conditional_layers {',
        '        compatible = "zmk,conditional-layers";',
    ]
    if items:
        block_lines.append('')
        block_lines.extend(format_conditional_layer(item) for item in items)
    block_lines.append('    };')
    new_block = '\n'.join(block_lines)

    span = find_block_span(original, 'conditional_layers')
    if span:
        block_start, block_end, _, _ = span
        return original[:block_start] + new_block + original[block_end:]

    keymap_pat = re.compile(r'\n\s*keymap\s*\{', re.DOTALL)
    m = keymap_pat.search(original)
    if not m:
        return original + '\n\n' + new_block + '\n'
    root_end = original.rfind('};')
    if root_end == -1:
        return original.rstrip() + '\n\n' + new_block + '\n'
    return original[:root_end] + '\n\n' + new_block + '\n' + original[root_end:]


def update_keymap(original, layers, combos=None, td_definitions=None,
                   conditional_layers=None, macro_definitions=None):
    result = original
    keymap_span = find_block_span(result, 'keymap')
    if keymap_span:
        keymap_start, keymap_end, _, _ = keymap_span
        keymap_block = result[keymap_start:keymap_end]
        for layer in reversed(layers or []):
            layer_name = layer.get('name', '').strip()
            if not layer_name:
                continue
            layer_span = find_block_span(keymap_block, layer_name)
            if not layer_span:
                continue
            layer_start, layer_end, _, _ = layer_span
            layer_block = keymap_block[layer_start:layer_end]
            keymap_block = (
                keymap_block[:layer_start]
                + replace_bindings_block(layer_block, layer.get('bindings', []))
                + keymap_block[layer_end:]
            )
        result = result[:keymap_start] + keymap_block + result[keymap_end:]
    result = update_combos(result, combos)
    result = update_tap_dance_nodes(result, td_definitions)
    result = update_macro_nodes(result, macro_definitions)
    result = update_conditional_layers(result, conditional_layers)
    return result


# ──────────────────────────────────────────────
# Config (.conf) parsing / writing
# ──────────────────────────────────────────────

def parse_conf(content):
    cfg = {}
    for line in content.splitlines():
        s = line.strip()
        if s and not s.startswith('#') and '=' in s:
            k, _, v = s.partition('=')
            cfg[k.strip()] = v.strip()
    return cfg


def update_conf(original, new_cfg):
    lines = original.splitlines()
    result, done = [], set()
    for line in lines:
        s = line.strip()
        if s and not s.startswith('#') and '=' in s:
            k = s.split('=')[0].strip()
            if k in new_cfg:
                result.append(f'{k}={new_cfg[k]}')
                done.add(k)
            else:
                result.append(line)
        else:
            result.append(line)
    for k, v in new_cfg.items():
        if k not in done:
            result.append(f'{k}={v}')
    return '\n'.join(result)


# ──────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    if request.method == 'GET':
        return jsonify(load_settings())
    s = load_settings()
    payload = dict(request.json or {})
    if payload.get('mt_definitions') is not None and payload.get('td_definitions') is None:
        payload['td_definitions'] = payload.pop('mt_definitions')
    s.update(payload)
    save_settings_file(s)
    return jsonify({'ok': True})


@app.route('/api/browse_folder', methods=['POST'])
def api_browse_folder():
    """OS標準のフォルダ選択ダイアログを開いてパスを返す。"""
    root = tk.Tk()
    root.withdraw()
    root.wm_attributes('-topmost', True)
    folder = filedialog.askdirectory(parent=root, title='LaLapad Gen2 firmware フォルダを選択')
    root.destroy()
    if not folder:
        return jsonify({'cancelled': True})
    return jsonify({'folder': os.path.normpath(folder)})


@app.route('/api/folder', methods=['POST'])
def api_folder():
    """Accept a firmware root folder, discover files, save settings, return paths."""
    data = request.json or {}
    folder = norm(data.get('folder', ''))
    if not folder or not os.path.isdir(folder):
        return jsonify({'error': f'フォルダが見つかりません: {folder}'}), 404
    found = discover_files(folder)
    if not found.get('keymap_path'):
        return jsonify({'error': 'config/*.keymap ファイルが見つかりません'}), 404
    s = load_settings()
    # フォルダ切り替え時にマクロをフォルダごとに保存・復元する
    old_folder = norm(s.get('firmware_folder', ''))
    per_folder = s.setdefault('per_folder_macros', {})
    if old_folder:
        per_folder[old_folder] = s.get('macro_definitions', [])
    if folder in per_folder:
        s['macro_definitions'] = normalize_macro_definitions(per_folder[folder])
    else:
        s['macro_definitions'] = make_default_macro_definitions()
    s.update(found)
    save_settings_file(s)
    return jsonify(found)


@app.route('/api/folder_history/delete', methods=['POST'])
def api_folder_history_delete():
    data = request.json or {}
    folder = norm(data.get('folder', ''))
    if not folder:
        return jsonify({'error': 'folder is required'}), 400

    s = load_settings()
    per_folder = s.setdefault('per_folder_macros', {})
    per_folder.pop(folder, None)

    current_folder = norm(s.get('firmware_folder', ''))
    clear_current = bool(data.get('clear_current'))
    if clear_current and current_folder == folder:
        s.update({
            'firmware_folder': '',
            'keymap_path': '',
            'main_conf_path': '',
            'left_conf_path': '',
            'right_conf_path': '',
            'keyboard_name': '',
            'macro_definitions': make_default_macro_definitions(),
        })

    save_settings_file(s)
    return jsonify({'ok': True, 'settings': load_settings()})


@app.route('/api/keymap', methods=['GET', 'POST'])
def api_keymap():
    s = load_settings()
    path = norm(s.get('keymap_path', ''))

    if request.method == 'GET':
        if not path or not os.path.exists(path):
            return jsonify({'error': f'ファイルが見つかりません: {path or "(未設定)"}'}), 404
        content = _read_text_file(path)
        layers = extract_layers(content)
        custom = extract_custom_bindings(content)
        defines = extract_defines(content)
        td_definitions = extract_td_definitions(content)
        # マクロ定義はsettingsを正とし、display_nameもsettingsから復元する
        settings_macros = normalize_macro_definitions(s.get('macro_definitions'))
        km_macros = extract_macro_definitions(content)
        macro_definitions = []
        for i in range(MACRO_COUNT):
            sm = settings_macros[i]
            km = km_macros[i]
            # textステップがある場合やsettingsにステップがある場合はsettingsを優先
            if sm['steps']:
                macro_definitions.append(sm)
            elif km['steps']:
                km['display_name'] = sm['display_name']
                macro_definitions.append(km)
            else:
                macro_definitions.append(sm)
        return jsonify({
            'layers': layers,
            'combos': extract_combos(content),
            'conditional_layers': extract_conditional_layers(content),
            'td_definitions': td_definitions,
            'macro_definitions': macro_definitions,
            'custom_bindings': custom,
            'defines': defines,
            'path': path,
        })

    # POST — save
    if not path or not os.path.exists(path):
        return jsonify({'error': 'キーマップパスが無効'}), 400
    original = _read_text_file(path)
    payload = request.json or {}
    td_definitions = payload.get('td_definitions', s.get('td_definitions', []))
    td_module_status = 'not_needed'
    td_module_plan = None
    try:
        macro_definitions = payload.get('macro_definitions', s.get('macro_definitions', []))
        new = update_keymap(
            original,
            payload.get('layers', []),
            payload.get('combos', []),
            td_definitions,
            payload.get('conditional_layers', []),
            macro_definitions,
        )
        if td_definitions_require_module(td_definitions):
            td_module_plan = plan_td_module_install(s.get('firmware_folder', ''))
            td_module_status = td_module_plan['status']
    except Exception as e:
        if isinstance(e, TDModuleConflict):
            return jsonify({'error': str(e)}), 409
        return jsonify({'error': str(e)}), 500
    try:
        if td_module_plan and td_module_plan['writes']:
            apply_td_module_install(td_module_plan)
        write_text_file(path, new)
    except Exception as e:
        return jsonify({'error': f'ファイル書き込みエラー: {e}'}), 500
    # マクロ定義をsettingsにも保存（textステップ等を保持するため）
    s2 = load_settings()
    s2['macro_definitions'] = normalize_macro_definitions(macro_definitions)
    folder2 = norm(s2.get('firmware_folder', ''))
    if folder2:
        s2.setdefault('per_folder_macros', {})[folder2] = s2['macro_definitions']
    save_settings_file(s2)
    return jsonify({'ok': True, 'td_module': td_module_status})


@app.route('/api/config/<side>', methods=['GET', 'POST'])
def api_config(side):
    s = load_settings()
    key_map = {
        'main':  'main_conf_path',
        'left':  'left_conf_path',
        'right': 'right_conf_path',
    }
    if side not in key_map:
        return jsonify({'error': '無効なサイド指定'}), 400
    path = norm(s.get(key_map[side], ''))

    if request.method == 'GET':
        if not path or not os.path.exists(path):
            return jsonify({'error': f'ファイルが見つかりません: {path or "(未設定)"}'}), 404
        content = _read_text_file(path)
        return jsonify({'config': parse_conf(content), 'path': path})

    # POST
    if not path:
        return jsonify({'error': 'パスが未設定'}), 400
    original = _read_text_file(path) if os.path.exists(path) else ''
    new_cfg = (request.json or {}).get('config', {})
    new_content = update_conf(original, new_cfg)
    try:
        write_text_file(path, new_content)
    except Exception as e:
        return jsonify({'error': f'ファイル書き込みエラー: {e}'}), 500
    return jsonify({'ok': True})


if __name__ == '__main__':
    import threading, webbrowser, time
    threading.Thread(
        target=lambda: (time.sleep(0.8), webbrowser.open('http://localhost:5173')),
        daemon=True
    ).start()
    app.run(host='127.0.0.1', port=5173, debug=False)
