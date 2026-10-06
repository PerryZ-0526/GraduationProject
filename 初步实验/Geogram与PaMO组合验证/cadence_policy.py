"""间歇维护的冻结调度规则；质量阈值触发维护，不拒绝几何帧。"""
POLICIES=('every','period2','period4','period8','adaptive','never')
ADAPTIVE=dict(max_interval=8,angle10_growth=0.03,angle1_growth=0.002,area10_growth=0.01,face_growth_ratio=1.5)


def maintenance_reason(policy,pending,current,baseline,final=False,valid=True):
    if policy not in POLICIES or pending<1:
        raise ValueError('未知策略或没有待处理切削')
    if policy=='never':
        return None
    # 有效性修复单独计数，不能冒充周期或质量触发收益。
    if not valid:
        return 'mandatory_validity_repair'
    if policy=='every':
        return 'every_cut'
    if final:
        return 'final_flush'
    if policy.startswith('period'):
        return 'period_elapsed' if pending>=int(policy[6:]) else None
    if pending>=ADAPTIVE['max_interval']:
        return 'maximum_interval'
    for angle,limit in ((10,ADAPTIVE['angle10_growth']),(1,ADAPTIVE['angle1_growth'])):
        key=f'angle_below_{angle}_deg'
        if current[key]['fraction']-baseline[key]['fraction']>=limit:
            return f'angle{angle}_growth'
    if current['angle_below_10_deg']['area_fraction']-baseline['angle_below_10_deg']['area_fraction']>=ADAPTIVE['area10_growth']:
        return 'angle10_area_growth'
    if current['total_faces']>=baseline['total_faces']*ADAPTIVE['face_growth_ratio']:
        return 'face_count_growth'
    return None
