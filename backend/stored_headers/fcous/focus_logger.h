/**
 * @file focus_logger.h
 * @brief Defines the abstract base class for logging and concrete 
 * implementations for EDMS and development environment.
 * 
 * Provides a unified logging interface that supports severity
 * levels and captures file and line number metadata.
 */

#ifndef FOCUS_LOGGER
#define FOCUS_LOGGER

#include <fmt/core.h> // FMT is not QM! 
#include <fmt/format.h> // FMT is not QM! 
#include <string>
#include <iostream>

/**
 * @brief Macro to return file name and line number as a formatted string.
 */
#define LOG_LOC() fmt::format("{} ({})", __FILE__, __LINE__)

namespace focus_framework {

    /**
     * @brief Abstract base class for logging functionality.
     */
    class FocusLogger {

        public:
            /**
             * @brief Constructor.
             * @param log_level The logging level.
             */
            explicit FocusLogger(int logLevel) : log_level_(logLevel) {}
        
            /**
             * @brief Virtual destructor.
             */
            virtual ~FocusLogger() = default;

            /**
             * @brief Log an informational message.
             * 
             * @tparam Args Format arguments
             * @param file Source file name
             * @param line Line number in source file
             * @param format Format string
             * @param args Format arguments
             */
            template<typename... Args>
            void log_info(const char* file, int line, fmt::string_view format, Args&&... args) {
                do_log_info(file, line, fmt::format(format, std::forward<Args>(args)...).c_str());
            }

            /**
             * @brief Log an error message.
             */
            template<typename... Args>
            void log_error(const char* file, int line, fmt::string_view format, Args&&... args) {
                do_log_error(file, line, fmt::format(format, std::forward<Args>(args)...).c_str());
            }

            /**
             * @brief Log a warning message.
             */
            template<typename... Args>
            void log_warning(const char* file, int line, fmt::string_view format, Args&&... args) {
                do_log_warning(file, line, fmt::format(format, std::forward<Args>(args)...).c_str());
            }

            /**
             * @brief Log a fatal message.
             */
            template<typename... Args>
            void log_fatal(const char* file, int line, fmt::string_view format, Args&&... args) {
                do_log_fatal(file, line, fmt::format(format, std::forward<Args>(args)...).c_str());
            }

        protected:
            /**
             * @brief Implementation for logging informational messages.
             */
            virtual void do_log_info(const char* file, int line, const char* message) = 0;

            /**
             * @brief Implementation for logging error messages.
             */
            virtual void do_log_error(const char* file, int line, const char* message) = 0;

             /**
             * @brief Implementation for logging warning messages.
             */
            virtual void do_log_warning(const char* file, int line, const char* message) = 0;

            /**
             * @brief Implementation for logging fatal messages.
             */
            virtual void do_log_fatal(const char* file, int line, const char* message) = 0;

            /**
             * @brief Current logging level.
             */
            int log_level_;
    };

    /**
     * @brief Logger implementation that integrates with the EDMS logging infrastructure.
     */
    class EdmsLogger : public FocusLogger {

    public:
        /**
         * @brief Constructor.
         * @param log_level Logging level to use.
         */
        explicit EdmsLogger(int logLevel);

        /**
         * @brief Destructor.
         */
        ~EdmsLogger() override = default;

    protected:
        void do_log_info(const char* file, int line, const char* message) override;
        void do_log_error(const char* file, int line, const char* message) override;
        void do_log_warning(const char* file, int line, const char* message) override;
        void do_log_fatal(const char* file, int line, const char* message) override;
    };

    /**
     * @brief Logger implementation for development/debugging.
     */
    class DevelopmentLogger : public FocusLogger {

    public:
        /**
         * @brief Constructor with custom log level.
         * @param log_level Logging level to use.
         */
        explicit DevelopmentLogger(int logLevel);

        /**
         * @brief Default constructor (log level 1).
         */
        DevelopmentLogger() : FocusLogger(1) {}

        /**
         * @brief Destructor.
         */
        ~DevelopmentLogger() override = default;
        
    protected:
        void do_log_info(const char* file, int line, const char* message) override;
        void do_log_error(const char* file, int line, const char* message) override;
        void do_log_warning(const char* file, int line, const char* message) override;
        void do_log_fatal(const char* file, int line, const char* message) override;
    };

    /**
     * @brief Global logger used throughout the framework.
     */
    extern DevelopmentLogger global_logger_;
    // extern EdmsLogger global_logger_;

} // namespace focus_framework

/**
 * @brief Extracts just the filename from the full path.
 */
#define RELATIVE_FILE (__builtin_strrchr(__FILE__, '/') ? __builtin_strrchr(__FILE__, '/') + 1 : __FILE__)

/**
 * @brief Log macros for convenience, using global_logger_ and automatic file/line metadata.
 */
#define FOCUS_LOG_INFO(...) focus_framework::global_logger_.log_info(RELATIVE_FILE, __LINE__, __VA_ARGS__)
#define FOCUS_LOG_ERROR(...) focus_framework::global_logger_.log_error(RELATIVE_FILE, __LINE__, __VA_ARGS__)
#define FOCUS_LOG_WARNING(...) focus_framework::global_logger_.log_warning(RELATIVE_FILE, __LINE__, __VA_ARGS__)
#define FOCUS_LOG_FATAL(...) focus_framework::global_logger_.log_fatal(RELATIVE_FILE, __LINE__, __VA_ARGS__)

#endif 