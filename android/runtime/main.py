"""Private loopback runtime for the local Android app; no desktop launcher."""
from datetime import datetime, timedelta, timezone
from html import escape as h
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from validation import normalize_fields
import secrets
import shutil
from urllib.parse import parse_qs, urlencode, urlparse

from planner import mutate, rank, spent_on, goal_progress
from storage import empty_state, load_state, save_state, import_state, export_state
from holidays import holiday_name, YEARS
from i18n import localize_html, translate
from events import occurrences, event_cells, save_event, move_occurrence, cancel_occurrence
from timetable import (available_cells, blocks_from_cells, candidate, cells, clock, day_windows,
                       decide, initialize, occupied, preview_parts, record_clock, refresh, stamp, update_windows, move_block)

ROOT=Path(__file__).parent
TOKEN=secrets.token_urlsafe(24)
HKT=timezone(timedelta(hours=8))


def today_hk():
    return datetime.now(HKT).date()


def current_floor():
    now=datetime.now(HKT)
    return min(1440,((now.hour*60+now.minute+29)//30)*30)


def hours(value):
    return f'{value/60:g}'


def hidden(action,ident='',tab='map'):
    return f'<input type="hidden" name="token" value="{TOKEN}"><input type="hidden" name="action" value="{action}"><input type="hidden" name="id" value="{h(ident)}"><input type="hidden" name="tab" value="{tab}">'


def link(**values):
    return '/?'+h(urlencode(values))


def time_select(name,value='',label=''):
    options='<option value="">—</option>'+''.join(f'<option value="{stamp(m)}" {"selected" if value==m else ""}>{stamp(m)}</option>' for m in range(0,1441,30))
    return f'<select name="{name}" aria-label="{label}">{options}</select>'


def task_map(state,today,zoom):
    active=[t for t in state['tasks'] if not t['completed']]
    dots=''
    for category in (0,1,2,3):
        group=sorted((t for t in active if rank(t,today)==category),key=lambda t:t['id'])
        for index,t in enumerate(group):
            # Positions inside each category only spread dots apart; they are not numeric scores.
            columns=2 if len(active)<=12 else 4
            x=(595 if category in (0,1) else 100)+(index%columns)*(200 if columns==2 else 94)+(index//columns%2)*12
            y=(95 if category in (0,2) else 315)+(index//columns+1)*175/((len(group)+columns-1)//columns+1)+(index%columns)*8
            title=t['title'][:7]+('…' if len(t['title'])>7 else '')
            label_x,anchor=x+16,'start'
            invested,target,fraction=goal_progress(state,t)
            progress=f'<clipPath id="goal{category}_{index}"><circle cx="{x}" cy="{y}" r="7"/></clipPath><rect class="goal-fill" clip-path="url(#goal{category}_{index})" x="{x-8}" y="{y+7-14*fraction:g}" width="16" height="{14*fraction:g}"/>' if t['kind']=='goal' else ''
            dots+=f'<a class="map-point tone-{category} {"goal" if t["kind"]=="goal" else ""}" href="{link(tab="map",task=t["id"],zoom=zoom)}" aria-label="查看 {h(t["title"])}"><title data-user>{h(t["title"])}</title><circle class="point-hit" cx="{x}" cy="{y}" r="24"/><circle class="point-dot" cx="{x}" cy="{y}" r="7"/>{progress}<text data-user class="point-label" x="{label_x}" y="{y+5:g}" text-anchor="{anchor}">{h(title)}</text></a>'
    return f'''<section class="map-section"><div class="section-title"><div><span class="eyebrow">A LITTLE ROOM FOR EVERYTHING</span><h1>把心裡的事，輕輕放下。</h1></div><div class="zoom-tools" aria-label="地圖縮放"><a aria-label="縮小地圖" href="{link(tab='map',zoom=max(.75,zoom-.25))}">−</a><a aria-label="重設地圖縮放" href="{link(tab='map',zoom=1)}">{zoom*100:g}%</a><a aria-label="放大地圖" href="{link(tab='map',zoom=min(2,zoom+.25))}">＋</a></div></div><div class="map-viewport"><svg class="map-svg {'dense' if len(active)>12 else ''}" viewBox="0 0 1000 570" role="img" aria-label="任務座標圖，向右越重要，向上越緊急">
<defs><pattern id="paperdots" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="0.7" fill="#c8c2b6" opacity=".32"/></pattern></defs><rect width="1000" height="570" fill="url(#paperdots)"/>
<path class="wash wash-amber" d="M55 55 Q270 40 484 58 L480 278 Q280 285 55 276Z"/><path class="wash wash-rose" d="M518 57 Q750 42 945 65 L947 279 Q730 281 519 275Z"/><path class="wash wash-sage" d="M519 310 Q730 298 946 315 L943 520 Q740 532 520 515Z"/><path class="wash wash-gray" d="M55 310 Q280 300 480 313 L481 520 Q270 530 57 515Z"/>
<path class="axis axis-x" d="M34 292 Q270 286 500 294 T965 290 M950 281 L966 290 L951 301"/><path class="axis axis-y" d="M500 545 Q507 400 501 287 T504 25 M493 40 L504 24 L515 40"/>
<text class="axis-label" x="522" y="33">更緊急 ↑</text><text class="axis-label" x="831" y="558">更重要 →</text><text class="region-label" x="75" y="87">緊急・較不重要</text><text class="region-label" x="540" y="87">緊急・重要</text><text class="region-label" x="75" y="502">不緊急・較不重要</text><text class="region-label" x="540" y="502">不緊急・重要</text>{dots}</svg></div><div class="map-footer"><span>● 有 DDL　◔ 長期目標隨投入填滿</span><span>點一下看詳情 · 放大可看更多</span></div></section>'''


def proposal_panel(state):
    pending=state.get('proposal')
    if not pending:
        return ''
    tasks={t['id']:t for t in state['tasks']}
    _,old,new=preview_parts(state)
    names=sorted({b['task_id'] for b in old+new})
    rows=''
    for ident in names:
        before=[b for b in old if b['task_id']==ident]
        after=[b for b in new if b['task_id']==ident]
        if not before or not after:
            continue
        a,b=before[0],after[0]
        rows+=f'<li><b data-user>{h(tasks[ident]["title"])}</b><span>{a["date"][5:]} {stamp(a["start"])} → {b["date"][5:]} {stamp(b["start"])}</span></li>'
    return f'''<details class="move-panel"><summary>有前移建議，可稍後查看</summary><div class="move-panel-content"><div><span class="eyebrow">A LITTLE TIME OPENED UP</span><h2>空出一點時間，要把後面的事提前嗎？</h2><p>原安排仍可記錄與調整；半透明是建議位置，只有確認後才會採用。</p><ul>{rows}</ul></div><div class="move-actions"><form method="post" action="/">{hidden('confirm_move',tab='schedule')}<input type="hidden" name="revision" value="{pending['id']}"><button class="primary">確認前移</button></form><form method="post" action="/">{hidden('keep_plan',tab='schedule')}<input type="hidden" name="revision" value="{pending['id']}"><button class="secondary">保留原安排</button></form></div></div></details>'''


def render_calendar(state,today,styles,span='week',offset=0):
    days=[(today+timedelta(days=i)).isoformat() for i in (range(7) if span=='week' else [offset])]
    accepted,old,new=preview_parts(state)
    tasks={t['id']:t for t in state['tasks']}
    instances=occurrences(state,today,today+timedelta(days=6))
    private_cells=event_cells(state,today,'private')
    changed=set(cells(old))
    display=[(b,'solid origin' if set(cells([b])).intersection(changed) else 'solid') for b in state.get('calendar',[])]+[(b,'ghost destination') for b in new]
    styles.append(f'.clockbody,.day-column,.time-axis{{height:1440px}}.clockheads,.clockbody{{grid-template-columns:52px repeat({len(days)},minmax(0,1fr))}}')
    labels=''
    for minute in range(0,1441,60):
        labels+=f'<span class="time-label t{minute}">{stamp(minute)}</span>'
        styles.append(f'.t{minute}{{top:{minute}px}}')
    weekdays='一二三四五六日'
    heads='<div class="time-corner">GMT+8</div>'
    columns=''
    for day in days:
        dt=datetime.fromisoformat(day).date()
        holiday=holiday_name(dt)
        heads+=f'<a class="day-heading {"is-holiday" if holiday else ""} {"is-today" if day==today.isoformat() else ""}" href="{link(tab="schedule",span="day",day=(dt-today).days)}"><span>週{weekdays[dt.weekday()]}</span><b>{dt.day}</b><small>{h(holiday)}</small></a>'
        content=''
        for j,block in enumerate(b for b in instances if b['date']==day):
            uid=f'fixed{dt.day}_{j}'
            styles.append(f'#{uid}{{top:{block["start"]}px;height:{block["end"]-block["start"]}px}}')
            whole=block['category']=='private' and block['whole_end']<=1440
            title=block['title']
            repeat=' ↻' if block['repeat']!='none' else ''
            group='私人時間' if block['category']=='private' else '固定事項'
            content+=f'<a data-bubble class="event scheduled-event {block["category"]}-event" id="{uid}" href="{link(tab="schedule",event=block["event_id"],occurrence_date=block["occurrence_date"])}" data-entity="event" data-id="{h(block["event_id"])}" data-occurrence="{block["occurrence_date"]}" data-date="{day}" data-start="{block["start"]}" data-end="{block["end"]}" data-draggable="{str(whole).lower()}" draggable="false" aria-label="{h(title)} {day} {stamp(block["start"])}–{stamp(block["end"])} {group}"><span class="event-kind">{group}{repeat}</span><b data-user>{h(title)}</b><small>{stamp(block["start"])}–{stamp(block["end"])}</small></a>'
        for j,b in enumerate(blocks_from_cells({(day,m):'actual' for m in occupied(state,day)})):
            uid=f'actual{dt.day}_{j}'
            styles.append(f'#{uid}{{top:{b["start"]}px;height:{b["end"]-b["start"]}px}}')
            content+=f'<div class="event worked" id="{uid}"><b>已投入</b><small>{stamp(b["start"])}–{stamp(b["end"])}</small></div>'
        for index,(block,cls) in enumerate(display):
            if block['date']!=day:continue
            task=tasks[block['task_id']]
            uid=f'event{index}'
            styles.append(f'#{uid}{{top:{block["start"]}px;height:{block["end"]-block["start"]}px}}')
            description='原位置' if 'origin' in cls else '建議位置' if 'destination' in cls else '已確認安排'
            borrowed=bool(set(cells([block])).intersection(private_cells))
            caption=description if 'ghost' in cls or 'origin' in cls else '借用私人時間' if borrowed else '手動安排' if any(set(cells([block])).intersection(cells([pin])) for pin in state.get('pins',[])) else ''
            content+=f'<a data-bubble class="event tone-{rank(task,today)} {cls} {"borrowed" if borrowed else ""}" id="{uid}" href="{link(tab="schedule",task=task["id"],span=span,day=offset)}" data-entity="task" data-id="{h(task["id"])}" data-date="{day}" data-start="{block["start"]}" data-end="{block["end"]}" data-draggable="{str(cls.startswith("solid")).lower()}" draggable="false" aria-label="{h(task["title"])} {day} {stamp(block["start"])}–{stamp(block["end"])} {description}"><span class="event-kind">{caption}</span><b data-user>{h(task["title"])}</b><small>{stamp(block["start"])}–{stamp(block["end"])}</small></a>'
        columns+=f'<div class="day-column" data-date="{day}" data-first-minute="0">{content}</div>'
    total=len(available_cells(state,today,current_floor()).difference(cells(state.get('calendar',[]))))*30
    upcoming=[dict(b,title=tasks[b['task_id']]['title']) for b in state.get('calendar',[])]+instances
    first_up=next((b for b in sorted(upcoming,key=lambda b:(b['date'],b['start'])) if b['date']>today.isoformat() or b['end']>current_floor()),None)
    next_up=f'{first_up["date"][5:]} {stamp(first_up["start"])} · <span data-user>{h(first_up["title"])}</span>' if first_up else '暫時沒有安排'
    _,missing=candidate(state,today,current_floor())
    warning=''.join(f'<li><span data-user>{h(t["title"])}</span> · {hours(left)} h：'+{'overdue':'已逾期。','deadline_capacity':'期限前空檔不足。','outside_week':'尚未排入本週，期限在七天以外。'}[reason]+'</li>' for t,left,reason in missing)
    dates=''.join(f'<a class="{"selected" if i==offset else ""}" href="{link(tab="schedule",span="day",day=i)}">{(today+timedelta(days=i)).day}</a>' for i in range(7)) if span=='day' else ''
    jump=''.join(f'<button type="button" data-scroll-hour="{hour}">{label}</button>' for hour,label in [(0,'00–08'),(8,'08–16'),(16,'16–24'),(max(0,current_floor()//60-1),'現在')])
    guide='<div class="setup-hint">先把課程、輪班和睡眠／私人時間放進「事項」。未被佔用的時間才是可管理空檔；此處沒有預設上班時段。<a href="/?tab=events">去設定 →</a></div>' if not state.get('events') else ''
    calendar_warning='<p class="hint">目前只內置 2026–2027 香港公眾假期；其他年份僅按工作星期區分。</p>' if today.year not in YEARS or (today+timedelta(days=6)).year not in YEARS else ''
    return f'''<section class="calendar-section"><div class="section-title"><div><span class="eyebrow">FIRST LIFE, THEN THE GAPS</span><h1>{today.year} 年 {today.month} 月 <small>的時間留白</small></h1></div><div class="view-toggle"><a class="{'selected' if span=='week' else ''}" href="{link(tab='schedule',span='week')}">週總覽</a><a class="{'selected' if span=='day' else ''}" href="{link(tab='schedule',span='day',day=offset)}">單日</a></div></div>{guide}{calendar_warning}<div class="up-next"><span>接下來</span><b>{next_up}</b><a href="/?tab=events">事項與私人時間 ↗</a></div>{proposal_panel(state)}<div class="calendar-toolbar"><div class="calendar-legend"><span>■ DDL 任務</span><span>■ 固定事項</span><span>▧ 私人時間</span><span class="legend-ghost">半透明：待確認</span></div><div class="time-jump">{jump}</div></div><div class="day-picker">{dates}</div><p class="mobile-calendar-hint">週總覽可看七天；點日期可展開完整單日。</p><div class="calendar-scroll {'single-day' if span=='day' else ''}" data-initial-hour="{max(0,current_floor()//60-1)}"><div class="time-table"><div class="clockheads">{heads}</div><div class="clockbody"><div class="time-axis">{labels}</div>{columns}</div></div></div><p class="calendar-foot">00:00–24:00 · 半小時一格 · 點選展開氣泡，拖動調整<span>未佔用空檔 {hours(max(total,0))} h</span></p>{f'<details class="quiet-details"><summary>待留意的任務 · {len(missing)}</summary><ul>{warning}</ul></details>' if missing else ''}</section>'''


def task_bubble(state,today,ident,edit,tab,query=None):
    query=query or {}
    t=next((t for t in state['tasks'] if t['id']==ident),{})
    values=t if edit else {}
    if t and not edit:
        timeline=next((b for b in state.get('calendar',[]) if b['task_id']==ident and (not query.get('source_date') or b['date']==query['source_date'][0]) and (not query.get('source_start') or stamp(b['start'])==query['source_start'][0])),None)
        begin=timeline['start'] if timeline else min(current_floor(),1410)
        title=h(t['title'])
        if t['completed']:
            content=f'<h2 data-user>{title}</h2><p>✓ 已完成 · {t["completed_on"]}</p>'
        else:
            invested,target,fraction=goal_progress(state,t)
            goal_note=f'<p><span>累計投入</span> {hours(invested)} / {hours(target)} h · {fraction:.0%}</p><p class="hint">圓點填滿代表投入達到參考工時，不代表目標已完成。</p>' if t['kind']=='goal' else ''
            timing=f'DDL {t["due"]} · 剩餘 {hours(t["minutes"])} h' if t['kind']=='deadline' else '長期目標 · 有空再做'
            content=f'''<span data-user class="eyebrow">{h(t['course'])}</span><h2 data-user>{title}</h2><p>{timing}</p>{goal_note}<a class="edit-link" href="{link(tab=tab,edit=ident)}">編輯任務 ↗</a><hr><h3>這次做了多少？</h3><form method="post" action="/">{hidden('progress',ident,tab)}<label>實際開始時間{time_select('session_start',begin,'實際開始時間')}</label><label>實際投入（小時）<input type="number" name="actual" value="0.5" min="0.5" max="24" step="0.5" required></label><label class="check"><input name="finished" type="checkbox" value="yes">整份任務已完成</label><p class="hint">提前完成會釋放剩餘時間。其他任務若能前移，會先顯示建議，等你確認。</p><button class="primary">記錄投入</button></form><details class="quiet-details"><summary>其他操作</summary><form method="post" action="/">{hidden('delete',ident,tab)}<button class="text-button danger">刪除此任務</button></form></details>'''
    else:
        content=f'''<span class="eyebrow">JUST ONE SMALL THING</span><h2>{'編輯任務' if t else '記下一件事'}</h2><form method="post" action="/">{hidden('save',t.get('id',''),tab)}<label>任務名稱<input name="title" maxlength="100" value="{h(values.get('title',''))}" placeholder="例如：小組報告、日語 N1" required></label><label>類型<select name="kind"><option value="deadline">有 DDL 的任務</option><option value="goal" {'selected' if values.get('kind')=='goal' else ''}>有空再做的長期目標</option></select></label><label>分類（可留空）<input name="course" maxlength="60" value="{h(values.get('course',''))}"></label><div class="form-pair"><label>截止日期<input type="date" name="due" value="{values.get('due',(today+timedelta(days=3)).isoformat())}"></label><label>剩餘工時（h）<input type="number" name="hours" min="0.5" step="0.5" max="1000" value="{hours(values.get('minutes') or 60)}"></label></div><p class="hint">長期目標不用填期限或剩餘工時。</p><label class="goal-target">圓點填滿參考工時（h）<input name="target_hours" type="number" min="0.5" max="1000" step="0.5" value="{hours(values.get('target_minutes',600))}"></label><p class="hint goal-target">預設 10 小時，可自行修改；只用於圓點顯示，不會自動排程或標記完成。</p><label>最早開始日（可留空）<input name="start" type="date" value="{values.get('start','')}"></label><label>重要程度<select name="important"><option value="yes">重要</option><option value="no" {'selected' if values and not values['important'] else ''}>較不重要</option></select></label><button class="primary">{'儲存修改' if t else '加入任務'}</button></form>'''
    if t and not edit and not t['completed'] and timeline:
        content+=f'<details class="quiet-details"><summary>用表單調整這段安排</summary><form method="post" action="/">{hidden("move_block",ident,"schedule")}<input type="hidden" name="source_date" value="{timeline["date"]}"><input type="hidden" name="source_start" value="{stamp(timeline["start"])}"><input type="hidden" name="source_end" value="{stamp(timeline["end"])}"><label>移到日期<input type="date" name="new_date" value="{timeline["date"]}" required></label><label>開始時間{time_select("new_start",timeline["start"],"調整任務開始時間")}</label><button class="primary">移動這段任務</button></form></details>'
    content=content.replace('class="edit-link"','data-bubble class="edit-link"')
    return bubble_shell(content,ident,tab,'任務詳情')


def bubble_shell(content,ident='',tab='map',label='事項詳情'):
    return f'<section class="anchor-bubble" role="dialog" aria-label="{label}" data-anchor-id="{h(ident)}" tabindex="-1"><div class="bubble-arrow"></div><a data-close-bubble class="bubble-close" aria-label="關閉氣泡" href="{link(tab=tab)}">×</a><div class="bubble-body">{content}</div></section>'


def event_bubble(state,today,ident='',tab='events',query=None):
    e=next((item for item in state.get('events',[]) if item['id']==ident),{})
    weekdays='一二三四五六日'
    choices=''.join(f'<label><input name="weekdays" type="checkbox" value="{i}" {"checked" if i in e.get("weekdays",[today.weekday()]) else ""}>週{weekdays[i]}</label>' for i in range(7))
    options=''.join(f'<option value="{key}" {"selected" if e.get("repeat","none")==key else ""}>{title}</option>' for key,title in [('none','不重複'),('daily','每天'),('weekly','每週'),('monthly','每月同日'),('workdays','每工作日'),('holidays','每假日')])
    end=e.get('end',600)
    end=end-1440 if end>1440 else end
    content=f'''<span class="eyebrow">LIFE COMES FIRST</span><h2>{'編輯事項系列' if e else '留一段固定的時間'}</h2><form method="post" action="/">{hidden('save_event',e.get('id',''),tab)}<label>事項名稱<input name="title" maxlength="100" value="{h(e.get('title',''))}" placeholder="例如：Python 課、夜班、睡眠" required></label><label>類型<select name="category"><option value="fixed">固定事項（課程／工作／出差）</option><option value="private" {'selected' if e.get('category')=='private' else ''}>私人時間（睡眠／休息／陪伴）</option></select></label><label>開始日期<input type="date" name="date" value="{e.get('date',today.isoformat())}" required></label><div class="form-pair"><label>開始時間{time_select('event_start',e.get('start',540),'事項開始時間')}</label><label>結束時間{time_select('event_end',end,'事項結束時間')}</label></div><p class="hint">結束早於開始代表跨午夜；全天請用 00:00–24:00。</p><label>重複<select name="repeat">{options}</select></label><fieldset class="weekday-picker"><legend>每週的這些日子</legend>{choices}</fieldset><label>重複直到（可留空）<input type="date" name="until" value="{e.get('until','')}"></label><p class="hint">每月若沒有同一天，該月略過。儲存會更新整個系列，並保留已移除的日期。固定事項不能拖動或單次移動。</p><button class="primary">{'儲存事項系列' if e else '加入事項'}</button></form>'''
    if e:
        original=(query or {}).get('occurrence_date',[e['date']])[0]
        override=e['overrides'].get(original,{})
        selected_date=override.get('date',original)
        selected_start=override.get('start',e['start'])
        if e['category']=='private':
            content+=f'<details class="quiet-details"><summary>只調整這一次</summary><form method="post" action="/">{hidden("move_event",ident,"schedule")}<input type="hidden" name="occurrence_date" value="{h(original)}"><label>移到日期<input type="date" name="new_date" value="{h(selected_date)}" required></label><label>開始時間{time_select("new_start",selected_start,"這次事項開始時間")}</label><p class="hint">保留原長度，只改本次日期與時間；其他重複日期不變。</p><button class="primary">移動這一次事項</button></form></details>'
        content+=f'<details class="quiet-details"><summary>只移除這一次</summary><form method="post" action="/">{hidden("cancel_occurrence",ident,tab)}<label>移除哪一天的事項<input type="date" name="occurrence_date" value="{h(original)}" required></label><p class="hint">只移除此日期開始的那一次，其他日期照常；跨午夜的部分會一併移除。</p><button class="text-button danger">移除這一次事項</button></form></details>'
        content+=f'<details class="quiet-details"><summary>移除這個系列</summary><form method="post" action="/">{hidden("delete_event",ident,tab)}<button class="text-button danger">刪除整個事項系列</button></form></details>'
    return bubble_shell(content,ident,tab,'事項詳情')


def events_panel(state,today):
    groups=''
    labels={'none':'單次','daily':'每天','weekly':'每週','monthly':'每月','workdays':'每工作日','holidays':'每假日'}
    for category,title,subtitle in [('fixed','固定事項','課程、輪班、出差與已約定的事情。'),('private','私人時間','睡眠、休息、家庭與不想被任務佔用的時段。')]:
        rows=''
        for e in state.get('events',[]):
            if e['category']!=category:continue
            end=stamp(e['end']%1440) if e['end']>1440 else stamp(e['end'])
            weekly=' · '+' / '.join('週'+'一二三四五六日'[i] for i in e['weekdays']) if e['repeat']=='weekly' else ''
            rows+=f'<a data-bubble class="routine-row {category}-row" data-id="{h(e["id"])}" href="{link(tab="events",event=e["id"])}"><span class="routine-icon">{"◷" if category=="fixed" else "☾"}</span><span><b data-user>{h(e["title"])}</b><small>{e["date"]} 起 · {labels[e["repeat"]]}{weekly} · {stamp(e["start"])}–{end}{" 翌日" if e["end"]>1440 else ""}</small></span><span>↗</span></a>'
        groups+=f'<section class="routine-group"><div><h2>{title}</h2><p>{subtitle}</p></div>{rows or "<p class=empty-routine>還沒有設定，按右上角加入。</p>"}</section>'
    return f'''<section class="routines-section"><div class="section-title"><div><span class="eyebrow">MAKE THE FOUNDATION FIRST</span><h1>先放生活，再安排空檔。</h1></div><a data-bubble class="add-button" href="/?tab=events&event_new=1">＋ 加入事項</a></div><p class="routine-intro">沒有預設 08:00–16:00 的工作時間。你填入的課程、班次及私人時間會先被保留，其餘才是可規劃空檔。</p><form class="private-policy" method="post" action="/">{hidden('save_policy',tab='events')}<label class="check"><input type="checkbox" name="borrow_private" value="yes" {'checked' if state.get('borrow_private') else ''}>允許緊急 DDL 借用私人時間</label><p>預設關閉。開啟後，只在普通空檔不足、且期限在三天內時借用；固定事項始終不能被佔用，借用的格子會標示出來。</p><button class="secondary">儲存私人時間設定</button></form>{groups}{settings_panel(state,today)}</section>'''


def settings_panel(state,today):
    language=state.get('language','zh-Hant')
    options=''.join(f'<option value="{key}" {"selected" if language==key else ""}>{label}</option>' for key,label in [('zh-Hant','繁體中文'),('zh-Hans','简体中文'),('en','English')])
    weekdays=''.join(f'<label class="check"><input type="checkbox" name="workdays" value="{i}" {"checked" if i in state.get("workdays",[0,1,2,3,4]) else ""}>週{"一二三四五六日"[i]}</label>' for i in range(7))
    return f'''<section class="settings-card"><h2>偏好設定</h2><form method="post" action="/">{hidden('save_settings',tab='events')}<label>語言<select name="language">{options}</select></label><h3>我的工作星期</h3><div class="workday-picker">{weekdays}</div><p>工作日＝選定星期扣除香港公眾假期；其餘為假日。此設定只影響重複規則，不會封鎖整天。</p><p>已內置 2026–2027 香港公眾假期，週日亦為公眾假期。其他年份僅按工作星期區分，請自行核對。</p><button class="secondary">儲存設定</button></form><p><a href="https://www.gov.hk/tc/about/abouthk/holiday/index.htm" target="_blank" rel="noopener">香港政府公眾假期資料 ↗</a></p></section><section class="settings-card"><h2>資料導入／導出</h2><p>備份包含任務、投入紀錄、事項、手動安排及偏好設定。網頁版與 Android 使用相同 JSON 格式。</p><a class="add-button" id="export-data" href="/export" download="Planwise-backup.json">導出 JSON 備份</a><form id="import-form" method="post" action="/">{hidden('import_data',tab='events')}<label>選擇 JSON 備份<input id="import-file" type="file" accept=".json,application/json"></label><label>備份內容<textarea id="backup-json" name="backup_json" rows="4" maxlength="2000000" placeholder="也可貼上 JSON 備份內容" required></textarea></label><p id="import-preview" role="status"></p><label class="check"><input type="checkbox" name="replace_confirm" value="yes" required>我確認以此備份取代目前資料</label><p>導入會取代目前資料；先驗證檔案並自動備份原資料。建議先導出，方便還原。</p><button class="primary">驗證並導入</button></form></section>'''


def render(state,notice='',edit='',demo=False,query=None):
    today=today_hk()
    query=query or {}
    tab=query.get('tab',['map'])[0]
    if tab not in ('map','schedule','events'):tab='map'
    try:
        zoom=max(.75,min(2,float(query.get('zoom',['1'])[0])))
        if not zoom==zoom:
            zoom=1
        offset=max(0,min(6,int(query.get('day',['0'])[0])))
    except ValueError:
        zoom,offset=1,0
    styles=[f'.map-svg{{width:{zoom*100:g}%}}'+('.map-viewport{max-height:none}' if zoom<=1 else '')]
    active=[t for t in state['tasks'] if not t['completed']]
    completed=[t for t in state['tasks'] if t['completed']]
    body=events_panel(state,today) if tab=='events' else render_calendar(state,today,styles,query.get('span',['week'])[0] if query.get('span',['week'])[0]=='day' else 'week',offset) if tab=='schedule' else task_map(state,today,zoom)
    if tab=='map' and state.get('proposal'):
        body='<a class="pending-link" href="/?tab=schedule">有前移建議，可稍後查看 →</a>'+body
    history=''.join(f'<a href="{link(tab=tab,task=t["id"])}">✓ <span data-user>{h(t["title"])}</span><span>{t["completed_on"]}</span></a>' for t in completed)
    drawer=''
    ident=query.get('task',[''])[0]
    edit=edit or query.get('edit',[''])[0]
    if ident or edit or query.get('add'):
        drawer=task_bubble(state,today,edit or ident,bool(edit or query.get('add')),tab,query)
    if query.get('event') or query.get('event_new'):
        drawer=event_bubble(state,today,query.get('event',[''])[0],tab,query)
    html=f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="language" content="{state.get('language','zh-Hant')}"><meta name="csrf-token" content="{TOKEN}"><title>留白 Planwise · 任務與時間</title><link rel="stylesheet" href="/style.css"><script src="/app.js" defer></script><style nonce="{TOKEN}">{''.join(styles)}</style></head><body><header><a class="brand" href="/">◫ <b>留白</b><span>PLANWISE</span></a><nav aria-label="主要分頁"><a class="{'active' if tab=='map' else ''}" href="/?tab=map">任務地圖</a><a class="{'active' if tab=='schedule' else ''}" href="/?tab=schedule">時間行程</a><a class="{'active' if tab=='events' else ''}" href="/?tab=events">事項與設定</a></nav><a data-bubble class="add-button" href="{link(tab=tab,add=1)}">＋ <span>記一件事</span></a></header><main><div class="context-line"><span>{today.month} 月 {today.day} 日，週{'一二三四五六日'[today.weekday()]}</span><span>{sum(t['kind']=='deadline' for t in active)} 件待做 · {sum(t['kind']=='goal' for t in active)} 個長期想做的事</span></div>{f'<div class="notice" role="alert">{h(notice)}</div>' if notice else ''}{body}<details class="history"><summary>已完成 · {len(completed)}</summary>{history or '<p>完成的事會留在這裡。</p>'}</details><footer><span>留白，給接下來的自己。</span><span>{'示例模式' if demo else '本機保存'} · 半小時剛剛好</span></footer></main>{drawer}<div class="ui-toast" role="status" aria-live="polite" hidden></div></body></html>'''
    return localize_html(html,state.get('language','zh-Hant'))


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        route=urlparse(self.path)
        if route.path=='/style.css':
            self.reply(200,(ROOT/'style.css').read_text(encoding='utf-8'),'text/css')
        elif route.path=='/app.js':
            self.reply(200,(ROOT/'app.js').read_text(encoding='utf-8'),'text/javascript')
        elif route.path=='/bubble':
            query=parse_qs(route.query)
            tab=query.get('tab',['map'])[0]
            if tab not in ('map','schedule','events'):tab='map'
            if query.get('event') or query.get('event_new'):
                content=event_bubble(self.server.state,today_hk(),query.get('event',[''])[0],tab,query)
            else:
                content=task_bubble(self.server.state,today_hk(),query.get('edit',query.get('task',['']))[0],bool(query.get('edit') or query.get('add')),tab,query)
            self.reply(200,localize_html(content,self.server.state.get('language','zh-Hant')))
        elif route.path=='/translations':
            self.reply(200,json.dumps(__import__('i18n').client_messages(self.server.state.get('language','zh-Hant')),ensure_ascii=False),'application/json')
        elif route.path=='/export':
            self.reply(200,export_state(self.server.state),'application/json',attachment='Planwise-backup.json')
        elif route.path=='/':
            initialize(self.server.state,today_hk(),current_floor())
            self.reply(200,render(self.server.state,self.server.notice,demo=self.server.demo,query=parse_qs(route.query)))
        else:
            self.reply(404,'Not found')

    def do_POST(self):
        if self.path!='/':
            self.reply(404,'Not found')
            return
        if self.server.read_only:
            self.reply(503,render(self.server.state,self.server.notice,demo=self.server.demo))
            return
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=8000000:
                raise ValueError('表單大小不正確。')
            data=normalize_fields(parse_qs(self.rfile.read(length).decode()))
            if not secrets.compare_digest(data.get('token',[''])[0],TOKEN):
                self.reply(403,translate('頁面已過期，請重新整理。',self.server.state.get('language','zh-Hant')))
                return
            updated=json.loads(json.dumps(self.server.state))
            initialize(updated,today_hk(),current_floor())
            action=data.get('action',[''])[0]
            if action=='import_data':
                if data.get('replace_confirm',[''])[0]!='yes':raise ValueError('請先確認以備份取代目前資料。')
                updated=import_state(data.get('backup_json',[''])[0])
                initialize(updated,today_hk(),current_floor())
                if self.server.data_path.exists():
                    backup=self.server.data_path.with_name(self.server.data_path.name+'.before-import-'+datetime.now(HKT).strftime('%Y%m%d-%H%M%S')+'-'+secrets.token_hex(3)+'.bak')
                    shutil.copy2(self.server.data_path,backup)
                notice='資料已導入，原有資料已另存備份。'
            elif action=='save_settings':
                language=data.get('language',[''])[0]
                if language not in ('zh-Hant','zh-Hans','en'):raise ValueError('語言設定不正確。')
                try:workdays=sorted({int(day) for day in data.get('workdays',[])})
                except ValueError:raise ValueError('工作日設定不正確。') from None
                if any(day not in range(7) for day in workdays):raise ValueError('工作日設定不正確。')
                changed=workdays!=updated.get('workdays',[0,1,2,3,4])
                updated.update(language=language,workdays=workdays)
                if changed:refresh(updated,today_hk(),propose=True,not_before=current_floor())
                notice='設定已儲存。'
            elif action in ('confirm_move','keep_plan'):
                decide(updated,action,data.get('revision',[''])[0],today_hk())
                notice='已確認前移，新位置已成為正式安排。' if action=='confirm_move' else '已保留原安排，空出的時間留白。'
            else:
                if action=='move_block':
                    move_block(updated,data,today_hk(),current_floor())
                    refresh(updated,today_hk(),propose=True,not_before=current_floor())
                elif action=='move_event':
                    move_occurrence(updated,data,today_hk())
                    refresh(updated,today_hk(),propose=True,not_before=current_floor())
                elif action=='cancel_occurrence':
                    cancel_occurrence(updated,data)
                    refresh(updated,today_hk(),propose=True,not_before=current_floor())
                elif action in ('save_event','delete_event'):
                    save_event(updated,data)
                    refresh(updated,today_hk(),propose=True,not_before=current_floor())
                elif action=='save_policy':
                    updated['borrow_private']=data.get('borrow_private',[''])[0]=='yes'
                    refresh(updated,today_hk(),propose=True,not_before=current_floor())
                elif action=='windows':
                    update_windows(updated,data,today_hk())
                    refresh(updated,today_hk(),propose=True,not_before=current_floor())
                else:
                    session=record_clock(updated,data,today_hk()) if action=='progress' else None
                    mutate(updated,data,today_hk())
                    if session:
                        updated['work_log'][-1].update(start=session[0],end=session[1])
                    refresh(updated,today_hk(),propose=True,not_before=current_floor())
                notice='已儲存，原安排保留；你可以繼續操作，或查看新的前移建議。' if updated.get('proposal') else '已儲存。'
                if action=='cancel_occurrence':notice='已移除這一次事項，其他日期照常；釋放的時間已留白。'
                elif action=='move_event':notice='已調整這一次事項，其他重複日期不變，空檔已重新計算。'
                elif action=='move_block':notice='已移動這段任務，手動位置會保留；固定事項與私人時間已檢查。'
            save_state(self.server.data_path,updated)
            self.server.state,self.server.notice=updated,notice
        except (ValueError,UnicodeError) as exc:
            if self.headers.get('Accept')=='application/json':
                self.reply(400,json.dumps(dict(ok=False,error=translate(str(exc),self.server.state.get('language','zh-Hant'))),ensure_ascii=False),'application/json')
                return
            self.reply(400,render(self.server.state,f'未儲存：{exc}',demo=self.server.demo,query={'tab':[data.get('tab',['schedule'])[0] if 'data' in locals() else 'schedule']}))
            return
        except OSError:
            if self.headers.get('Accept')=='application/json':
                self.reply(500,json.dumps(dict(ok=False,error=translate('儲存失敗，原有資料未更改。',self.server.state.get('language','zh-Hant'))),ensure_ascii=False),'application/json')
                return
            self.reply(500,render(self.server.state,'儲存失敗，原有資料未更改。',demo=self.server.demo))
            return
        tab=data.get('tab',['map'])[0]
        if tab not in ('map','schedule','events'):tab='map'
        if self.headers.get('Accept')=='application/json':
            self.reply(200,json.dumps(dict(ok=True,redirect='/?tab='+tab,message=translate(notice,self.server.state.get('language','zh-Hant'))),ensure_ascii=False),'application/json')
            return
        self.send_response(303)
        self.send_header('Location','/?tab='+tab)
        self.end_headers()

    def reply(self,code,body,content_type='text/html',attachment=''):
        payload=body.encode()
        self.send_response(code)
        self.send_header('Content-Type',content_type+'; charset=utf-8')
        self.send_header('Content-Length',str(len(payload)))
        self.send_header('Cache-Control','no-store')
        if attachment:self.send_header('Content-Disposition','attachment; filename="'+attachment+'"')
        self.send_header('Content-Security-Policy',f"default-src 'self'; style-src 'self' 'nonce-{TOKEN}'; script-src 'self'; form-action 'self'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(payload)


def make_server(path,port=0,demo=False):
    server=HTTPServer(('127.0.0.1',port),Handler)
    server.data_path,server.demo,server.read_only=Path(path),demo,False
    try:
        server.state,server.notice=load_state(server.data_path,today_hk())
        initialize(server.state,today_hk(),current_floor())
    except ValueError as exc:
        server.state,server.notice,server.read_only=empty_state(),str(exc),True
    return server
