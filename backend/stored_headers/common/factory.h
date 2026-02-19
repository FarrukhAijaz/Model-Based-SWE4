#ifndef VEHICLE_FACTORY_H
#define VEHICLE_FACTORY_H

#include <vehicle.h>
#include <long_haul_truck.h>
#include <memory>

class Factory {
    public:
        enum class Vehicles {
            LongHaulTruck,
            BEV,
        };
        virtual std::unique_ptr<Vehicle> createVehicle(Vehicles vehicle) const = 0;
        virtual ~Factory() = default;
};

#endif // VEHICLE_FACTORY_H