#ifndef EPICS_XTC_SETTINGS_H
#define EPICS_XTC_SETTINGS_H

#include "xtcdata/xtc/ShapesData.hh"
#include "xtcdata/xtc/VarDef.hh"

namespace Pds
{

namespace EpicsXtcSettings
{
  const int                   iNamesIndex = 0; // < 255
  const int                   iMaxNumPv   = 10000;

  /*
   * 200 Bytes: For storing a DBR_CTRL_DOUBLE PV
   */
  const int                   iMaxXtcSize = iMaxNumPv * 200;
}

class EpicsArchDef : public XtcData::VarDef
{
public:
  enum index
  {
    Stale,
    Data,                               // Pseudonym for the start of PV data
  };

  EpicsArchDef()
  {
    NameVec.push_back({"StaleFlags", XtcData::Name::UINT32, 1});
    // PVs are added to NameVec in the code
  }
};

}

#endif
