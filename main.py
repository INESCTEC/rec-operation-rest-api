from helpers.generate_order_id import generate_order_id
from fastapi import (
	FastAPI,
	HTTPException,
	status
)
from fastapi.responses import JSONResponse
from schemas.enums import PricingMechanism
from schemas.input_schemas import (
	MILPUserParams,
	UserParams
)
from schemas.output_schemas import (
	AcceptedResponse,
	MemberIDNotFound,
	OrderNotFound,
	OrderNotProcessed,
	OrderProcessed
)


# Example storage for orders
orders_db = {}


# Model for the order
class OrderResult:
	def __init__(self, order_id: str, result: str, processed: bool = False, error: bool = False):
		self.order_id = order_id
		self.result = result
		self.processed = processed
		self.error = error


app = FastAPI(
	title='Enershare - REC LEM pricing API',
	description='REST API for computing local energy market (LEM) prices for a Renewable Energy Community (REC).',
	version='0.1.0'
)


@app.post('/vanilla/{pricing_mechanism}',
          description='Compute a LEM prices\' array based on the chosen pricing mechanism. <br />'
                      'No MILP is solved, the LEM offers are constructed based only on the members\' historical or '
                      'estimated net consumption and respective opportunity costs.',
          status_code=status.HTTP_202_ACCEPTED,
          tags=['Calculate LEM Prices'])
def vanilla(pricing_mechanism: PricingMechanism, user_params: UserParams) -> AcceptedResponse:
	member_ids = user_params.member_ids
	pm = pricing_mechanism.value
	order_id = generate_order_id()
	if pm == 'mmr':
		pass
	if pm == 'sdr':
		pass
	if pm == 'crossing_value':
		pass
	return {
		'message': 'Processing has started. Use the order ID for status updates.',
		'order_id': order_id
	}


@app.post('/dual',
          description='Compute a LEM prices\' array by running a purely collective post-delivery MILP where the shadow '
		              'prices of a LEM equilibrium constraint are returned as the optimal LEM prices',
          status_code=status.HTTP_202_ACCEPTED,
          tags=['Calculate LEM Prices'])
def dual(user_params: MILPUserParams) -> AcceptedResponse:
	order_id = generate_order_id()
	return {
		'message': 'Processing has started. Use the order ID for status updates.',
		'order_id': order_id
	}


@app.post('/loop/{pricing_mechanism}',
          description='Compute a LEM prices\' array by running an overarching iterative algorithm where successive '
                      'two-stage MILP are solved for the post-delivery timeframe until a stopping criterion is met. '
                      'Each two-stage MILP procedure is run considering LEM prices calculated under the pricing '
                      'mechanism defined by the user, where offers are constructed based on the resulting net '
                      'loads resulting from the previous MILP solved.',
          status_code=status.HTTP_202_ACCEPTED,
          tags=['Calculate LEM Prices'])
def loop(pricing_mechanism: PricingMechanism, user_params: MILPUserParams) -> AcceptedResponse:
	member_ids = user_params.member_ids
	pm = pricing_mechanism.value
	order_id = generate_order_id()
	if pm == 'mmr':
		pass
	if pm == 'sdr':
		pass
	if pm == 'crossing_value':
		pass
	return {
		'message': 'Processing has started. Use the order ID for status updates.',
		'order_id': order_id
	}


@app.get('/get_prices/{order_id}',
         description='Endpoint for retrieving a request results\', provided the order ID.',
         responses={
	         202: {'model': OrderNotProcessed, 'description': 'Order found but not yet processed.'},
	         404: {'model': OrderNotFound, 'description': 'Order not found.'},
	         412: {'model': MemberIDNotFound, 'description': 'One or more member IDs not found.'}
         },
         status_code=status.HTTP_200_OK,
         tags=['Retrieve LEM Prices'])
def get_prices(order_id: str) -> OrderProcessed:
	orders_db['123'] = OrderResult(order_id='123', result=None, processed=False)
	# Check if the order_id exists in the database
	if order_id in orders_db:
		order = orders_db[order_id]

		# Check if the order is processed
		if order.processed:
			if order.error:
				raise HTTPException(status_code=412, detail='Precondition Failed.')
			else:
				return order
		else:
			# If the order is found but not processed, return 202 Accepted
			return JSONResponse(content={'message': 'Order found but not yet processed.',
			                             'order_id': order.order_id},
			                    status_code=status.HTTP_202_ACCEPTED)
	else:
		# If not found, raise an HTTPException with a 404 status code
		raise HTTPException(status_code=404, detail='Order not found.')
