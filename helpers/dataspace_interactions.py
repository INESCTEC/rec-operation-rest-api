import json
import numpy as np
import os
import pandas as pd
import pickle

from dotenv import dotenv_values
from loguru import logger
from tsg_client.controllers import TSGController
from typing import Union

from helpers.ceve_shelly_info import CEVE_SHELLY_INFO
from helpers.meter_tariff_cycles import (
	CEVE_TARIFF_CYCLES,
	SEL_TARIFF_CYCLES
)
from schemas.input_schemas import (
	BaseUserParams,
	UserParams
)


def fetch_dataspace(user_params: Union[UserParams, BaseUserParams]) \
		-> (pd.DataFrame, pd.Series, list[str], list[str], dict[str, list[str]]):
	"""
	Auxiliary function to fetch all necessary data to answer a "vanilla" request, from the dataspace.
	Necessary data includes:
	- historical metered consumption and generation (if existent) for the period defined in the request;
	- contracted tariffs for buying and selling energy to the retailer.
	:param user_params: class with all parameters passed by the user
	:return: a pandas DataFrame with 6 columns: datetime, e_c, e_g, meter_id, buy_tariff and sell_tariff,
		a pandas Series with the self-consumption tariffs applicable to the desired operation horizon,
		a list of all datetimes (in string format) that comprise the horizon set by the user,
		a list with all missing meter_id
		and a dictionary listing all missing datetimes per meter ID
	"""
	dataset_origin = user_params.dataset_origin
	if dataset_origin == 'CEVE':
		return fetch_ceve(user_params)
	elif dataset_origin == 'SEL':
		return fetch_sel(user_params)
	else:
		raise ValueError('Unidentified dataset_origin provided.')


def fetch_ceve(user_params: Union[UserParams, BaseUserParams])\
		-> (pd.DataFrame, pd.Series, list[str], list[str], dict[str, list[str]]):
	"""
	Auxiliary function specific for fetching CEVE data.
	:param user_params: class with all parameters passed by the user
	:return: a pandas DataFrame with 6 columns: datetime, e_c, e_g, meter_id, buy_tariff and sell_tariff,
		a pandas Series with the self-consumption tariffs applicable to the desired operation horizon,
		a list of all datetimes (in string format) that comprise the horizon set by the user,
		a list with all missing meter_id
		and a dictionary listing all missing datetimes per meter ID
	"""
	# load environment variables
	config = dotenv_values('.env')

	# unpack user_params
	meter_ids = user_params.meter_ids  # unequivocal meter ID to search in the dataspace
	start_datetime = user_params.start_datetime  # start datetime.datetime variable
	end_datetime = user_params.end_datetime  # end datetime.datetime variable

	# create a placeholder for the final dataframe to return
	final_df = pd.DataFrame()

	####################################################################################################################
	# Set up a connection to the dataspace through a dedicated TSG connector
	####################################################################################################################
	# set up the TSG connector
	conn = TSGController(
		api_key=config['API_KEY'],
		connector_id=config['CONNECTOR_ID'],
		access_url=config['ACCESS_URL'],
		agent_id=config['AGENT_ID'],
		metadata_broker_url=config['METADATA_BROKER_URL']
	)
	logger.info('Successfully connected to the TSG connector!')
	logger.info(f'Connector info: \n\n {conn} \n')  # print connection details

	####################################################################################################################
	# Retrieve data from the select dataset origin through the dataspace
	####################################################################################################################
	# get external connector info (self-descriptions):
	EXTERNAL_CONNECTOR = {
		'CONNECTOR_ID': 'urn:ids:enershare:connectors:connector-sentinel',
		'ACCESS_URL': 'https://connector-sentinel.enershare.inesctec.pt',
		'AGENT_ID': 'urn:ids:enershare:participants:INESCTEC-CPES'
	}

	# get authorization token
	AUTH = {'Authorization': f'Token {config['TOKEN']}'}

	# get the external connector's self-description
	logger.info(f'Retrieving connector self-description...')
	self_description = conn.get_connector_selfdescription(
		access_url=EXTERNAL_CONNECTOR['ACCESS_URL'],
		connector_id=EXTERNAL_CONNECTOR['CONNECTOR_ID'],
		agent_id=EXTERNAL_CONNECTOR['AGENT_ID']
	)
	logger.info(f'Retrieving connector self-description... OK!')

	# get the OpenAPI specs
	logger.info(f'Retrieving OpenAPI specs...')
	api_version = '1.0.0'
	open_api_specs = conn.get_openapi_specs(self_description, api_version)
	endpoint = '/dataspace/inesctec/observed/ceve_living-lab/metering/energy'
	data_app_agent_id = open_api_specs[0]['agent']
	logger.info(f'Retrieving OpenAPI specs... OK!')

	# expand the start and end datetimes with a 15' before and 15' after buffer;
	# these buffers will help to better interpolate at the limits if needed
	buffer_start_date = start_datetime - pd.to_timedelta('15T')
	buffer_end_date = end_datetime + pd.to_timedelta('15T')
	logger.debug(f'start:{buffer_start_date}, end: {buffer_end_date}')

	# since each request has a limit of 1500 data points, and given that the data granularity can be of 1 second,
	# the horizon configured by the user must be divided into 25' length consecutive requests
	interval_start = buffer_start_date
	interval_end = buffer_start_date + pd.to_timedelta('25T')
	time_intervals = []
	while interval_end < buffer_end_date:
		time_intervals.append((interval_start, interval_end))
		interval_start += pd.to_timedelta('25T')
		interval_end += pd.to_timedelta('25T')
	if (interval_end >= buffer_end_date) and (interval_start < buffer_end_date):
		time_intervals.append((interval_start, buffer_end_date))

	# loop through requested meter ids, since only one at a time can be requested
	logger.info(f'''Performing requests to:\n
				- Agent ID: {data_app_agent_id}
				- API Version: {api_version}
				- Endpoint: {endpoint}
				''')
	# instantiate outputs structure
	dataset = []
	for meter_id in meter_ids:
		logger.info(f'- End User ID: {meter_id} ')
		# validate meter_id provided
		meter_info = CEVE_SHELLY_INFO.get(meter_id)
		if meter_info is None:
			raise ValueError(f'{meter_id} is not a valid meter_id')
		# initialize the meter's retrieved data
		data = None
		# loop through the 25' intervals
		for interval_start, interval_end in time_intervals:
			logger.trace(f'start:{interval_start}, end: {interval_end}')
			# define the request parameters
			params = {
				'shelly_id': meter_id,
				'phase': meter_info.get('phase'),
				'parameter': 'active_power',
				'start_date': interval_start.strftime('%Y-%m-%dT%H:%M:%SZ'),
				'end_date': interval_end.strftime('%Y-%m-%dT%H:%M:%SZ'),
			}
			# execute external OpenAPI request:
			response = conn.openapi_request(
				headers=AUTH,
				external_access_url=EXTERNAL_CONNECTOR['ACCESS_URL'],
				data_app_agent_id=data_app_agent_id,
				api_version=api_version,
				endpoint=endpoint,
				params=params,
				method='get'
			)
			logger.debug(f' > Connector {EXTERNAL_CONNECTOR["CONNECTOR_ID"]} RESPONSE:')
			logger.debug(f' > Status Code: {response.status_code}')

			# retrieve the data from the json response;
			# a correction is required for an error in the conversion of the response to JSON format
			json_response = json.loads(response.text.replace('\n', ''))

			curr_data = json_response.get('data')
			if data is None:
				data = curr_data
			else:
				data.extend(curr_data)

		dataset.extend(data)
	# convert the current dataset to a pandas dataframe
	dataset_df = pd.DataFrame(dataset)

	# load the local file with buying and selling tariffs per tariff cycle
	current_dir = os.path.dirname(os.path.abspath(__file__))
	parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
	pkl_file_path = os.path.join(parent_dir, 'pickles', 'prices_and_tariffs.pkl')
	with open(pkl_file_path, 'rb') as handle:
		tariffs_df = pickle.load(handle)

	# parse all data
	logger.info('Parsing retrieved data...')
	if not dataset_df.empty:
		# to avoid any mixing between energy and power measurements that might occur,
		# the data is filtered to match the desired power measurement unit
		dataset_df = dataset_df.loc[dataset_df['unit'] == 'W']
		# re-order and re-index the dataframe
		dataset_df['datetime'] = pd.to_datetime(dataset_df['datetime'], utc=True)
		dataset_df.sort_values(['shelly_id', 'datetime'], inplace=True)
		dataset_df.set_index('datetime', inplace=True)
		# prune the dataframe
		dataset_df = dataset_df[['shelly_id', 'value']]
		# parse the dataframe per shelly (i.e., per meter)
		FOUND_MEMBERS = list(dataset_df['shelly_id'].unique())
		for shelly_id in FOUND_MEMBERS:
			# filter by shelly_id
			shelly_df = dataset_df[dataset_df['shelly_id'] == shelly_id].copy()
			del shelly_df['shelly_id']
			# sort datetime index
			shelly_df.sort_index(inplace=True)
			# add boundary dates if their missing
			if shelly_df.index.min() > buffer_start_date:
				shelly_df.loc[buffer_start_date, 'value'] = np.NaN
			if shelly_df.index.max() < buffer_end_date:
				shelly_df.loc[buffer_end_date, 'value'] = np.NaN
			# sort datetime index
			shelly_df.sort_index(inplace=True)
			# resample data to 15' timestep
			resampled_df = shelly_df['value'].resample(f'15T').mean()
			# log a warning about the percentage of missing data time steps, after resampling, for the requested horizon
			if resampled_df.isna().any():
				non_buffer_df = resampled_df.loc[start_datetime:buffer_end_date].copy()
				nan_percentage = len(non_buffer_df[non_buffer_df.isna()]) / len(non_buffer_df) * 100
				logger.warning(f'- [{shelly_id}] Missing {nan_percentage: 5.2f}% of values after resampling to 15\'. '
							   f'Applying interpolation.')
			# fill missing values by interpolation
			interpol_df = resampled_df.interpolate(method='slinear', fill_value='extrapolate', limit_direction='both')
			# with the interpolation performed, the buffer datetime rows can be removed
			energy_df = interpol_df.loc[start_datetime:end_datetime].copy()
			# convert power [W] to energy [kWh] measurements
			energy_df *= 0.25 / 1000
			# because this df only has one column it is being treated as a pandas series
			# convert to pandas dataframe
			energy_df = pd.DataFrame(energy_df)
			# divide the net load column into load and generation separate columns
			energy_df['e_c'] = energy_df['value'].apply(lambda x: x if x >= 0.0 else 0.0)
			energy_df['e_g'] = energy_df['value'].apply(lambda x: -x if x < 0.0 else 0.0)
			del energy_df['value']
			# add the information about the "meter_id" once again
			energy_df['meter_id'] = shelly_id
			# add buy and sell tariffs' information
			# - check the tariff type of the shelly_id (one of "simples", "bi-horárias", "tri-horárias")
			tariff_type = CEVE_TARIFF_CYCLES[shelly_id]
			# add buy and sell tariffs information for the meter_id
			energy_df['buy_tariff'] = tariffs_df[tariff_type].loc[start_datetime:end_datetime]
			# - obtain sell tariffs by considering 25% of the buy tariffs for the same period
			energy_df['sell_tariff'] = energy_df['buy_tariff'] * 0.25

			# concatenate parsed dataframe to final dataframe
			if final_df.empty:
				final_df = energy_df
			else:
				final_df = pd.concat([final_df, energy_df])

	####################################################################################################################
	# Verify data availability for all meter_ids
	####################################################################################################################
	datetime_range_dt = pd.date_range(start_datetime, end_datetime, freq='15T')  # list with all requested datetimes
	datetime_range_str = list(datetime_range_dt.strftime('%Y-%m-%dT%H:%M:%SZ'))  # datetimes in str format

	# list with meter (shelly) ids missing from dataspace
	if final_df.empty:
		available_meter_ids = []
	else:
		available_meter_ids = list(final_df['meter_id'].unique())
	missing_meter_ids = [meter_id for meter_id in meter_ids if meter_id not in available_meter_ids]

	# check for missing combinations of meter ID and time step in the data
	missing_meter_id_dt = {mid: [] for mid in meter_ids}
	available_meter_ids = [meter_id for meter_id in meter_ids if meter_id not in missing_meter_ids]
	for meter_id in available_meter_ids:
		meter_id_data = final_df.loc[final_df['meter_id'] == meter_id]
		missing_dts = [dt for dt in datetime_range_str if dt not in meter_id_data.index]
		missing_meter_id_dt[meter_id] = missing_dts

	# get the self-consumption grid tariffs for the respective operation horizon
	sc_tariffs_df = tariffs_df['autoconsumo_simples'].loc[start_datetime:end_datetime]
	sc_tariffs_df.name = 'l_grid'

	return final_df, sc_tariffs_df, datetime_range_str, missing_meter_ids, missing_meter_id_dt


def fetch_sel(user_params: Union[UserParams, BaseUserParams]) \
		-> (pd.DataFrame, pd.Series, list[str], list[str], dict[str, list[str]]):
	"""
	Auxiliary function specific for fetching SEL data.
	:param user_params: class with all parameters passed by the user
	:return: a pandas DataFrame with 6 columns: datetime, e_c, e_g, meter_id, buy_tariff and sell_tariff,
		a pandas Series with the self-consumption tariffs applicable to the desired operation horizon,
		a list of all datetimes (in string format) that comprise the horizon set by the user,
		a list with all missing meter_id
		and a dictionary listing all missing datetimes per meter ID
	"""
	# unpack user_params
	meter_ids = user_params.meter_ids  # unequivocal meter ID to search in the dataspace
	start_datetime = user_params.start_datetime  # start datetime.datetime variable
	end_datetime = user_params.end_datetime  # end datetime.datetime variable

	# create a placeholder for the final dataframe to return
	final_df = pd.DataFrame()

	####################################################################################################################
	# As a failsafe, try to obtain the same data locally
	# NOTE: data only spans from 2022-03-31 23:45:00 to 2023-03-31 23:30:00
	####################################################################################################################
	logger.warning('- Failed to retrieve data through dataspace; trying to obtain data locally ...')

	# read local parsed database
	current_dir = os.path.dirname(os.path.abspath(__file__))
	parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
	pkl_file_path = os.path.join(parent_dir, 'pickles', 'sel_parsed_data.pkl')
	with open(pkl_file_path, 'rb') as handle:
		data_dict = pickle.load(handle)

	# load the local file with buying and selling tariffs per tariff cycle
	pkl_file_path = os.path.join(parent_dir, 'pickles', 'prices_and_tariffs.pkl')
	with open(pkl_file_path, 'rb') as handle:
		tariffs_df = pickle.load(handle)
	logger.info(f'- Successfully loaded SEL data from local pkl files.')

	# loop through requested meter ids, since only one at a time can be requested
	for meter_id in meter_ids:
		logger.info(f'- End User ID: {meter_id} ')
		# parse all data
		energy_df = data_dict.get(meter_id)
		if energy_df is not None:
			# specify that the data being parsed is in UTC
			energy_df.index.name = 'datetime'
			energy_df.index = pd.to_datetime(energy_df.index, utc=True)
			# assert that the datetime index is sorted
			energy_df.sort_index(inplace=True)
			# prune the dataframe
			energy_df = energy_df[['load_kwh', 'pv_kwh']]
			# add a column with the meter_id
			energy_df['meter_id'] = meter_id
			# check the tariff type of the meter_id (one of "simples", "bi-horárias", "tri-horárias")
			tariff_type = SEL_TARIFF_CYCLES[meter_id]
			# add buy and sell tariffs information for the meter_id
			energy_df['buy_tariff'] = tariffs_df[tariff_type].loc[start_datetime:end_datetime]
			# - obtain sell tariffs by considering 25% of the buy tariffs for the same period
			energy_df['sell_tariff'] = energy_df['buy_tariff'] * 0.25
			# rename columns to match expected outputs
			energy_df.columns = ['e_c', 'e_g', 'meter_id', 'buy_tariff', 'sell_tariff']
			# limit the resulting dataframe to the request horizon
			energy_df = energy_df.loc[start_datetime:end_datetime]
		else:
			energy_df = pd.DataFrame()

		# concatenate the resulting dataframe to the final one with the data for all meter ids
		if final_df.empty:
			final_df = energy_df
		else:
			final_df = pd.concat([final_df, energy_df])

	####################################################################################################################
	# Verify data availability for all meter_ids
	####################################################################################################################
	datetime_range_dt = pd.date_range(start_datetime, end_datetime, freq='15T')  # list with all requested datetimes
	datetime_range_str = list(datetime_range_dt.strftime('%Y-%m-%dT%H:%M:%SZ'))  # datetimes in str format

	# list with meter (shelly) ids missing from dataspace
	if final_df.empty:
		available_meter_ids = []
	else:
		available_meter_ids = list(final_df['meter_id'].unique())
	missing_meter_ids = [meter_id for meter_id in meter_ids if meter_id not in available_meter_ids]

	# check for missing combinations of meter ID and time step in the data
	missing_meter_id_dt = {mid: [] for mid in meter_ids}
	available_meter_ids = [meter_id for meter_id in meter_ids if meter_id not in missing_meter_ids]
	for meter_id in available_meter_ids:
		meter_id_data = final_df.loc[final_df['meter_id'] == meter_id]
		missing_dts = [dt for dt in datetime_range_str if dt not in meter_id_data.index]
		missing_meter_id_dt[meter_id] = missing_dts

	# get the self-consumption grid tariffs for the respective operation horizon
	sc_tariffs_df = tariffs_df['autoconsumo_simples'].loc[start_datetime:end_datetime]
	sc_tariffs_df.name = 'l_grid'

	return final_df, sc_tariffs_df, datetime_range_str, missing_meter_ids, missing_meter_id_dt
