#!/usr/bin/env python
#-----------------------------------------------------------------------------
# Title      : PyRogue AXI-Lite Ring Buffer Module
#-----------------------------------------------------------------------------
# File       : AxiLiteRingBuffer.py
# Created    : 2019-06-24
#-----------------------------------------------------------------------------
# Description:
# PyRogue AXI-Lite Ring Buffer Module
#-----------------------------------------------------------------------------
# This file is part of the rogue software platform. It is subject to
# the license terms in the LICENSE.txt file found in the top-level directory
# of this distribution and at:
#    https://confluence.slac.stanford.edu/display/ppareg/LICENSE.html.
# No part of the rogue software platform, including this file, may be
# copied, modified, propagated, or distributed except according to the terms
# contained in the LICENSE.txt file.
#-----------------------------------------------------------------------------

import datetime
import parse
import pyrogue as pr

class AxiLiteRingBuffer(pr.Device):

    # Last comment added by rherbst for demonstration.
    def __init__(
            self,       
            datawidth        = 32,
            name             = 'AxiLiteRingBuffer',
            description      = 'AXI-Lite Ring Buffer Module',
            **kwargs):
        
        super().__init__(
            name        = name,
            description = description,
            **kwargs)

        self._datawidth = datawidth

        ##############################
        # Variables
        ##############################

        self.add(pr.RemoteVariable(
            name         = 'blen',
            description  = 'Length of ring buffer',
            offset       = 0x00,
            bitSize      = 20,
            bitOffset    = 0x00,
            base         = pr.UInt,
            mode         = 'RO'
        ))

        self.add(pr.RemoteVariable(   
            name         = 'clear',
            description  = 'Clear buffer',
            offset       = 0x03,
            bitSize      = 1,
            bitOffset    = 0x06,
            base         = pr.UInt,
            mode         = 'RW',
            verify       = False,
        ))

        self.add(pr.RemoteVariable(   
            name         = 'start',
            description  = 'Start buffer',
            offset       = 0x03,
            bitSize      = 1,
            bitOffset    = 0x07,
            base         = pr.UInt,
            mode         = 'RW',
            verify       = False,
        ))

        self.addRemoteVariables(   
            name         = 'data',
            description  = 'Buffer values',
            offset       = 0x4,
            bitSize      = 32,
            bitOffset    = 0x00,
            base         = pr.UInt,
            mode         = 'RO',
            number       = 0x3ff,
            stride       = 4,
            hidden       = True,
        )

        @self.command(name='Dump',description='Dump buffer')
        def _Dump():
            mask  = (1<<self._datawidth)-1
            cmask = (self._datawidth+3)/4
            len_  = self.blen.get()
            if len_ > 0x3ff: 
                len_ = 0x3ff

            buff = []
            for i in range(len_):
                buff.append( self.data[i].get() & mask )

            fmt = '{:0%d'%(self._datawidth/4)+'x} '
            for i in range(len_):
                print(fmt.format(buff[i]),end='')
                if (i&0xf)==0xf:
                    print()
            if (len_&0xf)!=0:
                print()
