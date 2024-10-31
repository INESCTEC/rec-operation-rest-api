# Hardcoded information about the shelly IDs from SEL.
#
# REGARDING CONSUMPTION
# The user provides the main shelly ID that identifies a certain household and the device type "MAIN_METER", which
# relates to the total consumption of the household. In some cases, a sub sensor ID must also be provided.
#
# REGARDING GENERATION
# If a PV panel is installed in the household, the shelly ID that identifies the household also includes another
# device type called "PV". As it was the case for the MAIN_METER device types, a sub sensor ID must be provided in
# certain cases.
#
# DESCRIPTION
# The keys represent the shelly ID and the values represent a list. Each element on that list represents one
# device type. Since we are only interested in total consumption and generation each list will always have at least one
# structure for the "MAIN_METER" device and will have a second structure if the household has PV installed.
# Each structure, a dictionary, will have the indication of the device type and a sub sensor ID, which, if non existant,
# must be passed as None


SEL_SHELLY_INFO = {
		'00e61ee19628': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'}],
		'05a92c8c62aa': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '2'}],
		'0c7886733863': [{'device_type': 'MAIN_METER', 'sub_sensor_id': None},
						 {'device_type': 		 'PV', 'sub_sensor_id': '1'}],
		'170f37bdf13f': [{'device_type': 'MAIN_METER', 'sub_sensor_id': None}],
		'1a9defc4ff40': [{'device_type': 'MAIN_METER', 'sub_sensor_id': None}],
		'1bb05aef72da': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'}],
		'2e7aa1e3f706': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'},
						 {'device_type': 		 'PV', 'sub_sensor_id': '1'}],
		'39bfae7af603': [{'device_type': 'MAIN_METER', 'sub_sensor_id': None}],
		'3eab161b76b4': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'},
						 {'device_type': 		 'PV', 'sub_sensor_id': None}],
		'493ad0182e0c': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '1'}],
		'4cbe01cb9cfd': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'},
						 {'device_type': 		 'PV', 'sub_sensor_id': '1'}],
		'4f1c99c0c199': [{'device_type': 'MAIN_METER', 'sub_sensor_id': None}],
		'6164e03bd2a7': [{'device_type': 'MAIN_METER', 'sub_sensor_id': None},
						 {'device_type': 		 'PV', 'sub_sensor_id': '0'}],
		'61fc5293fd52': [{'device_type': 'MAIN_METER', 'sub_sensor_id': None}],
		'63aee2538cdc': [{'device_type': 'MAIN_METER', 'sub_sensor_id': None}],
		'704b6f864760': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'}],
		'78c602cc58bb': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'}],
		'7ae273adbe80': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'}],
		'8861e8af7053': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'}],
		'8cc637b3bb53': [{'device_type': 'MAIN_METER', 'sub_sensor_id': None}],
		'92eac9402957': [{'device_type': 'MAIN_METER', 'sub_sensor_id': None}],
		'94f356c4717c': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'},
						 {'device_type': 		 'PV', 'sub_sensor_id': '1'}],
		'a76698a2563f': [{'device_type': 'MAIN_METER', 'sub_sensor_id': None},
						 {'device_type': 		 'PV', 'sub_sensor_id': None}],
		'aa0ed5960c57': [{'device_type': 'MAIN_METER', 'sub_sensor_id': None}],
		'ad1fdca09bb0': [{'device_type': 'MAIN_METER', 'sub_sensor_id': None}],
		'b27a89d8336c': [{'device_type': 'MAIN_METER', 'sub_sensor_id': None}],
		'bcb843d5c0c6': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'}],
		'd1cbe72edcb6': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'}],
		'd1e49ca67e63': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'},
						 {'device_type': 		 'PV', 'sub_sensor_id': None}],
		'dead79656d17': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '2'}],
		'f3c07b9293f7': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'}],
		'f4a53aae164a': [{'device_type': 'MAIN_METER', 'sub_sensor_id': None}],
		'f4f44dd669e8': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'}],
		'fbe599917f4d': [{'device_type': 'MAIN_METER', 'sub_sensor_id': '0'}]
	}
