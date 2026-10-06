"""按相同原扫掠前缀比较逐刀和批量保存网格，完整复审后统计几何与质量。"""
import hashlib,json,sys
from datetime import datetime,timezone,timedelta
from pathlib import Path
from time import perf_counter
import numpy as np
from audit_resident_batch_geometry import points,distances


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    root=Path(sys.argv[1]);sys.path.insert(0,str(root/'workers'))
    from exact_mesh_memory import ExactMeshMemory
    from benchmark import quality
    report_path=root/'03-完整批量父反馈记录.json';report=json.loads(report_path.read_text(encoding='utf-8'))
    assert report['status'] in ('completed','completed_with_recorded_failures') and report['mode']=='long'
    config=json.loads((root/'config.json').read_text());base=Path(config['base'])
    assert sha(base/'manifest.json')==sha(root/'manifest.json')
    audit_path=root/'04-实际保存数组完整精确复审.json';audit=json.loads(audit_path.read_text(encoding='utf-8'))
    checks={(entry['run'],entry['update'],entry['kind']):entry for entry in audit['arrays']}
    full=ExactMeshMemory();rows=[];started=perf_counter()
    for run in report['runs']:
        if not run['label'].endswith('_candidate'):continue
        baseline=base/run['label'];saved_path=baseline/'03-保存数组清单.json'
        saved=json.loads(saved_path.read_text(encoding='utf-8'))
        baseline_outputs={entry['step']:entry for entry in saved if entry['kind']=='output'}
        for row in run['rows']:
            step=row['event_steps'][-1]
            if row['status']!='published_verified' or step not in baseline_outputs:continue
            saved_batch=checks[run['label'],row['update'],'output'];batch_path=root/saved_batch['path']
            before_path=baseline/f'e{step:03d}_output.npz';assert sha(before_path)==baseline_outputs[step]['sha256']
            assert sha(batch_path)==saved_batch['file_sha256'] and saved_batch['check']['embedded_closed']
            with np.load(before_path) as data:sv,sf=data['vertices'].copy(),data['faces'].copy()
            with np.load(batch_path) as data:bv,bf=data['vertices'].copy(),data['faces'].copy()
            source_check=full.audit(sv,sf);assert source_check['embedded_closed']
            rows.append(dict(route=run['label'],last_event=step+1,
                original_manifest_sha256=sha(root/'manifest.json'),
                sequential_file_sha256=sha(before_path),batch_file_sha256=sha(batch_path),sequential_full_check=source_check,
                sequential_quality=quality(sv,sf,0),batch_quality=quality(bv,bf,0),
                sequential_to_batch=distances(bv,bf,points(sv,sf,20261007+step)),
                batch_to_sequential=distances(sv,sf,points(bv,bf,20261007+step))))
    result=dict(time_beijing=datetime.now(timezone(timedelta(hours=8))).isoformat(),status='completed',rows=rows,
        worker_sha256=sha(__file__),probe_worker_sha256=sha(Path(__file__).with_name('audit_resident_batch_geometry.py')),
        report_sha256=sha(report_path),batch_full_audit_sha256=sha(audit_path),elapsed_ms=(perf_counter()-started)*1000,
        scope='同初态与完全相同原工具前缀，各自反馈父网格；质量和有限距离对照，非独立真值或同父组件时延加速比',
        geometry_policy='report_only_no_distance_stop')
    path=root/'10-同原扫掠前缀逐刀批量几何及质量.json';temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)
    print(json.dumps(dict(prefixes=len(rows),elapsed_ms=result['elapsed_ms'],max_mm=max((item[key]['max_mm'] for item in rows for key in ('sequential_to_batch','batch_to_sequential')),default=None))),flush=True)


if __name__=='__main__':main()
