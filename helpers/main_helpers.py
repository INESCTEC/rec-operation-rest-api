import pandas as pd
import secrets
import sqlite3

from pydantic import BaseModel
from typing import Union

from rec_op_lem_prices.custom_types.pricing_mechanims_types import OffersList
from rec_op_lem_prices.custom_types.stage_two_milp_pool_types import SinglePreBackpackS2PoolDict
from schemas.enums import LemOrganization
from schemas.output_schemas import (
	LemPrice,
	Offer
)
from schemas.output_schemas import (
	BilateralMILPOutputs,
	PoolMILPOutputs
)


class InnerOffer(BaseModel):
	origin: str
	amount: float
	value: float


def generate_order_id() -> str:
	"""
	Return an unequivocal ID that identifies the request and can be used
	to retrieve the results later on
	:return: a token in string format
	"""
	return secrets.token_urlsafe(45)


def build_offers(all_data_df: pd.core.frame.DataFrame, datetime_range_str: list[str]) \
		-> (list[OffersList], list[OffersList]):
	"""
	Auxiliary function to compute the buying and selling offers from the
	consumption, generation and retail tariffs of the meter ID retrieved from the dataspace.
	:param all_data_df: a pandas DataFrame with 6 columns: datetime, e_c, e_g, meter_id, buy_tariff and sell_tariff
	:param datetime_range_str: list of all datetimes in the horizon, in string format
	:return: the list of buying offers and the list of selling offers
	"""
	buy_offers_per_time_step = []  # list of buying offers (lists), ordered by time step
	sell_offers_per_time_step = []  # list of selling offers (lists), ordered by time step

	# get the net load from the consumption and generation data points
	all_data_df['net_load'] = all_data_df['e_c'] - all_data_df['e_g']

	# divide the data according to the positive and negative net loads
	buyers_df = all_data_df.loc[all_data_df['net_load'] > 0]
	sellers_df = all_data_df.loc[all_data_df['net_load'] < 0]

	# remove unnecessary columns
	buyers_df = buyers_df[['datetime', 'meter_id', 'net_load', 'buy_tariff']]
	sellers_df = sellers_df[['datetime', 'meter_id', 'net_load', 'sell_tariff']]

	# rename columns to match the names of the pricing calculation functions
	buyers_df.rename(columns={
		'meter_id': 'origin',
		'net_load': 'amount',
		'buy_tariff': 'value'
	}, inplace=True)
	sellers_df.rename(columns={
		'meter_id': 'origin',
		'net_load': 'amount',
		'sell_tariff': 'value'
	}, inplace=True)

	# compile all buying and selling offers per time step
	for dt in datetime_range_str:
		# select the rows with dt as the datetime
		dt_buyers_df = buyers_df.loc[buyers_df['datetime'] == dt, ['origin', 'amount', 'value']]
		dt_sellers_df = sellers_df.loc[sellers_df['datetime'] == dt, ['origin', 'amount', 'value']]

		# convert the dataframe into the final format
		dt_buyers_lst = dt_buyers_df.to_dict('records')
		dt_sellers_lst = dt_sellers_df.to_dict('records')

		buy_offers_per_time_step.append(dt_buyers_lst)
		sell_offers_per_time_step.append(dt_sellers_lst)

	return buy_offers_per_time_step, sell_offers_per_time_step


def generate_vanilla_outputs(
		buy_offers: list[list[InnerOffer]],
		sell_offers: list[list[InnerOffer]],
		prices: dict[str, float]) \
		-> (list[LemPrice], list[Offer]):
	"""
	Prepare vanilla outputs to be stored in database.
	:param buy_offers: list with buying offers as computed on main thread
	:param sell_offers: list with selling offers as computed on main thread
	:param prices: list of prices as computed by the pricing library
	:return: list of prices and offers ready to be stored in local database
	"""
	# read the inputs into a pandas structure for easier resample
	lem_prices_series = pd.Series(prices)
	lem_prices_df = lem_prices_series.reset_index()
	lem_prices_df.columns = ['datetime', 'value']
	lem_prices = lem_prices_df.to_dict('records')

	# create the final outputs' offers structure
	offers = []
	for dt_buy_offers, dt_sell_offers, dt in zip(buy_offers, sell_offers, lem_prices_series.index):
		for dt_buy_offer in dt_buy_offers:
			offers.append({
				'datetime': dt,
				'meter_id': dt_buy_offer['origin'],
				'amount': dt_buy_offer['amount'],
				'value': dt_buy_offer['value'],
				'type': 'buy'
			})
		for dt_sell_offer in dt_sell_offers:
			offers.append({
				'datetime': dt,
				'meter_id': dt_sell_offer['origin'],
				'amount': dt_sell_offer['amount'],
				'value': dt_sell_offer['value'],
				'type': 'sell'
			})

	return lem_prices, offers


def lem_prices_return_structure(cursor: sqlite3.Cursor, order_id: str) -> list[LemPrice]:
	"""
	Prepare the structure to be returned with the LEM prices, in accordance with the API specifications
	:param cursor: cursor to the database
	:param order_id: order id provided by the user
	:return: list of prices in the API specified outputs' format
	"""
	# Retrieve the LEM prices calculated for the order ID
	cursor.execute('''
		SELECT * FROM Lem_Prices WHERE order_id = ?
	''', (order_id,))
	lem_prices = cursor.fetchall()

	# Convert to dataframe for easy manipulation
	lem_prices_df = pd.DataFrame(lem_prices)
	lem_prices_df.columns = ['index', 'order_id', 'datetime', 'value']
	del lem_prices_df['index']
	del lem_prices_df['order_id']

	return lem_prices_df.to_dict('records')


def offers_return_structure(cursor: sqlite3.Cursor, order_id: str) -> list[LemPrice]:
	"""
	Prepare the structure to be returned with the offers, in accordance with the API specifications
	:param cursor: cursor to the database
	:param order_id: order id provided by the user
	:return: list of offers in the API specified outputs' format
	"""
	# Retrieve the LEM prices calculated for the order ID
	cursor.execute('''
		SELECT * FROM Offers WHERE order_id = ?
	''', (order_id,))
	offers = cursor.fetchall()

	# Convert to dataframe for easy manipulation
	offers_df = pd.DataFrame(offers)
	offers_df.columns = ['index', 'order_id', 'datetime', 'meter_id', 'amount', 'value', 'type']
	del offers_df['index']
	del offers_df['order_id']

	return offers_df.to_dict('records')


def milp_inputs(all_data_df: pd.core.frame.DataFrame, lem_organization: LemOrganization) \
		-> SinglePreBackpackS2PoolDict:
	"""
	Auxiliary function to build the inputs for post-delivery MILP functions
	:param all_data_df: a pandas DataFrame with 6 columns: datetime, e_c, e_g, meter_id, buy_tariff and sell_tariff
	:param lem_organization: string indicating if LEM is organized in a "pool" or by "bilateral" transactions
	:return: structure ready to run the desired MILP
	"""
	meter_ids = all_data_df['meter_id'].unique()
	nr_time_steps = len(all_data_df['datetime'].unique())

	all_data_df['datetime'] = pd.to_datetime(all_data_df['datetime'])

	# pool market organization - self-consumption tariffs are the same for all transactions
	if lem_organization == 'pool':
		l_grid = [0.01] * nr_time_steps
	# bilateral market organization - self-consumption tariffs must be defined between pairs of meters
	else:
		l_grid = {receiver_meter_id:
					  {provider_meter_id: [0.01] * nr_time_steps
					   for provider_meter_id in meter_ids if provider_meter_id != receiver_meter_id}
				  for receiver_meter_id in meter_ids}

	backpack = {
		'meters': {
			meter_id: {
				'btm_storage': {  # todo: where to fetch these, locally?
					f'storage_{meter_id}': {
						'degradation_cost': 0.01,
						'e_bn': 5.0,
						'eff_bc': 1.0,
						'eff_bd': 1.0,
						'init_e': 0.0,
						'p_max': 5.0,
						'soc_max': 100.0,
						'soc_min': 0.0
					}
				},
				'e_c': all_data_df.loc[
					all_data_df['meter_id'] == meter_ids[0]].sort_values(['datetime'])['e_c'].to_list(),
				'e_g': all_data_df.loc[
					all_data_df['meter_id'] == meter_ids[0]].sort_values(['datetime'])['e_g'].to_list(),
				'l_buy': all_data_df.loc[
					all_data_df['meter_id'] == meter_ids[0]].sort_values(['datetime'])['buy_tariff'].to_list(),
				'l_sell': all_data_df.loc[
					all_data_df['meter_id'] == meter_ids[0]].sort_values(['datetime'])['sell_tariff'].to_list(),
				'max_p': 100  # todo: where to fetch these, locally?
			}
			for meter_id in meter_ids
		},
		'delta_t': 0.25,
		'horizon': nr_time_steps * 0.25,
		'l_extra': 10,
		'l_grid': l_grid,  # todo: where to fetch these? locally?
		'l_lem': [0.0] * nr_time_steps,
		'l_market_buy': [10] * nr_time_steps,
		'l_market_sell': [0] * nr_time_steps,
		'strict_pos_coeffs': True,
		'sum_one_coeffs': True
	}

	return backpack


def milp_return_structure(cursor: sqlite3.Cursor,
						  order_id: str,
						  lem_organization: str) \
		-> Union[BilateralMILPOutputs, PoolMILPOutputs]:
	"""
	Prepare the structure to be returned with the MILP outputs, in accordance with the API specifications
	:param cursor: cursor to the database
	:param order_id: order id provided by the user
	:param lem_organization: string indicating if LEM organization is "pool" or "bilateral"
	:return: structure with MILP outputs in the API specified outputs' format
	"""
	# Initialize the return structure
	milp_return = {
		'order_id': order_id,
	}

	# GENERAL MILP OUTPUTS #############################################################################################
	# Retrieve the general MILP outputs calculated for the order ID
	cursor.execute('''
		SELECT * FROM General_MILP_Outputs WHERE order_id = ?
	''', (order_id,))
	general_milp_outputs = cursor.fetchall()

	# Convert to dataframe for easy manipulation
	general_milp_outputs_df = pd.DataFrame(general_milp_outputs)
	general_milp_outputs_df.columns = ['index', 'order_id', 'objective_value', 'milp_status', 'total_rec_cost']
	del general_milp_outputs_df['index']
	del general_milp_outputs_df['order_id']

	# Create final dictionary substructure
	general_milp_outputs_dict = general_milp_outputs_df.to_dict('records')[0]

	# Update the return dictionary
	milp_return.update(general_milp_outputs_dict)

	# INDIVIDUAL COSTS #################################################################################################
	# Retrieve the individual costs calculated for the order ID
	cursor.execute('''
		SELECT * FROM Individual_Costs WHERE order_id = ?
	''', (order_id,))
	individual_costs = cursor.fetchall()

	# Convert to dataframe for easy manipulation
	individual_costs_df = pd.DataFrame(individual_costs)
	individual_costs_df.columns = ['index', 'order_id', 'meter_id', 'individual_cost']
	del individual_costs_df['index']
	del individual_costs_df['order_id']

	# Create final dictionary substructure
	individual_costs_dict = {
		'individual_costs': individual_costs_df.to_dict('records')
	}

	# Update the return dictionary
	milp_return.update(individual_costs_dict)

	# METER INPUTS #####################################################################################################
	# Retrieve the meter inputs used in the order ID
	cursor.execute('''
		SELECT * FROM Meter_Inputs WHERE order_id = ?
	''', (order_id,))
	meter_inputs = cursor.fetchall()

	# Convert to dataframe for easy manipulation
	meter_inputs_df = pd.DataFrame(meter_inputs)
	meter_inputs_df.columns = ['index', 'order_id', 'meter_id', 'datetime',
							   'energy_generated', 'energy_consumed',
							   'buy_tariff', 'sell_tariff']
	del meter_inputs_df['index']
	del meter_inputs_df['order_id']

	# Create final dictionary substructure
	meter_inputs_dict = {
		'meter_inputs': meter_inputs_df.to_dict('records')
	}

	# Update the return dictionary
	milp_return.update(meter_inputs_dict)

	# METER OUTPUTS ####################################################################################################
	# Retrieve the meter outputs calculated for the order ID
	cursor.execute('''
		SELECT * FROM Meter_Outputs WHERE order_id = ?
	''', (order_id,))
	meter_outputs = cursor.fetchall()

	# Convert to dataframe for easy manipulation
	meter_outputs_df = pd.DataFrame(meter_outputs)
	meter_outputs_df.columns = ['index', 'order_id', 'meter_id', 'datetime',
							   'energy_surplus', 'energy_supplied',
								'net_load', 'bess_energy_charged',
								'bess_energy_discharged', 'bess_energy_content']
	del meter_outputs_df['index']
	del meter_outputs_df['order_id']

	# Create final dictionary substructure
	meter_outputs_dict = {
		'meter_outputs': meter_outputs_df.to_dict('records')
	}

	# Update the return dictionary
	milp_return.update(meter_outputs_dict)

	# LEM TRANSACTIONS #################################################################################################
	if lem_organization == 'pool':
		# Retrieve the meter outputs calculated for the order ID
		cursor.execute('''
				SELECT * FROM Pool_LEM_Transactions WHERE order_id = ?
			''', (order_id,))
		lem_transactions = cursor.fetchall()

		# Convert to dataframe for easy manipulation
		lem_transactions_df = pd.DataFrame(lem_transactions)
		lem_transactions_df.columns = ['index', 'order_id', 'meter_id', 'datetime',
									   'energy_purchased', 'energy_sold']

	else:
		# Retrieve the meter outputs calculated for the order ID
		cursor.execute('''
						SELECT * FROM Bilateral_LEM_Transactions WHERE order_id = ?
					''', (order_id,))
		lem_transactions = cursor.fetchall()

		# Convert to dataframe for easy manipulation
		lem_transactions_df = pd.DataFrame(lem_transactions)
		lem_transactions_df.columns = ['index', 'order_id', 'provider_meter_id',
									   'receiver_mere_id', 'datetime', 'energy']

	del lem_transactions_df['index']
	del lem_transactions_df['order_id']

	# Create final dictionary substructure
	lem_transactions = {
		'lem_transactions': lem_transactions_df.to_dict('records')
	}

	# Update the return dictionary
	milp_return.update(meter_outputs_dict)

	# LEM PRICES #######################################################################################################
	# Retrieve the LEM prices calculated for the order ID
	cursor.execute('''
		SELECT * FROM Lem_Prices WHERE order_id = ?
	''', (order_id,))
	lem_prices = cursor.fetchall()

	# Convert to dataframe for easy manipulation
	lem_prices_df = pd.DataFrame(lem_prices)
	lem_prices_df.columns = ['index', 'order_id', 'datetime', 'value']
	del lem_prices_df['index']
	del lem_prices_df['order_id']

	lem_prices_dict = {
		'lem_prices': lem_prices_df.to_dict('records')
	}

	# Update the return dictionary
	milp_return.update(lem_prices_dict)

	# SELF CONSUMPTION TARIFFS #########################################################################################
	# Retrieve the self-consumption tariffs used for the order ID
	if lem_organization == 'pool':
		cursor.execute('''
			SELECT * FROM Pool_Self_Consumption_Tariffs WHERE order_id = ?
		''', (order_id,))
		self_consumption_tariffs = cursor.fetchall()

		# Convert to dataframe for easy manipulation
		self_consumption_tariffs_df = pd.DataFrame(self_consumption_tariffs)
		self_consumption_tariffs_df.columns = ['index', 'order_id', 'datetime', 'self_consumption_tariff']

	else:
		cursor.execute('''
					SELECT * FROM Bilateral_Self_Consumption_Tariffs WHERE order_id = ?
				''', (order_id,))
		self_consumption_tariffs = cursor.fetchall()

		# Convert to dataframe for easy manipulation
		self_consumption_tariffs_df = pd.DataFrame(self_consumption_tariffs)
		self_consumption_tariffs_df.columns = ['index', 'order_id', 'datetime', 'self_consumption_tariff',
											   'provider_meter_id', 'receiver_meter_id']

	del self_consumption_tariffs_df['index']
	del self_consumption_tariffs_df['order_id']

	self_consumption_tariffs_dict = {
		'self_consumption_tariffs': self_consumption_tariffs_df.to_dict('records')
	}

	# Update the return dictionary
	milp_return.update(self_consumption_tariffs_dict)

	return milp_return
