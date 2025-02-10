import itertools
import json
import numpy as np
import os
import pandas as pd
import pickle
import pytz
import requests

from copy import deepcopy
from datetime import timedelta
from dotenv import dotenv_values
from loguru import logger
from tsg_client.controllers import TSGController
from typing import Union

from helpers.indata_shelly_info import INDATA_SHELLY_INFO
from helpers.meter_locations import (
	INDATA_LOCATION_INFO,
	SEL_LOCATION_INFO
)
from helpers.meter_installed_pv import (
	INDATA_PV_INFO,
	SEL_PV_INFO
)
from helpers.meter_tariff_cycles import (
	INDATA_TARIFF_CYCLES,
	SEL_TARIFF_CYCLES
)
from helpers.pvgis_interactions import fetch_pvgis
from helpers.sel_shelly_info import SEL_SHELLY_INFO
from schemas.input_schemas import (
	BaseUserParams,
	VanillaUserParams
)


def fetch_dataspace(user_params: Union[VanillaUserParams, BaseUserParams]) \
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
	if dataset_origin == 'INDATA':
		return fetch_indata(user_params)
	elif dataset_origin == 'SEL':
		return fetch_sel(user_params)
	else:
		raise ValueError('Unidentified dataset_origin provided.')


def fetch_indata(user_params: Union[VanillaUserParams, BaseUserParams])\
		-> (pd.DataFrame, pd.Series, list[str], list[str], dict[str, list[str]]):
	"""
	Auxiliary function specific for fetching INDATA data.
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
	try:
		shared_meter_ids = user_params.shared_meter_ids  # unequivocal meter ID for new shared meters
	except AttributeError:
		shared_meter_ids = set()

	start_datetime = user_params.start_datetime  # start datetime.datetime variable
	end_datetime = user_params.end_datetime  # end datetime.datetime variable
	if start_datetime.tzinfo is None:
		start_datetime = pytz.utc.localize(start_datetime)
	if end_datetime.tzinfo is None:
		end_datetime = pytz.utc.localize(end_datetime)

	meter_installed_pv_capacities = user_params.meter_installed_pv_capacities
	shared_meter_installed_pv_capacities = user_params.shared_meter_installed_pv_capacities

	# if there are meters without PV or shared meters, that will require estimated data for potential PV generation,
	# fetch here all necessary data from PVGIS for the period desired
	pvgis_df = fetch_pvgis(start_datetime, end_datetime, *INDATA_LOCATION_INFO)

	# todo: function to truncate dates (end_datetime) to ensure that the horizon is a multiple of 24h;
	#  if changes are made to start_datetime or end_datetime, log a warning;
	#  for now, since dates (without time information) are provided, times are processed as 00:00:00
	#  (or 23:00:00 depending on the DST) so it is sufficient to subtract 15' from the end_datetime to ensure that
	end_datetime -= timedelta(minutes=15)

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
	AUTH = {'Authorization': f'Token {config["TOKEN"]}'}

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
		meter_phase = INDATA_SHELLY_INFO.get(meter_id)
		if meter_phase is None:
			raise ValueError(f'{meter_id} is not a valid meter_id')
		# initialize the meter's retrieved data
		data = None
		# loop through the 25' intervals
		for interval_start, interval_end in time_intervals:
			logger.trace(f'start:{interval_start}, end: {interval_end}')
			# define the request parameters
			params = {
				'shelly_id': meter_id,
				'phase': meter_phase,
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
			# check if a PV installed capacity was provided for the meter ID
			position = next(
				(idx for (idx, d) in enumerate(meter_installed_pv_capacities)
				 if d.meter_id == shelly_id),
				None
			)
			if position is not None:
				pv_installed_capacity = meter_installed_pv_capacities[position].installed_pv_capacity
			else:
				pv_installed_capacity = INDATA_PV_INFO[shelly_id]
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
			resampled_df = shelly_df['value'].resample('15T').mean()
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
			# check if the meter has PV, if not, and if new installed capacity is to be considered,
			# fetch the expected generation from PVGIS;
			if INDATA_PV_INFO[shelly_id] == 0:
				energy_df['e_g'] = pvgis_df['e_g']
			# else normalize the e_g values by the initial installed capacity
			# to obtain a generation profile between 0 and 1
			else:
				energy_df['e_g'] /= (INDATA_PV_INFO[shelly_id] * 0.25)
			# scale the values by the provided installed capacity
			energy_df['e_g'] *= pv_installed_capacity
			# add the information about the "meter_id" once again
			energy_df['meter_id'] = shelly_id
			# add buy and sell tariffs' information
			# - check the tariff type of the shelly_id (one of "simples", "bi-horárias", "tri-horárias")
			tariff_type = INDATA_TARIFF_CYCLES[shelly_id]
			# add buy and sell tariffs information for the meter_id
			energy_df['buy_tariff'] = tariffs_df[tariff_type].loc[start_datetime:end_datetime]
			# - obtain sell tariffs by considering 25% of the buy tariffs for the same period
			energy_df['sell_tariff'] = energy_df['buy_tariff'] * 0.25

			# concatenate parsed dataframe to final dataframe
			if final_df.empty:
				final_df = energy_df
			else:
				final_df = pd.concat([final_df, energy_df])

	# Include the data for new, shared, meters
	for shelly_id in shared_meter_ids:
		# check if a PV installed capacity was provided for the shared meter ID
		position = next(
			(idx for (idx, d) in enumerate(shared_meter_installed_pv_capacities)
			 if d.meter_id == shelly_id),
			None
		)
		if position is not None:
			pv_installed_capacity = shared_meter_installed_pv_capacities[position].installed_pv_capacity
		else:
			pv_installed_capacity = 0.0
		# the meter's PV generation profile will come from the PVGIS service
		energy_df = deepcopy(pvgis_df)
		# scale the values by the provided installed capacity
		energy_df['e_g'] *= pv_installed_capacity
		# the meter's initial consumption is naturally 0
		energy_df['e_c'] = 0
		# add information about the new "meter_id"
		energy_df['meter_id'] = shelly_id
		# add buy and sell tariffs' information
		# - check the tariff type for 'shared' IDs (one of "simples", "bi-horárias", "tri-horárias")
		tariff_type = INDATA_TARIFF_CYCLES['shared']
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


def fetch_sel(user_params: Union[VanillaUserParams, BaseUserParams]) \
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
	# load environment variables
	config = dotenv_values('.env')

	# unpack user_params
	meter_ids = user_params.meter_ids  # unequivocal meter ID to search in the dataspace
	try:
		shared_meter_ids = user_params.shared_meter_ids  # unequivocal meter ID for new shared meters
	except AttributeError:
		shared_meter_ids = set()
	start_datetime = user_params.start_datetime  # start datetime.datetime variable
	end_datetime = user_params.end_datetime  # end datetime.datetime variable
	if start_datetime.tzinfo is None:
		start_datetime = pytz.utc.localize(start_datetime)
	if end_datetime.tzinfo is None:
		end_datetime = pytz.utc.localize(end_datetime)

	meter_installed_pv_capacities = user_params.meter_installed_pv_capacities
	shared_meter_installed_pv_capacities = user_params.shared_meter_installed_pv_capacities

	# if there are meters without PV or shared meters, that will require estimated data for potential PV generation,
	# fetch here all necessary data from PVGIS for the period desired
	pvgis_df = fetch_pvgis(start_datetime, end_datetime, *SEL_LOCATION_INFO)

	# todo: function to truncate dates (end_datetime) to ensure that the horizon is a multiple of 24h;
	#  if changes are made to start_datetime or end_datetime, log a warning;
	#  for now, since dates (without time information) are provided, times are processed as 00:00:00
	#  (or 23:00:00 depending on the DST) so it is sufficient to subtract 15' from the end_datetime to ensure that
	end_datetime -= timedelta(minutes=15)
	buffer_end_date = end_datetime + pd.to_timedelta('15T')

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
		'CONNECTOR_ID': 'urn:ids:enershare:connectors:SEL:connector',
		'ACCESS_URL': 'https://enershare.smartenergylab.pt',
		'AGENT_ID': 'urn:ids:enershare:participants:SEL'
	}

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
	api_version = '1.0.1'
	open_api_specs = conn.get_openapi_specs(self_description, api_version)
	endpoint = '/api/fetch-data'
	data_app_agent_id = open_api_specs[0]['agent']
	logger.info(f'Retrieving OpenAPI specs... OK!')

	# since each request has a limit of 24h
	# the horizon configured by the user must be divided into 24h length consecutive requests
	interval_start = start_datetime
	time_intervals = []
	while interval_start < end_datetime:
		time_intervals.append(interval_start.strftime(format='%Y-%m-%d'))
		interval_start += pd.to_timedelta('1D')

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
		# fetch the device type and sub sensor ID from hardcoded information
		sensors = SEL_SHELLY_INFO.get(meter_id) if SEL_SHELLY_INFO.get(meter_id) is not None else []
		# initialize the meter's retrieved data
		data = None
		# loop through the 24h intervals
		for interval_start, sensor in itertools.product(time_intervals, sensors):
			# allow at maximum 10 request retries
			while i := 0 < 10:
				try:
					device_type = sensor['device_type']
					sub_sensor_id = sensor['sub_sensor_id']
					# get authorization token
					SEL_TOKEN_URL = 'https://backoffice.smartenergylab.pt/api/token/'
					SEL_EMAIL = config['SEL_EMAIL']
					SEL_PASS = config['SEL_PASS']
					token_response = requests.post(SEL_TOKEN_URL, data={"email": SEL_EMAIL, "password": SEL_PASS})
					TOKEN = json.loads(token_response.text)['access']
					AUTH = {'access-token': f'{TOKEN}'}
					# define the request parameters
					params = {
						'request_type': 'fetch',
						# 'participant_access_token': meter_id,
						'participant_permanent_code': meter_id,
						'start_date': interval_start,
						'device_type': device_type,
						'access_token': TOKEN
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
					if response.status_code != 200:
						print(f'{response.status_code}')
						curr_data = []
						break
					# load data in json format
					json_response = json.loads(response.text.replace('\n', ''))
					# load based on sub_sensor_id (if None, load list, if str, load list from sub_sensor_id key)
					curr_data = json_response['data'][device_type]
					break
				except KeyError:
					i += 1
					logger.warning(f' - start:{interval_start} | sensor:{device_type} | RETRY {i}')
					curr_data = []
					pass
			if sub_sensor_id is not None and curr_data:
				curr_data = curr_data[sub_sensor_id]
			if curr_data is None:
				curr_data = []
			# to avoid any missing information at sel_shelly_info.py, regarding sub_sensor_id
			if type(curr_data) is dict:
				real_sub_sensor_id = list(curr_data.keys())[0]
				curr_data = curr_data[real_sub_sensor_id]
			# include information about the meter_id and the sensor
			for datapoint in curr_data:
				datapoint['meter_id'] = meter_id
				datapoint['sensor'] = device_type
			# extend the list of structured data for the shelly ID with new dates or additional sensor data
			if data is None:
				data = curr_data
			else:
				data.extend(curr_data)

		# in case the provided meter_ids are not part of the dataset, data is None and must be
		if data is None:
			data = []
		dataset.extend(data)
	# convert the current dataset to a pandas dataframe
	dataset_df = pd.DataFrame(dataset)

	# load the local file with buying and selling tariffs per tariff cycle
	current_dir = os.path.dirname(os.path.abspath(__file__))
	parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
	pkl_file_path = os.path.join(parent_dir, 'pickles', 'prices_and_tariffs.pkl')
	with open(pkl_file_path, 'rb') as handle:
		tariffs_df = pickle.load(handle)

	# CREATE A PARSED VERSION #################################################
	logger.info('Parsing retrieved data...')
	if not dataset_df.empty:
		# prune dataframe (from voltage, current and energy_returned)
		dataset_df = dataset_df[['datetime', 'energy', 'meter_id', 'sensor']]
		# "marshall" the datetime column
		dataset_df['datetime'] = pd.to_datetime(dataset_df['datetime'], utc=True)
		# pivot the table to get two energy columns (one for consumption and other for generation)
		dataset_df = dataset_df.pivot_table(values='energy', index=['meter_id', 'datetime'], columns=['sensor'])
		dataset_df.index -= timedelta(minutes=1)
		dataset_df.reset_index(inplace=True)
		# re-order and re-index the dataframe
		dataset_df.sort_values(['meter_id', 'datetime'], inplace=True)
		dataset_df.set_index('datetime', inplace=True)
		# if the meters do not have initial PV, a new column must be provided
		if 'PV' not in dataset_df.columns:
			dataset_df['PV'] = 0
		# re-order and rename the columns on the dataframe
		dataset_df = dataset_df[['MAIN_METER', 'PV', 'meter_id']]
		dataset_df.columns = ['e_c', 'e_g', 'meter_id']
		# fill NaN values that appear on both columns
		dataset_df.fillna(0, inplace=True)
		# parse the dataframe per shelly (i.e., per meter)
		FOUND_MEMBERS = list(dataset_df['meter_id'].unique())
		for shelly_id in FOUND_MEMBERS:
			# check if a PV installed capacity was provided for the meter ID
			position = next(
				(idx for (idx, d) in enumerate(meter_installed_pv_capacities)
				 if d.meter_id == shelly_id),
				None
			)
			if position is not None:
				pv_installed_capacity = meter_installed_pv_capacities[position].installed_pv_capacity
			else:
				pv_installed_capacity = SEL_PV_INFO[shelly_id]
			# filter by shelly_id
			shelly_df = dataset_df[dataset_df['meter_id'] == shelly_id].copy()
			del shelly_df['meter_id']
			# sort datetime index
			shelly_df.sort_index(inplace=True)
			# add boundary dates if their missing
			if shelly_df.index.min() > start_datetime:
				shelly_df.loc[start_datetime] = np.NaN
			if shelly_df.index.max() < buffer_end_date:
				shelly_df.loc[buffer_end_date] = np.NaN
			# sort datetime index
			shelly_df.sort_index(inplace=True)
			# resample the dataset to 15' time step
			resampled_df = shelly_df.resample('15T').sum()
			# log a warning about the percentage of missing data time steps, after resampling, for the requested horizon
			if resampled_df.isna().any().any():
				non_buffer_df = resampled_df.loc[start_datetime:buffer_end_date].copy()
				nan_percentage = len(non_buffer_df[non_buffer_df.isna().any(axis=1)]) / len(non_buffer_df) * 100
				logger.warning(f'- [{shelly_id}] Missing {nan_percentage: 5.2f}% of values after resampling to 15\'. '
							   f'Applying interpolation.')
			# fill missing values by interpolation
			interpol_df = resampled_df.interpolate(method='slinear', fill_value='extrapolate', limit_direction='both')
			# with the interpolation performed, the buffer datetime rows can be removed
			energy_df = interpol_df.loc[start_datetime:end_datetime].copy()
			# check if the meter has PV, if not, and if new installed capacity is to be considered,
			# fetch the expected generation from PVGIS;
			if not SEL_PV_INFO[shelly_id] == 0:
				energy_df['e_g'] = pvgis_df['e_g']
			# else normalize the e_g values by the initial installed capacity
			# to obtain a generation profile between 0 and 1
			else:
				energy_df['e_g'] /= (SEL_PV_INFO[shelly_id] * 0.25)
			# scale the values by the provided installed capacity
			energy_df['e_g'] *= pv_installed_capacity
			# add the information about the "meter_id" once again
			energy_df['meter_id'] = shelly_id
			# add buy and sell tariffs' information
			# - check the tariff type of the shelly_id (one of "simples", "bi-horárias", "tri-horárias")
			tariff_type = SEL_TARIFF_CYCLES[shelly_id]
			# add buy and sell tariffs information for the meter_id
			energy_df['buy_tariff'] = tariffs_df[tariff_type].loc[start_datetime:end_datetime]
			# - obtain sell tariffs by considering 25% of the buy tariffs for the same period
			energy_df['sell_tariff'] = energy_df['buy_tariff'] * 0.25

			# concatenate parsed dataframe to final dataframe
			if final_df.empty:
				final_df = energy_df
			else:
				final_df = pd.concat([final_df, energy_df])

	# Include the data for new, shared, meters
	for shelly_id in shared_meter_ids:
		# check if a PV installed capacity was provided for the meter ID
		position = next(
			(idx for (idx, d) in enumerate(meter_installed_pv_capacities)
			 if d.meter_id == shelly_id),
			None
		)
		if position is not None:
			pv_installed_capacity = meter_installed_pv_capacities[position].installed_pv_capacity
		else:
			pv_installed_capacity = 0.0
		# the meter's PV generation profile will come from the PVGIS service
		energy_df = deepcopy(pvgis_df)
		# scale the values by the provided installed capacity
		energy_df['e_g'] *= pv_installed_capacity
		# the meter's initial consumption is naturally 0
		energy_df['e_c'] = 0
		# add information about the new "meter_id"
		energy_df['meter_id'] = shelly_id
		# add buy and sell tariffs' information
		# - check the tariff type for 'shared' IDs (one of "simples", "bi-horárias", "tri-horárias")
		tariff_type = SEL_TARIFF_CYCLES['shared']
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
