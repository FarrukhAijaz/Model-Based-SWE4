/**
 * @file focus_data_inbox.h
 * @brief Provides templated classes for data buffering and validation logic used in the Focus Framework.
 * 
 * Defines FocusDataSlot for wrapping individual data items with validity flags,
 * and FocusDataInbox for managing a fixed-size array of such slots.
 */

#ifndef FOCUS_DATA_INBOX
#define FOCUS_DATA_INBOX

#include <vector>
#include <array>
#include <iostream>
#include <functional>
#include <chrono>
#include <memory>
#include <type_traits>

namespace focus_framework 
{
    /**
     * @brief FocusDataSlot is a wrapper for a data pointer along with a status byte used to track validity.
     * 
     * @tparam T The type of the data being wrapped.
     */
    template <typename T>
    class FocusDataSlot
    {
    public:

        /**
         * @brief If T is const, pointer_type becomes const T*, otherwise T*.
         */
        using pointer_type = typename std::conditional<std::is_const<T>::value, const T*, T*>::type;
    
        /**
         * @brief Pointer to the actual data.
         */
        pointer_type data_ {nullptr};

        /**
         * @brief Status byte for tracking validity and other flags.
         */
        uint8_t status_ {0};

        /**
         * @brief Bitmask used to represent the validity of the data.
         */
        const uint8_t valid_mask_ = 0b00000001;

        /**
         * @brief Default constructor.
         */
        FocusDataSlot()=default;
        
        /**
         * @brief Get a reference to the data pointed by the internal pointer.
         * 
         * @return decltype(*data) Reference to the data.
         */
        auto get_data_ref() -> decltype(*data_) {
            return *data_;
        }


        /**
         * @brief Checks if the current data slot is valid.
         * 
         * @return true if valid, false otherwise.
         */
        bool is_valid()
        {
            bool return_value = false;
            if ((status_ & valid_mask_) == 0)
            {
                return_value = false;
            }
            else
            {
                return_value = true;
            }
            return return_value;
        }


        /**
         * @brief Marks the data slot as valid.
         */
        void set_valid()
        {
            status_ |= valid_mask_;
        }


        /**
         * @brief Clears the valid flag from the data slot.
         */
        void clear_valid()
        {
            status_ &= ~valid_mask_;
        }
    };

    /**
     * @brief FocusDataInbox manages an array of FocusDataSlot entries and 
     * provides access to valid elements. This class is inspired by EDMS's
     * double circular approach.
     * 
     * @tparam T The type of data to store.
     * @tparam N The number of slots in the inbox.
     */
    template <typename T, std::size_t N>
    class FocusDataInbox
    {
    public:
        /**
         * @brief Array of data slots.
         */
        std::array <FocusDataSlot<T>, N> ret_array_;

        /**
         * @brief Current count of valid elements in the array.
         */
        uint32_t valid_size_ = {0};

        /**
         * @brief Default constructor.
         */
        FocusDataInbox()=default;

        /**
         * @brief Get the number of valid elements.
         * 
         * @return uint32_t Number of valid entries.
         */
        uint32_t get_size()
        {
            return valid_size_;
        }

        /**
         * @brief Get reference to the data at the given index.
         * If the index is out of bounds, fallback to the last element.
         * 
         * @param index Index to access.
         * @return T& Reference to the data element.
         */
        T& operator[](size_t index)
        {            
            if (index >= valid_size_)
            {
                index = N-1;
            }
            
            return ret_array_[index].get_data_ref();
        }
    };

} // namespace focus_framework

#endif // FOCUS_FocusDataInbox
