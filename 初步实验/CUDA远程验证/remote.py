"""读取本地环境文件，通过固定主机密钥执行远程实验或传输指定文件。"""
import argparse
import base64
import hashlib
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[2]


class FirstUsePolicy(paramiko.MissingHostKeyPolicy):
    def missing_host_key(self, client, hostname, key):
        # 首次连接采用TOFU记录指纹；后续密钥变化由Paramiko拒绝。
        fingerprint = base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
        print(f'首次主机指纹 SHA256:{fingerprint}', flush=True)
        client.get_host_keys().add(hostname, key.get_name(), key)
        client.save_host_keys(str(ROOT / '.ssh_known_hosts'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--command')
    parser.add_argument('--put', nargs=2, metavar=('LOCAL', 'REMOTE'))
    parser.add_argument('--get', nargs=2, metavar=('REMOTE', 'LOCAL'))
    args = parser.parse_args()
    # 密码不进入命令行、日志、远端文件或版本控制。
    config = dict(line.split('=', 1) for line in (ROOT / '.env').read_text(encoding='utf-8').splitlines() if line and not line.startswith('#'))
    client = paramiko.SSHClient()
    if (ROOT / '.ssh_known_hosts').exists():
        client.load_host_keys(str(ROOT / '.ssh_known_hosts'))
    client.set_missing_host_key_policy(FirstUsePolicy())
    try:
        client.connect(config['CUDA_SSH_HOST'], port=int(config['CUDA_SSH_PORT']), username=config['CUDA_SSH_USER'], password=config['CUDA_SSH_PASSWORD'], look_for_keys=False, allow_agent=False, timeout=20, auth_timeout=20)
        if args.put or args.get:
            with client.open_sftp() as sftp:
                if args.put:
                    sftp.put(*args.put)
                else:
                    sftp.get(*args.get)
        if args.command:
            _, stdout, stderr = client.exec_command(args.command, timeout=600)
            # 合并输出并逐行读取，避免大量错误输出填满SSH窗口。
            stdout.channel.set_combine_stderr(True)
            for line in stdout:
                print(line, end='', flush=True)
            raise SystemExit(stdout.channel.recv_exit_status())
    finally:
        client.close()


if __name__ == '__main__':
    main()
