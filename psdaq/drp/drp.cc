#include <getopt.h>
#include <sstream>
#include <iostream>
#include <algorithm>
#include "drp.hh"
#include "PGPDetectorApp.hh"
#include "rapidjson/document.h"
#include "psalg/utils/SysLog.hh"
using logging = psalg::SysLog;
using json = nlohmann::json;

void get_kwargs(Drp::Parameters& para, const std::string& kwargs_str) {
    std::istringstream ss(kwargs_str);
    std::string kwarg;
    while (getline(ss, kwarg, ',')) {
        kwarg.erase(std::remove(kwarg.begin(), kwarg.end(), ' '), kwarg.end());
        auto pos = kwarg.find("=", 0);
        if (!pos) {
            logging::critical("Keyword argument with no equal sign");
            throw "drp.cc error: keyword argument with no equal sign: "+kwargs_str;
        }
        std::string key = kwarg.substr(0,pos);
        std::string value = kwarg.substr(pos+1,kwarg.length());
        //std::cout << "kwarg = '" << kwarg << "' key = '" << key << "' value = '" << value << "'" << std::endl;
        para.kwargs[key] = value;
    }
}

int main(int argc, char* argv[])
{
    Drp::Parameters para;
    int c;
    std::string kwargs_str;
    std::string::size_type ii = 0;
    while((c = getopt(argc, argv, "p:o:l:D:S:C:d:u:k:P:T::M:v")) != EOF) {
        switch(c) {
            case 'p':
                para.partition = std::stoi(optarg);
                break;
            case 'o':
                para.outputDir = optarg;
                break;
            case 'l':
                para.laneMask = std::stoul(optarg, nullptr, 16);
                break;
            case 'D':
                para.detType = optarg;
                break;
            case 'S':
                para.serNo = optarg;
                break;
            case 'u':
                para.alias = optarg;
                break;
            case 'C':
                para.collectionHost = optarg;
                break;
            case 'd':
                para.device = optarg;
                break;
            case 'k':
                kwargs_str = std::string(optarg);
                break;
            case 'P':
                para.instrument = optarg;
                // remove station number suffix, if present
                ii = para.instrument.find(":");
                if (ii != std::string::npos) {
                    para.instrument.erase(ii, std::string::npos);
                }
                break;
            case 'T':
                para.trgDetName = optarg ? optarg : "trigger";
                break;
            case 'M':
                para.prometheusDir = optarg;
                break;
            case 'v':
                ++para.verbose;
                break;
            default:
                return 1;
        }
    }

    switch (para.verbose) {
      case 0:  logging::init(para.instrument.c_str(), LOG_INFO);     break;
      default: logging::init(para.instrument.c_str(), LOG_DEBUG);    break;
    }
    logging::info("logging configured");
    // Check required parameters
    if (para.instrument.empty()) {
        logging::critical("-P: instrument name is mandatory");
        return 1;
    }
    if (para.partition == unsigned(-1)) {
        logging::critical("-p: partition is mandatory");
        return 1;
    }
    if (para.device.empty()) {
        logging::critical("-d: device is mandatory");
        return 1;
    }
    if (para.alias.empty()) {
        logging::critical("-u: alias is mandatory");
        return 1;
    }

    // Alias must be of form <detName>_<detSegment>
    size_t found = para.alias.rfind('_');
    if ((found == std::string::npos) || !isdigit(para.alias.back())) {
        logging::critical("-u: alias must have _N suffix");
        return 1;
    }
    para.detName = para.alias.substr(0, found);
    para.detSegment = std::stoi(para.alias.substr(found+1, para.alias.size()));

    get_kwargs(para, kwargs_str);

    para.nworkers = 10;
    para.batchSize = 32; // Must be a power of 2
    para.maxTrSize = 4 * 1024 * 1024;
    para.nTrBuffers = 8; // Power of 2 greater than the maximum number of
                         // transitions in the system at any given time, e.g.,
                         // MAX_LATENCY * (SlowUpdate rate), in same units
    try {
        Drp::PGPDetectorApp app(para);
        app.run();
        app.handleReset(json({}));
        std::cout<<"end of drp main\n";
        return 0;
    }
    catch (std::exception& e)  { logging::critical("%s", e.what()); }
    catch (std::string& e)     { logging::critical("%s", e.c_str()); }
    catch (char const* e)      { logging::critical("%s", e); }
    catch (...)                { logging::critical("Default exception"); }
    return EXIT_FAILURE;
}
