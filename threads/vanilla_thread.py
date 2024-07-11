import sqlite3

from loguru import logger

from helpers.dataspace_interactions import fetch_mock_dataspace
from helpers.main_helpers import (
	build_offers,
	generate_vanilla_outputs
)
from rec_op_lem_prices import (
	vanilla_crossing_value,
	vanilla_mmr,
	vanilla_sdr
)
from schemas.enums import PricingMechanism
from schemas.input_schemas import UserParams


def run_vanilla_thread(pricing_mechanism: PricingMechanism,
					   user_params: UserParams,
					   id_order: str,
					   conn: sqlite3.Connection,
					   curs: sqlite3.Cursor):
	# get the pricing mechanism defined by the user
	pm = pricing_mechanism.value

	# get the necessary meters' data from the dataspace
	logger.info('[THREAD] Fetching data from dataspace.')
	data_df, list_of_datetimes, missing_ids, missing_dts = fetch_mock_dataspace(user_params)

	# if any missing meter ids or missing datetimes in the data for those meter ids was found,
	# update the database with an error and an indication of which data is missing
	if missing_ids:
		logger.warning('[THREAD] Missing meter IDs in dataspace.')
		message = f'One or more meter IDs not found on registry system: {missing_ids}'
		curs.execute('''
			UPDATE Orders
			SET processed = ?, error = ?, message = ?
			WHERE order_id = ?
		''', (True, '412', message, id_order))
		conn.commit()

	elif any(missing_dts.values()):
		logger.warning('[THREAD] Missing data points in dataspace.')
		missing_pairs = {k: v for k, v in missing_dts.items() if v}
		message = f'One or more data point for one or more meter IDs not found on registry system: {missing_pairs}'
		curs.execute('''
			UPDATE Orders
			SET processed = ?, error = ?, message = ?
			WHERE order_id = ?
		''', (True, '422', message, id_order))
		conn.commit()

	# otherwise, proceed normally
	else:
		# compute the buying and selling offers to be used for the price calculation
		logger.info('[THREAD] Building offers.')
		buy_offers_list, sell_offers_list = build_offers(data_df, list_of_datetimes)

		# compute the LEM price for each time step, defined by the start datetime, end datetime and step of t,
		# plus the
		logger.info('[THREAD] Computing prices.')
		lem_prices = {}
		output_price = None
		for idx, dt in enumerate(list_of_datetimes):
			if pm == 'mmr':
				output_price = vanilla_mmr(
					buys=buy_offers_list[idx],
					sells=sell_offers_list[idx],
					pruned=True,
					divisor=user_params.mmr_divisor
				)

			elif pm == 'sdr':
				output_price = vanilla_sdr(
					buys=buy_offers_list[idx],
					sells=sell_offers_list[idx],
					pruned=True,
					compensation=user_params.sdr_compensation
				)

			elif pm == 'crossing_value':
				output_price = vanilla_crossing_value(
					buys=buy_offers_list[idx],
					sells=sell_offers_list[idx],
					small_increment=0.0
				)

			# Round the result to the 2nd decimal place, i.e., to the cents (prices are given in €/kWh)
			lem_prices[dt] = round(output_price, 2)

		# Prepare the outputs to be stored in the local database
		logger.info('[THREAD] Updating database with results.')
		lem_prices, offers = generate_vanilla_outputs(buy_offers_list, sell_offers_list, lem_prices)

		# update the database with the new order ID
		curs.execute('''
			UPDATE Orders
			SET processed = ?
			WHERE order_id = ?
		''', (True, id_order))

		for price in lem_prices:
			curs.execute('''
				INSERT INTO Lem_Prices (order_id, datetime, value)
				VALUES (?, ?, ?)
			''', (id_order, price['datetime'], price['value']))

		for offer in offers:
			curs.execute('''
				INSERT INTO Offers (order_id, datetime, meter_id, amount, value, type)
				VALUES (?, ?, ?, ?, ?, ?)
			''', (id_order, offer['datetime'], offer['meter_id'],
				  offer['amount'], offer['value'], offer['type']))

		conn.commit()

		logger.info('[THREAD] Finished!')
