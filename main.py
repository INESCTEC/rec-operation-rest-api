import threading
import warnings

from fastapi import (
	FastAPI,
	status
)
from fastapi.responses import JSONResponse
from loguru import logger

from helpers.database_interactions import connect_to_sqlite_db
from helpers.log_setting import (
	remove_logfile_handler,
	set_logfile_handler,
	set_stdout_logger
)
from helpers.main_helpers import (
	generate_order_id,
	lem_prices_return_structure,
	milp_return_structure,
	offers_return_structure
)
from schemas.enums import (
	LemOrganization,
	PricingMechanism
)
from schemas.input_schemas import (
	BaseUserParams,
	UserParams
)
from schemas.output_schemas import (
	AcceptedResponse,
	BilateralMILPOutputs,
	MeterIDNotFound,
	OrderNotFound,
	OrderNotProcessed,
	PoolMILPOutputs,
	TimeseriesDataNotFound,
	VanillaOutputs
)
from threads.vanilla_thread import run_vanilla_thread
from threads.dual_thread import run_dual_thread
from threads.loop_thread import run_loop_thread


# Silence deprecation warning for startup and shutdown events
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Initialize the app
app = FastAPI(
	title='Enershare - REC Operation and LEM pricing API',
	description='A REST API designed to calculate the prices in a Local Energy Market (LEM) and '
				'to determine the operational schedule of Battery Energy Storage System (BESS) assets '
				'within a Renewable Energy Community (REC).',
	version='0.2.0'
)

# Set up logging
set_stdout_logger()
app.state.handler = set_logfile_handler('logs')


# Runs when the API is started: set loggers and create / connect to SQLite database ####################################
@app.on_event('startup')
def startup_event():
	# Get cursor and connection to SQLite database
	app.state.conn, app.state.cursor = connect_to_sqlite_db()


# Runs when the API is closed: remove logger handlers and disconnect SQLite database
@app.on_event('shutdown')
def shutdown_event():
	# Remove all handlers associated with the logger object
	remove_logfile_handler(app.state.handler)

	# Get cursor and connection to SQLite database
	app.state.conn.close()


# VANILLA ENDPOINTS ####################################################################################################
@app.post('/vanilla/{pricing_mechanism}',
		  description='Calculate an array of LEM prices using the selected pricing mechanism. <br />'
					  'No Mixed Integer Linear Programming (MILP) is solved. '
					  'The LEM offers are formulated solely on the basis of the meters’ historical or '
					  'projected net consumption and their corresponding opportunity costs',
          status_code=status.HTTP_202_ACCEPTED,
          tags=['Calculate LEM Prices'])
def vanilla(pricing_mechanism: PricingMechanism, user_params: UserParams) -> AcceptedResponse:
	# generate an order ID for the user to fetch the results when ready
	logger.info('Generating unique order ID.')
	id_order = generate_order_id()

	# get the type of mechanism select for price computation
	pm = pricing_mechanism.value

	# update the database with the new order ID
	logger.info('Creating registry in database for new order ID.')
	app.state.cursor.execute('''
		INSERT INTO Orders (order_id, processed, error, message, request_type, lem_organization, pricing_mechanism)
		VALUES (?, ?, ?, ?, ?, ?, ?)
	''', (id_order, False, '', '', 'vanilla', 'pool', pm))
	app.state.conn.commit()

	# initiate a parallel process (thread) to start computing the prices
	# while a message is immediately sent to the user
	logger.info('Launching thread.')
	threading.Thread(target=run_vanilla_thread,
					 args=(pricing_mechanism, user_params, id_order, app.state.conn, app.state.cursor)).start()

	logger.info('Returning confirmation message with order ID.')
	return JSONResponse(content={'message': 'Processing has started. Use the order ID for status updates.',
								 'order_id': id_order},
						status_code=status.HTTP_202_ACCEPTED)


@app.get('/vanilla/{order_id}',
         description='An endpoint for fetching the results of a "vanilla" request, given the order ID.',
         responses={
	         202: {'model': OrderNotProcessed, 'description': 'Order found but not yet processed.'},
	         404: {'model': OrderNotFound, 'description': 'Order not found.'},
	         412: {'model': MeterIDNotFound, 'description': 'One or more meter IDs not found.'},
			 422: {'model': TimeseriesDataNotFound,
				   'description': 'One or more data points for one or more meter IDs not found.'}
         },
         status_code=status.HTTP_200_OK,
         tags=['Retrieve LEM Prices'])
def vanilla(order_id: str) -> VanillaOutputs:
	# Check if the order_id exists in the database
	logger.info('Searching for order ID in local database.')
	app.state.cursor.execute('''
		SELECT * FROM Orders WHERE order_id = ?
	''', (order_id,))

	# Fetch one row
	order = app.state.cursor.fetchone()
	order_type = order[4]
	if order is not None and order_type == 'vanilla':
		logger.info('Order ID found. Checking if order has already been processed.')
		processed = bool(order[1])
		error = order[2]
		message = order[3]

		# Check if the order is processed
		if processed:
			logger.info('Order ID processed. Checking if process raised error.')
			if error == '412':
				# If the order is found but was met with missing meter ID(s)
				return JSONResponse(content={'message': message,
											 'order_id': order_id},
									status_code=status.HTTP_412_PRECONDITION_FAILED)

			elif error == '422':
				# If the order is found but was met with missing data point(s)
				return JSONResponse(content={'message': message,
											 'order_id': order_id},
									status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

			else:
				logger.info('Order ID correctly processed. Fetching outputs.')
				# If the order resulted from a request to a "vanilla" endpoint,
				# prepare the response message accordingly
				lem_prices = lem_prices_return_structure(app.state.cursor, order_id)
				offers = offers_return_structure(app.state.cursor, order_id)

				return JSONResponse(content={'order_id': order_id,
											 'lem_prices': lem_prices,
											 'offers': offers},
									status_code=status.HTTP_200_OK)

		else:
			# If the order is found but not processed, return 202 Accepted
			return JSONResponse(content={'message': 'Order found but not yet processed.',
										 'order_id': order_id},
								status_code=status.HTTP_202_ACCEPTED)

	else:
		# If the order is not found, return 404 Not Found
		return JSONResponse(content={'message': 'Order not found.',
									 'order_id': order_id},
							status_code=status.HTTP_404_NOT_FOUND)


# MILP ENDPOINTS #######################################################################################################
@app.post('/dual',
          description='Calculate an array of LEM prices and the operational schedule of the BESS assets '
					  'by executing a purely collective MILP. <br />'
					  'In this process, the shadow prices of a LEM equilibrium constraint are returned as the optimal '
					  'LEM prices.',
          status_code=status.HTTP_202_ACCEPTED,
          tags=['Schedule operation and calculate LEM Prices'])
def dual(user_params: BaseUserParams) -> AcceptedResponse:
	# generate an order ID for the user to fetch the results when ready
	logger.info('Generating unique order ID.')
	id_order = generate_order_id()

	# update the database with the new order ID
	logger.info('Creating registry in database for new order ID.')
	app.state.cursor.execute('''
			INSERT INTO Orders (order_id, processed, error, message, request_type, lem_organization, pricing_mechanism)
			VALUES (?, ?, ?, ?, ?, ?, ?)
		''', (id_order, False, '', '', 'dual', 'pool', ''))
	app.state.conn.commit()

	# initiate a parallel process (thread) to start computing the prices
	# while a message is immediately sent to the user
	logger.info('Launching thread.')
	threading.Thread(target=run_dual_thread,
					 args=(user_params, id_order, app.state.conn, app.state.cursor)).start()

	return JSONResponse(content={'message': 'Processing has started. Use the order ID for status updates.',
								 'order_id': id_order},
						status_code=status.HTTP_202_ACCEPTED)


@app.post('/loop/{lem_organization}/{pricing_mechanism}',
          description='Calculate an array of LEM prices and the operational schedule of the BESS assets '
					  'by implementing an iterative algorithm. <br />'
					  'In this process, successive two-stage MILP are solved until a specified stopping criterion '
					  'is achieved. Each two-stage MILP procedure is executed with LEM prices that are calculated '
					  'based on the user-defined pricing mechanism. '
					  'The offers are formulated based on the net loads that result from the previously solved MILP.',
          status_code=status.HTTP_202_ACCEPTED,
          tags=['Schedule operation and calculate LEM Prices'])
def loop(pricing_mechanism: PricingMechanism,
		 lem_organization: LemOrganization,
		 user_params: UserParams) -> AcceptedResponse:
	# generate an order ID for the user to fetch the results when ready
	logger.info('Generating unique order ID.')
	id_order = generate_order_id()

	# get the type of mechanism select for price computation
	pm = pricing_mechanism.value

	# get the LEM organization
	lo = lem_organization.value

	# update the database with the new order ID
	logger.info('Creating registry in database for new order ID.')
	app.state.cursor.execute('''
			INSERT INTO Orders (order_id, processed, error, message, request_type, lem_organization, pricing_mechanism)
			VALUES (?, ?, ?, ?, ?, ?, ?)
		''', (id_order, False, '', '', 'loop', lo, pm))
	app.state.conn.commit()

	# initiate a parallel process (thread) to start computing the prices
	# while a message is immediately sent to the user
	logger.info('Launching thread.')

	threading.Thread(target=run_loop_thread,
				 args=(pm, lo, user_params, id_order, app.state.conn, app.state.cursor)).start()

	logger.info('Returning confirmation message with order ID.')

	return JSONResponse(content={'message': 'Processing has started. Use the order ID for status updates.',
								 'order_id': id_order},
						status_code=status.HTTP_202_ACCEPTED)


@app.get('/dual/{order_id}',
         description='An endpoint for fetching the results of a request that involves solving one or several MILP, '
					 'given the order ID.',
         responses={
	         202: {'model': OrderNotProcessed, 'description': 'Order found but not yet processed.'},
	         404: {'model': OrderNotFound, 'description': 'Order not found.'},
	         412: {'model': MeterIDNotFound, 'description': 'One or more meter IDs not found.'},
			 422: {'model': TimeseriesDataNotFound,
				   'description': 'One or more data point for one or more meter IDs not found.'}
         },
         status_code=status.HTTP_200_OK,
         tags=['Retrieve operation and LEM prices'])
def dual(order_id: str) -> PoolMILPOutputs:
	# Check if the order_id exists in the database
	logger.info('Searching for order ID in local database.')
	app.state.cursor.execute('''
		SELECT * FROM Orders WHERE order_id = ?
	''', (order_id,))

	# Fetch one row
	order = app.state.cursor.fetchone()
	order_type = order[4]
	lem_organization = order[5]
	if order is not None and order_type == 'dual' and lem_organization == 'pool':
		logger.info('Order ID found. Checking if order has already been processed.')
		processed = bool(order[1])
		error = order[2]
		message = order[3]

		# Check if the order is processed
		if processed:
			logger.info('Order ID processed. Checking if process raised error.')
			if error == '412':
				# If the order is found but was met with missing meter ID(s)
				return JSONResponse(content={'message': message,
											 'order_id': order_id},
									status_code=status.HTTP_412_PRECONDITION_FAILED)

			elif error == '422':
				# If the order is found but was met with missing data point(s)
				return JSONResponse(content={'message': message,
											 'order_id': order_id},
									status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

			else:
				logger.info('Order ID correctly processed. Fetching outputs.')
				# If the order resulted from a request to a "vanilla" endpoint,
				# prepare the response message accordingly
				milp_return = milp_return_structure(app.state.cursor, order_id, 'pool')

				return JSONResponse(content=milp_return,
									status_code=status.HTTP_200_OK)

		else:
			# If the order is found but not processed, return 202 Accepted
			return JSONResponse(content={'message': 'Order found but not yet processed.',
										 'order_id': order_id},
								status_code=status.HTTP_202_ACCEPTED)

	else:
		# If the order is not found, return 404 Not Found
		return JSONResponse(content={'message': 'Order not found.',
									 'order_id': order_id},
							status_code=status.HTTP_404_NOT_FOUND)


@app.get('/loop/pool/{order_id}',
         description='An endpoint for fetching the results of a request that involves solving one or several MILP, '
					 'given the order ID.',
         responses={
	         202: {'model': OrderNotProcessed, 'description': 'Order found but not yet processed.'},
	         404: {'model': OrderNotFound, 'description': 'Order not found.'},
	         412: {'model': MeterIDNotFound, 'description': 'One or more meter IDs not found.'},
			 422: {'model': TimeseriesDataNotFound,
				   'description': 'One or more data point for one or more meter IDs not found.'}
         },
         status_code=status.HTTP_200_OK,
         tags=['Retrieve operation and LEM prices'])
def loop_pool(order_id: str) -> PoolMILPOutputs:
	# Check if the order_id exists in the database
	logger.info('Searching for order ID in local database.')
	app.state.cursor.execute('''
		SELECT * FROM Orders WHERE order_id = ?
	''', (order_id,))

	# Fetch one row
	order = app.state.cursor.fetchone()
	order_type = order[4]
	lem_organization = order[5]
	if order is not None and order_type == 'loop' and lem_organization == 'pool':
		logger.info('Order ID found. Checking if order has already been processed.')
		processed = bool(order[1])
		error = order[2]
		message = order[3]

		# Check if the order is processed
		if processed:
			logger.info('Order ID processed. Checking if process raised error.')
			if error == '412':
				# If the order is found but was met with missing meter ID(s)
				return JSONResponse(content={'message': message,
											 'order_id': order_id},
									status_code=status.HTTP_412_PRECONDITION_FAILED)

			elif error == '422':
				# If the order is found but was met with missing data point(s)
				return JSONResponse(content={'message': message,
											 'order_id': order_id},
									status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

			else:
				logger.info('Order ID correctly processed. Fetching outputs.')
				# If the order resulted from a request to a "vanilla" endpoint,
				# prepare the response message accordingly
				milp_return = milp_return_structure(app.state.cursor, order_id, 'pool')

				return JSONResponse(content=milp_return,
									status_code=status.HTTP_200_OK)

		else:
			# If the order is found but not processed, return 202 Accepted
			return JSONResponse(content={'message': 'Order found but not yet processed.',
										 'order_id': order_id},
								status_code=status.HTTP_202_ACCEPTED)

	else:
		# If the order is not found, return 404 Not Found
		return JSONResponse(content={'message': 'Order not found.',
									 'order_id': order_id},
							status_code=status.HTTP_404_NOT_FOUND)


@app.get('/loop/bilateral/{order_id}',
         description='An endpoint for fetching the results of a request that involves solving one or several MILP, '
					 'given the order ID.',
         responses={
	         202: {'model': OrderNotProcessed, 'description': 'Order found but not yet processed.'},
	         404: {'model': OrderNotFound, 'description': 'Order not found.'},
	         412: {'model': MeterIDNotFound, 'description': 'One or more meter IDs not found.'},
			 422: {'model': TimeseriesDataNotFound,
				   'description': 'One or more data point for one or more meter IDs not found.'}
         },
         status_code=status.HTTP_200_OK,
         tags=['Retrieve operation and LEM prices'])
def loop_bilateral(order_id: str) -> BilateralMILPOutputs:
	# Check if the order_id exists in the database
	logger.info('Searching for order ID in local database.')
	app.state.cursor.execute('''
		SELECT * FROM Orders WHERE order_id = ?
	''', (order_id,))

	# Fetch one row
	order = app.state.cursor.fetchone()
	order_type = order[4]
	lem_organization = order[5]
	if order is not None and order_type == 'loop' and lem_organization == 'bilateral':
		logger.info('Order ID found. Checking if order has already been processed.')
		processed = bool(order[1])
		error = order[2]
		message = order[3]

		# Check if the order is processed
		if processed:
			logger.info('Order ID processed. Checking if process raised error.')
			if error == '412':
				# If the order is found but was met with missing meter ID(s)
				return JSONResponse(content={'message': message,
											 'order_id': order_id},
									status_code=status.HTTP_412_PRECONDITION_FAILED)

			elif error == '422':
				# If the order is found but was met with missing data point(s)
				return JSONResponse(content={'message': message,
											 'order_id': order_id},
									status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)

			else:
				logger.info('Order ID correctly processed. Fetching outputs.')
				# If the order resulted from a request to a "vanilla" endpoint,
				# prepare the response message accordingly
				milp_return = milp_return_structure(app.state.cursor, order_id, 'bilateral')

				return JSONResponse(content=milp_return,
									status_code=status.HTTP_200_OK)

		else:
			# If the order is found but not processed, return 202 Accepted
			return JSONResponse(content={'message': 'Order found but not yet processed.',
										 'order_id': order_id},
								status_code=status.HTTP_202_ACCEPTED)

	else:
		# If the order is not found, return 404 Not Found
		return JSONResponse(content={'message': 'Order not found.',
									 'order_id': order_id},
							status_code=status.HTTP_404_NOT_FOUND)


if __name__ == '__main__':
	import uvicorn
	uvicorn.run(app, host="127.0.0.1", port=8000)
