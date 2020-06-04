
#import detectors

from psana import dgram
from psana.psexp.packet_footer import PacketFooter
import numpy as np
from psana.psexp.TransitionId import TransitionId

# TO DO
# 1) remove comments
# 2) pass detector class table from run > dgrammgr > event
# 3) hook up the detector class table


class DrpClassContainer(object):
    def __init__(self):
            pass

class Event():
    """
    Event holds list of dgrams
    """
    def __init__(self, dgrams, run=None):
        self._dgrams = dgrams
        self._size = len(dgrams)
        self._complete()
        self._position = 0
        self._run = run

    def __iter__(self):
        return self

    def __next__(self):
        return self.next()

    # we believe this can be hidden with underscores when we eliminate py2 support
    def next(self):
        if self._position >= len(self._dgrams):
            raise StopIteration
        d = self._dgrams[self._position]
        self._position += 1
        return d

    def _replace(self, pos, d):
        assert pos < self._size
        self._dgrams[pos] = d

    def _to_bytes(self):
        event_bytes = bytearray()
        pf = PacketFooter(self._size)
        for i, d in enumerate(self._dgrams):
            event_bytes.extend(bytearray(d))
            pf.set_size(i, memoryview(bytearray(d)).shape[0])

        if event_bytes:
            event_bytes.extend(pf.footer)

        return event_bytes

    @classmethod
    def _from_bytes(cls, configs, event_bytes, run=None):
        dgrams = []
        if event_bytes:
            pf = PacketFooter(view=event_bytes)
            views = pf.split_packets()
            
            assert len(configs) == pf.n_packets
            
            dgrams = [None]*pf.n_packets # make sure that dgrams are arranged 
                                         # according to the smd files.
            for i in range(pf.n_packets):
                if views[i].shape[0] > 0: # do not include any missing dgram
                    dgrams[i] = dgram.Dgram(config=configs[i], view=views[i])
        
        evt = cls(dgrams, run=run)
        return evt
    
    @property
    def _seconds(self):
        _high = (self.timestamp >> 32) & 0xffffffff
        return _high
    
    @property
    def _nanoseconds(self):
        _low = self.timestamp & 0xffffffff
        return _low

    @property
    def timestamp(self):
        ts = None
        for d in self._dgrams:
            if d:
                ts = d.timestamp()
                break
        assert ts
        return ts

    def run(self):
        return self._run

    def _assign_det_segments(self):
        """
        """

        self._det_segments = {}
        for evt_dgram in self._dgrams:

            if evt_dgram: # dgram can be None (missing) in an event

                # detector name (e.g. "xppcspad")
                for det_name, segment_dict in evt_dgram.__dict__.items():
                    # skip hidden dgram attributes
                    if det_name.startswith('_'): continue

                    # drp class name (e.g. "raw", "fex")
                    for segment, det in segment_dict.items():
                        for drp_class_name, drp_class in det.__dict__.items():
                            class_identifier = (det_name,drp_class_name)
                        
                            if class_identifier not in self._det_segments.keys():
                                self._det_segments[class_identifier] = {}
                            segs = self._det_segments[class_identifier]

                            if det_name not in ['runinfo','smdinfo'] :
                                assert segment not in segs, 'Found duplicate segment: '+str(segment)+' for '+str(class_identifier)
                            segs[segment] = drp_class

        return

    # this routine is called when all the dgrams have been inserted into
    # the event (e.g. by the eventbuilder calling _replace())
    def _complete(self):
        self._assign_det_segments()

    @property
    def _has_offset(self):
        return hasattr(self._dgrams[0], "info")

    def service(self):
        service = None
        for d in self._dgrams:
            if d:
                service = d.service()
                break
        assert service

        return service

    def get_offsets_and_sizes(self):
        ofsz = np.zeros((self._size, 2), dtype=np.int)
        for i, d in enumerate(self._dgrams):
            if d:
                if self.service() == TransitionId.L1Accept:
                    ofsz[i,:] = [d.smdinfo[0].offsetAlg.intOffset, \
                            d.smdinfo[0].offsetAlg.intDgramSize]
                else:
                    ofsz[i,1] = d._size
        return ofsz

