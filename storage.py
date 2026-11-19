"""Versioned local JSON storage. Never overwrite unreadable input."""
from datetime import date, timedelta
import json
from pathlib import Path
import secrets
import shutil
from events import validate_events


def empty_state():
    return dict(version=2, tasks=[], capacity={}, work_log=[], availability={}, calendar=[], proposal=None, calendar_day='', events=[], borrow_private=False, time_model='free', pins=[], calendar_model='', language='zh-Hant', workdays=[0,1,2,3,4])


def seed(today):
    state = empty_state()
    examples = [('課堂短評', '本週作業', 0, 1, False), ('Python 小組報告', 'INT6181', 2, 2, True), ('研究方法簡報', 'Research Methods', 5, 3, True), ('期末研究計劃', 'AI & EduTech', 12, 8, True)]
    for title, course, delta, hours, important in examples:
        state['tasks'].append(dict(id=secrets.token_hex(8), title=title, course=course, kind='deadline', start='', due=(today + timedelta(days=delta)).isoformat(), minutes=hours*60, important=important, completed=False, completed_on=''))
    for title, start in [('考駕照：了解報名流程', ''), ('日語 N1：假期開始準備', (today + timedelta(days=14)).isoformat())]:
        state['tasks'].append(dict(id=secrets.token_hex(8), title=title, course='長期成長', kind='goal', start=start, due='', minutes=0, important=True, completed=False, completed_on=''))
    state['capacity'] = {(today + timedelta(days=i)).isoformat(): value*60 for i, value in enumerate([2, 1, 2, 1, 2, 2, 1])}
    return state


def migrate(raw):
    if not isinstance(raw, dict) or raw.get('version', 1) not in (1, 2):
        raise ValueError('不支援的資料格式。')
    legacy = raw.get('version', 1) == 1
    if not isinstance(raw.get('tasks'), list) or not isinstance(raw.get('capacity'), dict):
        raise ValueError('缺少任務或可用時間資料。')
    state = empty_state()
    for item in raw['tasks']:
        t = dict(item)
        if legacy:
            t.update(kind='deadline', start='', completed=t['minutes'] == 0, completed_on='')
            t['minutes'] = ((t['minutes'] + 29) // 30) * 30
        if t['kind'] not in ('deadline', 'goal') or not isinstance(t['important'], bool) or not isinstance(t['completed'], bool):
            raise ValueError('任務欄位不正確。')
        if not all(isinstance(t[k], str) for k in ('id', 'title', 'course', 'start', 'due', 'completed_on')) or not t['id'] or not t['title']:
            raise ValueError('任務名稱或識別碼不正確。')
        if type(t['minutes']) is not int or not 0 <= t['minutes'] <= 60000 or t['minutes'] % 30:
            raise ValueError('任務工時不正確。')
        target=t.get('target_minutes',600)
        if type(target) is not int or not 30<=target<=60000 or target%30:
            raise ValueError('圓點參考工時不正確。')
        if 'target_minutes' in t:t['target_minutes']=target
        if t['kind'] == 'deadline':
            t['due'] = date.fromisoformat(t['due']).isoformat()
            if not t['completed'] and t['minutes'] == 0:
                raise ValueError('未完成的 DDL 任務必須有剩餘工時。')
        elif t['due'] or t['minutes']:
            raise ValueError('長期目標不應有 DDL 或剩餘工時。')
        for key in ('start', 'completed_on'):
            if t[key]:
                t[key] = date.fromisoformat(t[key]).isoformat()
        if t['kind'] == 'deadline' and t['start'] and t['start'] > t['due']:
            raise ValueError('開始日晚於截止日。')
        if any(old['id'] == t['id'] for old in state['tasks']):
            raise ValueError('任務識別碼重複。')
        state['tasks'].append(t)
    for day, amount in raw['capacity'].items():
        day = date.fromisoformat(day).isoformat()
        if type(amount) is not int or not 0 <= amount <= 1440:
            raise ValueError('可用時間不正確。')
        state['capacity'][day] = amount // 30 * 30 if legacy else amount
        if state['capacity'][day] % 30:
            raise ValueError('可用時間須以半小時為單位。')
    logs = raw.get('work_log', [])
    if not isinstance(logs, list):
        raise ValueError('投入紀錄不正確。')
    for row in logs:
        row = dict(row)
        row['date'] = date.fromisoformat(row['date']).isoformat()
        if not isinstance(row['task_id'], str) or not isinstance(row['title'], str) or type(row['finished']) is not bool or type(row['minutes']) is not int or not 30 <= row['minutes'] <= 1440 or row['minutes'] % 30:
            raise ValueError('投入紀錄欄位不正確。')
        if sum(old['minutes'] for old in state['work_log'] if old['date'] == row['date']) + row['minutes'] > 1440:
            raise ValueError('當日投入超過 24 小時。')
        if 'start' in row or 'end' in row:
            if any(type(row.get(k)) is not int or row[k] % 30 for k in ('start','end')) or not 0 <= row['start'] < row['end'] <= 1440 or row['end']-row['start']!=row['minutes']:
                raise ValueError('投入時間不正確。')
        state['work_log'].append(row)
    availability=raw.get('availability',{})
    if not isinstance(availability,dict):
        raise ValueError('可用時段格式不正確。')
    for day,windows in availability.items():
        day=date.fromisoformat(day).isoformat()
        if not isinstance(windows,list) or len(windows)>2:
            raise ValueError('可用時段格式不正確。')
        for window in windows:
            if not isinstance(window,list) or len(window)!=2 or any(type(v) is not int or v%30 for v in window) or not 0<=window[0]<window[1]<=1440:
                raise ValueError('可用時段須以半小時為單位。')
        windows=sorted(windows)
        if any(a[1]>b[0] for a,b in zip(windows,windows[1:])):
            raise ValueError('可用時段重疊。')
        state['availability'][day]=windows
        state['capacity'][day]=sum(b-a for a,b in windows)
    def checked_blocks(blocks):
        if not isinstance(blocks,list):
            raise ValueError('行程格式不正確。')
        occupied=set()
        for block in blocks:
            date.fromisoformat(block['date'])
            if not any(t['id']==block['task_id'] for t in state['tasks']) or any(type(block[k]) is not int or block[k]%30 for k in ('start','end')) or not 0<=block['start']<block['end']<=1440:
                raise ValueError('行程時段不正確。')
            positions={(block['date'],m) for m in range(block['start'],block['end'],30)}
            if occupied.intersection(positions):
                raise ValueError('行程重疊。')
            occupied.update(positions)
        return blocks
    state['calendar']=checked_blocks(raw.get('calendar',[]))
    state['calendar_day']=raw.get('calendar_day','')
    if state['calendar_day']:
        date.fromisoformat(state['calendar_day'])
    proposal=raw.get('proposal')
    if proposal is not None:
        if not isinstance(proposal,dict) or not isinstance(proposal['id'],str):
            raise ValueError('前移建議格式不正確。')
        date.fromisoformat(proposal['date'])
        checked_blocks(proposal['after'])
    state['proposal']=proposal
    state['events']=validate_events(raw.get('events',[]))
    if type(raw.get('borrow_private',False)) is not bool or raw.get('time_model','free') not in ('free','custom'):
        raise ValueError('私人時間或規劃模式不正確。')
    state['borrow_private']=raw.get('borrow_private',False)
    state['time_model']=raw.get('time_model','free')
    state['pins']=checked_blocks(raw.get('pins',[]))
    state['calendar_model']=raw.get('calendar_model','')
    language=raw.get('language','zh-Hant')
    if language not in ('zh-Hant','zh-Hans','en'):raise ValueError('語言設定不正確。')
    workdays=raw.get('workdays',[0,1,2,3,4])
    if not isinstance(workdays,list) or any(type(v) is not int or v not in range(7) for v in workdays):raise ValueError('工作日設定不正確。')
    state.update(language=language,workdays=sorted(set(workdays)))
    return state


def load_state(path, today):
    if not path.exists():
        return seed(today), ''
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
        state = migrate(raw)
    except (ValueError, KeyError, TypeError, AttributeError, OverflowError, RecursionError, OSError) as exc:
        raise ValueError('無法讀取資料，原檔已保留。請先備份並修復資料檔，或將其改名後重新啟動。') from exc
    message = '舊資料已讀入；舊有 15 分鐘工時向上取整、可用時間向下取整至半小時。首次儲存會保留舊版備份。' if raw.get('version', 1) == 1 else ''
    return state, message


def save_state(path, state):
    if path.exists():
        raw = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(raw, dict):
            raise ValueError('原資料格式已改變，請先檢查檔案後再儲存。')
        if raw.get('version', 1) == 1:
            backup = path.with_suffix('.v1.bak')
            if not backup.exists():
                shutil.copy2(path, backup)
        if raw.get('calendar_model')!='events-v4':
            backup=path.with_suffix('.pre-events.bak')
            if not backup.exists():shutil.copy2(path,backup)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def import_state(text):
    """Validate the complete replacement before touching the live file."""
    try:
        raw=json.loads(text)
        if isinstance(raw,dict) and raw.get('format')=='planwise-backup':
            if raw.get('backup_version')!=1:raise ValueError()
            raw=raw['data']
        return migrate(raw)
    except (ValueError,KeyError,TypeError,AttributeError,OverflowError,RecursionError):
        raise ValueError('備份檔格式不正確，原有資料未更改。') from None


def export_state(state):
    return json.dumps(dict(format='planwise-backup',backup_version=1,data=state),ensure_ascii=False,indent=2)
