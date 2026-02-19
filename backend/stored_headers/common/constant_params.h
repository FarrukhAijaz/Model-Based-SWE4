#ifndef CONSTANT_PARAMS_H
#define CONSTANT_PARAMS_H

namespace ConstantParams {
    inline constexpr float kMps2Kph = 3.6f;
    inline constexpr float kTDeltaHLC = 0.05f;             // unit: seconds
    inline constexpr float kAntiWindupLowLimDV = -1.225f;  // unit: N/A
    inline constexpr float kAntiWindupUpLimDV = 1.225f;    // unit: N/A
    inline constexpr float kBackCalculationCoefDV = 15.0f; // unit: N/A
    inline constexpr float kSlowingDownThreshold = 1.75f;  // unit m/s
    inline constexpr float kSpeedingUpThreshold = 0.27f;   // unit m/s
    inline constexpr float kBHAccel = -2.5f;               // unit m/s^2
    inline constexpr float kStopped = 0.0f;                // unit m/s^2
    inline constexpr float kStopping = 0.1f;               // unit m/s
    inline constexpr float kBackCalculationCoefVA = 30.0f; // unit: N/A
    inline constexpr float kAntiWindupUpLimVa = 0.5;       
    inline constexpr float kAntiWindupLowLimVa = -0.5;
    inline constexpr float kSlowingDownThresholdDV = 1.0f;
    inline constexpr float kAxMinRateLimit = -3.5f;
    inline constexpr float kAxMaxRateLimit = 1.0f; 
    /* Distance loop lookup table boundaries */
    inline constexpr float kPHlcDvMin = 0.25f;
    inline constexpr float kPHlcDvMax = 6.0f;
    inline constexpr float kIHlcDvMin = 0.01f;
    inline constexpr float kIHlcDvMax = 0.4f;
    inline constexpr float kMinDistError = -50.0f;
    inline constexpr float kMaxDistError = 50.0f;
    /* Velocity loop lookup table boundaries */
    inline constexpr float kPHlcVaMin = 0.1f;
    inline constexpr float kPHlcVaMax = 0.06f;
    inline constexpr float kIHlcVaMin = 0.000001f;
    inline constexpr float kIHlcVaMax = 0.000001f;
    inline constexpr float kMinVelError = -12.0f;
    inline constexpr float kMaxVelError = 23.0f;
    /* Filter Coefficients */
    inline constexpr float kNumCoeff = 0.2212;
    inline constexpr float kDenCoeff = -0.7788;
    inline constexpr float kMinNumFilter = 0.0699;
    inline constexpr float kMaxNumFilter = 0.0392;
    inline constexpr float kMinDenFilter = -0.9301;
    inline constexpr float kMaxDenFilter = -0.9608;
    inline constexpr float kMinObjVel = 0.0;
    inline constexpr float kMaxObjVel = 33.333;
}; // namespace ConstantParams

#endif // CONSTANT_PARAMS_H