#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path

import yaml

LINGFENG = 'lingfeng'
LINGFENG_HOME = Path('/home/lingfeng')
MIHOMO_CONFIG = Path('/home/claw/.config/mihomo/config.yaml')
PROXY_URL = 'http://127.0.0.1:7890'
NO_PROXY = '127.0.0.1,localhost,::1'
OPENAI_GROUP = '🌍 国外媒体'
OPENAI_RULES = [
    f'DOMAIN-SUFFIX,chatgpt.com,{OPENAI_GROUP}',
    f'DOMAIN-SUFFIX,openai.com,{OPENAI_GROUP}',
    f'DOMAIN-SUFFIX,oaistatic.com,{OPENAI_GROUP}',
    f'DOMAIN-SUFFIX,oaiusercontent.com,{OPENAI_GROUP}',
    f'DOMAIN-SUFFIX,auth0.com,{OPENAI_GROUP}',
]
PROXY_ENV = {
    'HTTP_PROXY': PROXY_URL,
    'HTTPS_PROXY': PROXY_URL,
    'http_proxy': PROXY_URL,
    'https_proxy': PROXY_URL,
    'NO_PROXY': NO_PROXY,
    'no_proxy': NO_PROXY,
}


def run(cmd, *, check=True, capture=False, env=None):
    return subprocess.run(cmd, check=check, text=True, capture_output=capture, env=env)


def timestamp():
    return datetime.now().strftime('%Y%m%d-%H%M%S')


def require_root():
    if os.geteuid() != 0:
        raise SystemExit('apply must be run with sudo because it edits mihomo and /usr/local/bin')


def chown_lingfeng(path: Path):
    shutil.chown(path, user=LINGFENG, group=LINGFENG)


def backup(path: Path) -> Path:
    dst = path.with_name(path.name + f'.backup.codex-proxy-{timestamp()}')
    shutil.copy2(path, dst)
    return dst


def ensure_mihomo_rules():
    if not MIHOMO_CONFIG.exists():
        raise SystemExit(f'mihomo config not found: {MIHOMO_CONFIG}')
    cfg = yaml.safe_load(MIHOMO_CONFIG.read_text(encoding='utf-8')) or {}
    groups = {g.get('name') for g in cfg.get('proxy-groups', []) if isinstance(g, dict)}
    if OPENAI_GROUP not in groups:
        raise SystemExit(f'proxy group not found: {OPENAI_GROUP}')
    old_rules = cfg.get('rules') or []
    filtered = [
        r for r in old_rules
        if not (isinstance(r, str) and any(domain in r for domain in ['chatgpt.com', 'openai.com', 'oaistatic.com', 'oaiusercontent.com', 'auth0.com']))
    ]
    cfg['rules'] = OPENAI_RULES + filtered
    b = backup(MIHOMO_CONFIG)
    MIHOMO_CONFIG.write_text(yaml.safe_dump(cfg, allow_unicode=True, sort_keys=False), encoding='utf-8')
    print(f'updated mihomo rules; backup={b}')
    run(['systemctl', 'restart', 'mihomo.service'])
    print('restarted mihomo.service')


def install_wrapper(command: str, real_target: str):
    wrapper = Path('/usr/local/bin') / command
    real_link = Path('/usr/local/bin') / f'{command}-real'
    if wrapper.exists() or wrapper.is_symlink():
        try:
            current = wrapper.read_text(errors='ignore') if wrapper.is_file() and not wrapper.is_symlink() else ''
        except OSError:
            current = ''
        if f'exec /usr/local/bin/{command}-real "$@"' not in current:
            dst = wrapper.with_name(wrapper.name + f'.backup.codex-proxy-{timestamp()}')
            wrapper.rename(dst)
            print(f'backed up {wrapper} -> {dst}')
    if real_link.exists() or real_link.is_symlink():
        real_link.unlink()
    real_link.symlink_to(real_target)
    script = textwrap.dedent(f'''\
        #!/usr/bin/env bash
        export HTTP_PROXY="${{HTTP_PROXY:-{PROXY_URL}}}"
        export HTTPS_PROXY="${{HTTPS_PROXY:-{PROXY_URL}}}"
        export http_proxy="${{http_proxy:-{PROXY_URL}}}"
        export https_proxy="${{https_proxy:-{PROXY_URL}}}"
        export NO_PROXY="${{NO_PROXY:-{NO_PROXY}}}"
        export no_proxy="${{no_proxy:-{NO_PROXY}}}"
        exec /usr/local/bin/{command}-real "$@"
    ''')
    wrapper.write_text(script, encoding='utf-8')
    wrapper.chmod(0o755)
    print(f'installed proxy wrapper: {wrapper}')


def update_env_file(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        b = backup(path)
        lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
        print(f'backed up {path} -> {b}')
    else:
        lines = []
    seen = set()
    out = []
    for line in lines:
        if '=' in line and not line.lstrip().startswith('#'):
            key = line.split('=', 1)[0]
            if key in PROXY_ENV:
                out.append(f'{key}={PROXY_ENV[key]}')
                seen.add(key)
                continue
        out.append(line)
    for key, val in PROXY_ENV.items():
        if key not in seen:
            out.append(f'{key}={val}')
    path.write_text('\n'.join(out).rstrip() + '\n', encoding='utf-8')
    chown_lingfeng(path)
    path.chmod(0o600)
    print(f'updated env file: {path}')


def update_claude_settings():
    path = LINGFENG_HOME / '.claude/settings.json'
    if not path.exists():
        raise SystemExit(f'Claude settings not found: {path}')
    b = backup(path)
    data = json.loads(path.read_text(encoding='utf-8'))
    env = data.setdefault('env', {})
    env.update(PROXY_ENV)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    chown_lingfeng(path)
    path.chmod(0o600)
    print(f'updated Claude settings; backup={b}')


def write_systemd_dropins():
    env_lines = ''.join(f'Environment="{k}={v}"\n' for k, v in PROXY_ENV.items())
    content = '[Service]\n' + env_lines

    user_dir = LINGFENG_HOME / '.config/systemd/user/hermes-gateway.service.d'
    user_dir.mkdir(parents=True, exist_ok=True)
    user_dropin = user_dir / 'proxy.conf'
    user_dropin.write_text(content, encoding='utf-8')
    chown_lingfeng(user_dir)
    chown_lingfeng(user_dropin)
    user_dropin.chmod(0o644)

    system_dir = Path('/etc/systemd/system/hermes-web-ui.service.d')
    system_dir.mkdir(parents=True, exist_ok=True)
    system_dropin = system_dir / 'proxy.conf'
    system_dropin.write_text(content, encoding='utf-8')
    system_dropin.chmod(0o644)

    run(['systemctl', 'daemon-reload'])
    uid = subprocess.check_output(['id', '-u', LINGFENG], text=True).strip()
    user_env = os.environ.copy()
    user_env['XDG_RUNTIME_DIR'] = f'/run/user/{uid}'
    run(['sudo', '-u', LINGFENG, 'systemctl', '--user', 'daemon-reload'], check=False, env=user_env)
    run(['systemctl', 'restart', 'hermes-web-ui.service'], check=False)
    run(['sudo', '-u', LINGFENG, 'systemctl', '--user', 'restart', 'hermes-gateway.service'], check=False, env=user_env)
    print('wrote Hermes systemd proxy drop-ins')


def verify_url(url: str):
    last_code = '000'
    for attempt in range(1, 4):
        cmd = ['curl', '--connect-timeout', '10', '--max-time', '30', '-sS', '-o', '/dev/null', '-w', '%{http_code}', '-x', PROXY_URL, url]
        result = run(cmd, check=False, capture=True)
        code = (result.stdout or '').strip() or '000'
        last_code = code
        if code != '000':
            print(f'{url}: http_code={code} status=ok attempt={attempt}')
            return True
    print(f'{url}: http_code={last_code} status=failed attempts=3')
    return False


def safe_path_status(path: Path):
    try:
        return 'present' if path.exists() else 'missing'
    except PermissionError:
        return 'protected'


def status():
    print(f'proxy={PROXY_URL}')
    result = run(['systemctl', 'is-active', 'mihomo.service'], check=False, capture=True)
    print(f'mihomo.service={result.stdout.strip() or result.stderr.strip()}')
    for path in [MIHOMO_CONFIG, LINGFENG_HOME / '.codex/auth.json', LINGFENG_HOME / '.claude/settings.json', LINGFENG_HOME / '.hermes/.env']:
        print(f'{path}: {safe_path_status(path)}')
    for command in ['codex', 'claude']:
        p = shutil.which(command)
        print(f'{command}: {p or "missing"}')


def apply():
    require_root()
    ensure_mihomo_rules()
    install_wrapper('codex', '/usr/local/lib/node_modules/@openai/codex/bin/codex.js')
    install_wrapper('claude', '/usr/local/lib/node_modules/@anthropic-ai/claude-code/cli.js')
    update_claude_settings()
    update_env_file(LINGFENG_HOME / '.hermes/.env')
    write_systemd_dropins()


def verify():
    ok = True
    ok &= verify_url('https://chatgpt.com')
    ok &= verify_url('https://api.openai.com/v1/models')
    for command in [['codex', '--version'], ['claude', '--version']]:
        result = run(command, check=False, capture=True)
        text = (result.stdout or result.stderr or '').strip().splitlines()[0] if (result.stdout or result.stderr) else ''
        print(f'{command[0]}: rc={result.returncode} {text}')
        ok &= result.returncode == 0
    raise SystemExit(0 if ok else 1)


def main():
    parser = argparse.ArgumentParser(description='Configure server mihomo proxy for Codex, Claude, and Hermes.')
    parser.add_argument('command', choices=['status', 'apply', 'verify'])
    args = parser.parse_args()
    if args.command == 'status':
        status()
    elif args.command == 'apply':
        apply()
    elif args.command == 'verify':
        verify()


if __name__ == '__main__':
    main()
