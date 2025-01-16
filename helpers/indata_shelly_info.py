# Hardcoded information about the shelly IDs from IN-DATA.
#
# REGARDING CONSUMPTION
# The user provides the main shelly ID that identifies a certain household. That shelly must always include the total
# liquid consumption of the house, either in one of its "phases", A, B, C (when mono-phase) or by summing the 3 phases
# (when tri-phase).
#
# REGARDING GENERATION
# For mono-phase households, if a PV panel is present, it can either have its own shelly or be measured in one of the
# identifying shelly's phases (A, B or C).
#
# DESCRIPTION
# the keys represent the shelly ID and the values in which shelly phase, A, B, C or Total
# can we read the total liquid consumption


INDATA_SHELLY_INFO = {
	'0cb815fd4dec': 'total',
	'0cb815fd4bcc': 'total',
	'0cb815fc5350': 'a',
	'0cb815fcc358': 'a',
	'34987a685128': 'a',
	'0cb815fcc31c': 'total',
	'0cb815fcf5b4': 'a',
	'0cb815fd15bc': 'total',
	'0cb815fd4b30': 'a',
	'0cb815fc72bc': 'total',
	'0cb815fd3608': 'total',
	'34987a675924': 'total',
	'0cb815fcc220': 'total',
	'0cb815fc6178': 'total',
	'0cb815fd1d38': 'total',
	'0cb815fd5654': 'total',
	'0cb815fd534c': 'total',
	'34987a676138': 'total',
	'34987a675060': 'total',
	'0cb815fd49c4': 'a'
}
