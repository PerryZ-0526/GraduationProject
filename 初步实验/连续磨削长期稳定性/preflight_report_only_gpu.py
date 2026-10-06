"""只读核查用户指定实例的设备、剩余空间、依赖与活动作业。"""
import getpass
import json
import paramiko


def main():
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    password = getpass.getpass('GPU SSH password: ')
    client.connect('connect.westb.seetacloud.com', port=14137, username='root', password=password,
                   look_for_keys=False, allow_agent=False, timeout=30)
    del password
    try:
        # 只读取设备、磁盘、进程名及明确依赖，不输出进程参数或环境凭据。
        commands = {
            'device': 'nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader',
            'disk': 'df -h /root/autodl-tmp',
            'jobs': 'ps -eo pid,comm | head -60',
            'dependencies': 'test -x /root/autodl-tmp/graduation_project/pamo_quality_20260927_015556_807159_retry3/venv/bin/python && test -x /root/autodl-tmp/graduation_project/followup_20260928_2344/bin/geogram_boolean && test -x /root/autodl-tmp/graduation_project/locality_20261004_021939/geogram_provenance',
        }
        for name, command in commands.items():
            _, stdout, stderr = client.exec_command(command, timeout=30)
            out, err = stdout.read().decode('utf-8', 'replace'), stderr.read().decode('utf-8', 'replace')
            print(json.dumps({'check': name, 'returncode': stdout.channel.recv_exit_status(),
                              'stdout': out, 'stderr': err}, ensure_ascii=False), flush=True)
    finally:
        client.close()


if __name__ == '__main__':
    main()
