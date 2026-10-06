"""核对完整Linux连续批次与独立控制，封存可恢复的源码、库和实际保存对象。"""
import argparse
from datetime import datetime,timezone,timedelta
import hashlib,json,os,statistics,subprocess,zipfile
from pathlib import Path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);args=p.parse_args()
    root=args.root.resolve();sha=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()
    driver=json.loads((root/'trials_02/01-Linux完整链交错批次记录.json').read_text())
    assert len(driver['trials'])==6 and all(t['status']=='completed' for t in driver['trials'])
    for filename in ['trials_02.pid','fixed_flip_recheck2.pid','affinity_01.pid']:
        assert not Path('/proc/'+(root/filename).read_text()).exists()
    for name,expected in driver['worker_sha256'].items():assert sha(root/name)==expected
    for library in driver['build_identity']['libraries']:assert sha(library['path'])==library['sha256']
    # 原作者源码及四个非图形子模块均按归档成员重新核查，构建参数不冒称源码改动。
    archive_checks=[]
    for name,directory in [('geogram.zip','geogram_source'),('opennl.zip','geogram_source/src/lib/geogram/third_party/OpenNL'),
        ('amgcl.zip','geogram_source/src/lib/geogram/third_party/amgcl'),('libmeshb.zip','geogram_source/src/lib/geogram/third_party/libMeshb'),
        ('rply.zip','geogram_source/src/lib/geogram/third_party/rply')]:
        with zipfile.ZipFile(root/name) as z:
            files=[x for x in z.infolist() if not x.is_dir()]
            for item in files:assert (root/directory/item.filename).read_bytes()==z.read(item)
        archive_checks.append(dict(name=name,sha256=sha(root/name),members=len(files)))
    records=[];audited=0;planned=0
    for t in driver['trials']:
        d=root/'trials_02'/f'r{t["repeat"]}_{t["backend"]}'
        record=json.loads((d/'01-真实父反馈四预算完整记录.json').read_text());audit=json.loads((d/'02-完整保存全量精确复审与四预算统计.json').read_text())
        assert record['status']==audit['status']=='completed' and audit['all_parent_chains_valid']
        assert audit['all_saved_published_and_sources_embedded'];audited+=audit['full_audited_objects']
        for route in record['routes']:assert len(route['events'])==route['planned_events']==16;planned+=16
        records.append(dict(repeat=t['repeat'],backend=t['backend'],summaries=audit['summaries']))
    controls=json.loads((root/'trials_02/05-Linux实际翻边与无维护帧完整对拍.json').read_text())
    assert controls['status']=='completed' and controls['paired_runs']==48 and controls['protocol_controls']==6
    affinity=json.loads((root/'affinity_01/01-亲和性完整交错对照.json').read_text());assert affinity['status']=='completed' and affinity['all_output_sets_identical']
    summaries=[]
    for count in [0,4,8,16]:
        values=[x['total_ms'] for r in affinity['rows'] if r['cpus']==count for x in r['record']['timings'][1:]]
        summaries.append(dict(cpus=count,warm_samples=len(values),median_ms=statistics.median(values),mean_ms=statistics.mean(values)))
    report=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',
        original_driver_status=driver['status'],original_post_control_failure_retained=True,
        planned_events=planned,full_audited_saved_objects=audited,trials=records,archives_verified=archive_checks,
        fixed_flip_pairs=48,protocol_controls=6,affinity_summary=summaries,
        source_and_runtime_binding=True,no_display_claim=True,no_full_pamo=True)
    summary=root/'02-Linux完整连续证据与资源对照汇总.json';assert not summary.exists()
    summary.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    selected=set()
    for directory in ['workers','inputs','diagnosis','trials_01','trials_02','affinity_01','phase_profile']:
        for path in (root/directory).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:selected.add(path)
    selected.update(p for p in root.iterdir() if p.is_file() and p.suffix in ('.py','.cpp','.json','.log','.zip','.pid'))
    selected.update((root/'geogram_build/lib').glob('libgeogram.so*'))
    members=[];archive=root/'完整Linux连续与资源诊断证据.zip';assert not archive.exists()
    with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=1) as z:
        for path in sorted(selected):
            data=path.read_bytes();name=str(path.relative_to(root));z.writestr(name,data)
            members.append(dict(name=name,size=len(data),sha256=hashlib.sha256(data).hexdigest()))
        z.writestr('01-完整Linux证据包成员清单.json',json.dumps(members,ensure_ascii=False,indent=2))
    receipt=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',members=len(members),
        archive_sha256=sha(archive),archive_bytes=archive.stat().st_size,summary_sha256=sha(summary))
    (root/'03-Linux完整证据封存回执.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
