#include "psalg/shmem/XtcMonitorServer.hh"

#include "psdaq/eb/eb.hh"
#include "psdaq/eb/EbAppBase.hh"
#include "psdaq/eb/EbEvent.hh"

#include "psdaq/eb/EbLfClient.hh"

#include "psdaq/eb/utilities.hh"

#include "psdaq/service/Fifo.hh"
#include "psdaq/service/GenericPool.hh"
#include "psdaq/service/Collection.hh"
#include "psdaq/service/MetricExporter.hh"
#include "psalg/utils/SysLog.hh"
#include "xtcdata/xtc/Dgram.hh"

#include <signal.h>
#include <errno.h>
#include <unistd.h>                     // For getopt(), gethostname()
#include <string.h>
#include <vector>
#include <bitset>
#include <iostream>
#include <atomic>
#include <climits>                      // For HOST_NAME_MAX

static const int      CORE_0               = -1; // devXXX: 18, devXX:  7, accXX:  9
static const int      CORE_1               = -1; // devXXX: 19, devXX: 19, accXX: 21
static const unsigned EPOCH_DURATION       = 8;  // Revisit: 1 per xferBuffer
static const unsigned NUMBEROF_XFERBUFFERS = 8;  // Value corresponds to ctrb:maxEvents
static const unsigned PROM_PORT_BASE       = 9200; // Prometheus port
static const unsigned MAX_PROM_PORTS       = 100;

using namespace XtcData;
using namespace Pds::Eb;
using namespace psalg::shmem;
using namespace Pds;

using json    = nlohmann::json;
using logging = psalg::SysLog;

static struct sigaction      lIntAction;
static volatile sig_atomic_t lRunning = 1;

void sigHandler( int signal )
{
  static unsigned callCount(0);

  if (callCount == 0)
  {
    logging::info("Shutting down");

    lRunning = 0;
  }

  if (callCount++)
  {
    logging::critical("Aborting on 2nd ^C");

    sigaction(signal, &lIntAction, NULL);
    raise(signal);
  }
}


namespace Pds {
  namespace Eb {
    struct MebParams : public EbParams
    {
      MebParams(EbParams prms, unsigned mbs, unsigned neb) :
        EbParams(prms), maxBufferSize(mbs), numEvBuffers(neb) {}

      unsigned maxBufferSize;           // Maximum built event size
      unsigned numEvBuffers;            // Number of event buffers
    };
  };

  class MyXtcMonitorServer : public XtcMonitorServer {
  public:
    MyXtcMonitorServer(const char*      tag,
                       unsigned         numberofEvQueues,
                       const MebParams& prms) :
      XtcMonitorServer(tag,
                       prms.maxBufferSize,
                       prms.numEvBuffers,
                       numberofEvQueues),
      _sizeofBuffers(prms.maxBufferSize),
      _iTeb         (0),
      _mrqTransport (prms.verbose),
      _mrqLinks     (),
      _bufFreeList  (prms.numEvBuffers),
      _id           (-1u)
    {
    }
    virtual ~MyXtcMonitorServer()
    {
    }
    int configure(const MebParams& prms)
    {
      _iTeb = 0;
      _id   = prms.id;
      _mrqLinks.resize(prms.addrs.size());

      for (unsigned i = 0; i < _mrqLinks.size(); ++i)
      {
        int            rc;
        const char*    addr = prms.addrs[i].c_str();
        const char*    port = prms.ports[i].c_str();
        EbLfCltLink*   link;
        const unsigned tmo(120000);     // Milliseconds
        if ( (rc = _mrqTransport.connect(&link, addr, port, _id, tmo)) )
        {
          logging::error("%s:\n  Error connecting to TEB at %s:%s",
                         __PRETTY_FUNCTION__, addr, port);
          return rc;
        }
        unsigned rmtId = link->id();
        _mrqLinks[rmtId] = link;

        logging::debug("Outbound link with TEB ID %d connected", rmtId);

        if ( (rc = link->prepare()) )
        {
          logging::error("%s:\n  Failed to prepare link with TEB ID %d",
                         __PRETTY_FUNCTION__, rmtId);
          return rc;
        }

        logging::info("Outbound link with TEB ID %d connected and configured",
                      rmtId);
      }

      unsigned numBuffers = _bufFreeList.size();
      for (unsigned i = 0; i < numBuffers; ++i)
      {
        if (_bufFreeList.push(i))
        {
          logging::error("%s:\n  _bufFreeList.push(%d) failed", __PRETTY_FUNCTION__, i);
          return -1;
        }
      }

      _init();

      return 0;
    }
  public:
    void shutdown()
    {
      for (auto it = _mrqLinks.begin(); it != _mrqLinks.end(); ++it)
      {
        _mrqTransport.disconnect(*it);
      }
      _mrqLinks.clear();

      _bufFreeList.clear();
      _id = -1;
    }

  private:
    virtual void _copyDatagram(Dgram* dg, char* buf)
    {
      //printf("_copyDatagram:   dg = %p, ts = %u.%09u to %p\n",
      //       dg, dg->time.seconds(), dg->time.nanoseconds(), buf);

      // The dg payload is a directory of contributions to the built event.
      // Iterate over the directory and construct, in shared memory, the event
      // datagram (odg) from the contribution XTCs
      const EbDgram** const  last = (const EbDgram**)dg->xtc.next();
      const EbDgram*  const* ctrb = (const EbDgram**)dg->xtc.payload();
      Dgram*                 odg  = new((void*)buf) Dgram(**ctrb); // Not an EbDgram!
      odg->xtc.src      = XtcData::Src(XtcData::Level::Event);
      odg->xtc.contains = XtcData::TypeId(XtcData::TypeId::Parent, 0);
      do
      {
        const EbDgram* idg = *ctrb;

        odg->xtc.damage.increase(idg->xtc.damage.value());

        buf = (char*)odg->xtc.alloc(idg->xtc.extent);

        if (sizeof(*odg) + odg->xtc.sizeofPayload() > _sizeofBuffers)
        {
          logging::critical("%s:\n  Datagram is too large (%zd) for buffer of size %d",
                            __PRETTY_FUNCTION__, sizeof(*odg) + odg->xtc.sizeofPayload(), _sizeofBuffers);
          throw "Fatal: Datagram is too large for buffer"; // The memcpy would blow by the buffer size limit
        }

        memcpy(buf, &idg->xtc, idg->xtc.extent);
      }
      while (++ctrb != last);
    }

    virtual void _deleteDatagram(Dgram* dg, int bufIdx) // Not called for transitions
    {
      //printf("_deleteDatagram @ %p: ts = %u.%09u\n",
      //       dg, dg->time.seconds(), dg->time.nanoseconds());

      //if ((bufIdx < 0) || (size_t(bufIdx) >= _bufFreeList.size()))
      //{
      //  printf("deleteDatagram: Unexpected buffer index %d\n", bufIdx);
      //}

      unsigned idx = (dg->env >> 16) & 0xff;
      if (idx >= _bufFreeList.size())
      {
        logging::warning("deleteDatagram: Unexpected index %08x", idx);
      }
      //if (idx != bufIdx)
      //{
      //  printf("Buffer index mismatch: got %d, expected %d, dg %p, pid %014lx\n",
      //         idx, bufIdx, dg, dg->pulseId());
      //}
      for (unsigned i = 0; i < _bufFreeList.count(); ++i)
      {
        if (idx == _bufFreeList.peek(i))
        {
          logging::error("Attempted double free of list entry %d: idx %d, bufIdx %d, dg %p, ts %u.%09u",
                         i, idx, bufIdx, dg, dg->time.seconds(), dg->time.nanoseconds());
          // Does the dg still need to be freed?  Apparently so.
          Pool::free((void*)dg);
          return;
        }
      }
      if (_bufFreeList.push(idx))
      {
        logging::error("_bufFreeList.push(%d) failed, bufIdx %d, count = %zd", idx, bufIdx, _bufFreeList.count());
        for (unsigned i = 0; i < _bufFreeList.size(); ++i)
        {
          printf("Free list entry %d: %d\n", i, _bufFreeList.peek(i));
        }
      }
      //printf("_deleteDatagram: dg = %p, pid = %014lx, _bufFreeList.push(%d), bufIdx %d, count = %zd\n",
      //       dg, dg->pulseId(), idx, bufIdx, _bufFreeList.count());

      Pool::free((void*)dg);
    }

    virtual void _requestDatagram(int bufIdx)
    {
      //printf("_requestDatagram\n");

      unsigned data;
      if (_bufFreeList.pop(data))
      {
        logging::error("%s:\n  No free buffers available: bufIdx %d", __PRETTY_FUNCTION__, bufIdx);
        return;
      }

      //printf("_requestDatagram: _bufFreeList.pop(): %d, bufIdx %d, count = %zd\n", data, bufIdx, _bufFreeList.count());

      //if ((bufIdx < 0) || (size_t(bufIdx) >= _bufFreeList.size()))
      //{
      //  printf("requestDatagram: Unexpected buffer index %d\n", bufIdx);
      //}

      data = ImmData::value(ImmData::Buffer, _id, data); // bufIdx);

      int rc = -1;
      for (unsigned i = 0; i < _mrqLinks.size(); ++i)
      {
        // Round robin through Trigger Event Builders
        unsigned iTeb = _iTeb++;
        if (_iTeb == _mrqLinks.size())  _iTeb = 0;

        rc = _mrqLinks[iTeb]->post(nullptr, 0, data);

        //printf("_requestDatagram: Post %d EB[iTeb = %d], value = %08x, rc = %d\n",
        //       i, iTeb, data, rc);

        if (rc == 0)  break;            // Break if message was delivered
      }
      if (rc)
      {
        logging::error("%s:\n  Unable to post request to any TEB: rc %d, data %d",
                       __PRETTY_FUNCTION__, rc, data);
        // Revisit: Is this fatal or ignorable?
      }
    }

  private:
    unsigned                  _sizeofBuffers;
    unsigned                  _iTeb;
    EbLfClient                _mrqTransport;
    std::vector<EbLfCltLink*> _mrqLinks;
    FifoMT<unsigned>          _bufFreeList;
    unsigned                  _id;
  };

  class Meb : public EbAppBase
  {
  public:
    Meb(const MebParams&                       prms,
        const std::shared_ptr<MetricExporter>& exporter) :
      EbAppBase  (prms, EPOCH_DURATION, 1, prms.numEvBuffers),
      _apps      (nullptr),
      _pool      (nullptr),
      _eventCount(0),
      _prms      (prms)
    {
      std::map<std::string, std::string> labels{{"instrument", prms.instrument},{"partition", std::to_string(prms.partition)}};
      exporter->add("MEB_EvtRt",  labels, MetricType::Rate,    [&](){ return _eventCount;      });
      exporter->add("MEB_EvtCt",  labels, MetricType::Counter, [&](){ return _eventCount;      });
      exporter->add("MEB_EpAlCt", labels, MetricType::Counter, [&](){ return  epochAllocCnt(); });
      exporter->add("MEB_EpFrCt", labels, MetricType::Counter, [&](){ return  epochFreeCnt();  });
      exporter->add("MEB_EvAlCt", labels, MetricType::Counter, [&](){ return  eventAllocCnt(); });
      exporter->add("MEB_EvFrCt", labels, MetricType::Counter, [&](){ return  eventFreeCnt();  });
    }
    virtual ~Meb()
    {
    }
  public:
    void run(MyXtcMonitorServer& apps)
    {
      logging::info("MEB thread is starting");

      int rc = pinThread(pthread_self(), _prms.core[0]);
      if (rc != 0)
      {
        logging::error("%s:\n  Error from pinThread:\n  %s",
                       __PRETTY_FUNCTION__, strerror(rc));
      }

      _apps = &apps;

      // Create pool for transferring events to MyXtcMonitorServer
      unsigned    entries = std::bitset<64>(_prms.contributors).count();
      size_t      size    = sizeof(Dgram) + entries * sizeof(Dgram*);
      GenericPool pool(size, 1 + _prms.numEvBuffers); // +1 for Transitions
      _pool = &pool;

      _eventCount = 0;

      while (lRunning)
      {
        if (EbAppBase::process() < 0)
        {
          if (checkEQ() == -FI_ENOTCONN)  break;
        }
      }

      _shutdown();

      logging::info("MEB thread is exiting");
    }
    void _shutdown()
    {
      _apps->shutdown();

      EbAppBase::shutdown();

      if (_pool)
      {
        printf("Directory datagram pool\n");
        _pool->dump();
      }

      _apps = nullptr;
      _pool = nullptr;
    }
    virtual void process(EbEvent* event)
    {
      if (_prms.verbose >= VL_DETAILED)
      {
        static unsigned cnt = 0;
        printf("Meb::process event dump:\n");
        event->dump(++cnt);
      }
      ++_eventCount;

      // Create a Dgram with a payload that is a directory of contribution
      // Dgrams to the built event in order to avoid first assembling the
      // datagram from its contributions in a temporary buffer, only to then
      // copy it into shmem in _copyDatagram() above.  Since the contributions,
      // and thus the full datagram, can be quite large, this would amount to
      // a lot of copying
      size_t   sz     = (event->end() - event->begin()) * sizeof(*(event->begin()));
      unsigned idx    = ImmData::idx(event->parameter());
      void*    buffer = _pool->alloc(sizeof(Dgram) + sz);
      if (!buffer)
      {
        logging::critical("%s:\n  Dgram pool allocation of size %zd failed:",
                          __PRETTY_FUNCTION__, sizeof(Dgram) + sz);
        printf("Directory datagram pool\n");
        _pool->dump();
        printf("Meb::process event dump:\n");
        event->dump(-1);
        throw "Fatal: Dgram pool exhausted";
      }

      Dgram* dg  = new(buffer) Dgram(*(event->creator()));
      void*  buf = dg->xtc.alloc(sz);
      memcpy(buf, event->begin(), sz);
      dg->env = (dg->env & 0xff00ffff) | (idx << 16); // Pass buffer's index to _deleteDatagram()

      if (_prms.verbose >= VL_EVENT)
      {
        uint64_t    pid = event->creator()->pulseId();
        unsigned    ctl = dg->control();
        unsigned    env = dg->env;
        size_t      sz  = sizeof(*dg) + dg->xtc.sizeofPayload();
        unsigned    src = dg->xtc.src.value();
        const char* knd = TransitionId::name(dg->service());
        printf("MEB processed %5ld %15s  [%5d] @ "
               "%16p, ctl %02x, pid %014lx, env %08x, sz %6zd, src %2d, ts %u.%09u\n",
               _eventCount, knd, idx, dg, ctl, pid, env, sz, src, dg->time.seconds(), dg->time.nanoseconds());
      }

      if (_apps->events(dg) == XtcMonitorServer::Handled)
      {
        Pool::free((void*)dg);          // Handled means _deleteDatagram() won't be called
      }
    }
    void beginrun() { _eventCount = 0; }
  private:
    MyXtcMonitorServer* _apps;
    GenericPool*        _pool;
    uint64_t            _eventCount;
    const MebParams&    _prms;
  };
};


class MebApp : public CollectionApp
{
public:
  MebApp(const std::string&              collSrv,
         const char*                     tag,
         unsigned                        numEvQueues,
         bool                            distribute,
         MebParams&                      prms);
public:                                 // For CollectionApp
  json         connectionInfo() override;
  void         handleConnect(const json& msg) override;
  void         handleDisconnect(const json& msg) override;
  void         handlePhase1(const json& msg) override;
  void         handleReset(const json& msg) override;
private:
  std::string _connect(const json& msg);
  std::string _configure(const json& msg);
  int         _parseConnectionParams(const json& msg);
  void        _printParams(const EbParams& prms, unsigned groups) const;
  void        _printGroups(unsigned groups, const u64arr_t& array) const;
private:
  const char*                          _tag;
  unsigned                             _numEvQueues;
  bool                                 _distribute;
  MebParams&                           _prms;
  std::unique_ptr<prometheus::Exposer> _exposer;
  std::shared_ptr<MetricExporter>      _exporter;
  std::unique_ptr<Meb>                 _meb;
  std::unique_ptr<MyXtcMonitorServer>  _apps;
  std::thread                          _appThread;
  uint16_t                             _groups;
};

MebApp::MebApp(const std::string&              collSrv,
               const char*                     tag,
               unsigned                        numEvQueues,
               bool                            distribute,
               MebParams&                      prms) :
  CollectionApp(collSrv, prms.partition, "meb", prms.alias),
  _tag         (tag),
  _numEvQueues (numEvQueues),
  _distribute  (distribute),
  _prms        (prms)
{
  logging::info("Ready for transitions");
}

json MebApp::connectionInfo()
{
  // Allow the default NIC choice to be overridden
  std::string ip = _prms.ifAddr.empty() ? getNicIp() : _prms.ifAddr;
  json body = {{"connect_info", {{"nic_ip", ip}}}};
  json bufInfo = {{"buf_count", _prms.numEvBuffers}};
  body["connect_info"].update(bufInfo);
  return body;
}

std::string MebApp::_connect(const json &msg)
{
  int rc = _parseConnectionParams(msg["body"]);
  if (rc)  return std::string("Error parsing parameters");

  return std::string{};
}

void MebApp::handleConnect(const json &msg)
{
  json body = json({});
  int  rc   = _parseConnectionParams(msg["body"]);
  if (rc)
  {
    std::string errorMsg = "Error parsing connect parameters";
    body["err_info"] = errorMsg;
    logging::error("%s:\n  %s", __PRETTY_FUNCTION__, errorMsg.c_str());
  }

  // Reply to collection with transition status
  reply(createMsg("connect", msg["header"]["msg_id"], getId(), body));
}

std::string MebApp::_configure(const json &msg)
{
  if (_exposer)  _exposer.reset();
  unsigned port = 0;
  for (unsigned i = 0; i < MAX_PROM_PORTS; ++i) {
    try {
      port = PROM_PORT_BASE + i;
      _exposer = std::make_unique<prometheus::Exposer>("0.0.0.0:"+std::to_string(port), "/metrics", 1);
      if (i > 0) {
        if ((i < MAX_PROM_PORTS) && !_prms.prometheusDir.empty()) {
          char hostname[HOST_NAME_MAX];
          gethostname(hostname, HOST_NAME_MAX);
          std::string fileName = _prms.prometheusDir + "/drpmon_" + std::string(hostname) + "_" + std::to_string(i) + ".yaml";
          FILE* file = fopen(fileName.c_str(), "w");
          if (file) {
            fprintf(file, "- targets:\n    - '%s:%d'\n", hostname, port);
            fclose(file);
          }
          else {
            // %m will be replaced by the string strerror(errno)
            logging::error("Error creating file %s: %m", fileName.c_str());
          }
        }
        else {
          logging::warning("Could not start run-time monitoring server");
        }
      }
      break;
    }
    catch(const std::runtime_error& e) {
      logging::debug("Could not start run-time monitoring server on port %d", port);
      logging::debug("%s", e.what());
    }
  }

  if (_exporter)  _exporter.reset();
  _exporter = std::make_shared<MetricExporter>();
  if (_exposer) {
    logging::info("Providing run-time monitoring data on port %d", port);
    _exposer->RegisterCollectable(_exporter);
  }

  if (_meb)  _meb.reset();
  _meb = std::make_unique<Meb>(_prms, _exporter);
  int rc = _meb->configure("MEB", _prms, _exporter);
  if (rc)  return std::string("Failed to configure MEB");

  _apps = std::make_unique<MyXtcMonitorServer>(_tag, _numEvQueues, _prms);
  rc = _apps->configure(_prms);
  if (rc)  return std::string("Failed XtcMonitorServer configure()");

  return std::string{};
}

void MebApp::handlePhase1(const json& msg)
{
  json        body = json({});
  std::string key  = msg["header"]["key"];

  if (key == "configure")
  {
    // Shut down the previously running instance, if any
    if (_appThread.joinable())
    {
      lRunning = 0;

      _appThread.join();
      _apps.reset();
    }

    std::string errMsg = _configure(msg);
    if (!errMsg.empty())
    {
      body["error_info"] = "Phase 1 error: " + errMsg;
      logging::error("%s:\n  %s", __PRETTY_FUNCTION__, errMsg.c_str());
    }
    else
    {
      _printParams(_prms, _groups);

      _apps->distribute(_distribute);

      lRunning = 1;

      _appThread = std::thread(&Meb::run, std::ref(*_meb), std::ref(*_apps));
    }
  }
  else if (key == "beginrun")
  {
    _meb->beginrun();
  }

  // Reply to collection with transition status
  reply(createMsg(key, msg["header"]["msg_id"], getId(), body));
}

void MebApp::handleDisconnect(const json &msg)
{
  lRunning = 0;
  if (_appThread.joinable())  _appThread.join();

  _apps.reset();

  // Reply to collection with connect status
  json body = json({});
  reply(createMsg("disconnect", msg["header"]["msg_id"], getId(), body));
}

void MebApp::handleReset(const json &msg)
{
  lRunning = 0;
  if (_appThread.joinable())  _appThread.join();

  _apps.reset();

  if (_exporter)  _exporter.reset();
}

int MebApp::_parseConnectionParams(const json& body)
{
  const unsigned numPorts    = MAX_DRPS + MAX_TEBS + MAX_TEBS + MAX_MEBS;
  const unsigned mrqPortBase = MRQ_PORT_BASE + numPorts * _prms.partition;
  const unsigned mebPortBase = MEB_PORT_BASE + numPorts * _prms.partition;

  printf("  MRQ port range: %d - %d\n", mrqPortBase, mrqPortBase + MAX_MEBS - 1);
  printf("  MEB port range: %d - %d\n", mebPortBase, mebPortBase + MAX_MEBS - 1);
  printf("\n");

  std::string id = std::to_string(getId());
  _prms.id       = body["meb"][id]["meb_id"];
  if (_prms.id >= MAX_MEBS)
  {
    logging::error("MEB ID %d is out of range 0 - %d", _prms.id, MAX_MEBS - 1);
    return 1;
  }

  _prms.ifAddr = body["meb"][id]["connect_info"]["nic_ip"];
  _prms.ebPort = std::to_string(mebPortBase + _prms.id);

  if (body.find("drp") == body.end())
  {
    logging::error("Missing required DRP specs");
    return 1;
  }

  size_t   maxTrSize     = 0;
  size_t   maxBufferSize = 0;
  _prms.contributors     = 0;
  _prms.maxBufferSize    = 0;
  _prms.maxTrSize.resize(body["drp"].size());

  _prms.contractors.fill(0);
  _prms.receivers.fill(0);
  _groups = 0;

  for (auto it : body["drp"].items())
  {
    unsigned drpId = it.value()["drp_id"];
    if (drpId > MAX_DRPS - 1)
    {
      logging::error("DRP ID %d is out of range 0 - %d", drpId, MAX_DRPS - 1);
      return 1;
    }
    _prms.contributors |= 1ul << drpId;

    unsigned group = it.value()["det_info"]["readout"];
    if (group > NUM_READOUT_GROUPS - 1)
    {
      logging::error("Readout group %d is out of range 0 - %d", group, NUM_READOUT_GROUPS - 1);
      return 1;
    }
    _prms.contractors[group] |= 1ul << drpId;
    _prms.receivers[group]    = 0;      // Unused by MEB
    _groups |= 1 << group;

    _prms.maxTrSize[drpId] = size_t(it.value()["connect_info"]["max_tr_size"]);
    maxTrSize             += _prms.maxTrSize[drpId];
    maxBufferSize         += size_t(it.value()["connect_info"]["max_ev_size"]);
  }
  // shmem buffers must fit both built events and transitions of worst case size
  _prms.maxBufferSize = maxBufferSize > maxTrSize ? maxBufferSize : maxTrSize;

  if (body.find("teb") == body.end())
  {
    logging::error("Missing required TEB specs");
    return 1;
  }

  _prms.addrs.clear();
  _prms.ports.clear();

  for (auto it : body["teb"].items())
  {
    unsigned    tebId   = it.value()["teb_id"];
    std::string address = it.value()["connect_info"]["nic_ip"];
    if (tebId > MAX_TEBS - 1)
    {
      logging::error("TEB ID %d is out of range 0 - %d", tebId, MAX_TEBS - 1);
      return 1;
    }
    _prms.addrs.push_back(address);
    _prms.ports.push_back(std::string(std::to_string(mrqPortBase + tebId)));
  }

  return 0;
}

void MebApp::_printGroups(unsigned groups, const u64arr_t& array) const
{
  while (groups)
  {
    unsigned group = __builtin_ffs(groups) - 1;
    groups &= ~(1 << group);

    printf("%d: 0x%016lx  ", group, array[group]);
  }
  printf("\n");
}

void MebApp::_printParams(const EbParams& prms, unsigned groups) const
{
  printf("\nParameters of MEB ID %d:\n",                       _prms.id);
  printf("  Thread core numbers:        %d, %d\n",             _prms.core[0], _prms.core[1]);
  printf("  Partition:                  %d\n",                 _prms.partition);
  printf("  Bit list of contributors:   0x%016lx, cnt: %zd\n", _prms.contributors,
                                                               std::bitset<64>(_prms.contributors).count());
  printf("  Readout group contractors:  ");                    _printGroups(_groups, _prms.contractors);
  printf("  Number of TEB requestees:   %zd\n",                _prms.addrs.size());
  printf("  Buffer duration:            0x%014lx\n",           BATCH_DURATION);
  printf("  Number of event buffers:    %d\n",                 _prms.numEvBuffers);
  printf("  Max # of entries / buffer:  %d\n",                 1);
  printf("  shmem buffer size:          %d\n",                 _prms.maxBufferSize);
  printf("  Number of event queues:     %d\n",                 _numEvQueues);
  printf("  Distribute:                 %s\n",                 _distribute ? "yes" : "no");
  printf("  Tag:                        %s\n",                 _tag);
  printf("\n");
}


using namespace Pds;


void usage(char* progname)
{
  printf("Usage: %s -C <collection server> "
                   "-p <partition> "
                   "-P <partition name> "
                   "-n <numb shm buffers> "
                   "-u <alias> "
                  "[-q <# event queues>] "
                  "[-t <tag name>] "
                  "[-d] "
                  "[-A <interface addr>] "
                  "[-1 <core to pin App thread to>]"
                  "[-2 <core to pin other threads to>]" // Revisit: None?
                  "[-M <Prometheus config file directory>]"
                  "[-v] "
                  "[-h] "
                  "\n", progname);
}

int main(int argc, char** argv)
{
  const unsigned NO_PARTITION = unsigned(-1u);
  const char*    tag          = 0;
  std::string    collSrv;
  MebParams      prms { { /* .ifAddr        = */ { }, // Network interface to use
                          /* .ebPort        = */ { },
                          /* .mrqPort       = */ { }, // Unused here
                          /* .instrument    = */ { },
                          /* .partition     = */ NO_PARTITION,
                          /* .alias         = */ { }, // Unique name passed on cmd line
                          /* .id            = */ -1u,
                          /* .contributors  = */ 0,   // DRPs
                          /* .contractors   = */ { },
                          /* .receivers     = */ { },
                          /* .addrs         = */ { }, // MonReq addr served by TEB
                          /* .ports         = */ { }, // MonReq port served by TEB
                          /* .maxTrSize     = */ { }, // Filled in @ connect
                          /* .maxResultSize = */ 0,   // Unused here
                          /* .numMrqs       = */ 0,   // Unused here
                          /* .trgDetName    = */ { }, // Unused here
                          /* .prometheusDir = */ { }, // Optionally filled in below
                          /* .core          = */ { CORE_0, CORE_1 },
                          /* .verbose       = */ 0 },
                        /* .maxBufferSize = */ 0,     // Filled in @ connect
                        /* .numEvBuffers  = */ NUMBEROF_XFERBUFFERS };
  unsigned       nevqueues = 1;
  bool           ldist     = false;

  int c;
  while ((c = getopt(argc, argv, "p:P:n:t:q:dA:C:1:2:u:M:vh")) != -1)
  {
    errno = 0;
    char* endPtr;
    switch (c) {
      case 'p':
        prms.partition = strtoul(optarg, &endPtr, 0);
        if (errno != 0 || endPtr == optarg) prms.partition = NO_PARTITION;
        break;
      case 'P':
        prms.instrument = std::string(optarg);
        break;
      case 'n':
        sscanf(optarg, "%d", &prms.numEvBuffers);
        break;
      case 't':
        tag = optarg;
        break;
      case 'q':
        nevqueues = strtoul(optarg, NULL, 0);
        break;
      case 'd':
        ldist = true;
        break;
      case 'A':  prms.ifAddr        = optarg;        break;
      case 'C':  collSrv            = optarg;        break;
      case '1':  prms.core[0]       = atoi(optarg);  break;
      case '2':  prms.core[1]       = atoi(optarg);  break;
      case 'u':  prms.alias         = optarg;        break;
      case 'M':  prms.prometheusDir = optarg;        break;
      case 'v':  ++prms.verbose;                     break;
      case 'h':                         // help
        usage(argv[0]);
        return 0;
        break;
      default:
        printf("Unrecogized parameter '%c'\n", c);
        usage(argv[0]);
        return 1;
    }
  }

  logging::init(prms.instrument.c_str(), prms.verbose ? LOG_DEBUG : LOG_INFO);
  logging::info("logging configured");

  if (prms.partition == NO_PARTITION)
  {
    logging::critical("-p: partition number is mandatory");
    return 1;
  }
  if (prms.instrument.empty())
  {
    logging::critical("-P: instrument name is mandatory");
    return 1;
  }
  if (!prms.numEvBuffers)
  {
    logging::critical("-n: max buffers is mandatory");
    return 1;
  }
  if (collSrv.empty())
  {
    logging::critical("-C: collection server is mandatory");
    return 1;
  }
  if (prms.alias.empty()) {
    logging::critical("-u: alias is mandatory");
    return 1;
  }

  if (prms.numEvBuffers < NUMBEROF_XFERBUFFERS)
    prms.numEvBuffers = NUMBEROF_XFERBUFFERS;
  if (prms.numEvBuffers > 255)
  {
    // The problem is that there are only 8 bits available in the env
    // Could use the lower 24 bits, but then we have a nonstandard env
    logging::critical("%s:\n  Number of event buffers > 255 is not supported: got %d", prms.numEvBuffers);
    return 1;
  }

  if (!tag)  tag = prms.instrument.c_str();
  logging::info("Partition Tag: '%s'", tag);

  struct sigaction sigAction;

  sigAction.sa_handler = sigHandler;
  sigAction.sa_flags   = SA_RESTART;
  sigemptyset(&sigAction.sa_mask);
  if (sigaction(SIGINT, &sigAction, &lIntAction) > 0)
    logging::warning("Failed to set up ^C handler");

  try
  {
    MebApp app(collSrv, tag, nevqueues, ldist, prms);

    app.run();

    app.handleReset(json({}));

    return 0;
  }
  catch (std::exception& e)  { logging::critical("%s", e.what()); }
  catch (std::string& e)     { logging::critical("%s", e.c_str()); }
  catch (char const* e)      { logging::critical("%s", e); }
  catch (...)                { logging::critical("Default exception"); }

  return EXIT_FAILURE;
}
