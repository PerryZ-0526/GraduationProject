"""连接用户指定实例，凭据仅从忽略配置读取；保留原版安装和历史冻结结果。"""
import argparse
import importlib.util
from pathlib import Path
import paramiko


def connect():
    """复用项目主机密钥策略，固定使用用户最后指定的主机和端口。"""
    root = Path(__file__).resolve().parents[4]
    spec = importlib.util.spec_from_file_location('existing_remote', root/'初步实验/CUDA远程验证/remote.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    config = dict(line.split('=', 1) for line in (root/'.env').read_text('utf8').splitlines()
                  if line and not line.startswith('#'))
    client = paramiko.SSHClient()
    known = root/'.ssh_known_hosts'
    if known.exists():
        client.load_host_keys(str(known))
    client.set_missing_host_key_policy(module.FirstUsePolicy())
    client.connect('connect.westb.seetacloud.com', port=14137, username='root',
                   password=config['CUDA_SSH_PASSWORD'], look_for_keys=False,
                   allow_agent=False, timeout=30, auth_timeout=30)
    client.get_transport().set_keepalive(30)
    return client


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--command')
    parser.add_argument('--put', nargs=2)
    parser.add_argument('--get', nargs=2)
    args = parser.parse_args()
    client = connect()
    try:
        if args.put or args.get:
            with client.open_sftp() as sftp:
                if args.put:
                    sftp.put(*args.put)
                else:
                    sftp.get(*args.get)
        if args.command:
            _, out, _ = client.exec_command(args.command)
            out.channel.set_combine_stderr(True)
            for line in out:
                print(line, end='', flush=True)
            raise SystemExit(out.channel.recv_exit_status())
    finally:
        client.close()
