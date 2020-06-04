from psdaq.configdb.typed_json import cdict
import psdaq.configdb.configdb as cdb
import sys
import IPython
import argparse

def opal_cdict(args):

    #database contains collections which are sets of documents (aka json objects).
    #each type of device has a collection.  The elements of that collection are configurations of that type of device.
    #e.g. there will be OPAL, EVR, and YUNGFRAU will be collections.  How they are configured will be a document contained within that collection
    #Each hutch is also a collection.  Documents contained within these collection have an index, alias, and list of devices with configuration IDs
    #How is the configuration of a state is described by the hutch and the alias found.  E.g. TMO and BEAM.  TMO is a collection.
    #BEAM is an alias of some of the documents in that collection. The document with the matching alias and largest index is the current
    #configuration for that hutch and alias.
    #When a device is configured, the device has a unique name OPAL7.  Need to search through document for one that has an NAME called OPAL7.  This will have
    #have two fields "collection" and ID field (note how collection here is a field. ID points to a unique document).  This collection field and
    #ID point to the actuall Mongo DB collection and document

    top = cdict()
    top.setInfo('opal', args.name, args.segm, args.id, 'No comment')
    top.setAlg('config', [2,0,0])

    top.set("firmwareBuild:RO"  , "-", 'CHARSTR')
    top.set("firmwareVersion:RO",   0, 'UINT32')

    help_str  = "-- user interface --"
    help_str += "\nstart_ns : nanoseconds from fiducial to exposure start"
    help_str += "\ngate_ns  : nanoseconds of exposure; rounded up to 10 microseconds"
    top.set("help:RO", help_str, 'CHARSTR')

    top.define_enum('binEnum', {'x%d'%(2**key):key for key in range(4)})

    #Create a user interface that is an abstraction of the common inputs
    top.set("user.start_ns", 107749, 'UINT32')
    top.set("user.gate_ns" ,    100, 'UINT32')  
    top.set("user.black_level",  32, 'UINT32')  
    top.set("user.vertical_bin",  0, 'binEnum')  

    # timing system
    top.set('expert.ClinkPcie.Hsio.TimingRx.TriggerEventManager.TriggerEventBuffer[0].PauseThreshold',16,'UINT32')
    top.set('expert.ClinkPcie.Hsio.TimingRx.TriggerEventManager.TriggerEventBuffer[0].TriggerDelay',42,'UINT32')
    top.set('expert.ClinkPcie.Hsio.TimingRx.TriggerEventManager.TriggerEventBuffer[0].Partition',0,'UINT32')

    top.define_enum('rateEnum', {'929kHz':0, '71kHz':1, '10kHz':2, '1kHz':3, '100Hz':4, '10Hz':5, '1Hz':6})
    top.set('expert.ClinkPcie.Hsio.TimingRx.XpmMiniWrapper.XpmMini.Config_L0Select_RateSel',6,'rateEnum')

    # Feb[0] refers to pgp lane, Ch[0][,1] refers to camera link channel from Feb (these should be abstracted)
    # UartOpal1000 is camType; sets serial registers
    # ClinkTop.LinkMode is Base,Medium,Full,Deca
    # ClinkTop.DataMode is 8b,10b,12b,14b,16b,24b,30b,36b
    # ClinkTop.FrameMode is None,Line,Frame
    # ClinkTop.TapCount
    # All serial commands are enumerated as registers
    top.set('expert.ClinkFeb[0].TrigCtrl[0].EnableTrig', 1, 'UINT8')   # rogue wants 'bool'
    top.set('expert.ClinkFeb[0].TrigCtrl[0].InvCC'     , 0, 'UINT8')   # rogue wants 'bool'
    top.set('expert.ClinkFeb[0].TrigCtrl[0].TrigMap'   , 0, 'UINT32')  # ChanA/ChanB
    top.set('expert.ClinkFeb[0].TrigCtrl[0].TrigMask'  , 1, 'UINT32')  # CC1
    top.set('expert.ClinkFeb[0].TrigCtrl[0].TrigPulseWidth', 32.768, 'FLOAT')

    top.set("expert.ClinkFeb[0].ClinkTop.PllConfig[0]"      ,'80MHz','CHARSTR')
    top.set("expert.ClinkFeb[0].ClinkTop.PllConfig[1]"      ,'80MHz','CHARSTR')
    top.set("expert.ClinkFeb[0].ClinkTop.PllConfig[2]"      ,'80MHz','CHARSTR')

    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].LinkMode"    ,      1,'UINT32')   # Base mode
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].DataMode"    ,      3,'UINT32')   # 12-bit
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].FrameMode"    ,     2,'UINT32')   # Frame
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].TapCount"    ,      2,'UINT32')   # 
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].DataEn"    ,        1,'UINT8')   # rogue wants 'bool'
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].Blowoff"    ,       0,'UINT8')   # rogue wants 'bool'
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].BaudRate"      ,57600,'UINT32')   # bps
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].SerThrottle"   ,10000,'UINT32')   
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].SwControlValue",    0,'UINT32')   # Frame
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].SwControlEn"   ,    0,'UINT32')   # Frame

    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.BL"  ,  32,'UINT32')  # black level
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.GA"  , 100,'UINT32')  # digital gain, percent
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.VBIN",   0,'UINT32')  # vertical binning (powers-of-two)[0..3]
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.VR"  ,   1,'UINT32')  # vertical remapping (top-to-bottom, left-to-right)
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.MI"  ,   0,'UINT32')  # output mirroring (hor=b0, ver=b1)
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.OR"  ,  12,'UINT32')  # output resolution, bits
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.TP"  ,   0,'UINT32')  # test pattern on/off
#    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.OLUTE",  0,'UINT32')  # output lookup table enable on/off (not implemented)
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.DPE"  ,  0,'UINT32')  # defect pixel correction on/off
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.OVL"  ,  1,'UINT32')  # overlay frame counter and integration time
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.MO"   ,  1,'UINT32')  # operating mode continuous, triggered
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.CCE[0]", 0,'UINT32')  # trigger on CC1
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.CCE[1]", 0,'UINT32')  # polarity 0=rise-to-fall 1=fall-to-rise
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.FP"   ,  0,'UINT32')  # frame period, continuous mode, 10 us units
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.IT"   ,  1,'UINT32')  # integration time, 10 us units (< FP-10 and 32000)
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.CCFS[0]",0,'UINT32')  # only relevant for modes 2,3
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.CCFS[1]",0,'UINT32')  # only relevant for modes 2,3
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.OFS"  ,  1,'UINT32')  # color cameras only      
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.WB[0]",100,'UINT32')  # red gain
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.WB[1]",100,'UINT32')  # green gain
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.WB[2]",100,'UINT32')  # blue gain

#    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.FSE",0,'UINT32')      # flash strobe enable (not implemented)
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.FSM",0,'UINT32')      # flash strobe mode
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.FST[0]",0,'UINT32')   # flash stroble timing
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.FST[1]",0,'UINT32')
    top.set("expert.ClinkFeb[0].ClinkTop.Ch[0].UartOpal1000.FSP",   1,'UINT32')   # flash strobe polarity
    return top

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Write a new TimeTool configuration into the database')
    parser.add_argument('--inst', help='instrument', type=str, default='tst')
    parser.add_argument('--alias', help='alias name', type=str, default='BEAM')
    parser.add_argument('--name', help='detector name', type=str, default='tsttt')
    parser.add_argument('--segm', help='detector segment', type=int, default=0)
    parser.add_argument('--id', help='device id/serial num', type=str, default='serial1234')
    parser.add_argument('--user', help='user for HTTP authentication', type=str, default='xppopr')
    parser.add_argument('--password', help='password for HTTP authentication', type=str, default='pcds')
    args = parser.parse_args()

    create = True
    dbname = 'configDB'     #this is the name of the database running on the server.  Only client care about this name.

    mycdb = cdb.configdb('https://pswww.slac.stanford.edu/ws-auth/devconfigdb/ws/', args.inst, create,
                         root=dbname, user=args.user, password=args.password)
    mycdb.add_alias(args.alias)
    mycdb.add_device_config('opal')

    top = opal_cdict(args)

    mycdb.modify_device(args.alias, top)
