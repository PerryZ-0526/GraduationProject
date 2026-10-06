"""只读检查本批远端独立目录的磁盘占用，不操作其他任务的文件。"""
import getpass
import hashlib
import json
from pathlib import Path
import shlex
import paramiko


def main():
    output = Path('D:/GraduationProject实验输出/20261006_取消几何距离停止完整反馈_14137')
    identity = hashlib.sha256(str(output.resolve()).encode('utf-8')).hexdigest()[:12]
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    password = getpass.getpass('GPU SSH password: ')
    client.connect('connect.westb.seetacloud.com', port=14137, username='root', password=password,
                   look_for_keys=False, allow_agent=False, timeout=30)
    del password
    sftp = client.open_sftp()
    try:
        base = '/root/autodl-tmp/graduation_project'
        # 按本地路径摘要查找实际服务器目录名，避免终端中文编码差异影响定位。
        names = [name for name in sftp.listdir(base) if name.startswith('constrained_') and name.endswith('_' + identity)]
        if len(names) != 1:
            raise ValueError('本批远端目录身份不唯一')
        remote = base + '/' + names[0]
        for command in ['du -sh ' + shlex.quote(remote),
                        'du -sh ' + shlex.quote(remote) + '/* | sort -hr | head -15']:
            _, stdout, stderr = client.exec_command(command, timeout=40)
            out, err = stdout.read().decode('utf-8', 'replace'), stderr.read().decode('utf-8', 'replace')
            print(json.dumps({'returncode': stdout.channel.recv_exit_status(), 'stdout': out, 'stderr': err}, ensure_ascii=False), flush=True)
    finally:
        sftp.close()
        client.close()


if __name__ == '__main__':
    main()
