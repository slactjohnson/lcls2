#include "TebContributor.hh"

#include "Endpoint.hh"
#include "EbLfClient.hh"
#include "Batch.hh"
#include "EbCtrbInBase.hh"

#include "utilities.hh"

#include "psalg/utils/SysLog.hh"
#include "psdaq/service/MetricExporter.hh"
#include "xtcdata/xtc/Dgram.hh"

#ifdef NDEBUG
#undef NDEBUG
#endif

#include <string.h>
#include <cassert>
#include <cstdint>
#include <bitset>
#include <string>
#include <thread>

#include <unistd.h>

using namespace XtcData;
using namespace Pds;
using namespace Pds::Eb;
using logging  = psalg::SysLog;


TebContributor::TebContributor(const TebCtrbParams&                   prms,
                               const std::shared_ptr<MetricExporter>& exporter) :
  _prms        (prms),
  _batMan      (prms.maxInputSize, prms.batching),
  _transport   (prms.verbose),
  _links       (),
  _id          (-1),
  _numEbs      (0),
  _pending     (MAX_LATENCY), // Revisit: MAX_BATCHES),
  _batchStart  (nullptr),
  _batchEnd    (nullptr),
  _eventCount  (0),
  _batchCount  (0)
{
  std::map<std::string, std::string> labels{{"instrument", prms.instrument},
                                            {"partition", std::to_string(prms.partition)}};
  exporter->add("TCtbO_EvtRt",  labels, MetricType::Rate,    [&](){ return _eventCount;             });
  exporter->add("TCtbO_EvtCt",  labels, MetricType::Counter, [&](){ return _eventCount;             });
  exporter->add("TCtbO_BtAlCt", labels, MetricType::Counter, [&](){ return _batMan.batchAllocCnt(); });
  exporter->add("TCtbO_BtFrCt", labels, MetricType::Counter, [&](){ return _batMan.batchFreeCnt();  });
  exporter->add("TCtbO_BtWtg",  labels, MetricType::Gauge,   [&](){ return _batMan.batchWaiting();  });
  exporter->add("TCtb_IUBats",  labels, MetricType::Gauge,   [&](){ return _batMan.inUseBatchCnt(); });
  exporter->add("TCtbO_BatCt",  labels, MetricType::Counter, [&](){ return _batchCount;             });
  exporter->add("TCtbO_TxPdg",  labels, MetricType::Gauge,   [&](){ return _transport.pending();    });
  exporter->add("TCtbO_InFlt",  labels, MetricType::Gauge,   [&](){ return _pending.guess_size();   });
}

int TebContributor::configure(const TebCtrbParams& prms)
{
  _id      = prms.id;
  _numEbs  = std::bitset<64>(prms.builders).count();
  const EbDgram* dg;
  while (_pending.try_pop(dg));

  void*  region  = _batMan.batchRegion();     // Local space for Trs is in the batch region
  size_t regSize = _batMan.batchRegionSize(); // No need to add Tr space size here

  _links.resize(prms.addrs.size());
  for (unsigned i = 0; i < _links.size(); ++i)
  {
    int            rc;
    const char*    addr = prms.addrs[i].c_str();
    const char*    port = prms.ports[i].c_str();
    EbLfCltLink*   link;
    const unsigned tmo(120000);         // Milliseconds
    if ( (rc = _transport.connect(&link, addr, port, _id, tmo)) )
    {
      logging::error("%s:\n  Error connecting to TEB at %s:%s",
                     __PRETTY_FUNCTION__, addr, port);
      return rc;
    }
    unsigned rmtId = link->id();
    _links[rmtId] = link;

    logging::debug("Outbound link with TEB ID %d connected", rmtId);

    if ( (rc = link->prepare(region, regSize)) )
    {
      logging::error("%s:\n  Failed to prepare link with TEB ID %d",
                     __PRETTY_FUNCTION__, rmtId);
      return rc;
    }

    logging::info("Outbound link with TEB ID %d connected and configured", rmtId);
  }

  return 0;
}

void TebContributor::startup(EbCtrbInBase& in)
{
  _batchStart = nullptr;
  _batchEnd   = nullptr;
  _eventCount = 0;
  _batchCount = 0;
  _running.store(true, std::memory_order_release);
  _rcvrThread = std::thread([&] { in.receiver(*this, _running); });
}

void TebContributor::shutdown()
{
  if (_running.load(std::memory_order_relaxed))
  {
    _running.store(false, std::memory_order_release);
    _batMan.stop();

    if (_rcvrThread.joinable())  _rcvrThread.join();

    _batMan.dump();
    _batMan.shutdown();
    _pending.shutdown();

    for (auto it = _links.begin(); it != _links.end(); ++it)
    {
      _transport.disconnect(*it);
    }
    _links.clear();

    _id = -1;
  }
}

void* TebContributor::allocate(const TimingHeader& hdr, const void* appPrm)
{
  auto pid   = hdr.pulseId();
  auto batch = _batMan.fetchW(pid);     // Can block

  if (unlikely(_prms.verbose >= VL_EVENT))
  {
    const char* svc = TransitionId::name(hdr.service());
    unsigned    idx = batch ? batch->index() : -1;
    unsigned    ctl = hdr.control();
    unsigned    env = hdr.env;
    printf("Batching  %15s  dg  [%8d]     @ "
           "%16p, ctl %02x, pid %014lx, env %08x,                    prm %p\n",
           svc, idx, &hdr, ctl, pid, env, appPrm);
  }

  if (unlikely(!batch)) return nullptr; // Null when terminating

  ++_eventCount;                        // Only count events handled

  _batMan.store(pid, appPrm);           // Save the appPrm for _every_ event

  return batch->allocate();
}

void TebContributor::process(const EbDgram* dgram)
{
  if (likely(dgram->readoutGroups() & (1 << _prms.partition))) // Common RoG triggered
  {
    // The batch start is the first dgram seen
    if (!_batchStart)
    {
      _batchStart = dgram;
      _contractor = dgram->readoutGroups() & _prms.contractor;
    }

    bool expired = _batMan.expired(dgram->pulseId(), _batchStart->pulseId());
    auto svc     = dgram->service();
    bool flush   = (!((svc == TransitionId::L1Accept) ||
                      (svc == TransitionId::SlowUpdate)) || !_prms.batching);

    if (!(expired || flush))            // Most frequent case when batching
    {
      _batchEnd    = dgram;             // The batch end is the previous Dgram
      _contractor |= dgram->readoutGroups() & _prms.contractor;
    }
    else
    {
      if (expired)                      // Never true when not batching
      {
        if (_contractor)  _post(_batchStart,
                                _batchEnd ? _batchEnd : _batchStart);

        // Start a new batch using the Dgram that expired the batch
        _batchStart = dgram;
        _batchEnd   = dgram;
        _contractor = dgram->readoutGroups() & _prms.contractor;
      }

      if (flush)                        // Post the batch + transition
      {
        _contractor |= dgram->readoutGroups() & _prms.contractor;

        if (_contractor)  _post(_batchStart, dgram);

        // Start a new batch
        _batchStart = nullptr;
        _batchEnd   = nullptr;
      }
    }
  }
  else                        // Common RoG didn't trigger: bypass the TEB
  {
    if (_batchStart && _contractor)  _post(_batchStart,
                                           _batchEnd ? _batchEnd : _batchStart);

    dgram->setEOL();          // Terminate for clarity and dump-ability
    _pending.push(dgram);
    if (!(size_t(_pending.guess_size()) < _pending.size()))
      throw std::string(__PRETTY_FUNCTION__) + ": _pending overflow";

    // Start a new batch
    _batchStart = nullptr;
    _batchEnd   = nullptr;
  }

  // Keep non-selected TEBs synchronized by forwarding transitions to them.  In
  // particular, the Disable transition flushes out whatever Results batch they
  // currently have in-progress.
  if (!dgram->isEvent())             // Also capture the most recent SlowUpdate
  {
    if (_contractor)  _post(dgram);
  }
}

void TebContributor::_post(const EbDgram* start, const EbDgram* end)
{
  uint64_t     pid    = start->pulseId();
  uint32_t     idx    = Batch::index(pid);
  size_t       extent = (reinterpret_cast<const char*>(end) -
                         reinterpret_cast<const char*>(start)) + _prms.maxInputSize;
  unsigned     offset = idx * _prms.maxInputSize;
  uint32_t     data   = ImmData::value(ImmData::Buffer | ImmData::Response, _id, idx);
  unsigned     dst    = (idx / MAX_ENTRIES) % _numEbs;
  EbLfCltLink* link   = _links[dst];

  end->setEOL();        // Avoid race: terminate before adding batch to pending list
  _pending.push(start); // Get the batch on the queue before any corresponding result can show up
  if (!(size_t(_pending.guess_size()) < _pending.size()))
    throw std::string(__PRETTY_FUNCTION__) + ": _pending overflow";

  if (unlikely(_prms.verbose >= VL_BATCH))
  {
    void* rmtAdx = (void*)link->rmtAdx(offset);
    printf("CtrbOut posts %9ld    batch[%8d]    @ "
           "%16p,         pid %014lx,               sz %6zd, TEB %2d @ %16p, data %08x\n",
           _batchCount, idx, start, pid, extent, dst, rmtAdx, data);
  }

  if (link->post(start, extent, offset, data) < 0)  return;

  ++_batchCount;                        // Count all batches handled
}

void TebContributor::_post(const EbDgram* dgram) const
{
  // Send transition datagrams to all TEBs, except the one that got the
  // batch containing it.  These TEBs won't generate responses.
  if (_links.size() < 2)  return;

  uint64_t pid    = dgram->pulseId();
  uint32_t idx    = Batch::index(pid);
  unsigned dst    = (idx / MAX_ENTRIES) % _numEbs;
  unsigned tr     = dgram->service();
  uint32_t data   = ImmData::value(ImmData::Transition | ImmData::NoResponse, _id, tr);
  size_t   extent = sizeof(*dgram);  if (dgram->xtc.sizeofPayload())  throw "Unexpected XTC payload";
  unsigned offset = _batMan.batchRegionSize() + tr * sizeof(*dgram);

  for (auto it = _links.begin(); it != _links.end(); ++it)
  {
    EbLfCltLink* link = *it;
    if (link->id() != dst)        // Batch posted to dst included this Dgram
    {
      if (unlikely(_prms.verbose >= VL_BATCH))
      {
        unsigned    env    = dgram->env;
        unsigned    ctl    = dgram->control();
        const char* svc    = TransitionId::name(dgram->service());
        void*       rmtAdx = (void*)link->rmtAdx(offset);
        printf("CtrbOut posts    %15s              @ "
               "%16p, ctl %02x, pid %014lx, env %08x, sz %6zd, TEB %2d @ %16p, data %08x\n",
               svc, dgram, ctl, pid, env, extent, link->id(), rmtAdx, data);
      }

      link->post(dgram, extent, offset, data); // Not a batch
    }
  }
}
