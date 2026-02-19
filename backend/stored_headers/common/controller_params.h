#ifndef CONTROLLER_PARAMS_H
#define CONTROLLER_PARAMS_H

#include <array>

struct ControllerParams {
    std::array<float, 3> LookUpKpHlcDv;
    std::array<float, 3> LookUpKiHlcDv;
    std::array<float, 3> LookUpDistErr;
    
    std::array<float, 36> LookUpKpHlcVa;
    std::array<float, 36> LookUpKiHlcVa;
    std::array<float, 36> LookUpVelErr;

    std::array<float, 3> LookUpDenFilter;
    std::array<float, 3> LookUpNumFilter;
    std::array<float, 3> LookUpLeadObjVel;
};

#endif // CONTROLLER_PARAMS_H