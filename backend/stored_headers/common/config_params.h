#ifndef CONFIG_PARAMS_H
#define CONFIG_PARAMS_H

#include <iostream>
#include <string>
#include <array>
#include <algorithm>

struct JerkValues {
    std::array<float, 4> LookUpCurrentVelocityMps;
    std::array<float, 4> LookUpLonJerkNgtMax;
};

struct MinTgapValues {
    std::array<float, 14> LookUpCurrentVelocitySatKph;
    std::array<float, 14> LookUpMinTgap;
};

struct ConfigValues {
    // Float parameters
    static constexpr float kVMin = 0.75f;
    static constexpr float kMps2Kph = 3.6f;
    static constexpr float kTimeGap1 = 3.55f;
    static constexpr float kTimeGap2 = 3.05f;
    static constexpr float kTimeGap3 = 2.6f;
    static constexpr float kTimeGap4 = 2.2f;
    static constexpr float kNoSet = 0.0f;
    static constexpr float kLonJerkPstNominal = 2.0f;
    static constexpr float kLonJerkPstMax = 5.0f;
    static constexpr float kLonJerkNgtNominal = -2.0f;
    static constexpr float kMinLaneCurv = 0.0000078125f;
    static constexpr float kLimAyCurve = 1.3f;
    static constexpr float kHystAyCurve = 1.3f;
    static constexpr float kHystTgapCurr = 1.015f;
    static constexpr float kHystTgapCondExit = 1.1f;
    // Uint8 parameters
	static constexpr uint8_t kVsetMinACC = 20;
    static constexpr uint8_t kVoprMaxO2MF = 120;
    static constexpr uint8_t kVoprMaxNominal = 90;
    // Lower longitudinal jerk limit lookup table boundaries
    static constexpr float kLonJerkNgtMaxVMin = -5.0f;
    static constexpr float kLonJerkNgtMaxVMax = -2.5f;
    static constexpr float kCurrentVelocityMpsMin = 0.0f;
    static constexpr float kCurrentVelocityMpsMax = 25.0f;
    // Minimum time gap lookup table boundaries
    static constexpr float kLookUpMinTgapVSatKphMin = 3.2f;
    static constexpr float kLookUpMinTgapVSatKphMax = 3.6f;
    static constexpr float kCurrentVelocitySatKphMin = 2.7f;
    static constexpr float kCurrentVelocitySatKphMax = 120.0f;
};

// Generate a 32-bit FNV-1a hash
constexpr uint32_t fnv1aHash(const char* str) {
    uint32_t hash = 2166136261u;

    if (!str) return hash;

    while (*str) {
        hash ^= static_cast<uint8_t>(*str++);
        hash *= 16777619u;
        if (!*str) break;
    }

    return hash;
}

// Define a struct to store hash-value pairs for integer parameters
struct KeyValueInt {
    uint32_t hash;
    uint8_t value;
};

// Define a struct to store hash-value pairs for float parameters
struct KeyValueFloat {
    uint32_t hash;
    float value;
};

//Lookup table for integer parameters
constexpr KeyValueInt lookupTableInt[] = {
    {fnv1aHash("kVsetMinACC"), ConfigValues::kVsetMinACC},
    {fnv1aHash("kVoprMaxO2MF"), ConfigValues::kVoprMaxO2MF},
    {fnv1aHash("kVoprMaxNominal"), ConfigValues::kVoprMaxNominal}
};
constexpr size_t lookupTableIntSize = sizeof(lookupTableInt) / sizeof(lookupTableInt[0]);

//Lookup table for float parameters
constexpr KeyValueFloat lookupTableFloat[] = {
    {fnv1aHash("kVMin"), ConfigValues::kVMin},
    {fnv1aHash("kMps2Kph"), ConfigValues::kMps2Kph},
    {fnv1aHash("kTimeGap1"), ConfigValues::kTimeGap1},
    {fnv1aHash("kTimeGap2"), ConfigValues::kTimeGap2},
    {fnv1aHash("kTimeGap3"), ConfigValues::kTimeGap3},
    {fnv1aHash("kTimeGap4"), ConfigValues::kTimeGap4},
    {fnv1aHash("kNoSet"), ConfigValues::kNoSet},
    {fnv1aHash("kLonJerkPstNominal"), ConfigValues::kLonJerkPstNominal},
    {fnv1aHash("kLonJerkPstMax"), ConfigValues::kLonJerkPstMax},
    {fnv1aHash("kLonJerkNgtNominal"), ConfigValues::kLonJerkNgtNominal},
    {fnv1aHash("kMinLaneCurv"), ConfigValues::kMinLaneCurv},
    {fnv1aHash("kLimAyCurve"), ConfigValues::kLimAyCurve},
    {fnv1aHash("kHystAyCurve"), ConfigValues::kHystAyCurve},
    {fnv1aHash("kHystTgapCurr"), ConfigValues::kHystTgapCurr},
    {fnv1aHash("kHystTgapCondExit"), ConfigValues::kHystTgapCondExit}
};
constexpr size_t lookupTableFloatSize = sizeof(lookupTableFloat) / sizeof(lookupTableFloat[0]);

// Function to get integer parameter value
constexpr uint8_t getIntParamValue(const char* key) {
    if (!key || !*key) return 0;

    const uint32_t hash = fnv1aHash(key);

    const KeyValueInt* const table = lookupTableInt;

    for (size_t i = 0; i < lookupTableIntSize; ++i) {
        if (table[i].hash == hash) {
            return table[i].value;
        }
    }

    return 0;
}

// Function to get float parameter value
constexpr float getFloatParamValue(const char* key) {
    if (!key || !*key) return 0.0f;

    const uint32_t hash = fnv1aHash(key);

    const KeyValueFloat* const table = lookupTableFloat;

    for (size_t i = 0; i < lookupTableFloatSize; ++i) {
        if (table[i].hash == hash) {
            return table[i].value;
        }
    }

    return 0.0f;
}

#endif // CONFIG_PARAMS_H