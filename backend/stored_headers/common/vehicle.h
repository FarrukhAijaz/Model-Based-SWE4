#ifndef VEHICLE_H
#define VEHICLE_H

// #include "ControllerParams.hpp"
#include <array>
#include "focus_software_unit.h"
// #include "edms_lead_obj_info.hpp"

class Vehicle {

    public:
        virtual ~Vehicle() = default;
        virtual float getInterpolatedKpDvGain(float dist_error) const = 0;
        virtual float getInterpolatedKiDvGain(float dist_error) const = 0;
        virtual float getInterpolatedKpVaGain(float error_val) const = 0;
        virtual float getInterpolatedKiVaGain(float error_val) const = 0;
        virtual float getInterpolatedLonNegativeJerkMaxLimit(float current_velocity_mps) const = 0;
        virtual float getInterpolatedMinTimeGap(float current_velocity_sat_kph) const = 0;
        virtual float getSaturatedInput(float input, float min, float max) const = 0;
        virtual float getInterpolatedDenFilter(float edms_lead_obj_info_vel) const = 0;
        virtual float getInterpolatedNumFilter(float edms_lead_obj_info_vel) const = 0;

    protected:

        template <typename T, std::size_t N>
        T interpolate2DTable(const std::array<T, N> &xData, const std::array<T, N> &yData, const T &x) const {
            T result{};

            if (xData.size() != yData.size() || xData.empty()) {
            // FOCUS_LOG_ERROR("Lookup tables must have the same size and be non-empty.");
            }
            if (x <= xData.front()) {
            result = yData.front();
            } else if (x >= xData.back()) {
            result = yData.back();
            } else {
            auto it = std::lower_bound(xData.begin(), xData.end(), x);
            size_t i = std::distance(xData.begin(), it);
            result = yData.at(i - 1) + (x - xData.at(i - 1)) * (yData.at(i) - yData.at(i - 1)) / (xData.at(i) - xData.at(i - 1));
            }
            return result;
        }

        template <typename T>

        T saturateInput(const T &input, const T &min, const T &max) const {
            T result{};
            if (input < min) {
                result = min;
            } else if (input > max) {
                result = max;
            } else {
                result = input;
            }
            return result;
        }
};
#endif