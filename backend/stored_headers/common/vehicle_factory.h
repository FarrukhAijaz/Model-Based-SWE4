#ifndef METHOD_FACTORY_H
#define METHOD_FACTORY_H

#include <iostream>
#include <memory>
#include "factory.h"

class VehicleFactory : public Factory {
    public:
        std::unique_ptr<Vehicle> createVehicle(Vehicles vehicle) const override
        {
            std::unique_ptr<Vehicle> result{nullptr};

            if (vehicle == Vehicles::LongHaulTruck)
            {
                result = std::make_unique<LongHaulTruck>();
            }
            else
            {
                // FOCUS_LOG_ERROR("Error: Invalid vehicle type ");
            }

            return result; 
        }
};

#endif // VEHCILE_FACTORY_H