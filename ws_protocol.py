"""KIS KRX protocol parsing, based on official open-trading-api column metadata."""
from datetime import datetime,timezone

TRADE_WIDTH=47
BOOK_WIDTH=63
PROGRAM_WIDTH=11

def parse_market_packet(message,received=None):
    if not isinstance(message,str) or not message.startswith('0|'): return []
    parts=message.split('|',3)
    if len(parts)!=4: raise ValueError('invalid packet')
    original_channel=parts[1]
    channel={'H0UNCNT0':'H0STCNT0','H0NXCNT0':'H0STCNT0','H0UNASP0':'H0STASP0','H0NXASP0':'H0STASP0','H0UNPGM0':'H0STPGM0','H0NXPGM0':'H0STPGM0'}.get(original_channel,original_channel)
    count=int(parts[2]);fields=parts[3].split('^')
    if count<1 or count>100: raise ValueError('invalid record count')
    if fields and fields[-1]=='':fields.pop()
    if len(fields)%count: raise ValueError('truncated packet')
    width=len(fields)//count
    minimum={'H0STCNT0':40,'H0STASP0':45,'H0STPGM0':11}.get(channel)
    if minimum is None:return []
    if width<minimum:raise ValueError('missing market fields')
    # Accept older single-record protocols. For batched messages use official width.
    expected_width={'H0STCNT0':TRADE_WIDTH,'H0STASP0':BOOK_WIDTH,'H0STPGM0':PROGRAM_WIDTH}[channel]
    if original_channel=='H0UNASP0':expected_width=66
    elif original_channel=='H0NXASP0':expected_width=65
    if count>1 and width!=expected_width:
        raise ValueError('unsupported batched field schema')
    stamp=received or datetime.now(timezone.utc).isoformat()
    results=[]
    for pos in range(count):
        raw=fields[pos*width:(pos+1)*width]
        code=raw[0]
        if len(code)!=6 or not code.isdigit():raise ValueError('invalid symbol')
        num=lambda n:float(raw[n] or 0)
        update={'코드':code,'quote_market': 'UN' if original_channel.startswith('H0UN') else 'NX' if original_channel.startswith('H0NX') else 'J'}
        if channel=='H0STCNT0':
            update.update({'체결시간':raw[1],'현재가':num(2),'등락%':num(5),'장중등락%':num(5),
              '매도1':num(10),'매수1':num(11),'체결량':num(12),'장중거래량':num(13),
              '장중거래대금':num(14),'체결강도':num(18),'총매도수량':num(19),'총매수수량':num(20),
              'trade_received_utc':stamp,'quote_received_utc':stamp,
              '장중시가':num(7),'장중고가':num(8),'장중저가':num(9),
              '누적거래량':num(13),'누적거래대금':num(14)})
            if width>33:update['market_date']=raw[33]
        elif channel=='H0STASP0':
            update.update({'호가시간':raw[1],'매도1':num(3),'매수1':num(13),
              '매도1잔량':num(23),'매수1잔량':num(33),'총매도잔량':num(43),
              '총매수잔량':num(44),'book_received_utc':stamp})
            total=num(43)+num(44)
            update['호가불균형']=(num(44)-num(43))/total if total>0 else None
        else:
            update.update({'프로그램':num(6),'프로그램순매수대금':num(7),'program_received_utc':stamp})
        results.append(update)
    return results
