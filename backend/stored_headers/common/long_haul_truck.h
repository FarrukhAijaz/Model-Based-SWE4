#ifndef CONCRETE_VEHICLE_H
#define CONCRETE_VEHICLE_H

#include "config_params.h"
#include "constant_params.h"
#include "controller_params.h"
#include "vehicle.h"
#include <array>
#include <iostream>

class LongHaulTruck : public Vehicle {
    public:
    float getInterpolatedKpDvGain(float dist_error) const override {
        return interpolate2DTable(controller_params_.LookUpDistErr, controller_params_.LookUpKpHlcDv, dist_error);
    }

    float getInterpolatedKiDvGain(float dist_error) const override {
        return interpolate2DTable(controller_params_.LookUpDistErr, controller_params_.LookUpKiHlcDv, dist_error);
    }

    float getInterpolatedKpVaGain(float velocity_error) const override {
        return interpolate2DTable(controller_params_.LookUpVelErr, controller_params_.LookUpKpHlcVa, velocity_error);
    }

    float getInterpolatedKiVaGain(float velocity_error) const override {
        return interpolate2DTable(controller_params_.LookUpVelErr, controller_params_.LookUpKiHlcVa, velocity_error);
    }

    float getInterpolatedLonNegativeJerkMaxLimit(float current_velocity_mps) const override {
        return interpolate2DTable(jerk_values_.LookUpCurrentVelocityMps, jerk_values_.LookUpLonJerkNgtMax, current_velocity_mps);
    }

    float getInterpolatedMinTimeGap(float current_velocity_sat_kph) const override {
        return interpolate2DTable(min_tgap_values_.LookUpCurrentVelocitySatKph, min_tgap_values_.LookUpMinTgap, current_velocity_sat_kph);
    }

    float getSaturatedInput(float input, float min, float max) const override { return saturateInput(input, min, max); }

    float getInterpolatedDenFilter(float edms_lead_obj_info_vel) const override {
        return interpolate2DTable(controller_params_.LookUpLeadObjVel, controller_params_.LookUpDenFilter, edms_lead_obj_info_vel);
    };

    float getInterpolatedNumFilter(float edms_lead_obj_info_vel) const override {
        return interpolate2DTable(controller_params_.LookUpLeadObjVel, controller_params_.LookUpNumFilter, edms_lead_obj_info_vel);
    };

    private:
    inline static constexpr JerkValues jerk_values_{
        std::array<float, 4>{ConfigValues::kCurrentVelocityMpsMin, 5.0f, 20.0f, ConfigValues::kCurrentVelocityMpsMax},
        std::array<float, 4>{ConfigValues::kLonJerkNgtMaxVMin, -5.0f, -2.5f, ConfigValues::kLonJerkNgtMaxVMax},
    };

    inline static constexpr MinTgapValues min_tgap_values_{
        std::array<float, 14>{ConfigValues::kCurrentVelocitySatKphMin, 7.2f, 10.0f, 20.0f, 30.0f, 40.0f, 50.0f, 60.0f, 70.0f, 80.0f, 90.0f, 100.0f,
                                110.0f, ConfigValues::kCurrentVelocitySatKphMax},
        std::array<float, 14>{ConfigValues::kLookUpMinTgapVSatKphMin, 1.2f, 1.4f, 1.6f, 1.8f, 2.0f, 2.2f, 2.4f, 2.6f, 2.8f, 3.0f, 3.2f, 3.4f,
                                ConfigValues::kLookUpMinTgapVSatKphMax},
    };

    inline static constexpr ControllerParams controller_params_{

        std::array<float, 3>{ConstantParams::kPHlcDvMin, 0.4f, ConstantParams::kPHlcDvMax},
        std::array<float, 3>{ConstantParams::kIHlcDvMin, 0.4f, ConstantParams::kIHlcDvMax},
        std::array<float, 3>{ConstantParams::kMinDistError, 0.0f, ConstantParams::kMaxDistError},

        std::array<float, 36>{
            ConstantParams::kPHlcVaMin,
            0.2447f,
            0.3557f,
            0.4078f,
            0.4407f,
            0.4701f,
            0.4970f,
            0.5210f,
            0.5415f,
            0.5580f,
            0.5701f,
            0.5775f,
            0.5800f,
            0.5775f,
            0.5701f,
            0.5580f,
            0.5415f,
            0.5210f,
            0.4970f,
            0.4701f,
            0.4408f,
            0.4098f,
            0.3777f,
            0.3452f,
            0.3128f,
            0.2810f,
            0.2502f,
            0.2210f,
            0.1935f,
            0.1679f,
            0.1445f,
            0.1233f,
            0.1043f,
            0.0875f,
            0.0728f,
            ConstantParams::kPHlcVaMax,
        },
        std::array<float, 36>{ConstantParams::kIHlcVaMin,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                0.000001,
                                ConstantParams::kIHlcVaMax},

        std::array<float, 36>{ConstantParams::kMinVelError,
                                -11.0f,
                                -10.0f,
                                -9.0f,
                                -8.0f,
                                -7.0f,
                                -6.0f,
                                -5.0f,
                                -4.0f,
                                -3.0f,
                                -2.0f,
                                -1.0f,
                                0.0f,
                                1.0f,
                                2.0f,
                                3.0f,
                                4.0f,
                                5.0f,
                                6.0f,
                                7.0f,
                                8.0f,
                                9.0f,
                                10.0f,
                                11.0f,
                                12.0f,
                                13.0f,
                                14.0f,
                                15.0f,
                                16.0f,
                                17.0f,
                                18.0f,
                                19.0f,
                                20.0f,
                                21.0f,
                                22.0f,
                                ConstantParams::kMaxVelError},

        std::array<float, 3>{ConstantParams::kMinDenFilter, -0.9498, ConstantParams::kMaxDenFilter},
        std::array<float, 3>{ConstantParams::kMinNumFilter, 0.0502, ConstantParams::kMaxNumFilter},
        std::array<float, 3>{ConstantParams::kMinObjVel, 16.666, ConstantParams::kMaxObjVel},
    };
};

#endif // LONG_HAUL_TRUCK_H