"""Editorial notes only; all playback still comes from audio/editing.events."""
from common import read_json, write_json

ROLES = ('ambience', 'sfx', 'music', 'silence')


def draft(project):
    return {'version': 1, 'beats': [
        {'beat': b['id'], **{role: {'decision': 'pending', 'reason': '', 'refs': []}
                              for role in ROLES}} for b in project['beats']]}


def warnings(project):
    plan = project.get('sound_design')
    if plan is None:
        return ['音設計が未記入です。sound-plan --initで下書きを作り、現場音・SE・音楽・静けさの採否を決めてください']
    if not isinstance(plan, dict) or plan.get('version') != 1 or not isinstance(plan.get('beats'), list):
        raise ValueError('sound_designはversion:1とbeats配列が必要です')
    beat_ids = {b['id'] for b in project['beats']}
    audio = {a.get('id'): a for a in project.get('audio', []) if a.get('id')}
    events = {e['id']: e for e in project.get('editing', {}).get('events', [])}
    seen, result = set(), []
    for row in plan['beats']:
        if not isinstance(row, dict) or row.get('beat') not in beat_ids or row['beat'] in seen:
            raise ValueError('sound_design.beatsのbeatは既存IDで重複不可です')
        bid = row['beat']; seen.add(bid)
        for role in ROLES:
            item = row.get(role, {'decision': 'pending'})
            if not isinstance(item, dict) or item.get('decision') not in {'use', 'omit', 'pending'}:
                raise ValueError(f'{bid}.{role}: decisionはuse/omit/pendingです')
            state = item['decision']; reason = item.get('reason', '')
            refs = item.get('refs', [])
            if not isinstance(reason, str) or not isinstance(refs, list) or any(not isinstance(x, str) for x in refs):
                raise ValueError(f'{bid}.{role}: reasonは文字列、refsは文字列配列です')
            if state == 'pending':
                result.append(f'音設計未決定: {bid}/{role}')
            elif not reason.strip():
                result.append(f'音の採否の理由が未記入: {bid}/{role}')
            if state == 'omit' and refs:
                result.append(f'不採用なのに音参照があります: {bid}/{role}')
            if state == 'use' and role != 'silence' and not refs:
                result.append(f'採用した音が未配置: {bid}/{role} (refsが空です)')
            for ref in refs:
                kind, _, key = ref.partition(':')
                obj = audio.get(key) if kind == 'audio' else events.get(key) if kind == 'event' else None
                if obj is None:
                    result.append(f'音参照が存在しません: {bid}/{role}/{ref}')
                elif kind == 'event' and (not obj.get('audio') or obj.get('intensity', .5) == 0):
                    result.append(f'参照した演出に有効なSEがありません: {ref}')
                elif obj.get('volume', 1) == 0 or obj.get('audio', {}).get('volume', 1) == 0:
                    result.append(f'採用した音の音量が0です: {ref}')
    for bid in sorted(beat_ids - seen):
        result.append(f'音設計のbeatが未記入: {bid}')
    return result


def inspect_plan(root, initialize=False):
    path = root / 'project.json'
    project = read_json(path)
    if initialize and 'sound_design' not in project:
        project['sound_design'] = draft(project)
        write_json(path, project)
    return {'sound_design': project.get('sound_design'), 'warnings': warnings(project)}
