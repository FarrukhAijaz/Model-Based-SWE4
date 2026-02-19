
/**
 * @file focus_io.h
 * @brief Defines the FocusIO class used for managing access to data buffers 
 * along with optional callback triggers.
 */

#ifndef FOCUS_IO
#define FOCUS_IO

#include "focus_data_inbox.h"

#include <vector>
#include <iostream>
#include <functional>
#include <chrono>
#include <memory>

namespace focus_framework
{
    /**
     * @brief FocusIO is a templated I/O wrapper around FocusDataInbox. 
     * It enables reading and writing data buffers with optional callback support.
     * 
     * @tparam T The type of data to store.
     * @tparam N The number of historical entries kept (e.g., 2 = current + previous).
     */
    template <typename T, std::size_t N>
    class FocusIO
    {
        private:
            /**
             * @brief Indicates whether a callback has been set.
             */
            bool callback_available_ = {false};

            /**
            * @brief Function to be invoked when trigger_callback() is called.
            */
            std::function<void(void)> callback_function_;

        public:
            /**
             * @brief Shared pointer to the connected FocusDataInbox that stores actual data entries.
             * @note TODO: This should be made private in future revisions.
             */
            std::shared_ptr<focus_framework::FocusDataInbox<T, N>> connected_data_inbox_; // TODO: make this private

            /**
             * @brief Default constructor.
             */
            FocusIO()=default;

            /**
             * @brief Set the data inbox (i.e., the source/sink buffer for this IO port).
             * 
             * @param new_data_inbox Shared pointer to a FocusDataInbox instance.
             */
            void set_data_inbox(std::shared_ptr<focus_framework::FocusDataInbox<T, N>> new_data_inbox)
            {
                connected_data_inbox_ = new_data_inbox;
            }

            /**
             * @brief Set a callback function to be triggered later via trigger_callback().
             * 
             * @param callback A reference to a std::function<void(void)>.
             */
            void set_callback(std::function<void(void)> &callback)
            {
                callback_function_ = callback;
                callback_available_ = true;
            }

            /**
             * @brief Call the registered callback function if it is set.
             */
            void trigger_callback()
            {
                if (callback_available_)
                {
                    callback_function_();
                }
            }

            /**
             * @brief Get a const reference to a specific element in the inbox.
             * 
             * @param index Index to retrieve (0 = newest, N-1 = oldest).
             * @return const T& Reference to the data element.
             * @throws std::out_of_range if index is >= N.
             */
            const T& operator[](const size_t index)
            {
                if (index >= N)
                {
                    throw std::out_of_range("FocusIO index operator out of range");
                }
                
                return connected_data_inbox_->ret_array_[index].get_data_ref();
            }

            /**
             * @brief Check if the newest data item (index 0) is valid.
             * 
             * @return true if valid, false otherwise.
             */
            bool is_valid()
            {
                return connected_data_inbox_->ret_array_[0].is_valid();
            }

            /**
             * @brief Check if the data at a specific index is valid.
             * 
             * @param index Index to check (0 = newest, N-1 = oldest).
             * @return true if valid, false otherwise.
             * @throws std::out_of_range if index is >= N.
             */
            bool is_valid(const size_t index)
            {
                if (index >= N)
                {
                    throw std::out_of_range("FocusIO index operator out of range");
                }

                return connected_data_inbox_->ret_array_[index].is_valid();
            }

            /**
             * @brief Assign new data into the most recent slot and mark it valid.
             * 
             * @param data The data to be written.
             * @return FocusIO<T, N>& Reference to the current object for chaining.
             */
            FocusIO<T,N>& operator=(const T& data)
            {
                connected_data_inbox_->ret_array_[0].get_data_ref() = data;
                connected_data_inbox_->ret_array_[0].set_valid();
                return *this;
            }

            /**
             * @brief Provide pointer-like access to the newest data and mark it valid.
             * 
             * @return T* Pointer to the most recent data object.
             */
            T* operator->()
            {
                connected_data_inbox_->ret_array_[0].set_valid();
                return &(connected_data_inbox_->ret_array_[0].get_data_ref()); 
            }
        
            /**
             * @brief Provide const pointer-like access to the newest data.
             * 
             * @return const T* Const pointer to the most recent data object.
             */
            const T* operator->() const 
            {
                return &(connected_data_inbox_->ret_array_[0].get_data_ref()); 
            }

            /**
             * @brief Cast operator for easy read access to the newest data.
             * 
             * @return const T& Reference to the newest data.
             */
            operator const T&()
            {
                return connected_data_inbox_->ret_array_[0].get_data_ref();
            }
            /**
             * @brief Dereference operator to access the newest data.
             * Automatically marks the slot as valid.
             */
            T& operator*()
            {
                connected_data_inbox_->ret_array_[0].set_valid();
                return connected_data_inbox_->ret_array_[0].get_data_ref();
            }

            /**
             * @brief Const dereference operator to access the newest data.
             */
            const T& operator*() const
            {
                return connected_data_inbox_->ret_array_[0].get_data_ref();
            }
    };
}

#endif 