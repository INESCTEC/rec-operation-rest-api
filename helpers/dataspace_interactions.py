import json
import pandas as pd

from datetime import datetime
from typing import Union

from schemas.input_schemas import (
	BaseUserParams,
	UserParams
)


DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%SZ'


def datetime_to_string(dt: datetime, fmt=DATETIME_FORMAT) -> str:
	"""
	Auxiliary function for parsing datetime values to strings with a specific format
	:param dt: original datetime variable
	:param fmt: datetime format for the string
	:return: str
	"""
	return dt.strftime(format=fmt)


def fetch_dataspace(user_params: Union[UserParams, BaseUserParams]) \
		-> (pd.core.frame.DataFrame, list[str], list[str], dict[str, list[str]]):
	"""
	Auxiliary function to fetch all necessary data to answer a "vanilla" request, from the dataspace.
	Necessary data includes:
	- historical metered consumption and generation (if existent) for the period defined in the request;
	- contracted tariffs for buying and selling energy  to the retailer.
	:param user_params: class with all parameters passed by the user
	:return: a pandas DataFrame with 6 columns: datetime, e_c, e_g, meter_id, buy_tariff and sell_tariff,
		a list of all datetimes (in string format) that comprise the horizon set by the user,
		a list with all missing meter_id
		and a dictionary listing all missing datetimes per meter ID
	"""
	meter_ids = user_params.meter_ids  # unequivocal meter ID to search in the dataspace
	delta_t = 0.25  # data step in hours; matches the expected dataspace step
	delta_t_minutes = int(delta_t * 60)
	start_datetime = user_params.start_datetime  # start datetime.datetime variable
	end_datetime = user_params.end_datetime  # end datetime.datetime variable

	# create ranges of datetime values between start_datetime and end_datetime with frequency = delta_t
	datetime_range = pd.date_range(start_datetime, end_datetime, freq=f'{delta_t_minutes}T')
	datetime_range_str = [datetime_to_string(dt) for dt in datetime_range]

	# instance the outputs
	all_data_df = None  # will store all retrieved data from the dataspace into a pandas dataframe

	####################################################################################################################
	#  MOCK DATASPACE - START                                                                                          #
	####################################################################################################################
	# read mock dataspace
	with open(r'helpers/mock_dataspace.json', 'rb') as handle:
		mock_dataspace = json.load(handle)

	meters_data = mock_dataspace.get('meters_data')
	buy_and_sell_tariffs = mock_dataspace.get('ERSE_tariffs')
	####################################################################################################################
	#  MOCK DATASPACE - END                                                                                            #
	####################################################################################################################

	# organize the data per meter ID
	missing_meter_ids = []
	for meter_id in meter_ids:
		meter_data = meters_data.get(meter_id)
		# check if there is data for that meter_id in the registry service
		if meter_data:
			# request data for the meter ID within the datetime interval
			meter_data = [data_point for data_point in meter_data if data_point['datetime'] in datetime_range_str]
			# check if there is data *within the desired horizon* for that meter_id in the registry service
			if meter_data:
				# build a dataframe with the datetime, meter_id, consumption and generation data
				meter_data_df = pd.DataFrame(meter_data)
				meter_data_df['meter_id'] = meter_id
				if all_data_df is not None:
					all_data_df = pd.concat([all_data_df, meter_data_df])
				else:
					all_data_df = pd.DataFrame(meter_data_df)

		else:
			# meter ID is not available in the dataspace
			missing_meter_ids.append(meter_id)

	# add the information about the buying and selling tariffs
	buy_and_sell_tariffs_df = pd.DataFrame(buy_and_sell_tariffs)
	if all_data_df is not None:
		all_data_df = pd.merge(all_data_df, buy_and_sell_tariffs_df, on='datetime')

	# check for missing combinations of meter ID and time step in the data
	missing_meter_id_dt = {mid: [] for mid in meter_ids}
	if all_data_df is not None:
		for mid in meter_ids:
			meter_id_data = all_data_df.loc[all_data_df['meter_id'] == mid]
			missing_dts = [dt for dt in datetime_range_str if dt not in meter_id_data['datetime'].values]
			missing_meter_id_dt[mid] = missing_dts
	else:
		# case where the meter ID are available but no data point was found
		missing_meter_id_dt = {mid: [dt for dt in datetime_range_str] for mid in meter_ids}

	return all_data_df, datetime_range_str, missing_meter_ids, missing_meter_id_dt
