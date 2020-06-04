import socket
from psdaq.cas.pvedit import *

def atcaIp(v):
    return '10.0.{:}.{:}'.format((v>>16)&0xf,(v>>8)&0xff)

def hostName(v):
    ip = '172.21.{:d}.{:d}'.format((v>>8)&0xff,(v>>0)&0xff)
    return socket.gethostbyaddr(ip)[0].split('.')[0].split('-')[-1]

def nameLinkXpm(v):
    return ('XPM:{:}'.format((v>>20)&0xf), atcaIp(v))

def nameLinkDti(v):
    return ('DTI', atcaIp(v))

def nameLinkDrp(v):
    return ('TDetSim', hostName(v))

def nameLinkHsd(v):
    return ('HSD', '{:}.{:x}'.format(hostName(v),(v>>16)&0xff))

def nameLinkTDet(v):
    return ('TDetSim', hostName(v))

def nameLinkWave8(v):
    return ('Wave8', hostName(v))

def nameLinkOpal(v):
    return ('Opal', hostName(v))

def nameLinkTimeTool(v):
    return ('TimeTool', hostName(v))

linkType = {}
linkType[0xff] = nameLinkXpm
linkType[0xfe] = nameLinkDti
linkType[0xfd] = nameLinkDrp
linkType[0xfc] = nameLinkHsd
linkType[0xfb] = nameLinkTDet
linkType[0xfa] = nameLinkWave8
linkType[0xf9] = nameLinkOpal
linkType[0xf8] = nameLinkTimeTool

def xpmLinkId(value):
    itype = (value>>24)&0xff
    names = None
    if itype in linkType:
        names = linkType[itype](value)
    else:
        names = ('undef','{:x}'.format(value))
    return names
