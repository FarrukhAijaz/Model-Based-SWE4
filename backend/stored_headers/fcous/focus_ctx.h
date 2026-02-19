/**
 * @file focus_ctx.h
 * @brief Defines the FocusCtx class template used to wrap context data for shared access.
 * 
 * This file provides a lightweight wrapper around a context object, allowing for pointer-style
 * access to the underlying data. This is useful for safely sharing and accessing context data
 * across multiple parts of the system while keeping access syntax intuitive.
 */

#ifndef FOCUS_CTX
#define FOCUS_CTX

namespace focus_framework
{
    /**
     * @brief Template class for wrapping a context object with pointer-style access.
     * @tparam T The type of the context object.
     */

    template <typename T>
    class FocusCtx
    {
    public:

        /**
         * @brief Default constructor. Initializes the data pointer to nullptr.
         */
        FocusCtx() = default;

        /**
         * @brief Pointer to the context data.
         */
        T* data_{}; ///< Initialized to nullptr by default.

        /**
         * @brief Accesses the context data as a pointer.
         * Enables usage like: `ctx->member` where `ctx` is of type `FocusCtx<T>`.
         * @return T* Pointer to the context data.
         */
        T* operator->()
        {
            return data_;
        }

        /**
         * @brief Const-access to the context data.
         * Enables usage like: `ctx->member` for `const FocusCtx<T>`.
         * @return const T* Pointer to the context data.
         */
        const T* operator->() const
        {
            return data_;
        }
        
        /**
         * @brief Dereferences the context data.
         */
        T& operator*()
        {
            return *data_;
        }

        /**
         * @brief Const-dereference to the context data.
         */
        const T& operator*() const
        {
            return *data_;
        }
    };
}

#endif
