#ifndef FOCUS_FUNCTIONAL_UNIT_H
#define FOCUS_FUNCTIONAL_UNIT_H

#include <functional>

namespace focus_framework {

    template <typename T_Input, typename T_Output>
    class FocusFunctionalUnit {
    public:
        // Logic signature: Constant reference for inputs, reference for outputs
        using LogicFunc = std::function<void(const T_Input&, T_Output&)>;

        explicit FocusFunctionalUnit(LogicFunc logic) : logic_(logic) {}

        void execute(const T_Input& in, T_Output& out) {
            logic_(in, out);
        }

    private:
        LogicFunc logic_;
    };
}

#endif
