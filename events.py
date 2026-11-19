"""Fixed appointments and protected personal time, expanded only for the visible dates."""
from datetime import date, timedelta
import secrets
from validation import parse_date
from holidays import is_workday
from time_slots import (EVENT_INVALID_TIME, EVENT_MISSING_TIME,
                        TIMETABLE_INVALID_TIME, TIMETABLE_MISSING_TIME, parse_clock)


def clock(value):
    return parse_clock(value, EVENT_MISSING_TIME, EVENT_INVALID_TIME)


def matches(event,day,workdays=(0,1,2,3,4)):
    origin=date.fromisoformat(event['date'])
    if day<origin or (event['until'] and day>date.fromisoformat(event['until'])):
        return False
    rule=event['repeat']
    if rule in ('workdays','holidays'):
        return is_workday(day,workdays) == (rule=='workdays')
    return (day==origin if rule=='none' else True if rule=='daily' else day.weekday() in event['weekdays'] if rule=='weekly' else day.day==origin.day)


def occurrences(state,first,last):
    result=[]
    for event in state.get('events',[]):
        origins={first+timedelta(days=i-1) for i in range((last-first).days+2)}
        origins.update(date.fromisoformat(key) for key in event['overrides'])
        for origin in sorted(origins):
            if not matches(event,origin,state.get("workdays",[0,1,2,3,4])):
                continue
            override=event['overrides'].get(origin.isoformat(),{})
            if override.get('cancelled'):
                continue
            day=date.fromisoformat(override.get('date',origin.isoformat()))
            start,end=override.get('start',event['start']),override.get('end',event['end'])
            segments=[(day,start,min(end,1440))]
            if end>1440:
                segments.append((day+timedelta(days=1),0,end-1440))
            for current,a,b in segments:
                if first<=current<=last and a<b:
                    result.append(dict(event_id=event['id'],occurrence_date=origin.isoformat(),date=current.isoformat(),start=a,end=b,title=event['title'],category=event['category'],whole_start=start,whole_end=end,whole_date=day.isoformat(),repeat=event['repeat']))
    return sorted(result,key=lambda item:(item['date'],item['start'],item['event_id']))


def event_cells(state,today,category):
    return {(block['date'],m) for block in occurrences(state,today,today+timedelta(days=6)) if block['category']==category for m in range(block['start'],block['end'],30)}


def save_event(state,data):
    def field(key):return data.get(key,[''])[0].strip()
    ident=field('id')
    old=next((e for e in state['events'] if e['id']==ident),None)
    if ident and old is None:
        raise ValueError('找不到這個事項。')
    if field('action')=='delete_event':
        if old is None:raise ValueError('找不到這個事項。')
        state['events'].remove(old)
        return
    title,category,rule=field('title'),field('category'),field('repeat')
    if not title or len(title)>100 or category not in ('fixed','private') or rule not in ('none','daily','weekly','monthly','workdays','holidays'):
        raise ValueError('請填寫事項名稱，並選擇正確的類型及重複規則。')
    day=parse_date(field('date')).isoformat()
    until=parse_date(field('until')).isoformat() if field('until') else ''
    if until and until<day:
        raise ValueError('重複結束日期不能早於開始日期。')
    begin,end=clock(field('event_start')),clock(field('event_end'))
    if begin>=1440 or end==begin:
        raise ValueError('開始與結束時間不能相同；全天請使用 00:00–24:00。')
    if end<begin:end+=1440
    try:weekdays=sorted({int(v) for v in data.get('weekdays',[])})
    except ValueError:raise ValueError('每週重複日期不正確。') from None
    if not weekdays:weekdays=[parse_date(day).weekday()]
    if any(not 0<=v<=6 for v in weekdays):raise ValueError('每週重複日期不正確。')
    cancelled={key:row for key,row in old['overrides'].items() if row.get('cancelled')} if old else {}
    values=dict(title=title,category=category,date=day,start=begin,end=end,repeat=rule,until=until,weekdays=weekdays,overrides=cancelled)
    if old is None:state['events'].append(dict(id=secrets.token_hex(8),**values))
    else:old.update(values)


def move_occurrence(state,data,today):
    def field(key):return data.get(key,[''])[0]
    event=next((e for e in state['events'] if e['id']==field('id')),None)
    if event is None:raise ValueError('找不到這個事項。')
    if event['category']=='fixed':raise ValueError('固定事項不能移動；如有需要，請編輯整個系列或只移除這一次。')
    original=parse_date(field('occurrence_date'))
    if not matches(event,original,state.get("workdays",[0,1,2,3,4])):raise ValueError('找不到這一次重複事項。')
    previous=event['overrides'].get(original.isoformat(),{})
    if previous.get('cancelled'):raise ValueError('這一次事項已移除。')
    duration=previous.get('end',event['end'])-previous.get('start',event['start'])
    new_day=parse_date(field('new_date'))
    begin=parse_clock(field('new_start'), TIMETABLE_MISSING_TIME, TIMETABLE_INVALID_TIME)
    if not today<=new_day<=today+timedelta(days=6) or begin>=1440:
        raise ValueError('請移到未來七天內的有效時段。')
    event['overrides'][original.isoformat()]=dict(date=new_day.isoformat(),start=begin,end=begin+duration)


def cancel_occurrence(state,data):
    """Cancel by original occurrence date, including both halves of an overnight event."""
    event=next((e for e in state['events'] if e['id']==data.get('id',[''])[0]),None)
    if event is None:raise ValueError('找不到這個事項。')
    original=parse_date(data.get('occurrence_date',[''])[0])
    if not matches(event,original,state.get('workdays',[0,1,2,3,4])):
        raise ValueError('找不到這一次重複事項。')
    if event['overrides'].get(original.isoformat(),{}).get('cancelled'):
        raise ValueError('這一次事項已移除。')
    event['overrides'][original.isoformat()]=dict(cancelled=True)


def validate_events(items):
    if not isinstance(items,list):raise ValueError('固定事項資料不正確。')
    seen=set()
    for e in items:
        if not all(isinstance(e[k],str) for k in ('id','title','date','category','repeat','until')) or not e['id'] or e['id'] in seen or not e['title'] or len(e['title'])>100:
            raise ValueError('固定事項名稱或識別碼不正確。')
        seen.add(e['id'])
        origin=date.fromisoformat(e['date'])
        if e['until'] and date.fromisoformat(e['until'])<origin:raise ValueError('事項結束日期不正確。')
        if e['category'] not in ('fixed','private') or e['repeat'] not in ('none','daily','weekly','monthly','workdays','holidays'):
            raise ValueError('事項類型或重複規則不正確。')
        if not isinstance(e['weekdays'],list) or not e['weekdays'] or any(type(v) is not int or not 0<=v<=6 for v in e['weekdays']):
            raise ValueError('每週重複日期不正確。')
        def check_time(row):
            if any(type(row[k]) is not int or row[k]%30 for k in ('start','end')) or not 0<=row['start']<1440 or not row['start']<row['end']<=row['start']+1440:
                raise ValueError('事項時段不正確。')
        check_time(e)
        if not isinstance(e['overrides'],dict):raise ValueError('單次事項修改資料不正確。')
        for key,row in e['overrides'].items():
            date.fromisoformat(key)
            if not isinstance(row,dict):raise ValueError('單次事項修改格式不正確。')
            if row.get('cancelled') is True:continue
            date.fromisoformat(row['date'])
            check_time(row)
    return items
