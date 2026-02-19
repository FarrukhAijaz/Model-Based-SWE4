/**
 * @file focus_software_unit.h
 * @brief Defines the abstract base class SoftwareUnit for all software modules.
 * 
 * This class provides a common interface for all software units in the focus framework,
 * including lifecycle hooks and runner management. It is designed to be subclassed.
 */

#ifndef FOCUS_SOFTWARE_UNIT
#define FOCUS_SOFTWARE_UNIT

#include "focus_io.h"
#include "focus_ctx.h"
#include "focus_logger.h"

#include <thread>
#include <functional>
#include <mutex>

namespace focus_framework
{
	/**
     * @brief Abstract base class for all software units in the focus framework.
     * 
     * Defines the lifecycle interface for initialization and periodic triggering,
     * and allows attaching a runner that manages execution.
     */

	class FocusSoftwareUnit
	{

	public:
	
	    /**
         * @brief Default constructor.
         */
		FocusSoftwareUnit()=default;

		/**
         * @brief Default constructor.
         */
		virtual ~FocusSoftwareUnit()=default;
	
        /**
         * @brief Handles asynchronous callbacks, if any.
         * 
         * Typically used after processing input/output during trigger.
         */
        virtual void handle_callbacks() = 0;

        /**
         * @brief Called once for initialization.
         * 
         * Should be overridden to set up initial state or allocate resources.
         */
        virtual void on_init() = 0;

        /**
         * @brief Called on each trigger event.
         * 
         * Should implement the main processing logic. It's expected that input data
         * is read and output data is written during this phase.
         */
        virtual void on_trigger() = 0;
	};
}

#endif // FOCUS_SWU
