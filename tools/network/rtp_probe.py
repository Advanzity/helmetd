"""Measure RTP sequence gaps at a Linux interface without saving video payloads.

Run with sudo on the Pi. This observes only the configured UDP ports and prints
aggregate counters; it neither forwards traffic nor writes packet captures.
"""
import argparse
import json
import socket
import struct
import time


def udp_counters():
    lines = open('/proc/net/snmp').read().splitlines()
    for i, line in enumerate(lines[:-1]):
        if line.startswith('Udp:'):
            return dict(zip(line.split()[1:], map(int, lines[i+1].split()[1:])))
    return {}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interface',default='wlan0')
    parser.add_argument('--seconds',type=int,default=30)
    args=parser.parse_args()
    start_counters=udp_counters()
    flows={}
    with socket.socket(socket.AF_PACKET,socket.SOCK_RAW,socket.htons(3)) as capture:
        capture.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,4*1024*1024)
        capture.bind((args.interface,0));capture.settimeout(.5)
        start=time.monotonic();end=start+args.seconds
        while time.monotonic()<end:
            try: packet,address=capture.recvfrom(65535)
            except TimeoutError: continue
            if len(packet)<54 or packet[12:14]!=b'\x08\x00':continue
            ihl=(packet[14]&15)*4
            if ihl<20 or packet[23]!=17 or len(packet)<14+ihl+20:continue
            udp=14+ihl
            port=struct.unpack_from('!H',packet,udp+2)[0]
            if port not in (5000,5002,5004,5006,5008):continue
            rtp=udp+8
            if packet[rtp]>>6!=2:continue
            seq=struct.unpack_from('!H',packet,rtp+2)[0]
            ssrc=struct.unpack_from('!I',packet,rtp+8)[0]
            key=f'{port}:{ssrc}:'+('out' if address[2]==socket.PACKET_OUTGOING else 'in')
            now=time.monotonic()
            flow=flows.setdefault(key,dict(seen=set(),highest=seq,last=now,max_gap_ms=0,reordered=0,duplicates=0,bytes=0,gaps_over_100ms=0))
            value=(flow['highest']&~65535)|seq
            if value-flow['highest']>32768:value-=65536
            elif flow['highest']-value>32768:value+=65536
            if value in flow['seen']:flow['duplicates']+=1
            elif value<flow['highest']:flow['reordered']+=1
            flow['seen'].add(value);flow['highest']=max(value,flow['highest'])
            gap=(now-flow['last'])*1000
            flow['max_gap_ms']=max(flow['max_gap_ms'],gap)
            flow['gaps_over_100ms']+=int(gap>100)
            flow['last']=now;flow['bytes']+=len(packet)
        capture_packets,capture_dropped=struct.unpack('II',capture.getsockopt(263,6,8))
    for flow in flows.values():
        seen=flow.pop('seen');expected=max(seen)-min(seen)+1
        flow['packets']=len(seen);flow['missing']=expected-len(seen)
        flow['loss_pct']=round(100*flow['missing']/expected,3)
        flow['mbps']=round(flow.pop('bytes')*8/(time.monotonic()-start)/1e6,3)
        flow['max_gap_ms']=round(flow['max_gap_ms'],1)
        flow.pop('highest');flow.pop('last')
    finish=udp_counters()
    print(json.dumps({'duration_s':args.seconds,'capture_packets':capture_packets,'capture_dropped':capture_dropped,'flows':flows,'udp_delta':{k:finish[k]-v for k,v in start_counters.items()}},indent=2))


if __name__=='__main__':main()
